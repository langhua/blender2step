import sys
import math
import re
from collections import defaultdict

def parse_step_file(filepath):
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    points = {}
    
    cartesian_point_pattern = re.compile(
        r'#(\d+)\s*=\s*CARTESIAN_POINT\s*\(\s*\'[^\']*\'\s*,\s*\(\s*([^)]+)\s*\)\s*\)'
    )
    for m in cartesian_point_pattern.finditer(content):
        pid = int(m.group(1))
        coord_str = m.group(2)
        coords = [float(x.strip()) for x in coord_str.split(',')]
        if len(coords) == 3:
            points[pid] = coords
    
    return content, points

def analyze_step_ring(filepath):
    print(f"Analyzing: {filepath}")
    content, points = parse_step_file(filepath)
    
    print(f"Total 3D points: {len(points)}")
    
    if not points:
        print("No 3D points found!")
        return
    
    # Filter to find objects near Z=0 with reasonable dimensions
    # Group points that are close in Z and have ~100x70 dimensions
    values = list(points.values())
    
    z_layers = defaultdict(list)
    for coords in values:
        z_key = round(coords[2] / 0.01) * 0.01
        z_layers[z_key].append(coords)
    
    sorted_z = sorted(z_layers.keys())
    
    # Find Z-levels near 0 with reasonable point counts (> 20 points)
    print(f"\nLooking for top shell (Z near 0, > 20 points, ~100x70):")
    candidates = []
    for zl in sorted_z:
        if -20 <= zl <= 20 and len(z_layers[zl]) > 20:
            coords = z_layers[zl]
            xs = [c[0] for c in coords]
            ys = [c[1] for c in coords]
            wx = max(xs) - min(xs)
            wy = max(ys) - min(ys)
            cx = sum(xs) / len(xs)
            cy = sum(ys) / len(ys)
            dists = sorted([math.sqrt((c[0] - cx)**2 + (c[1] - cy)**2) for c in coords])
            n10 = max(1, len(dists) // 10)
            inner_avg = sum(dists[:n10]) / n10
            outer_avg = sum(dists[-n10:]) / n10
            candidates.append((zl, len(coords), wx, wy, inner_avg, outer_avg))
            print(f"  z={zl:.3f}: {len(coords)} pts, X: {min(xs):.1f}..{max(xs):.1f} ({wx:.1f}), Y: {min(ys):.1f}..{max(ys):.1f} ({wy:.1f}), inner={inner_avg:.1f}, outer={outer_avg:.1f}")
    
    if not candidates:
        print("No candidates found near Z=0!")
        return
    
    # Find the group that looks like a top shell
    # Top shell should have: outer dimensions ~100x70, wall thickness ~2mm
    # Sort candidates by Z
    candidates.sort()
    
    print(f"\nStep ring analysis for top shell candidates:")
    if len(candidates) >= 2:
        z0_data = candidates[0]
        z1_data = candidates[1]
        print(f"  z0={z0_data[0]:.3f}: inner={z0_data[4]:.1f}, outer={z0_data[5]:.1f}")
        print(f"  z1={z1_data[0]:.3f}: inner={z1_data[4]:.1f}, outer={z1_data[5]:.1f}")
        print(f"  z0_inner - z1_inner = {z0_data[4] - z1_data[4]:.3f}")
        print(f"  z1 - z0 = {z1_data[0] - z0_data[0]:.3f}")
        
        if z0_data[4] > z1_data[4] + 0.1:
            width = round(z0_data[4] - z1_data[4], 1)
            height = round(z1_data[0] - z0_data[0], 1)
            print(f"  Step ring detected: height={height:.1f}mm, width={width:.1f}mm")
        else:
            print(f"  No step ring detected")

if __name__ == '__main__':
    filepath = sys.argv[1] if len(sys.argv) > 1 else 'f:/git/blender2step/step_exporter/test/test28.step'
    analyze_step_ring(filepath)