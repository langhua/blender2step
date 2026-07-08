# Z=0 Rule: Object Bottom at Z=0

## The Rule
**All geometric objects (shells, cylinders, cutters, rings) MUST have their bottom face at Z=0 in the final coordinate system.** This applies to both C++ OCCT shapes and Blender Python objects.

## C++ Convention
- Shapes built with bottom at z=0, top at z=total_h
- `gp_Trsf shiftUp; shiftUp.SetTranslation(gp_Vec(0, 0, hh));` shifts shape so bottom goes from -hh to 0
- All child shapes (ring, inner solid) are positioned relative to z=0 bottom

## Blender Convention  
- Objects built at origin (centered), THEN shifted so bottom at z=0
- `obj.location.z = total_h / 2` shifts centered object to z=0 bottom
- Cutter objects (RimRing, ShellInner) positioned in world coords assuming final bottom at z=0

## Ring Position Formula
- C++: ring occupies z = `height` to `height + rh` (shell top region, rh deep)
- Blender: `ring.location.z = total_h` (shift shell first, then ring at shell top)
- Both produce rim cut at z = `height` to `total_h` (top rh of shell)

## Verification
- Shell total height = height + rim_height (if has_rim)
- Rim cut should be at z = height to z = height + rim_height
- After shift: bottom at z=0, top at z=total_h
