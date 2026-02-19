"""Build script for creating Windows executable with PyInstaller."""

import os
import shutil
import subprocess
import sys
from pathlib import Path


def main():
    """Build executable using PyInstaller."""
    project_root = Path(__file__).parent
    src_dir = project_root / "src"
    dist_dir = project_root / "dist"
    build_dir = project_root / "build"

    # Clean previous builds
    if dist_dir.exists():
        print(f"Cleaning {dist_dir}...")
        shutil.rmtree(dist_dir)
    if build_dir.exists():
        print(f"Cleaning {build_dir}...")
        shutil.rmtree(build_dir)

    # Check if PyInstaller is installed
    try:
        import PyInstaller
    except ImportError:
        print("Error: PyInstaller is not installed.")
        print("Install it with: pip install pyinstaller")
        sys.exit(1)

    # Build command
    cmd = [
        "pyinstaller",
        "--onefile",
        "--windowed",  # No console window
        "--name",
        "rgb-keyboard-language",
        "--add-data",
        f"{src_dir}{os.pathsep}src",  # Include source files
        f"{src_dir}/rgb_keyboard_language_windows/main.py",
    ]

    # Add icon if exists
    icon_path = project_root / "assets" / "icon.ico"
    if icon_path.exists():
        cmd.extend(["--icon", str(icon_path)])

    print("Building executable with PyInstaller...")
    print(f"Command: {' '.join(cmd)}")
    print()

    try:
        result = subprocess.run(cmd, check=True, cwd=project_root)
        print()
        print("Build completed successfully!")
        print(f"Executable: {dist_dir / 'rgb-keyboard-language.exe'}")
    except subprocess.CalledProcessError as e:
        print(f"Build failed with exit code {e.returncode}")
        sys.exit(1)
    except FileNotFoundError:
        print("Error: pyinstaller command not found.")
        print("Make sure PyInstaller is installed and in PATH.")
        sys.exit(1)


if __name__ == "__main__":
    main()

