#!/usr/bin/env python3
"""Fix Qt default parameter issues."""

import re
from pathlib import Path


def fix_qmodelindex_defaults(file_path: Path) -> None:
    """Fix QModelIndex() in default parameters."""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Replace QModelIndex() with None and handle in function body
    # Pattern to match function definitions with QModelIndex() defaults
    pattern = r"(def \w+\([^)]*parent: QModelIndex = )QModelIndex\(\)([^)]*\)[^:]*:)"

    def replacer(match):
        return match.group(1) + "None" + match.group(2)

    content = re.sub(pattern, replacer, content)

    # Now add None handling in the function bodies
    # For rowCount
    content = re.sub(
        r'(def rowCount\([^)]+\) -> int:\s*\n\s*"""[^"]*"""\s*\n)',
        r"\1        if parent is None:\n            parent = QModelIndex()\n",
        content,
    )

    # For columnCount
    content = re.sub(
        r'(def columnCount\([^)]+\) -> int:\s*\n\s*"""[^"]*"""\s*\n)',
        r"\1        if parent is None:\n            parent = QModelIndex()\n",
        content,
    )

    # For data method with Qt.ItemDataRole.DisplayRole
    pattern2 = (
        r"(def data\([^)]*role: int = )Qt\.ItemDataRole\.DisplayRole([^)]*\)[^:]*:)"
    )
    content = re.sub(pattern2, r"\g<1>None\g<2>", content)

    # Add handling for role
    content = re.sub(
        r'(def data\([^)]+\) -> Any:\s*\n\s*"""[^"]*"""\s*\n)',
        r"\1        if role is None:\n            role = Qt.ItemDataRole.DisplayRole\n",
        content,
    )

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)


def main():
    """Fix all Qt default parameter issues."""
    fix_qmodelindex_defaults(Path("goesvfi/gui_tabs/operation_history_tab.py"))
    print("Qt default parameter issues fixed!")


if __name__ == "__main__":
    main()
