"""
Window Data Editor for Blender
- Lists all window entries from the active object's window_data
- Allows setting each window to box (0) or isosceles trapezoid (3) with optional angle
- Run this script in Blender's Scripting workspace, or paste into Python console

Usage in Blender Python console:
    import sys; sys.path.append(r'F:\git\blender2step')
    from step_exporter.edit_windows import show_windows, set_window, list_windows
    list_windows()    # show all windows with indices
    set_window(0, 3)  # set window #0 to trapezoid (default Y slant)
    set_window(1, 3, 90)  # set window #1 to trapezoid with 90° rotation (X slant)
    set_window(2, 0)  # set window #2 back to box
"""
import bpy

def _get_obj():
    """Get active object with window_data"""
    obj = bpy.context.active_object
    if not obj:
        # Try to find shell object in scene
        candidates = [o for o in bpy.data.objects if 'window_data' in o]
        if candidates:
            obj = candidates[0]
            print(f"[WinEditor] Auto-selected: {obj.name}")
        else:
            print("[WinEditor] ERROR: No object with window_data found. Select the shell object first.")
            return None
    if 'window_data' not in obj:
        print(f"[WinEditor] ERROR: '{obj.name}' has no window_data property.")
        return None
    return obj

def list_windows():
    """Print all window entries with index, type, position, size"""
    obj = _get_obj()
    if not obj: return
    
    wd = obj['window_data']
    entries = wd.split(';')
    
    print(f"\n{'='*80}")
    print(f"  Object: {obj.name}")
    print(f"  Window entries: {len(entries)}")
    print(f"{'='*80}")
    
    has_window = False
    for i, entry in enumerate(entries):
        parts = entry.split(',')
        n = len(parts)
        
        # Determine type: window (4-6 values, no hole type) vs hole
        if n >= 7:
            print(f"  [{i}] Rounded-rect hole (8v) — {entry[:60]}")
        elif (n == 5 or n == 6) and parts[4] == '1':
            fillet = f" fillet={parts[5]}" if n == 6 else ""
            print(f"  [{i}] Circular hole r={parts[3]} at ({parts[0]},{parts[1]},{parts[2]}){fillet}")
        elif n >= 4:
            has_window = True
            shape_type = parts[4] if n >= 5 else '0'
            angle = parts[5] if n >= 6 else '0'
            shape_name = {'0': 'BOX', '3': 'TRAPEZOID'}.get(shape_type, f'type={shape_type}')
            
            cx, cy, wlen, wwid = float(parts[0]), float(parts[1]), float(parts[2]), float(parts[3])
            print(f"  [{i}] WINDOW: {wlen:.0f}×{wwid:.0f} at ({cx:.0f},{cy:.0f}) — {shape_name}", end='')
            if shape_type == '3':
                print(f" angle={angle}°", end='')
            print()
        else:
            print(f"  [{i}] Unknown: {entry}")
    
    if not any(n >= 4 and not ((n==5 or n==6) and e.split(',')[4]=='1') and n < 7 
               for e in entries for n in [len(e.split(','))]):
        print(f"\n  (no rectangular windows found)")
    
    print(f"{'='*80}")
    print(f"\n  Tip: set_window(index, shape, angle=None)")
    print(f"       shape=0→box, shape=3→trapezoid")
    print(f"       angle=0(default)→Y slant, angle=90→X slant")
    return entries

def set_window(index, shape_type, angle=None):
    """
    Set window at given index to box (0) or trapezoid (3)
    
    Args:
        index: window index (0-based, from list_windows)
        shape_type: 0=box, 3=isosceles trapezoid
        angle: for trapezoid, rotation in degrees (0=Y slant, 90=X slant)
    """
    obj = _get_obj()
    if not obj: return
    
    wd = obj['window_data']
    entries = wd.split(';')
    
    if index < 0 or index >= len(entries):
        print(f"[WinEditor] ERROR: Index {index} out of range (0-{len(entries)-1})")
        return
    
    entry = entries[index]
    parts = entry.split(',')
    n = len(parts)
    
    # Check if it's a window entry
    if n >= 7:
        print(f"[WinEditor] [{index}] is a rounded-rect hole, not a window — skipped")
        return
    if (n == 5 or n == 6) and parts[4] == '1':
        print(f"[WinEditor] [{index}] is a circular hole, not a window — skipped")
        return
    if n < 4:
        print(f"[WinEditor] [{index}] Unknown format — skipped")
        return
    
    # Rebuild entry
    if shape_type == 0:
        # Box: just 4 values
        entries[index] = f"{parts[0]},{parts[1]},{parts[2]},{parts[3]}"
    elif shape_type == 3:
        if angle is not None and abs(angle) > 0.01:
            entries[index] = f"{parts[0]},{parts[1]},{parts[2]},{parts[3]},3,{angle}"
        else:
            entries[index] = f"{parts[0]},{parts[1]},{parts[2]},{parts[3]},3"
    else:
        print(f"[WinEditor] ERROR: Unknown shape_type={shape_type} (use 0=box, 3=trapezoid)")
        return
    
    obj['window_data'] = ';'.join(entries)
    
    shape_name = 'BOX' if shape_type == 0 else 'TRAPEZOID'
    angle_str = f" angle={angle}°" if (shape_type == 3 and angle) else ""
    print(f"[WinEditor] [{index}] → {shape_name}{angle_str} — DONE")
    print(f"  New window_data: {obj['window_data'][:120]}...")

def set_all_trapezoid():
    """Set ALL rectangular windows to trapezoid (for quick testing)"""
    obj = _get_obj()
    if not obj: return
    
    wd = obj['window_data']
    entries = wd.split(';')
    count = 0
    
    for i, entry in enumerate(entries):
        parts = entry.split(',')
        n = len(parts)
        if n >= 7: continue
        if (n == 5 or n == 6) and parts[4] == '1': continue
        if n < 4: continue
        parts = parts[:4]
        parts.append('3')
        entries[i] = ','.join(parts)
        count += 1
    
    obj['window_data'] = ';'.join(entries)
    print(f"[WinEditor] Set {count} windows to TRAPEZOID")

def set_all_box():
    """Reset ALL rectangular windows to box"""
    obj = _get_obj()
    if not obj: return
    
    wd = obj['window_data']
    entries = wd.split(';')
    count = 0
    
    for i, entry in enumerate(entries):
        parts = entry.split(',')
        n = len(parts)
        if n >= 7: continue
        if (n == 5 or n == 6) and parts[4] == '1': continue
        if n < 4: continue
        entries[i] = f"{parts[0]},{parts[1]},{parts[2]},{parts[3]}"
        count += 1
    
    obj['window_data'] = ';'.join(entries)
    print(f"[WinEditor] Reset {count} windows to BOX")

# ── Run when executed as script ──
if __name__ == '__main__':
    list_windows()
