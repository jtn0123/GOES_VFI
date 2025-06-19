#!/usr/bin/env python3
"""Script to fix missing imports in test files."""

import re
import subprocess
import sys
from pathlib import Path

# Common missing imports mapping
MISSING_IMPORTS = {
    "QSettings": "from PyQt6.QtCore import QSettings",
    "QTimer": "from PyQt6.QtCore import QTimer",
    "QDateTime": "from PyQt6.QtCore import QDateTime",
    "QDate": "from PyQt6.QtCore import QDate",
    "QTime": "from PyQt6.QtCore import QTime",
    "Image": "from PIL import Image",
    "Mock": "from unittest.mock import Mock",
    "MagicMock": "from unittest.mock import MagicMock",
    "patch": "from unittest.mock import patch",
    "AsyncMock": "from unittest.mock import AsyncMock",
}


def find_undefined_names(file_path):
    """Run flake8 to find undefined names."""
    result = subprocess.run(
        ["flake8", "--select=F821", str(file_path)], capture_output=True, text=True
    )

    undefined = []
    for line in result.stdout.splitlines():
        # Parse flake8 output: filename:line:col: F821 undefined name 'name'
        match = re.search(r"F821 undefined name '(\w+)'", line)
        if match:
            undefined.append(match.group(1))

    return list(set(undefined))  # Remove duplicates


def add_imports_to_file(file_path, imports_to_add):
    """Add missing imports to a file."""
    with open(file_path, "r") as f:
        lines = f.readlines()

    # Find where to insert imports (after existing imports)
    import_end = 0
    for i, line in enumerate(lines):
        if line.strip() and not line.startswith(("import ", "from ", "#")):
            if i > 0:  # We've passed the import section
                import_end = i
                break

    # Add imports
    for imp in imports_to_add:
        lines.insert(import_end, imp + "\n")
        import_end += 1

    # Write back
    with open(file_path, "w") as f:
        f.writelines(lines)


def fix_file(file_path):
    """Fix missing imports in a single file."""
    print(f"\nChecking {file_path}...")

    undefined = find_undefined_names(file_path)
    if not undefined:
        print(f"  ✓ No undefined names found")
        return False

    print(f"  Found undefined names: {', '.join(undefined)}")

    imports_to_add = []
    for name in undefined:
        if name in MISSING_IMPORTS:
            import_stmt = MISSING_IMPORTS[name]
            # Check if import already exists
            with open(file_path, "r") as f:
                content = f.read()
                if import_stmt not in content:
                    imports_to_add.append(import_stmt)
                    print(f"  + Will add: {import_stmt}")

    if imports_to_add:
        add_imports_to_file(file_path, imports_to_add)
        print(f"  ✓ Added {len(imports_to_add)} imports")
        return True
    else:
        print(f"  ! Could not fix undefined names: {', '.join(undefined)}")
        return False


def main():
    """Main function."""
    if len(sys.argv) > 1:
        # Fix specific files
        files = [Path(f) for f in sys.argv[1:]]
    else:
        # Fix all test files with issues
        files = [
            Path("tests/unit/test_main_tab_utils.py"),
            Path("tests/unit/test_enhanced_view_model.py"),
            Path("tests/unit/test_enhanced_gui_tab.py"),
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
