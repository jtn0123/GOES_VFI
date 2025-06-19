#!/usr/bin/env python3
"""Enhanced script to fix MyPy strict mode errors."""

import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple


def get_mypy_errors() -> List[Tuple[str, int, str, str]]:
    """Run mypy and parse errors with their notes."""
    result = subprocess.run(
        ["mypy", "--strict", "goesvfi/"], capture_output=True, text=True
    )

    errors = []
    lines = result.stdout.splitlines()
    i = 0
    while i < len(lines):
        # Parse mypy output: file.py:line: error: message [error-code]
        match = re.match(r"^(.+?):(\d+): error: (.+?) \[(.+?)\]$", lines[i])
        if match:
            file_path, line_num, message, error_code = match.groups()
            # Check if there's a note on the next line
            note = None
            if i + 1 < len(lines) and ": note:" in lines[i + 1]:
                note = lines[i + 1]
            errors.append((file_path, int(line_num), message, error_code, note))
        i += 1

    return errors


def fix_remaining_tr_errors(file_path: str) -> bool:
    """Fix remaining .tr() errors in gui_helpers.py"""
    if "gui_helpers.py" not in file_path:
        return False

    with open(file_path, "r") as f:
        content = f.read()

    original = content

    # Find all remaining self.tr( patterns and replace them
    # Handle multi-line tr() calls
    content = re.sub(
        r'self\.tr\(\s*\n\s*"([^"]+)"\s*\n\s*\)', r'"\1"', content, flags=re.MULTILINE
    )

    # Handle single-line tr() calls
    content = re.sub(r'self\.tr\("([^"]+)"\)', r'"\1"', content)

    if content != original:
        with open(file_path, "w") as f:
            f.write(content)
        return True

    return False


def fix_type_aliases(file_path: str) -> bool:
    """Fix type alias issues in reconcile_manager_refactored.py"""
    if "reconcile_manager_refactored.py" not in file_path:
        return False

    with open(file_path, "r") as f:
        lines = f.readlines()

    modified = False
    new_lines = []

    for line in lines:
        # Convert variable type aliases to TypeAlias
        if "Callback = Callable" in line and "TypeAlias" not in line:
            # Add TypeAlias import if needed
            if not any("TypeAlias" in l for l in lines[:50]):
                # Find the typing import line and add TypeAlias
                for i, l in enumerate(new_lines):
                    if l.startswith("from typing import") and "TypeAlias" not in l:
                        imports = re.match(r"from typing import (.+)", l.strip())
                        if imports:
                            current = {
                                name.strip() for name in imports.group(1).split(",")
                            }
                            current.add("TypeAlias")
                            sorted_imports = sorted(current)
                            new_lines[i] = (
                                f'from typing import {", ".join(sorted_imports)}\n'
                            )
                        break

            # Convert the type alias
            new_line = line.replace(" = Callable", ": TypeAlias = Callable")
            new_lines.append(new_line)
            modified = True
        else:
            new_lines.append(line)

    if modified:
        with open(file_path, "w") as f:
            f.writelines(new_lines)

    return modified


def fix_union_attr_errors(file_path: str) -> bool:
    """Fix union attribute errors by adding None checks."""
    with open(file_path, "r") as f:
        lines = f.readlines()

    modified = False
    new_lines = []

    for i, line in enumerate(lines):
        # Look for patterns like item.attribute where item might be None
        if "background_worker.py" in file_path:
            # Fix QThreadPool None checks
            if (
                "self._thread_pool." in line
                and "if self._thread_pool" not in lines[max(0, i - 3) : i]
            ):
                indent = len(line) - len(line.lstrip())
                new_lines.append(" " * indent + "if self._thread_pool is not None:\n")
                new_lines.append(" " * (indent + 4) + line.strip() + "\n")
                modified = True
                continue

        new_lines.append(line)

    if modified:
        with open(file_path, "w") as f:
            f.writelines(new_lines)

    return modified


def fix_missing_imports_v2(
    file_path: str, errors: List[Tuple[str, int, str, str, str]]
) -> bool:
    """Enhanced import fixing that handles more cases."""
    missing_imports: Dict[str, Set[str]] = {}

    # Collect missing imports with better detection
    for err_file, line_num, message, error_code, note in errors:
        if err_file != file_path:
            continue

        if error_code == "name-defined" and note:
            # Extract the missing name
            name_match = re.match(r'Name "(.+?)" is not defined', message)
            if name_match:
                missing_name = name_match.group(1)
                # Extract module from note
                import_match = re.search(r"from (\S+) import (\S+)", note)
                if import_match:
                    module = import_match.group(1)
                    if module not in missing_imports:
                        missing_imports[module] = set()
                    missing_imports[module].add(missing_name)

    if not missing_imports:
        return False

    # Read the file
    with open(file_path, "r") as f:
        lines = f.readlines()

    # Find where to insert imports
    import_section_end = 0
    last_import = -1
    for i, line in enumerate(lines):
        if line.startswith(("import ", "from ")):
            last_import = i
        elif line.strip() and not line.startswith(("#", '"""', "'''")):
            if last_import >= 0 and i > last_import + 1:
                import_section_end = last_import + 1
                break

    if import_section_end == 0 and last_import >= 0:
        import_section_end = last_import + 1

    # Add missing imports
    modified = False
    for module, names in missing_imports.items():
        # Check if we already have this import
        existing_line = None
        for i, line in enumerate(lines):
            if line.startswith(f"from {module} import"):
                existing_line = i
                break

        if existing_line is not None:
            # Merge with existing import
            line = lines[existing_line]
            match = re.match(r"from (.+?) import (.+)", line.strip())
            if match:
                current_imports = {name.strip() for name in match.group(2).split(",")}
                new_imports = current_imports | names
                if new_imports != current_imports:
                    sorted_imports = sorted(new_imports)
                    new_line = f'from {module} import {", ".join(sorted_imports)}\n'
                    lines[existing_line] = new_line
                    modified = True
        else:
            # Add new import
            sorted_names = sorted(names)
            new_import = f'from {module} import {", ".join(sorted_names)}\n'
            lines.insert(import_section_end, new_import)
            import_section_end += 1
            modified = True

    if modified:
        with open(file_path, "w") as f:
            f.writelines(lines)

    return modified


def fix_missing_os_import(file_path: str) -> bool:
    """Fix missing os import in enhanced_gui_tab.py"""
    if "enhanced_gui_tab.py" not in file_path:
        return False

    with open(file_path, "r") as f:
        lines = f.readlines()

    # Check if os is imported
    has_os_import = any(
        line.strip() == "import os" or "import os" in line for line in lines[:50]
    )

    if not has_os_import:
        # Find where to insert
        insert_pos = 0
        for i, line in enumerate(lines):
            if line.startswith("import ") or line.startswith("from "):
                insert_pos = i + 1

        lines.insert(insert_pos, "import os\n")

        with open(file_path, "w") as f:
            f.writelines(lines)
        return True

    return False


def fix_qcloseevent_import(file_path: str) -> bool:
    """Fix QCloseEvent import in gui.py"""
    if not file_path.endswith("gui.py"):
        return False

    with open(file_path, "r") as f:
        lines = f.readlines()

    modified = False
    for i, line in enumerate(lines):
        if "from PyQt6.QtCore import" in line and "QCloseEvent" in line:
            # QCloseEvent is in QtGui, not QtCore
            new_line = (
                line.replace("QCloseEvent", "").replace(", ,", ",").replace("( ,", "(")
            )
            lines[i] = new_line

            # Find or add QtGui import
            has_qtgui_import = False
            for j, l in enumerate(lines):
                if "from PyQt6.QtGui import" in l:
                    if "QCloseEvent" not in l:
                        # Add QCloseEvent to existing import
                        match = re.match(r"from PyQt6\.QtGui import (.+)", l.strip())
                        if match:
                            imports = [imp.strip() for imp in match.group(1).split(",")]
                            imports.append("QCloseEvent")
                            lines[j] = (
                                f"from PyQt6.QtGui import {', '.join(sorted(set(imports)))}\n"
                            )
                    has_qtgui_import = True
                    break

            if not has_qtgui_import:
                # Add new QtGui import after QtCore import
                lines.insert(i + 1, "from PyQt6.QtGui import QCloseEvent\n")

            modified = True
            break

    if modified:
        with open(file_path, "w") as f:
            f.writelines(lines)

    return modified


def main():
    """Main function."""
    print("Analyzing MyPy strict mode errors...")
    errors = get_mypy_errors()

    # Group errors by file
    errors_by_file: Dict[str, List[Tuple[str, int, str, str, str]]] = {}
    for error in errors:
        file_path = error[0]
        if file_path not in errors_by_file:
            errors_by_file[file_path] = []
        errors_by_file[file_path].append(error)

    print(f"Found {len(errors)} errors in {len(errors_by_file)} files")

    fixes_made = 0

    # 1. Fix remaining missing imports
    print("\n1. Fixing missing imports...")
    for file_path in sorted(errors_by_file.keys()):
        if fix_missing_imports_v2(file_path, errors_by_file[file_path]):
            print(f"  Fixed imports in: {file_path}")
            fixes_made += 1

    # 2. Fix remaining .tr() errors
    print("\n2. Fixing remaining .tr() errors...")
    for file_path in errors_by_file:
        if fix_remaining_tr_errors(file_path):
            print(f"  Fixed .tr() errors in: {file_path}")
            fixes_made += 1

    # 3. Fix type aliases
    print("\n3. Fixing type aliases...")
    for file_path in errors_by_file:
        if fix_type_aliases(file_path):
            print(f"  Fixed type aliases in: {file_path}")
            fixes_made += 1

    # 4. Fix union attribute errors
    print("\n4. Fixing union attribute errors...")
    for file_path in errors_by_file:
        if fix_union_attr_errors(file_path):
            print(f"  Fixed union attrs in: {file_path}")
            fixes_made += 1

    # 5. Fix specific missing imports
    print("\n5. Fixing specific import issues...")
    for file_path in errors_by_file:
        if fix_missing_os_import(file_path):
            print(f"  Fixed os import in: {file_path}")
            fixes_made += 1
        if fix_qcloseevent_import(file_path):
            print(f"  Fixed QCloseEvent import in: {file_path}")
            fixes_made += 1

    print(f"\nTotal fixes applied: {fixes_made}")

    # Re-run mypy to see remaining errors
    print("\n6. Re-running MyPy to check remaining errors...")
    result = subprocess.run(
        ["mypy", "--strict", "goesvfi/"], capture_output=True, text=True
    )

    remaining_errors = len(
        [line for line in result.stdout.splitlines() if ": error:" in line]
    )
    print(f"\nRemaining errors: {remaining_errors}")

    if remaining_errors > 0:
        print("\nSummary of remaining error types:")
        error_types: Dict[str, int] = {}
        for line in result.stdout.splitlines():
            match = re.match(r"^.+?: error: .+? \[(.+?)\]$", line)
            if match:
                error_type = match.group(1)
                error_types[error_type] = error_types.get(error_type, 0) + 1

        for error_type, count in sorted(error_types.items(), key=lambda x: -x[1]):
            print(f"  {error_type}: {count}")


if __name__ == "__main__":
    main()
