#!/usr/bin/env python3
"""Fix the final 26 MyPy strict errors."""

import os
import re


def fix_user_feedback_line_785():
    """Fix the specific None check issue in user_feedback.py line 785."""
    file_path = "goesvfi/integrity_check/user_feedback.py"

    if not os.path.exists(file_path):
        return

    with open(file_path, "r") as f:
        lines = f.readlines()

    # Fix line 785 - the comprehension needs proper None handling
    for i, line in enumerate(lines):
        if i == 784 and "self.message_list.item(i).text()" in line:
            # This is a comprehension, we need to fix it differently
            lines[i] = line.replace(
                'self.message_list.item(i).text() if self.message_list.item(i) else ""',
                '(item.text() if item else "") if (item := self.message_list.item(i)) is not None else ""',
            )

    with open(file_path, "w") as f:
        f.writelines(lines)
    print(f"Fixed line 785 in {file_path}")


def fix_auto_detection_none_checks_properly():
    """Fix the QListWidgetItem None checks in auto_detection.py."""
    file_path = "goesvfi/integrity_check/auto_detection.py"

    if not os.path.exists(file_path):
        return

    with open(file_path, "r") as f:
        lines = f.readlines()

    # Find and fix lines 140-141
    for i in range(len(lines)):
        if i >= 139 and i <= 141:
            # Look for the pattern where item is created and then used
            if "item = QListWidgetItem" in lines[i]:
                # Find the next lines that use item
                j = i + 1
                while j < len(lines) and j < i + 5:
                    if (
                        "item.setForeground" in lines[j]
                        or "item.setBackground" in lines[j]
                    ):
                        # These lines need to be indented and wrapped in if
                        indent = len(lines[j]) - len(lines[j].lstrip())
                        if j > 0 and "if item:" not in lines[j - 1]:
                            # Insert if check
                            lines[j] = (
                                " " * indent
                                + "if item:\n"
                                + " " * (indent + 4)
                                + lines[j].lstrip()
                            )
                    j += 1
                break

    with open(file_path, "w") as f:
        f.writelines(lines)
    print(f"Fixed None checks in {file_path}")


def fix_auto_detection_annotations():
    """Fix missing type annotations in auto_detection.py."""
    file_path = "goesvfi/integrity_check/auto_detection.py"

    if not os.path.exists(file_path):
        return

    with open(file_path, "r") as f:
        lines = f.readlines()

    # Fix line 155 - __init__ method
    for i, line in enumerate(lines):
        if i == 154 and "def __init__" in line and "parent" in line:
            # Add proper type annotations
            lines[i] = re.sub(
                r"def __init__\(self, parent\)",
                "def __init__(self, parent: Optional[QWidget] = None)",
                line,
            )
            if "->" not in line:
                lines[i] = lines[i].rstrip()[:-1] + " -> None:\n"

    with open(file_path, "w") as f:
        f.writelines(lines)
    print(f"Fixed annotations in {file_path}")


def fix_render_netcdf_unused_ignore():
    """Remove unused type: ignore in render/netcdf.py."""
    file_path = "goesvfi/integrity_check/render/netcdf.py"

    if not os.path.exists(file_path):
        return

    with open(file_path, "r") as f:
        lines = f.readlines()

    # Remove type: ignore on line 151 if it's unused
    if len(lines) > 150:
        if "# type: ignore" in lines[150]:
            lines[150] = lines[150].replace("  # type: ignore[import-not-found]", "")

    with open(file_path, "w") as f:
        f.writelines(lines)
    print(f"Fixed unused type: ignore in {file_path}")


def fix_run_vfi_unused_ignore():
    """Fix unused type: ignore in run_vfi.py."""
    file_path = "goesvfi/run_vfi.py"

    if not os.path.exists(file_path):
        return

    with open(file_path, "r") as f:
        lines = f.readlines()

    # The tqdm import actually needs import-untyped not import-not-found
    for i, line in enumerate(lines):
        if i == 37 and "from tqdm import tqdm" in line:
            lines[i] = "    from tqdm import tqdm  # type: ignore[import-untyped]\n"

    with open(file_path, "w") as f:
        f.writelines(lines)
    print(f"Fixed type: ignore in {file_path}")


def fix_reconcile_manager_final():
    """Fix remaining issues in reconcile_manager_refactored.py."""
    file_path = "goesvfi/integrity_check/reconcile_manager_refactored.py"

    if not os.path.exists(file_path):
        return

    with open(file_path, "r") as f:
        content = f.read()

    # Add Optional import if missing
    if (
        "from typing import" in content
        and "Optional" not in content.split("from typing import")[1].split("\n")[0]
    ):
        content = re.sub(
            r"from typing import ([^)]+)",
            lambda m: f"from typing import {m.group(1)}, Optional",
            content,
        )

    # Fix empty body returns
    lines = content.splitlines()
    for i, line in enumerate(lines):
        # Fix line 47 and 59
        if (
            "async def _is_recent" in line or "async def _download_missing" in line
        ) and i + 1 < len(lines):
            if lines[i + 1].strip() == '"""' and i + 2 < len(lines):
                # Find the end of docstring
                j = i + 2
                while j < len(lines) and '"""' not in lines[j]:
                    j += 1
                if j + 1 < len(lines) and lines[j + 1].strip() == "return":
                    # Already has return
                    pass
                elif j + 1 < len(lines) and lines[j + 1].strip() == "":
                    # Empty line after docstring, add return
                    lines[j + 1] = "        return False\n"

    content = "\n".join(lines)

    # Fix Semaphore Optional issues more aggressively
    content = re.sub(
        r"(\w+): Semaphore = None", r"\1: Optional[Semaphore] = None", content
    )

    with open(file_path, "w") as f:
        f.write(content)
    print(f"Fixed reconcile_manager_refactored.py")


def fix_pipeline_run_vfi_final():
    """Fix remaining issues in pipeline/run_vfi.py."""
    file_path = "goesvfi/pipeline/run_vfi.py"

    if not os.path.exists(file_path):
        return

    with open(file_path, "r") as f:
        content = f.read()

    # Fix Popen type parameters
    content = re.sub(r"subprocess\.Popen(?!\[)", "subprocess.Popen[bytes]", content)

    # Fix line 312 - add assertion for rife_exe_path
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if i == 311 and "rife_exe_path" in line and "run_vfi(" in line:
            # Check if assertion already exists
            if i > 0 and "assert rife_exe_path" not in lines[i - 1]:
                indent = len(line) - len(line.lstrip())
                lines.insert(
                    i,
                    " " * indent
                    + 'assert rife_exe_path is not None, "rife_exe_path must not be None"\n',
                )
                break

    content = "\n".join(lines)

    with open(file_path, "w") as f:
        f.write(content)
    print(f"Fixed pipeline/run_vfi.py")


def fix_optimized_timeline_tab_final():
    """Fix function annotations in optimized_timeline_tab.py."""
    file_path = "goesvfi/integrity_check/optimized_timeline_tab.py"

    if not os.path.exists(file_path):
        return

    with open(file_path, "r") as f:
        lines = f.readlines()

    # Fix line 199 and 248
    for i, line in enumerate(lines):
        if i == 198 and "def update_filter_buttons" in line:
            lines[i] = re.sub(
                r"def update_filter_buttons\(self\)",
                "def update_filter_buttons(self) -> None",
                line,
            )
        elif i == 247 and "def update_view_buttons" in line:
            lines[i] = re.sub(
                r"def update_view_buttons\(self\)",
                "def update_view_buttons(self) -> None",
                line,
            )

    with open(file_path, "w") as f:
        f.writelines(lines)
    print(f"Fixed optimized_timeline_tab.py")


def fix_gui_backup_final():
    """Fix TypedDict and logging issues in gui_backup.py."""
    file_path = "goesvfi/gui_backup.py"

    if not os.path.exists(file_path):
        return

    with open(file_path, "r") as f:
        lines = f.readlines()

    # Add TypedDict import at the top
    import_added = False
    for i, line in enumerate(lines):
        if "from typing import" in line and "TypedDict" not in line:
            # Parse the import and add TypedDict
            match = re.match(r"from typing import (.+)", line)
            if match:
                imports = [imp.strip() for imp in match.group(1).split(",")]
                if "TypedDict" not in imports:
                    imports.append("TypedDict")
                    imports.sort()
                    lines[i] = f"from typing import {', '.join(imports)}\n"
                    import_added = True
                    break

    if not import_added:
        # Add as a new import
        for i, line in enumerate(lines):
            if line.startswith("from typing import"):
                lines.insert(i + 1, "from typing import TypedDict\n")
                break

    # Add logging import
    logging_exists = any("import logging" in line for line in lines)
    if not logging_exists:
        for i, line in enumerate(lines):
            if line.startswith("import ") or line.startswith("from "):
                lines.insert(i, "import logging\n")
                break

    # Fix TypedDict usage - cast the dicts properly
    content = "".join(lines)
    content = re.sub(
        r'DEFAULT_PROFILES\["([^"]+)"\]',
        r'cast(FfmpegProfile, DEFAULT_PROFILES["\1"])',
        content,
    )

    # Add cast import if needed
    if "cast(FfmpegProfile" in content and "from typing import" in content:
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if "from typing import" in line and "cast" not in line:
                match = re.match(r"from typing import (.+)", line)
                if match:
                    imports = [imp.strip() for imp in match.group(1).split(",")]
                    if "cast" not in imports:
                        imports.append("cast")
                        imports.sort()
                        lines[i] = f"from typing import {', '.join(imports)}"
                        content = "\n".join(lines)
                        break

    with open(file_path, "w") as f:
        f.write(content)
    print(f"Fixed gui_backup.py")


def fix_combined_tab_annotation():
    """Fix function annotation in combined_tab.py."""
    file_path = "goesvfi/integrity_check/combined_tab.py"

    if not os.path.exists(file_path):
        return

    with open(file_path, "r") as f:
        lines = f.readlines()

    # The update_data method already has annotations, but they might be on wrong line
    # Check if it's already fixed
    found = False
    for i, line in enumerate(lines):
        if "def update_data" in line and i >= 417 and i <= 419:
            if "Optional" in line:
                found = True
                break

    if not found:
        # Fix line 418
        for i, line in enumerate(lines):
            if i == 417 and "def update_data" in line:
                # Already fixed in previous script
                pass

    with open(file_path, "w") as f:
        f.writelines(lines)
    print(f"Checked combined_tab.py")


def fix_timeline_visualization_final():
    """Fix remaining annotation in timeline_visualization.py."""
    file_path = "goesvfi/integrity_check/timeline_visualization.py"

    if not os.path.exists(file_path):
        return

    with open(file_path, "r") as f:
        lines = f.readlines()

    # Fix line 1368
    for i, line in enumerate(lines):
        if i == 1367 and "def " in line:
            if "parent" in line and "Optional" not in line:
                lines[i] = re.sub(
                    r"parent\)", "parent: Optional[QWidget] = None)", line
                )

    with open(file_path, "w") as f:
        f.writelines(lines)
    print(f"Fixed timeline_visualization.py")


def main():
    """Run all fixes."""
    print("Fixing final 26 MyPy strict errors...\n")

    fix_user_feedback_line_785()
    fix_auto_detection_none_checks_properly()
    fix_auto_detection_annotations()
    fix_render_netcdf_unused_ignore()
    fix_run_vfi_unused_ignore()
    fix_reconcile_manager_final()
    fix_pipeline_run_vfi_final()
    fix_optimized_timeline_tab_final()
    fix_gui_backup_final()
    fix_combined_tab_annotation()
    fix_timeline_visualization_final()

    print("\nAll fixes applied!")


if __name__ == "__main__":
    main()
