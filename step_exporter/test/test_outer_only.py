"""Export only raw outer lofted solid - no fillet, no hollowing."""
import sys, os, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import _step_exporter as cpp

out_dir = os.path.dirname(os.path.abspath(__file__))

# Build the shape manually: just the outer lofted solid, no fillets or cuts
# We can't call create_top_shell_filleted_solid directly for just the outer
# Instead, set wall_thickness=0 and fillet_radius=0 to skip hollowing

# Set wall_thickness very small (can't be 0 as that doesn't skip hollowing)
# Set fillets to 0
result = cpp.export_top_shell_filleted_step(
    os.path.join(out_dir, 'test28_outer_only.step'),
    100.0, 70.0, 10.0,  # w, d, h
    1.5, 0.01, 20.0,  # tt, wt(tiny), cr
    0.0, 0.0,  # ofr=0, ifr=0 (no fillets)
    11.5182, -3.0091,  # recess, yOff
    0.0, 0.0,  # no window
    "AP242DIS", "MILLIMETER", 0)
print(f"Export: {'OK' if result else 'FAILED'}")