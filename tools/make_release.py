"""Build a Blender-addon release zip of the `step_exporter` package.

Run:  python tools/make_release.py [version]
Output: blender2step-<version>.zip  (in the repo root)

The zip is directly installable in Blender via:
    Edit > Preferences > Add-ons > Install from Disk... > select the zip

Only git-tracked files under `step_exporter/` are packaged — untracked local
artifacts (test .step/.log/.blend files, __pycache__, debug scripts, ...) never
leak into the release. The compiled `_step_exporter.pyd` and the OpenCASCADE
`TK*.dll` runtimes are committed to git, so a fresh clone produces a complete,
installable zip without building.
"""
import os
import sys
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = os.path.join(REPO, "step_exporter")
LIB = os.path.join(PKG, "lib")

REQUIRED_LIB = ["_step_exporter.pyd", "TKernel.dll", "TKMath.dll", "TKSTEP.dll",
                "TKTopAlgo.dll", "TKBRep.dll", "TKBool.dll", "TKFillet.dll"]

# Only walk-pruning (such dirs are never tracked anyway); git-tracking is the
# authoritative filter deciding what goes into the release zip.
EXCLUDE_DIRS = {"__pycache__"}


def find_version():
    """Read version from step_exporter/__init__.py bl_info."""
    import re
    path = os.path.join(PKG, "__init__.py")
    txt = open(path, encoding="utf-8").read()
    m = re.search(r'"version":\s*\((\d+),\s*(\d+),\s*(\d+)\)', txt)
    if not m:
        raise SystemExit("Cannot find bl_info version")
    return ".".join(m.groups())


def git_tracked_files():
    """Repo-relative paths (forward slashes) of git-tracked files under step_exporter/.

    The release only ships files committed to the repository, so untracked local
    artifacts never leak into the zip.
    """
    import subprocess
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z", "--", "step_exporter"],
            cwd=REPO, capture_output=True)
    except FileNotFoundError:
        raise SystemExit("git not found on PATH — cannot determine tracked files.\n"
                         "Run this from the blender2step git working tree.")
    if result.returncode != 0:
        raise SystemExit("git ls-files failed:\n"
                         + result.stderr.decode("utf-8", "replace"))
    out = result.stdout.decode("utf-8", "replace")
    return {p.replace("\\", "/") for p in out.split("\0") if p.strip()}


def main():
    if not os.path.isdir(PKG):
        raise SystemExit(f"Package dir not found: {PKG}")
    for f in REQUIRED_LIB:
        p = os.path.join(LIB, f)
        if not os.path.exists(p):
            raise SystemExit(f"Missing required runtime file: {f}\n"
                             "Build/refresh it first (see BUILD.md).")

    version = sys.argv[1] if len(sys.argv) > 1 else find_version()
    out_zip = os.path.join(REPO, f"blender2step-{version}.zip")

    tracked = git_tracked_files()

    n_files = 0
    skipped = 0
    total = 0
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(PKG):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for fn in files:
                full = os.path.join(root, fn)
                arc = os.path.relpath(full, REPO).replace("\\", "/")  # step_exporter/...
                # Authoritative filter: only git-tracked files are released.
                # Untracked local artifacts (test .step/.log/.blend files, debug
                # scripts, __pycache__ ...) are never packed.
                if arc not in tracked:
                    skipped += 1
                    continue
                zf.write(full, arc)
                n_files += 1
                total += os.path.getsize(full)

    size_mb = os.path.getsize(out_zip) / (1024 * 1024)
    print(f"[RELEASE] {out_zip}")
    print(f"[RELEASE] {n_files} files packed, {skipped} untracked skipped, "
          f"{total/1024/1024:.1f} MB raw -> {size_mb:.1f} MB zip")
    print(f"[RELEASE] Install in Blender: Edit > Preferences > Add-ons > Install from Disk...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
