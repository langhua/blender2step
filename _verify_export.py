"""Verify cylinder gallery STEP export - check all 192 objects."""
import re, os, sys

step_file = r'f:\git\blender2step\step_exporter\test28.step'
log_file = r'f:\git\blender2step\step_exporter\test28.step.log'

print("=" * 60)
print("CYLINDER GALLERY STEP EXPORT VERIFICATION")
print("=" * 60)

# 1. Check STEP file
print("\n--- STEP File ---")
with open(step_file, 'r', encoding='utf-8') as f:
    content = f.read()

products = len(re.findall(r'PRODUCT\s*\(', content))
solids = len(re.findall(r'MANIFOLD_SOLID_BREP\s*\(', content))
shells = len(re.findall(r'CLOSED_SHELL\s*\(', content))
breps = len(re.findall(r'ADVANCED_BREP_SHAPE_REPRESENTATION\s*\(', content))
sdrs = len(re.findall(r'SHAPE_DEFINITION_REPRESENTATION\s*\(', content))
comps = len(re.findall(r'SHAPE_REPRESENTATION_RELATIONSHIP\s*\(', content))

print(f"  PRODUCTs: {products}")
print(f"  MANIFOLD_SOLID_BREPs: {solids}")
print(f"  CLOSED_SHELLs: {shells}")
print(f"  ADVANCED_BREP_SHAPE_REPs: {breps}")
print(f"  SHAPE_DEFINITION_REPs: {sdrs}")
print(f"  SHAPE_REPRESENTATION_RELATIONSHIPs: {comps}")

size = os.path.getsize(step_file)
print(f"  File size: {size:,} bytes ({size/1024/1024:.1f} MB)")

# Check if it's a compound or single solid
if comps > 0:
    print(f"  Structure: COMPOUND of {comps} sub-shapes")
elif solids > 0:
    print(f"  Structure: {solids} separate solids")

# 2. Check log file
print("\n--- Export Log ---")
with open(log_file, 'r', encoding='utf-8') as f:
    log = f.read()

# Find the 192-object export run
run_match = re.search(r'Total objects: 192.*?Stage 4', log, re.DOTALL)
if run_match:
    run = run_match.group()
    
    # Count by type
    type_counts = {}
    for m in re.finditer(r'Exporting (\S+) (\d+)/192', run):
        t = m.group(1)
        type_counts[t] = type_counts.get(t, 0) + 1
    
    print(f"  Objects by type:")
    for t, c in sorted(type_counts.items()):
        print(f"    {t}: {c}")
    print(f"  Total: {sum(type_counts.values())}")
    
    # Check verify results
    verify_ok = len(re.findall(r'verify: (\d+) shells, face counts: \[', run))
    verify_zero = len(re.findall(r'verify: 0 shells', run))
    failed = len(re.findall(r'FAILED', run))
    errors = len(re.findall(r'ERROR', run))
    
    print(f"\n  Verify OK: {verify_ok - verify_zero}")
    print(f"  Verify 0-shell: {verify_zero}")
    print(f"  Failed: {failed}")
    print(f"  Errors: {errors}")
    
    if verify_zero > 0:
        print("\n  ⚠️  ZERO-SHELL OBJECTS:")
        # Find which objects
        export_lines = re.findall(r'(Exporting \S+ \d+/192.*?)(?=Exporting|verify:)', run, re.DOTALL)
        for el in export_lines:
            if 'verify: 0 shells' in run[run.find(el):run.find(el)+len(el)+200]:
                print(f"    {el.strip()[:80]}")
else:
    # Try finding all export patterns
    runs = re.findall(r'Total objects: (\d+)', log)
    print(f"  Export runs found: {runs}")
    
    # Find verify results globally
    all_verify = re.findall(r'verify: (\d+) shells, face counts: \[(.*?)\]', log)
    zero_count = sum(1 for s, _ in all_verify if s == '0')
    print(f"  Total verify lines: {len(all_verify)}")
    print(f"  Zero-shell: {zero_count}")

# 3. Summary
print("\n" + "=" * 60)
if products >= 192 and comps > 0:
    print("✅ VERDICT: STEP file structure looks correct (compound of objects)")
elif solids >= 192:
    print("✅ VERDICT: STEP file has 192+ solids")
else:
    print(f"⚠️  VERDICT: Only {max(solids, products)} products/solids found (expected 192)")

print("=" * 60)
