#!/usr/bin/env python3
"""Fix the final 36 MyPy strict errors."""

import os
import re


def fix_reconcile_manager_imports():
    """Fix missing Any import in reconcile_manager_refactored.py."""
    file_path = "goesvfi/integrity_check/reconcile_manager_refactored.py"

    if not os.path.exists(file_path):
        return

    with open(file_path, "r") as f:
        lines = f.readlines()

    # Find typing import and add Any
    for i, line in enumerate(lines):
        if "from typing import" in line and "Any" not in line:
            # Extract imports and add Any
            imports = re.search(r"from typing import (.+)", line)
            if imports:
                import_list = [imp.strip() for imp in imports.group(1).split(",")]
                if "Any" not in import_list:
                    import_list.append("Any")
                    import_list.sort()
                    lines[i] = f"from typing import {', '.join(import_list)}\n"
                    break

    with open(file_path, "w") as f:
        f.writelines(lines)
    print(f"Fixed Any import in {file_path}")


def fix_matplotlib_imports():
    """Fix matplotlib imports in netcdf.py."""
    file_path = "goesvfi/integrity_check/render/netcdf.py"

    if not os.path.exists(file_path):
        return

    with open(file_path, "r") as f:
        lines = f.readlines()

    # Fix line 120 - add type: ignore
    for i, line in enumerate(lines):
        if "import matplotlib.pyplot as plt" in line and "# type: ignore" not in line:
            lines[i] = line.rstrip() + "  # type: ignore[import-not-found]\n"

    with open(file_path, "w") as f:
        f.writelines(lines)
    print(f"Fixed matplotlib imports in {file_path}")


def fix_run_vfi_type_ignore():
    """Fix unused type: ignore in run_vfi.py."""
    file_path = "goesvfi/run_vfi.py"

    if not os.path.exists(file_path):
        return

    with open(file_path, "r") as f:
        lines = f.readlines()

    # The type: ignore comment should be for a different error
    for i, line in enumerate(lines):
        if i == 37 and "# type: ignore[import-untyped]" in line:
            # Change to the correct error code
            lines[i] = line.replace("[import-untyped]", "[import-not-found]")

    with open(file_path, "w") as f:
        f.writelines(lines)
    print(f"Fixed type: ignore in {file_path}")


def fix_optimized_timeline_imports():
    """Fix missing Tuple import in optimized_timeline_tab.py."""
    file_path = "goesvfi/integrity_check/optimized_timeline_tab.py"

    if not os.path.exists(file_path):
        return

    with open(file_path, "r") as f:
        lines = f.readlines()

    # Find typing import and add Tuple
    for i, line in enumerate(lines):
        if "from typing import" in line and "Tuple" not in line:
            imports = re.search(r"from typing import (.+)", line)
            if imports:
                import_list = [imp.strip() for imp in imports.group(1).split(",")]
                if "Tuple" not in import_list:
                    import_list.append("Tuple")
                    import_list.sort()
                    lines[i] = f"from typing import {', '.join(import_list)}\n"
                    break

    # Fix missing type annotations
    for i, line in enumerate(lines):
        if i == 198 and "def update_filter_buttons" in line and "->" not in line:
            lines[i] = line.rstrip()[:-1] + " -> None:\n"
        elif i == 247 and "def update_view_buttons" in line and "->" not in line:
            lines[i] = line.rstrip()[:-1] + " -> None:\n"

    with open(file_path, "w") as f:
        f.writelines(lines)
    print(f"Fixed imports and annotations in {file_path}")


def fix_gui_backup():
    """Fix TypedDict and logging issues in gui_backup.py."""
    file_path = "goesvfi/gui_backup.py"

    if not os.path.exists(file_path):
        return

    with open(file_path, "r") as f:
        content = f.read()

    # Add TypedDict import
    if "from typing import" in content and "TypedDict" not in content:
        content = re.sub(
            r"from typing import ([^)]+)",
            lambda m: f"from typing import {m.group(1)}, TypedDict",
            content,
        )

    # Add logging import if missing
    if "logging.getLogger" in content and "import logging" not in content:
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if line.startswith("import ") or line.startswith("from "):
                lines.insert(i, "import logging")
                content = "\n".join(lines)
                break

    with open(file_path, "w") as f:
        f.write(content)
    print(f"Fixed TypedDict and logging in {file_path}")


def fix_combined_tab():
    """Fix type issues in combined_tab.py."""
    file_path = "goesvfi/integrity_check/combined_tab.py"

    if not os.path.exists(file_path):
        return

    with open(file_path, "r") as f:
        lines = f.readlines()

    # Fix line 271 - list without type parameter
    for i, line in enumerate(lines):
        if i == 270 and ": list" in line:
            lines[i] = line.replace(": list", ": List[Any]")

    # Fix line 418 - missing type annotation
    for i, line in enumerate(lines):
        if i == 417 and "def update_data" in line:
            lines[i] = re.sub(
                r"missing_items=None, start_date=None, end_date=None, total_expected=None",
                "missing_items: Optional[List[Any]] = None, start_date: Optional[Any] = None, end_date: Optional[Any] = None, total_expected: Optional[int] = None",
                line,
            )

    with open(file_path, "w") as f:
        f.writelines(lines)
    print(f"Fixed type issues in {file_path}")


def fix_timeline_visualization_types():
    """Fix remaining type annotations in timeline_visualization.py."""
    file_path = "goesvfi/integrity_check/timeline_visualization.py"

    if not os.path.exists(file_path):
        return

    with open(file_path, "r") as f:
        lines = f.readlines()

    # Fix HourCell __init__ parameters
    for i, line in enumerate(lines):
        if i >= 1259 and i <= 1268:
            if "parent=None" in line:
                lines[i] = line.replace(
                    "parent=None", "parent: Optional[QWidget] = None"
                )
            elif "hour=0" in line:
                lines[i] = line.replace("hour=0", "hour: int = 0")
            elif 'day=""' in line:
                lines[i] = line.replace('day=""', 'day: str = ""')
            elif "bg_color=None" in line:
                lines[i] = line.replace(
                    "bg_color=None", "bg_color: Optional[QColor] = None"
                )
            elif "text_color=None" in line:
                lines[i] = line.replace(
                    "text_color=None", "text_color: Optional[QColor] = None"
                )
            elif "is_selected=False" in line:
                lines[i] = line.replace(
                    "is_selected=False", "is_selected: bool = False"
                )

    # Fix line 1368
    if len(lines) > 1367:
        line = lines[1367]
        if "def " in line and "parent" in line:
            lines[1367] = re.sub(r"parent\)", "parent: Optional[QWidget])", line)

    with open(file_path, "w") as f:
        f.writelines(lines)
    print(f"Fixed type annotations in {file_path}")


def main():
    """Run all fixes."""
    print("Fixing final 36 MyPy strict errors...\n")

    fix_reconcile_manager_imports()
    fix_matplotlib_imports()
    fix_run_vfi_type_ignore()
    fix_optimized_timeline_imports()
    fix_gui_backup()
    fix_combined_tab()
    fix_timeline_visualization_types()

    print("\nAll fixes applied!")


if __name__ == "__main__":
    main()
