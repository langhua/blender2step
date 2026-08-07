"""Build a Blender-addon release zip of the `step_exporter` package.

Run:  python tools/make_release.py [version]
Output: step_exporter-<version>.zip  (in the repo root)

The zip is directly installable in Blender via:
    Edit > Preferences > Add-ons > Install from Disk... > select the zip
"""
import os
import sys
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = os.path.join(REPO, "step_exporter")
LIB = os.path.join(PKG, "lib")

REQUIRED_LIB = ["_step_exporter.pyd", "TKernel.dll", "TKMath.dll", "TKSTEP.dll",
                "TKTopAlgo.dll", "TKBRep.dll", "TKBool.dll", "TKFillet.dll"]

EXCLUDE_DIRS = {"__pycache__"}
EXCLUDE_SUFFIXES = (".pyc", ".log", ".step", ".stp", ".blend1", ".blend2")


def find_version():
    """Read version from step_exporter/__init__.py bl_info."""
    import re
    path = os.path.join(PKG, "__init__.py")
    txt = open(path, encoding="utf-8").read()
    m = re.search(r'"version":\s*\((\d+),\s*(\d+),\s*(\d+)\)', txt)
    if not m:
        raise SystemExit("Cannot find bl_info version")
    return ".".join(m.groups())


def main():
    if not os.path.isdir(PKG):
        raise SystemExit(f"Package dir not found: {PKG}")
    for f in REQUIRED_LIB:
        p = os.path.join(LIB, f)
        if not os.path.exists(p):
            raise SystemExit(f"Missing required runtime file: {f}\n"
                             "Build/refresh it first (see BUILD.md).")

    version = sys.argv[1] if len(sys.argv) > 1 else find_version()
    out_zip = os.path.join(REPO, f"step_exporter-{version}.zip")

    n_files = 0
    total = 0
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(PKG):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for fn in files:
                if fn.endswith(EXCLUDE_SUFFIXES):
                    continue
                full = os.path.join(root, fn)
                arc = os.path.relpath(full, REPO)  # step_exporter/...
                zf.write(full, arc)
                n_files += 1
                total += os.path.getsize(full)

    size_mb = os.path.getsize(out_zip) / (1024 * 1024)
    print(f"[RELEASE] {out_zip}")
    print(f"[RELEASE] {n_files} files, {total/1024/1024:.1f} MB raw -> {size_mb:.1f} MB zip")
    print(f"[RELEASE] Install in Blender: Edit > Preferences > Add-ons > Install from Disk...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
