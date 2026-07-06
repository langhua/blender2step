# Cone Stepped Hole Geometry (S*_TprStep)

Based on user's description comparing Blender original vs FreeCAD STEP:

## Correct geometry (top to bottom):
1. **Top (z=+0.5)**: Small straight hole opening (孔径 ≈ 63mm), fillet at entrance
2. **Straight hole section (直孔)**: Nearly constant radius (~63→84mm), taller section (~850mm)
3. **Step transition (z≈-0.35)**: Radius jumps from ~84mm to ~124mm, fillet at step  
4. **Tapered hole section (锥孔)**: Widens from ~124mm to ~235mm, shorter section (~150mm)
5. **Bottom (z=-0.5)**: Large tapered hole opening (孔径 ≈ 235mm), fillet at exit

Key facts:
- 锥孔底部孔径 > 直孔孔径 (tapered hole bottom aperture > straight hole aperture)
- 直孔高度较高 (straight hole is taller)
- 孔口孔底都有圆角 (both openings have fillets)

## C++ `export_cone_stepped_hole_step` params:
- small_hole_radius: radius of straight section (~84mm at step end)
- small_hole_height: height of small/straight section (~850mm)
- inner_bottom_radius: bottom hole radius (~235mm, tapered section bottom)
- inner_top_radius: top hole radius (~63mm, straight section top)
- top_fillet_radius: fillet at step transition
