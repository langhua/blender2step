import FreeCAD, Part

shape = Part.read(r"f:\git\blender2step\_dbg_test30.step")
print("vol=", round(shape.Volume, 1))
print("num solids:", len(shape.Solids), "num shells:", len(shape.Shells), "num faces:", len(shape.Faces))
for i, f in enumerate(shape.Faces):
    typ = f.Surface.TypeId
    bb = f.BoundBox
    info = f"  face{i}: {typ} area={f.Area:.1f} z=({bb.ZMin:.1f},{bb.ZMax:.1f})"
    if "Cone" in typ:
        info += f" R1={f.Surface.Radius:.2f}"
    elif "Cylinder" in typ:
        info += f" R={f.Surface.Radius:.2f}"
    print(info)
