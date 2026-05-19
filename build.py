"""Build script for VCU DevKit — creates a standalone executable via PyInstaller.

Usage:
    python build.py              # Build release
    python build.py --debug      # Build with console window
    python build.py --clean      # Remove build/dist dirs before building
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

# Read version from pyproject.toml
def get_version() -> str:
    try:
        import tomllib
        with open("pyproject.toml", "rb") as f:
            data = tomllib.load(f)
        return data.get("project", {}).get("version", "0.1.0")
    except Exception:
        return "0.1.0"


def main():
    parser = argparse.ArgumentParser(description="Build VCU DevKit executable")
    parser.add_argument("--debug", action="store_true", help="Build with console window")
    parser.add_argument("--clean", action="store_true", help="Clean build artifacts first")
    args = parser.parse_args()

    version = get_version()
    print(f"Building VCU DevKit v{version}")

    if args.clean:
        for d in ("build", "dist"):
            p = Path(d)
            if p.exists():
                print(f"  Removing {d}/")
                shutil.rmtree(p)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "vcu_devkit.spec",
        "--noconfirm",
        "--clean",
    ]
    if args.debug:
        cmd.append("--console")

    print(f"  Running: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print("Build FAILED")
        sys.exit(1)

    dist_dir = Path("dist") / "VCU-DevKit"
    exe_path = dist_dir / "VCU-DevKit.exe"
    if exe_path.exists():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print(f"  Output: {exe_path} ({size_mb:.1f} MB)")
    else:
        print(f"  Output directory: {dist_dir}")

    print("Build OK")


if __name__ == "__main__":
    main()
