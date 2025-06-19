#!/usr/bin/env python3
"""Fix the last 16 MyPy strict errors."""

import os
import re


def fix_auto_detection_item_proper():
    """Fix the QListWidgetItem None issue properly in auto_detection.py."""
    file_path = "goesvfi/integrity_check/auto_detection.py"

    if not os.path.exists(file_path):
        return

    with open(file_path, "r") as f:
        lines = f.readlines()

    # Fix lines 140-141 by storing item and checking
    for i, line in enumerate(lines):
        if i == 139 and "self.log_widget.item(0).setForeground" in line:
            # Replace these two lines with proper None check
            indent = len(line) - len(line.lstrip())
            lines[i] = " " * indent + "item = self.log_widget.item(0)\n"
            lines.insert(i + 1, " " * indent + "if item:\n")
            lines.insert(
                i + 2, " " * (indent + 4) + "item.setForeground(Qt.GlobalColor.white)\n"
            )
            if i + 3 < len(lines) and "setBackground" in lines[i + 3]:
                lines[i + 3] = (
                    " " * (indent + 4) + "item.setBackground(QColor(color))\n"
                )
            break

    # Fix line 155 __init__ annotation
    for i, line in enumerate(lines):
        if i == 154 and "def __init__" in line:
            if "Optional[QWidget]" not in line:
                lines[i] = re.sub(
                    r"def __init__\(self, parent.*?\)",
                    "def __init__(self, parent: Optional[QWidget] = None)",
                    line,
                )
            if "->" not in line:
                lines[i] = lines[i].rstrip()[:-1] + " -> None:\n"

    # Fix line 353 - the dict timestamps issue
    for i, line in enumerate(lines):
        if i == 352 and '"timestamps":' in line:
            # Change list to a JSON string
            lines[i] = line.replace(
                '"timestamps": json.dumps([ts.isoformat() if hasattr(ts, "isoformat") else str(ts) for ts in timestamps]) if timestamps else None',
                '"timestamps": json.dumps([ts.isoformat() if hasattr(ts, "isoformat") else str(ts) for ts in timestamps]) if timestamps else None',
            )
            # Actually, the issue is the type is list[str] | None but expected str | None
            # So we need to keep it as a JSON string which is correct
            pass

    with open(file_path, "w") as f:
        f.writelines(lines)
    print(f"Fixed auto_detection.py")


def fix_timeline_visualization_line_1368():
    """Fix the specific function annotation in timeline_visualization.py."""
    file_path = "goesvfi/integrity_check/timeline_visualization.py"

    if not os.path.exists(file_path):
        return

    with open(file_path, "r") as f:
        lines = f.readlines()

    # Fix line 1368
    for i, line in enumerate(lines):
        if i == 1367 and "def " in line:
            # Add full type annotations
            if "parent" in line and "Optional" not in line:
                lines[i] = re.sub(
                    r"def (\w+)\(self, parent.*?\)",
                    r"def \1(self, parent: Optional[QWidget] = None)",
                    line,
                )
            if "->" not in line:
                lines[i] = lines[i].rstrip()[:-1] + " -> None:\n"

    with open(file_path, "w") as f:
        f.writelines(lines)
    print(f"Fixed timeline_visualization.py")


def fix_run_vfi_tqdm():
    """Fix the tqdm type: ignore issue in run_vfi.py."""
    file_path = "goesvfi/run_vfi.py"

    if not os.path.exists(file_path):
        return

    with open(file_path, "r") as f:
        lines = f.readlines()

    # Remove the type: ignore since tqdm is untyped
    for i, line in enumerate(lines):
        if i == 37 and "from tqdm import tqdm" in line:
            lines[i] = "    from tqdm import tqdm\n"

    with open(file_path, "w") as f:
        f.writelines(lines)
    print(f"Fixed run_vfi.py")


def fix_reconcile_manager_properly():
    """Fix reconcile_manager_refactored.py issues properly."""
    file_path = "goesvfi/integrity_check/reconcile_manager_refactored.py"

    if not os.path.exists(file_path):
        return

    with open(file_path, "r") as f:
        content = f.read()

    # Find the methods and add proper return statements
    lines = content.splitlines()

    # Fix _is_recent method (around line 47)
    for i, line in enumerate(lines):
        if "async def _is_recent" in line:
            # Find the end of this method
            j = i + 1
            indent_level = len(line) - len(line.lstrip())
            while j < len(lines):
                if lines[j].strip() and not lines[j].startswith(
                    " " * (indent_level + 1)
                ):
                    # End of method
                    break
                j += 1
            # Insert return before the end
            if j > i + 1:
                lines.insert(j - 1, " " * (indent_level + 4) + "return False")
            break

    # Fix _download_missing method (around line 59)
    for i, line in enumerate(lines):
        if "async def _download_missing" in line:
            # Find the end of this method
            j = i + 1
            indent_level = len(line) - len(line.lstrip())
            while j < len(lines):
                if lines[j].strip() and not lines[j].startswith(
                    " " * (indent_level + 1)
                ):
                    # End of method
                    break
                j += 1
            # Insert return before the end
            if j > i + 1:
                lines.insert(j - 1, " " * (indent_level + 4) + "return None")
            break

    content = "\n".join(lines)

    with open(file_path, "w") as f:
        f.write(content)
    print(f"Fixed reconcile_manager_refactored.py")


def fix_pipeline_run_vfi_assertion():
    """Fix the rife_exe_path assertion in pipeline/run_vfi.py."""
    file_path = "goesvfi/pipeline/run_vfi.py"

    if not os.path.exists(file_path):
        return

    # Read the file and find the specific line
    with open(file_path, "r") as f:
        lines = f.readlines()

    # Find line 312 and add assertion if not already there
    for i, line in enumerate(lines):
        if i >= 310 and i <= 315 and "run_vfi(" in line and "rife_exe_path" in line:
            # Check if there's already an assertion
            if i > 0 and "assert rife_exe_path" not in lines[i - 1]:
                indent = len(line) - len(line.lstrip())
                if indent == 0:
                    indent = 4  # Default indent
                lines.insert(i, " " * indent + "assert rife_exe_path is not None\n")
                break

    with open(file_path, "w") as f:
        f.writelines(lines)
    print(f"Fixed pipeline/run_vfi.py assertion")


def fix_optimized_timeline_tab_annotations():
    """Fix function annotations in optimized_timeline_tab.py."""
    file_path = "goesvfi/integrity_check/optimized_timeline_tab.py"

    if not os.path.exists(file_path):
        return

    with open(file_path, "r") as f:
        content = f.read()

    # Fix the function definitions
    content = re.sub(
        r"def update_filter_buttons\(self\)(?!.*->)",
        "def update_filter_buttons(self) -> None",
        content,
    )
    content = re.sub(
        r"def update_view_buttons\(self\)(?!.*->)",
        "def update_view_buttons(self) -> None",
        content,
    )

    with open(file_path, "w") as f:
        f.write(content)
    print(f"Fixed optimized_timeline_tab.py")


def fix_combined_tab_update_data():
    """Fix update_data annotation in combined_tab.py."""
    file_path = "goesvfi/integrity_check/combined_tab.py"

    if not os.path.exists(file_path):
        return

    with open(file_path, "r") as f:
        lines = f.readlines()

    # Find line 418 with update_data
    for i, line in enumerate(lines):
        if i >= 416 and i <= 420 and "def update_data" in line:
            if "Optional" not in line:
                # Add proper annotations
                lines[i] = re.sub(
                    r"def update_data\(self, (.*?)\)",
                    r"def update_data(self, missing_items: Optional[List[Any]] = None, start_date: Optional[Any] = None, end_date: Optional[Any] = None, total_expected: Optional[int] = None)",
                    line,
                )
            if "->" not in line:
                lines[i] = lines[i].rstrip() + " -> None:\n"
            break

    with open(file_path, "w") as f:
        f.writelines(lines)
    print(f"Fixed combined_tab.py")


def main():
    """Run all fixes."""
    print("Fixing last 16 MyPy strict errors...\n")

    fix_auto_detection_item_proper()
    fix_timeline_visualization_line_1368()
    fix_run_vfi_tqdm()
    fix_reconcile_manager_properly()
    fix_pipeline_run_vfi_assertion()
    fix_optimized_timeline_tab_annotations()
    fix_combined_tab_update_data()

    print("\nAll fixes applied!")


if __name__ == "__main__":
    main()
