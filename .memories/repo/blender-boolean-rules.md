# Blender Boolean Rules

## Blender 4.2.1 Boolean Solver
- **FAST solver works correctly** in Blender 4.2.1
- **EXACT solver is unreliable** — produces no visible result or residual geometry
- Always use `mod.solver = 'FAST'` for boolean modifiers in Blender 4.2.1

## Rim Implementation for Square Shells
- Use BMesh ring + single boolean (FAST solver), NOT two-boolean approach
- Ring formula (inside rim): outer = w+t, inner = w-t, where t = wall thickness
- Example: shell w=100, t=2 → ring outer=102, inner=98
- Ring height = rh*2, positioned at z=total_h (outer top)
- Ring wall width matches shell wall thickness (t)
- Apply boolean modifier directly (not via _apply_bool helper which uses EXACT)