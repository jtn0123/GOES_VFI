#!/usr/bin/env python3
"""Fix remaining MyPy strict mode errors."""

import re
from pathlib import Path


def fix_background_worker_final():
    """Fix final issues in background_worker.py"""
    file_path = "goesvfi/integrity_check/background_worker.py"
    with open(file_path, "r") as f:
        lines = f.readlines()

    # Fix the broken get_task_result function
    for i, line in enumerate(lines):
        if "def get_task_result" in line and i + 10 < len(lines):
            # Find the problematic line
            for j in range(i, min(i + 20, len(lines))):
                if "background_manager.submit_task" in lines[j]:
                    # Remove this line - it's in the wrong place
                    lines[j] = ""
                    break

    # Fix run_in_background implementation
    new_lines = []
    skip_until = -1

    for i, line in enumerate(lines):
        if i < skip_until:
            continue

        if "def run_in_background(self, func:" in line:
            # Replace the entire method
            indent = len(line) - len(line.lstrip())
            new_lines.append(line)
            # Skip to the end of the current method
            j = i + 1
            while j < len(lines) and (
                lines[j].strip() == "" or lines[j].startswith(" " * (indent + 1))
            ):
                j += 1
            skip_until = j

            # Add the correct implementation
            new_lines.extend(
                [
                    " " * (indent + 4)
                    + '"""Submit a task for execution in the background.\n',
                    " " * (indent + 4) + "\n",
                    " " * (indent + 4) + "Args:\n",
                    " " * (indent + 8) + "func: Function to run in the background\n",
                    " " * (indent + 8)
                    + "*args: Positional arguments to pass to func\n",
                    " " * (indent + 8)
                    + "**kwargs: Keyword arguments to pass to func\n",
                    " " * (indent + 4) + "\n",
                    " " * (indent + 4) + "Returns:\n",
                    " " * (indent + 8) + "Task ID for tracking the task\n",
                    " " * (indent + 4) + '"""\n',
                    " " * (indent + 4) + "import uuid\n",
                    " " * (indent + 4) + "task_id = str(uuid.uuid4())\n",
                    " " * (indent + 4)
                    + "self.task_manager.submit_task(task_id, func, *args, **kwargs)\n",
                    " " * (indent + 4) + "return task_id\n",
                    "\n",
                ]
            )
        else:
            new_lines.append(line)

    with open(file_path, "w") as f:
        f.writelines(new_lines)
    print(f"Fixed {file_path}")


def fix_visual_date_picker_imports():
    """Fix missing QPoint import in visual_date_picker.py"""
    file_path = "goesvfi/integrity_check/visual_date_picker.py"
    with open(file_path, "r") as f:
        lines = f.readlines()

    # Find QtCore import and add QPoint
    for i, line in enumerate(lines):
        if "from PyQt6.QtCore import" in line and "QPoint" not in line:
            # Check if it's a multi-line import
            if line.strip().endswith("("):
                # Multi-line import
                j = i + 1
                while j < len(lines) and not lines[j].strip().endswith(")"):
                    j += 1
                # Add QPoint before the closing paren
                if j < len(lines):
                    lines[j] = lines[j].replace(")", ", QPoint)")
            else:
                # Single line import
                imports = line.strip().replace("from PyQt6.QtCore import ", "")
                current_imports = [imp.strip() for imp in imports.split(",")]
                if "QPoint" not in current_imports:
                    current_imports.append("QPoint")
                    lines[
                        i
                    ] = f"from PyQt6.QtCore import {', '.join(sorted(current_imports))}\n"
            break

    with open(file_path, "w") as f:
        f.writelines(lines)
    print(f"Fixed {file_path}")


def fix_time_index_imports():
    """Fix missing imports in time_index_refactored.py"""
    file_path = "goesvfi/integrity_check/time_index_refactored.py"
    with open(file_path, "r") as f:
        content = f.read()

    # Add missing imports
    if "from typing import" not in content:
        # Add typing imports after the docstring
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if line.strip() == '"""' and i > 0:  # End of module docstring
                lines.insert(i + 1, "\nfrom typing import Dict, List, Optional, Tuple")
                break
    else:
        # Update existing imports
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if line.startswith("from typing import"):
                imports = re.findall(r"from typing import (.+)", line)[0]
                current = {imp.strip() for imp in imports.split(",")}
                current.update({"Dict", "List", "Optional", "Tuple"})
                lines[i] = f"from typing import {', '.join(sorted(current))}"
                break

    # Also ensure re is imported
    has_re = any("import re" in line for line in lines)
    if not has_re:
        # Add after typing import
        for i, line in enumerate(lines):
            if line.startswith("from typing import"):
                lines.insert(i + 1, "import re")
                break

    with open(file_path, "w") as f:
        f.write("\n".join(lines))
    print(f"Fixed {file_path}")


def fix_reconcile_manager_type_aliases():
    """Fix type alias issues in reconcile_manager_refactored.py"""
    file_path = "goesvfi/integrity_check/reconcile_manager_refactored.py"
    if not Path(file_path).exists():
        print(f"Skipping {file_path} - file not found")
        return

    with open(file_path, "r") as f:
        content = f.read()

    # Ensure TypeAlias is imported
    if "TypeAlias" not in content:
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if line.startswith("from typing import"):
                imports = re.findall(r"from typing import (.+)", line)[0]
                current = {imp.strip() for imp in imports.split(",")}
                current.add("TypeAlias")
                lines[i] = f"from typing import {', '.join(sorted(current))}"
                content = "\n".join(lines)
                break

    # Fix all callback type aliases
    content = re.sub(
        r"(\w+Callback)\s*=\s*Callable", r"\1: TypeAlias = Callable", content
    )

    with open(file_path, "w") as f:
        f.write(content)
    print(f"Fixed {file_path}")


def fix_enhanced_gui_tab():
    """Fix issues in enhanced_gui_tab.py"""
    file_path = "goesvfi/integrity_check/enhanced_gui_tab.py"
    if not Path(file_path).exists():
        print(f"Skipping {file_path} - file not found")
        return

    with open(file_path, "r") as f:
        lines = f.readlines()

    # Fix undefined names like hostname, session_id, start_timestamp
    new_lines = []
    for i, line in enumerate(lines):
        if "hostname" in line and "hostname" not in "".join(lines[max(0, i - 10) : i]):
            # Add definition before use
            indent = len(line) - len(line.lstrip())
            new_lines.append(" " * indent + "import socket\n")
            new_lines.append(" " * indent + "hostname = socket.gethostname()\n")
        if "session_id" in line and "session_id" not in "".join(
            lines[max(0, i - 10) : i]
        ):
            indent = len(line) - len(line.lstrip())
            new_lines.append(" " * indent + "import uuid\n")
            new_lines.append(" " * indent + "session_id = str(uuid.uuid4())\n")
        if "start_timestamp" in line and "start_timestamp" not in "".join(
            lines[max(0, i - 10) : i]
        ):
            indent = len(line) - len(line.lstrip())
            new_lines.append(" " * indent + "from datetime import datetime\n")
            new_lines.append(
                " " * indent + "start_timestamp = datetime.now().isoformat()\n"
            )

        new_lines.append(line)

    with open(file_path, "w") as f:
        f.writelines(new_lines)
    print(f"Fixed {file_path}")


def fix_combined_tab_import():
    """Fix import issue in combined_tab.py"""
    file_path = "goesvfi/integrity_check/combined_tab.py"
    if not Path(file_path).exists():
        print(f"Skipping {file_path} - file not found")
        return

    with open(file_path, "r") as f:
        content = f.read()

    # Fix the import of OptimizedTimelineTab
    content = content.replace(
        "from goesvfi.integrity_check.satellite_integrity_tab_group import (\n    OptimizedResultsTab,\n    OptimizedTimelineTab,\n    SatelliteIntegrityTabGroup,\n)",
        "from goesvfi.integrity_check.satellite_integrity_tab_group import (\n    OptimizedResultsTab,\n    SatelliteIntegrityTabGroup,\n)\nfrom goesvfi.integrity_check.optimized_timeline_tab import OptimizedTimelineTab",
    )

    # Alternative pattern
    content = re.sub(
        r"from goesvfi\.integrity_check\.satellite_integrity_tab_group import[^)]+OptimizedTimelineTab[^)]+\)",
        lambda m: m.group(0)
        .replace("OptimizedTimelineTab,", "")
        .replace(",\n    OptimizedTimelineTab", ""),
        content,
        flags=re.DOTALL,
    )

    with open(file_path, "w") as f:
        f.write(content)
    print(f"Fixed {file_path}")


def fix_no_untyped_def():
    """Add type annotations to functions missing them."""
    files_to_fix = {
        "goesvfi/integrity_check/background_worker.py": [
            (
                "def _on_freeze_detected(self):",
                "def _on_freeze_detected(self) -> None:",
            ),
            (
                "def _on_freeze_resolved(self):",
                "def _on_freeze_resolved(self) -> None:",
            ),
        ],
        "goesvfi/integrity_check/standardized_combined_tab.py": [
            ("def _update_ui_state(self):", "def _update_ui_state(self) -> None:"),
        ],
        "goesvfi/integrity_check/combined_tab.py": [
            (
                "def _create_info_widget(self):",
                "def _create_info_widget(self) -> QWidget:",
            ),
        ],
    }

    for file_path, replacements in files_to_fix.items():
        if not Path(file_path).exists():
            continue

        with open(file_path, "r") as f:
            content = f.read()

        for old, new in replacements:
            content = content.replace(old, new)

        with open(file_path, "w") as f:
            f.write(content)
        print(f"Added type annotations to {file_path}")


def main():
    """Run all fixes."""
    print("Fixing remaining MyPy strict mode errors...\n")

    fix_background_worker_final()
    fix_visual_date_picker_imports()
    fix_time_index_imports()
    fix_reconcile_manager_type_aliases()
    fix_enhanced_gui_tab()
    fix_combined_tab_import()
    fix_no_untyped_def()

    print("\nAll fixes applied!")


if __name__ == "__main__":
    main()
