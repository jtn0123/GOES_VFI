#!/usr/bin/env python3
"""Fix Path.check_file_exists() calls that should be Path.exists()."""

import re
import sys
from pathlib import Path


def fix_file(file_path):
    """Fix Path.check_file_exists() calls in a file."""
    print(f"\nProcessing {file_path}...")

    with open(file_path, "r") as f:
        content = f.read()

    original_content = content

    # Fix Path objects calling check_file_exists when they should call exists
    # Pattern: path_variable.check_file_exists() -> path_variable.exists()
    # Only for local Path objects (not remote store objects)

    # Find patterns like: converted_dir.check_file_exists()
    # Where converted_dir is a Path object
    patterns = [
        # Any variable ending in _path, _dir, _file
        (r"(\w+(?:_path|_dir|_file))\.check_file_exists\(\)", r"\1.exists()"),
        # Path constructors
        (r"(Path\([^)]+\))\.check_file_exists\(\)", r"\1.exists()"),
        # Parenthesized path expressions like (converted_dir / "imageD")
        (r"\(([^)]+)\)\.check_file_exists\(\)", r"(\1).exists()"),
        # Dictionary access with ["path"] key
        (r'([a-zA-Z_]\w*\[["\']path["\']\])\.check_file_exists\(\)', r"\1.exists()"),
        # Any other variable that looks like a path
        (r"(\w*(?:file|path|dir)\w*)\.check_file_exists\(\)", r"\1.exists()"),
    ]

    for pattern, replacement in patterns:
        content = re.sub(pattern, replacement, content)

    if content != original_content:
        with open(file_path, "w") as f:
            f.write(content)
        print("  ✓ Fixed Path.check_file_exists() calls")
        return True
    else:
        print("  ✓ No Path fixes needed")
        return False


def main():
    """Main function."""
    if len(sys.argv) > 1:
        files = [Path(f) for f in sys.argv[1:]]
    else:
        files = [
            Path("tests/unit/test_file_sorter.py"),
            Path("tests/unit/test_file_sorter_refactored.py"),
        ]

    fixed_count = 0
    for file_path in files:
        if file_path.exists():
            if fix_file(file_path):
                fixed_count += 1
        else:
            print(f"File not found: {file_path}")

    print(f"\n✓ Fixed {fixed_count} files")


if __name__ == "__main__":
    main()
