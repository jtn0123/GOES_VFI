#!/usr/bin/env python3
"""
Script to fix PyQt import issues in gui.py.
"""

import re
from pathlib import Path


def fix_pyqt_imports(content):
    """Add missing PyQt imports."""
    # Add required PyQt imports
    if "from PyQt6.QtCore import pyqtSignal" not in content:
        # Add pyqtSignal import
        pattern = r"from PyQt6.QtCore import (.*?)\n"
        match = re.search(pattern, content)
        if match:
            imports = match.group(1).strip()
            if imports.endswith(","):
                new_imports = f"{imports} pyqtSignal"
            else:
                new_imports = f"{imports}, pyqtSignal"
            content = content.replace(match.group(1), new_imports)
        else:
            # Add a new import line
            content = re.sub(
                r"import PyQt6\n",
                "import PyQt6\nfrom PyQt6.QtCore import pyqtSignal\n",
                content,
            )

    # Add QSettings import if missing
    if (
        "QSettings" not in content
        or "from PyQt6.QtCore import QSettings" not in content
    ):
        # Add QSettings import
        pattern = r"from PyQt6.QtCore import (.*?)\n"
        match = re.search(pattern, content)
        if match:
            imports = match.group(1).strip()
            if "QSettings" not in imports:
                if imports.endswith(","):
                    new_imports = f"{imports} QSettings"
                else:
                    new_imports = f"{imports}, QSettings"
                content = content.replace(match.group(1), new_imports)

    # Fix spacing in inline comments
    content = re.sub(r"([^,]) #", r"\1  #", content)

    return content


def main():
    """Fix PyQt imports in gui.py."""
    file_path = Path(__file__).parent / "goesvfi" / "gui.py"

    print(f"Reading {file_path}...")
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Make a backup
    backup_path = file_path.with_suffix(".py.imports.bak")
    print(f"Creating backup at {backup_path}...")
    with open(backup_path, "w", encoding="utf-8") as f:
        f.write(content)

    # Apply fixes
    print("Fixing PyQt imports...")
    content = fix_pyqt_imports(content)

    # Write the fixed content back
    print(f"Writing fixed content to {file_path}...")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    print("Done.")


if __name__ == "__main__":
    main()
