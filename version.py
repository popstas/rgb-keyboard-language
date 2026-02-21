"""Version bump script - updates version in project files, optionally commits and tags."""

import argparse
import re
import subprocess
import sys
from pathlib import Path

VERSION_PATTERN = re.compile(r'version\s*=\s*"(\d+\.\d+\.\d+)"')
VERSION_PATTERN_PY = re.compile(r'__version__\s*=\s*"(\d+\.\d+\.\d+)"')

VERSION_FILES = [
    ("pyproject.toml", VERSION_PATTERN, 'version = "{new}"'),
    ("src/rgb_keyboard_language_windows/__init__.py", VERSION_PATTERN_PY, '__version__ = "{new}"'),
    ("keychron-via-hue/pyproject.toml", VERSION_PATTERN, 'version = "{new}"'),
    ("keychron-via-hue/src/keychron_via_hue/__init__.py", VERSION_PATTERN_PY, '__version__ = "{new}"'),
]


def get_current_version(project_root: Path) -> str:
    """Parse current version from root pyproject.toml."""
    path = project_root / "pyproject.toml"
    content = path.read_text(encoding="utf-8")
    m = VERSION_PATTERN.search(content)
    if not m:
        print("Error: Could not parse version from pyproject.toml (expected X.Y.Z format).")
        sys.exit(1)
    return m.group(1)


def bump_version(current: str, part: str) -> str:
    """Bump version by patch, minor, or major. Returns new version string."""
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)$", current)
    if not m:
        print(f"Error: Invalid version format '{current}' (expected X.Y.Z).")
        sys.exit(1)

    major, minor, patch = int(m.group(1)), int(m.group(2)), int(m.group(3))

    if part == "patch":
        return f"{major}.{minor}.{patch + 1}"
    if part == "minor":
        return f"{major}.{minor + 1}.0"
    if part == "major":
        return f"{major + 1}.0.0"

    print(f"Error: Unknown bump part '{part}' (use patch, minor, or major).")
    sys.exit(1)


def update_file(path: Path, pattern: re.Pattern[str], replacement: str) -> bool:
    """Update version in file. Returns True if file was modified."""
    content = path.read_text(encoding="utf-8")
    new_content = pattern.sub(replacement, content, count=1)
    if content != new_content:
        path.write_text(new_content, encoding="utf-8")
        return True
    return False


def tag_exists(project_root: Path, tag: str) -> bool:
    """Check if git tag exists."""
    result = subprocess.run(
        ["git", "tag", "-l", tag],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    return bool(result.stdout.strip())


def run_git(project_root: Path, args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run git command. Returns CompletedProcess."""
    return subprocess.run(
        ["git"] + args,
        cwd=project_root,
        capture_output=True,
        text=True,
        check=check,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Bump version in project files and optionally commit and tag."
    )
    parser.add_argument(
        "part",
        choices=["patch", "minor", "major"],
        help="Version part to bump",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show new version and files to change, no writes, no git",
    )
    parser.add_argument(
        "--no-commit",
        action="store_true",
        help="Update files only, no git add/commit/tag",
    )
    args = parser.parse_args()

    project_root = Path(__file__).parent

    current = get_current_version(project_root)
    new_version = bump_version(current, args.part)

    if args.dry_run:
        print(f"Dry run: {current} -> {new_version}")
        for rel_path, pattern, _ in VERSION_FILES:
            path = project_root / rel_path
            if path.exists():
                print(f"  Would update: {rel_path}")
            else:
                print(f"  Would update (missing): {rel_path}")
        return

    if not args.no_commit:
        if tag_exists(project_root, f"v{new_version}"):
            print(f"Error: Tag v{new_version} already exists.")
            sys.exit(1)

    modified = []
    for rel_path, pattern, template in VERSION_FILES:
        path = project_root / rel_path
        if not path.exists():
            print(f"Warning: {rel_path} not found, skipping.")
            continue
        replacement = template.format(new=new_version)
        if update_file(path, pattern, replacement):
            modified.append(rel_path)
            print(f"Updated {rel_path} -> {new_version}")

    if not modified:
        print("No files were modified.")
        return

    if args.no_commit:
        print(f"Version updated to {new_version}. Skipping git (--no-commit).")
        return

    run_git(project_root, ["add"] + modified)
    run_git(project_root, ["commit", "-m", f"release: v{new_version}"])
    run_git(project_root, ["tag", f"v{new_version}"])

    print()
    print(f"Version bumped to {new_version}")
    print(f"Committed and tagged v{new_version}")
    print("Push with: git push && git push --tags")


if __name__ == "__main__":
    main()
