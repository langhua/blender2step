"""Audit which files in step_exporter/lib are really needed at runtime.

Pure-Python PE import-table parser (no third-party dependencies). Starting from
`_step_exporter.pyd`, it builds the transitive closure over the DLLs present in
`step_exporter/lib/` and classifies every file as:

    NEEDED  - in the closure; must ship.
    ORPHAN  - present in lib/ but never referenced; candidate for removal.
    RISKY   - STEP-core DLLs that OCCT can load at runtime even though they are
              not in the static import graph; kept by default.

Why RISKY exists: OCCT's STEP resource/plugin mechanism may LoadLibrary
TKSTEP.dll / TKSTEPBase.dll / TKSTEPAttr.dll / TKXDESTEP.dll / TKFeat.dll at
runtime, so a static-import-only analysis is not enough to call them orphans.

Usage:
    python tools/audit_lib.py                 # report only (exit 0)
    python tools/audit_lib.py --check         # exit 1 if any ORPHAN is found
    python tools/audit_lib.py --strict        # also treat RISKY files as orphans
                                              # (for --check)
"""
import argparse
import os
import struct

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = os.path.join(REPO, "step_exporter", "lib")

# STEP-core DLLs that OCCT may dynamically load at runtime (not statically
# imported by _step_exporter.pyd). Kept unless --strict is used.
RISKY = {
    "tkstep.dll",
    "tkstepbase.dll",
    "tkstepattr.dll",
    "tkxdestep.dll",
    "tkfeat.dll",
}


def read_imports(path):
    """Return set of imported DLL names (lowercased) for a PE file."""
    try:
        return _read_imports(path)
    except Exception:
        return set()


def _read_imports(path):
    with open(path, "rb") as f:
        data = f.read()
    if data[:2] != b"MZ":
        return set()
    e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
    if data[e_lfanew:e_lfanew + 4] != b"PE\0\0":
        return set()
    num_sections = struct.unpack_from("<H", data, e_lfanew + 6)[0]
    opt_size = struct.unpack_from("<H", data, e_lfanew + 20)[0]
    opt_magic = struct.unpack_from("<H", data, e_lfanew + 24)[0]
    if opt_magic == 0x10B:          # PE32
        dd_offset = e_lfanew + 24 + 96
    elif opt_magic == 0x20B:        # PE32+
        dd_offset = e_lfanew + 24 + 112
    else:
        return set()
    imp_rva, _imp_size = struct.unpack_from("<II", data, dd_offset + 8)
    if imp_rva == 0:
        return set()
    sec_offset = e_lfanew + 24 + opt_size

    def rva_to_off(rva):
        for i in range(num_sections):
            base = sec_offset + i * 40
            va = struct.unpack_from("<I", data, base + 12)[0]
            virt_size = struct.unpack_from("<I", data, base + 8)[0]
            raw_size = struct.unpack_from("<I", data, base + 16)[0]
            raw_ptr = struct.unpack_from("<I", data, base + 20)[0]
            # Map by VIRTUAL extent. Using max(raw, virt) over-extends a section
            # past its true virtual range and can wrongly claim an RVA that
            # belongs to the NEXT section, silently losing imports.
            extent = virt_size if virt_size else raw_size
            if va <= rva < va + extent:
                return raw_ptr + (rva - va)
        return None

    off = rva_to_off(imp_rva)
    if off is None:
        return set()
    names = set()
    while True:
        oft, _ts, _fc, name_rva, _ft = struct.unpack_from("<IIIII", data, off)
        if oft == 0 and name_rva == 0:
            break
        noff = rva_to_off(name_rva)
        if noff is not None:
            end = data.find(b"\0", noff)
            if end > noff:
                names.add(data[noff:end].decode("ascii", "replace").lower())
        off += 20
    return names


def classify():
    """Return (needed, orphan, risky, sizes, root_imports)."""
    files = sorted(os.listdir(LIB))
    by_lower = {}
    for fn in files:
        by_lower.setdefault(fn.lower(), fn)

    imports = {}
    sizes = {}
    for fn in files:
        p = os.path.join(LIB, fn)
        sizes[fn] = os.path.getsize(p)
        imports[fn] = read_imports(p) if fn.lower().endswith((".dll", ".pyd")) else set()

    root = "_step_exporter.pyd"
    needed = set()
    seen = set()
    frontier = set(imports.get(root, set()))
    while frontier:
        d = frontier.pop()
        if d in seen:
            continue
        seen.add(d)
        if d in by_lower:
            real = by_lower[d]
            needed.add(real)
            for sub in imports.get(real, set()):
                if sub not in seen:
                    frontier.add(sub)
    needed.add(root)

    orphan = set()
    risky = set()
    for fn in files:
        if fn in needed:
            continue
        if fn.lower() in RISKY:
            risky.add(fn)
        else:
            orphan.add(fn)
    return needed, orphan, risky, sizes, imports.get(root, set())


def report(needed, orphan, risky, sizes, root_imports):
    def kb(fn):
        return sizes[fn] / 1024

    print("=" * 70)
    print("Direct imports of _step_exporter.pyd (sanity check)")
    print("=" * 70)
    for d in sorted(root_imports):
        print(f"    {d}")
    print()

    print("=" * 70)
    print("NEEDED (transitive closure from _step_exporter.pyd)")
    print("=" * 70)
    tot_needed = sum(sizes[f] for f in needed)
    for fn in sorted(needed, key=lambda x: x.lower()):
        print(f"  [NEEDED] {fn}  ({kb(fn):.0f} KB)")

    print()
    print("=" * 70)
    print("RISKY (STEP-core, OCCT may load at runtime) - kept unless --strict")
    print("=" * 70)
    tot_risky = sum(sizes[f] for f in risky)
    for fn in sorted(risky, key=lambda x: x.lower()):
        print(f"  [RISKY ] {fn}  ({kb(fn):.0f} KB)")

    print()
    print("=" * 70)
    print("ORPHAN (present but not referenced) - candidates to delete")
    print("=" * 70)
    tot_orphan = sum(sizes[f] for f in orphan)
    for fn in sorted(orphan, key=lambda x: x.lower()):
        print(f"  [ORPHAN] {fn}  ({kb(fn):.0f} KB)")

    total = sum(sizes.values())
    print()
    print(f"Total lib size: {total/1024/1024:.1f} MB")
    print(f"Needed: {tot_needed/1024/1024:.1f} MB  |  Risky: {tot_risky/1024/1024:.1f} MB"
          f"  |  Orphans: {tot_orphan/1024/1024:.1f} MB")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if any ORPHAN file is present in lib/")
    ap.add_argument("--strict", action="store_true",
                    help="treat RISKY STEP-core DLLs as orphans too (for --check)")
    args = ap.parse_args()

    if not os.path.isdir(LIB):
        raise SystemExit(f"lib dir not found: {LIB}")
    if not os.path.exists(os.path.join(LIB, "_step_exporter.pyd")):
        raise SystemExit("_step_exporter.pyd not found in lib/ - build it first.")

    needed, orphan, risky, sizes, root_imports = classify()
    report(needed, orphan, risky, sizes, root_imports)

    if not args.check:
        return 0

    removable = set(orphan)
    if args.strict:
        removable |= set(risky)
    if removable:
        print()
        print(f"[CHECK] FAIL: {len(removable)} unexpected file(s) in lib/:")
        for fn in sorted(removable, key=lambda x: x.lower()):
            print(f"    {fn}")
        return 1
    print("\n[CHECK] OK: lib/ contains only needed (and allowed risky) files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
