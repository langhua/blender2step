import bpy, sys, os

script_dir = os.path.dirname(os.path.abspath(__file__))
step_exporter_dir = os.path.dirname(script_dir)
lib_dir = os.path.join(step_exporter_dir, 'lib')

os.environ['PATH'] = lib_dir + os.pathsep + os.environ.get('PATH', '')
if hasattr(os, 'add_dll_directory'):
    os.add_dll_directory(lib_dir)

import step_exporter
import step_exporter.__init__ as init_mod
import importlib
importlib.reload(init_mod)

analyze_shell = init_mod._analyze_bottom_shell_from_mesh
analyze_cyl = init_mod._analyze_cylinder_from_mesh

# Run create_bottom_shell.py
print("Step 1: Creating bottom shells...")
create_script = os.path.join(script_dir, 'create_bottom_shell.py')
with open(create_script, 'r', encoding='utf-8') as f:
    code = f.read()
script_globals = {'__name__': '__main__', '__file__': create_script}
exec(compile(code, create_script, 'exec'), script_globals)

# Analyze
print("\nStep 2: Analyzing objects...")
context = bpy.context
scale = 1000.0

bottom_shells = []
cylinders = []

for obj in bpy.context.scene.objects:
    if obj.type == 'MESH':
        print(f"  Analyzing: {obj.name}")
        shell_params = analyze_shell(obj, context, scale)
        if shell_params:
            bottom_shells.append(shell_params)
            print(f"    -> Bottom shell! has_holes={shell_params.get('has_holes', False)}")
            continue
        
        cyl_params = analyze_cyl(obj, context, scale)
        if cyl_params:
            cylinders.append(cyl_params)
            print(f"    -> {cyl_params['obj_type']}")
            continue
        
        print(f"    -> NOT a parametric object")

print(f"\nDetected: {len(bottom_shells)} bottom shells, {len(cylinders)} cylinders")

# Export
if bottom_shells or cylinders:
    print("\nStep 3: Exporting...")
    output_path = os.path.join(step_exporter_dir, 'test', 'bottom_shells_test.step')
    
    import _step_exporter as cpp
    
    # Simulate timer function logic
    shells = bottom_shells
    temp_files = []
    temp_idx = 0
    
    for idx, params in enumerate(shells):
        has_holes = params.get('has_holes', False)
        desc = "with_holes" if has_holes else "no_holes"
        print(f"  Shell {idx+1} ({desc}): {params.get('width')}x{params.get('depth')}x{params.get('outer_height')}")
        
        temp_file = output_path + f".temp{temp_idx}.step"
        temp_files.append(temp_file)
        temp_idx += 1
        
        if has_holes:
            success = cpp.export_bottom_shell_filleted_with_holes_step(
                temp_file,
                params['width'], params['depth'], params['outer_height'],
                params['bottom_thickness'], params['wall_thickness'],
                params['corner_radius'], params['outer_fillet_radius'],
                params['inner_fillet_radius'], params.get('step_height', 1.0),
                params.get('hole_radius', 1.5), params.get('hole_offset_x', 13.0),
                params.get('hole_offset_y', 11.0),
                params.get('pos_x', 0.0), params.get('pos_y', 0.0), params.get('pos_z', 0.0),
                'AP214IS', 'MILLIMETER', 1
            )
        else:
            success = cpp.export_bottom_shell_filleted_step(
                temp_file,
                params['width'], params['depth'], params['outer_height'],
                params['bottom_thickness'], params['wall_thickness'],
                params['corner_radius'], params['outer_fillet_radius'],
                params['inner_fillet_radius'], params.get('step_height', 1.0),
                params.get('pos_x', 0.0), params.get('pos_y', 0.0), params.get('pos_z', 0.0),
                'AP214IS', 'MILLIMETER', 1
            )
        print(f"    -> {'OK' if success else 'FAIL'}")
    
    for idx, cparams in enumerate(cylinders):
        obj_type = cparams.get('obj_type', 'cylinder')
        print(f"  {obj_type} {idx+1}")
        
        temp_file = output_path + f".temp{temp_idx}.step"
        temp_files.append(temp_file)
        temp_idx += 1
        
        px, py, pz = cparams.get('pos_x', 0), cparams.get('pos_y', 0), cparams.get('pos_z', 0)
        
        if obj_type == 'cylinder':
            success = cpp.export_cylinder_step(temp_file, cparams['radius'], cparams['height'], px, py, pz)
        elif obj_type == 'cone':
            success = cpp.export_cone_step(temp_file, cparams['bottom_radius'], cparams['top_radius'], cparams['height'], px, py, pz)
        elif obj_type == 'hollow_cylinder':
            success = cpp.export_hollow_cylinder_step(temp_file, cparams['outer_radius'], cparams['inner_radius'], cparams['height'], px, py, pz)
        elif obj_type == 'hollow_cone':
            success = cpp.export_hollow_cone_step(temp_file, cparams['outer_bottom_radius'], cparams['outer_top_radius'],
                                                cparams['inner_bottom_radius'], cparams['inner_top_radius'], cparams['height'],
                                                px, py, pz)
        print(f"    -> {'OK' if success else 'FAIL'}")
    
    # Merge (use Python merge function from init_mod)
    if len(temp_files) > 1:
        print(f"\n  Merging {len(temp_files)} files...")
        merge_result = init_mod._merge_step_files(output_path, temp_files)
        print(f"    -> {'OK' if merge_result else 'FAIL'}")
    elif len(temp_files) == 1:
        os.replace(temp_files[0], output_path)
    
    # Verify
    print(f"\nStep 4: File info...")
    file_size = os.path.getsize(output_path)
    print(f"  {output_path}: {file_size} bytes")
    
    with open(output_path, 'r') as f:
        content = f.read()
        import re
        solids = len(re.findall(r'CLOSED_SHELL', content))
        surfaces = {
            'CYLINDRICAL_SURFACE': len(re.findall(r'CYLINDRICAL_SURFACE', content)),
            'CONICAL_SURFACE': len(re.findall(r'CONICAL_SURFACE', content)),
            'TOROIDAL_SURFACE': len(re.findall(r'TOROIDAL_SURFACE', content)),
            'PLANE': len(re.findall(r'PLANE', content)),
        }
        print(f"  {solids} solids, Surfaces: {surfaces}")
    
    # Cleanup
    for tf in temp_files:
        try:
            os.remove(tf)
        except:
            pass

print("\nDone!")