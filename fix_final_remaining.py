#!/usr/bin/env python3
"""Fix final remaining MyPy errors."""

import re
from pathlib import Path


def fix_time_index_refactored_again():
    """Fix time_index_refactored.py imports and type annotations."""
    file_path = "goesvfi/integrity_check/time_index_refactored.py"
    with open(file_path, "r") as f:
        content = f.read()

    # Ensure typing imports are at the top
    lines = content.splitlines()

    # Find where imports should go (after docstring)
    import_index = 0
    in_docstring = False
    for i, line in enumerate(lines):
        if line.strip().startswith('"""'):
            if not in_docstring:
                in_docstring = True
            else:
                import_index = i + 1
                break

    # Check if typing imports exist
    has_typing = False
    typing_line_index = -1
    for i, line in enumerate(lines):
        if line.startswith("from typing import"):
            has_typing = True
            typing_line_index = i
            break

    if not has_typing:
        # Add typing imports
        lines.insert(import_index, "")
        lines.insert(
            import_index + 1, "from typing import Dict, List, Optional, Pattern, Tuple"
        )
        lines.insert(import_index + 2, "import re")
    else:
        # Update existing typing imports
        current_line = lines[typing_line_index]
        if "Pattern" not in current_line:
            imports = re.findall(r"from typing import (.+)", current_line)[0]
            current_imports = {imp.strip() for imp in imports.split(",")}
            current_imports.update({"Dict", "List", "Optional", "Pattern", "Tuple"})
            lines[
                typing_line_index
            ] = f"from typing import {', '.join(sorted(current_imports))}"

    # Fix COMPILED_PATTERNS type annotation
    content = "\n".join(lines)
    content = re.sub(
        r"COMPILED_PATTERNS: Dict\[str, re\.Pattern\[str\]\] = {}",
        "COMPILED_PATTERNS: Dict[str, Pattern[str]] = {}",
        content,
    )

    with open(file_path, "w") as f:
        f.write(content)
    print(f"Fixed {file_path}")


def fix_visual_date_picker_types():
    """Fix type parameters in visual_date_picker.py"""
    file_path = "goesvfi/integrity_check/visual_date_picker.py"
    with open(file_path, "r") as f:
        content = f.read()

    # Fix Callable type parameter
    content = re.sub(r"on_complete: Callable\[", "on_complete: Callable[[],", content)

    # Fix return type for _generate_sample_data
    content = re.sub(
        r"def _generate_sample_data\(self\) -> list:",
        "def _generate_sample_data(self) -> List[datetime]:",
        content,
    )

    # Ensure List is imported
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("from typing import"):
            if "List" not in line:
                imports = re.findall(r"from typing import (.+)", line)[0]
                current_imports = {imp.strip() for imp in imports.split(",")}
                current_imports.add("List")
                lines[i] = f"from typing import {', '.join(sorted(current_imports))}"
                content = "\n".join(lines)
            break

    with open(file_path, "w") as f:
        f.write(content)
    print(f"Fixed {file_path}")


def fix_user_feedback_final():
    """Fix final issues in user_feedback.py"""
    file_path = "goesvfi/integrity_check/user_feedback.py"
    with open(file_path, "r") as f:
        content = f.read()

    # Fix win10toast import with proper type ignore
    content = re.sub(
        r"from win10toast import ToastNotifier  # type: ignore\[import-not-found\]",
        "from win10toast import ToastNotifier  # type: ignore[import-not-found]",
        content,
    )

    # Fix clipboard None checks - need to fix the actual usage
    lines = content.splitlines()
    new_lines = []

    for i, line in enumerate(lines):
        # Fix clipboard.setText calls
        if "clipboard = QApplication.clipboard()" in line:
            new_lines.append(line)
            # Look ahead for setText call
            if i + 1 < len(lines) and "clipboard.setText" in lines[i + 1]:
                indent = len(lines[i + 1]) - len(lines[i + 1].lstrip())
                new_lines.append(" " * indent + "if clipboard is not None:")
                new_lines.append(" " * (indent + 4) + lines[i + 1].strip())
                continue
        elif "QApplication.clipboard().setText" in line:
            indent = len(line) - len(line.lstrip())
            new_lines.append(" " * indent + "clipboard = QApplication.clipboard()")
            new_lines.append(" " * indent + "if clipboard is not None:")
            new_lines.append(
                " " * (indent + 4)
                + line.strip().replace("QApplication.clipboard().", "clipboard.")
            )
        elif "scrollbar.setValue(scrollbar.maximum())" in line:
            indent = len(line) - len(line.lstrip())
            new_lines.append(" " * indent + "if scrollbar is not None:")
            new_lines.append(" " * (indent + 4) + line.strip())
        elif line.strip() == "if clipboard is not None:":
            # Skip duplicate if statements
            continue
        elif "clipboard.setText" in line and "if clipboard" not in lines[i - 1]:
            # Ensure we have the if check
            indent = len(line) - len(line.lstrip())
            if indent > 0:  # Already indented, probably inside the if
                new_lines.append(line)
            else:
                new_lines.append(" " * indent + "if clipboard is not None:")
                new_lines.append(" " * 4 + line)
        else:
            new_lines.append(line)

    # Fix QListWidgetItem None check
    content = "\n".join(new_lines)
    content = re.sub(
        r"texts\.append\(item\.text\(\)\)",
        "if item is not None:\n                texts.append(item.text())",
        content,
    )

    with open(file_path, "w") as f:
        f.write(content)
    print(f"Fixed {file_path}")


def fix_ffmpeg_settings_final():
    """Fix final issues in ffmpeg_settings_tab.py"""
    file_path = "goesvfi/gui_tabs/ffmpeg_settings_tab.py"
    with open(file_path, "r") as f:
        content = f.read()

    # The issue is already fixed in our previous run
    # Just ensure Optional is used correctly
    if "current_settings: Optional[dict[str, Any]] = None" not in content:
        content = re.sub(
            r"current_settings: dict\[str, Any\] = None",
            "current_settings: Optional[dict[str, Any]] = None",
            content,
        )

    with open(file_path, "w") as f:
        f.write(content)
    print(f"Fixed {file_path}")


def fix_reconcile_manager_issues():
    """Fix remaining issues in reconcile_manager_refactored.py"""
    file_path = "goesvfi/integrity_check/reconcile_manager_refactored.py"
    with open(file_path, "r") as f:
        content = f.read()

    # Fix semaphore Optional issue
    content = re.sub(
        r"semaphore: Semaphore = None", "semaphore: Optional[Semaphore] = None", content
    )

    # Ensure Semaphore is imported
    if (
        "from asyncio import Semaphore" not in content
        and "asyncio.Semaphore" in content
    ):
        content = re.sub(
            r"import asyncio", "import asyncio\nfrom asyncio import Semaphore", content
        )

    with open(file_path, "w") as f:
        f.write(content)
    print(f"Fixed {file_path}")


def main():
    """Run all fixes."""
    print("Fixing final remaining MyPy errors...\n")

    fix_time_index_refactored_again()
    fix_visual_date_picker_types()
    fix_user_feedback_final()
    fix_ffmpeg_settings_final()
    fix_reconcile_manager_issues()

    print("\nAll fixes applied!")


if __name__ == "__main__":
    main()
