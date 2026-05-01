import sys
sys.path.insert(0, r'F:\git\blender2step\vcpkg_installed\x64-windows\python')

try:
    from OCC.Core.STEPControl import STEPControl_Reader
    from OCC.Core.IFSelect import IFSelect_RetDone
    from OCC.Core.TopAbs import TopAbs_ShapeEnum, TopAbs_SOLID, TopAbs_SHELL, TopAbs_COMPOUND
    
    step_file = r'F:\git\blender2step\step_exporter\test28_mesh_cylinder.step'
    
    reader = STEPControl_Reader()
    status = reader.ReadFile(step_file)
    
    print(f'STEP file read status: {status}')
    
    if status == IFSelect_RetDone:
        reader.TransferRoots()
        n_roots = reader.NbRootsForTransfer()
        print(f'Number of roots: {n_roots}')
        
        for i in range(1, n_roots + 1):
            shape = reader.RootForTransfer(i)
            if not shape.IsNull():
                shape_type = shape.ShapeType()
                type_names = {
                    TopAbs_SOLID: 'SOLID',
                    TopAbs_SHELL: 'SHELL',
                    TopAbs_COMPOUND: 'COMPOUND'
                }
                type_name = type_names.get(shape_type, f'OTHER({shape_type})')
                print(f'  Root {i}: Type={type_name}')
    else:
        print('Failed to read STEP file')
        
except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()
