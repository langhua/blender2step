# lib/ DLL audit (2026-08-07, OCCT 7.8.1 via vcpkg, Python 3.13)

Formal tool: `tools/audit_lib.py` (pure-python PE import parser, no deps).
- `python tools/audit_lib.py` — report only (exit 0)
- `python tools/audit_lib.py --check` — exit 1 if any ORPHAN found (regression guard)
- `python tools/audit_lib.py --strict` — also flag RISKY STEP-core DLLs as orphans
- Deleted old temp `_audit_lib.py` at repo root.

## Parser gotcha
RVA→offset must use **VirtualSize** extent, NOT max(raw,virt) — max() over-extends a
section and silently loses imports (e.g. TKSTEP/TKFeat wrongly flagged orphan).

## Key facts
- `STEPControl_Writer` lives in **TKDESTEP.dll** in this OCCT build (pyd imports
  tkdestep.dll, not tkstep.dll). TKSTEP.dll is NOT statically imported.
- pyd direct imports (26): kernel32, python313.dll (Blender provides), 8x
  api-ms-win-crt, msvcp140, vcruntime140(_1), + OCCT TK*.dll (TKDESTEP, TKernel,
  TKBRep, TKBool, TKFillet, TKTopAlgo, TKShHealing, TKGeomBase, TKGeomAlgo, TKMath,
  TKMesh, TKOffset, TKPrim, TKBO, TKG2d, TKG3d, TKHLR, TKCAF, TKCDF, TKDE, TKLCAF,
  TKService, TKV3d, TKVCAF, TKXCAF, TKXSBase)
- freetype.dll (vcpkg) pulls brotlicommon/brotlidec/bz2/libpng16/zlib1 → KEEP.
- KEEP VC runtime msvcp140/vcruntime140(_1).

## Deleted (safe, ~19 MB, 42 files)
- Python 3.11 leftovers: blender_python311.exp/.lib, python311.dll, brotlienc,
  charset-1, fontconfig-1, iconv-2, intl-8, json-c, libexpat, pthreadVC3/VCE3/VSE3
- Other-format OCCT translators (STEP-only addon never loads them): TKIGES/TKDEIGES,
  TKSTL/TKDESTL, TKVRML/TKDEVRML, TKDEGLTF, TKDEOBJ, TKDEPLY, TKDECascade, TKSTEP209,
  TKBin* (4), TKXml* (4), TKStd/TKStdL, TKTObj, TKXMesh, TKRWMesh, TKMeshVS, TKOpenGl,
  TKXDE/TKXDECascade/TKXDEIGES

## KEEP but risky (not statically imported, possibly dynamic-loaded by OCCT)
TKSTEP.dll, TKSTEPBase.dll, TKSTEPAttr.dll, TKXDESTEP.dll, TKFeat.dll
→ keep for now; can test-delete later after verifying STEP export still works.
