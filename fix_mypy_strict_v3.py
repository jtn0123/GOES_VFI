#!/usr/bin/env python3
"""Final script to fix remaining MyPy strict mode errors."""

import re
import subprocess
from pathlib import Path
from typing import Dict, List, Set, Tuple


def fix_specific_missing_imports():
    """Fix specific missing imports in known files."""
    fixes = 0

    # Fix visual_date_picker.py
    file_path = "goesvfi/integrity_check/visual_date_picker.py"
    try:
        with open(file_path, "r") as f:
            content = f.read()

        # Check if imports are missing
        if (
            "from typing import" in content
            and "Optional" not in content.split("\n")[0:20]
        ):
            lines = content.splitlines()
            for i, line in enumerate(lines):
                if line.startswith("from typing import"):
                    imports = re.findall(r"from typing import (.+)", line)[0]
                    current = {imp.strip() for imp in imports.split(",")}
                    current.update({"Optional", "Callable"})
                    lines[i] = f"from typing import {', '.join(sorted(current))}"
                    break

            with open(file_path, "w") as f:
                f.write("\n".join(lines) + "\n")
            print(f"Fixed imports in {file_path}")
            fixes += 1
    except Exception as e:
        print(f"Error fixing {file_path}: {e}")

    # Fix user_feedback.py
    file_path = "goesvfi/integrity_check/user_feedback.py"
    try:
        with open(file_path, "r") as f:
            content = f.read()

        lines = content.splitlines()
        for i, line in enumerate(lines):
            if line.startswith("from typing import"):
                imports = re.findall(r"from typing import (.+)", line)[0]
                current = {imp.strip() for imp in imports.split(",")}
                current.update({"Optional", "List", "Tuple"})
                lines[i] = f"from typing import {', '.join(sorted(current))}"
                break

        with open(file_path, "w") as f:
            f.write("\n".join(lines) + "\n")
        print(f"Fixed imports in {file_path}")
        fixes += 1
    except Exception as e:
        print(f"Error fixing {file_path}: {e}")

    # Fix standardized_combined_tab.py and combined_tab_refactored.py
    for file_name in ["standardized_combined_tab.py", "combined_tab_refactored.py"]:
        file_path = f"goesvfi/integrity_check/{file_name}"
        try:
            with open(file_path, "r") as f:
                content = f.read()

            lines = content.splitlines()
            for i, line in enumerate(lines):
                if line.startswith("from typing import"):
                    imports = re.findall(r"from typing import (.+)", line)[0]
                    current = {imp.strip() for imp in imports.split(",")}
                    if file_name == "standardized_combined_tab.py":
                        current.add("Optional")
                    else:
                        current.update({"Optional", "List"})
                    lines[i] = f"from typing import {', '.join(sorted(current))}"
                    break

            with open(file_path, "w") as f:
                f.write("\n".join(lines) + "\n")
            print(f"Fixed imports in {file_path}")
            fixes += 1
        except Exception as e:
            print(f"Error fixing {file_path}: {e}")

    return fixes


def fix_union_attr_errors():
    """Fix union attribute errors by adding None checks."""
    fixes = 0

    # Fix background_worker.py
    file_path = "goesvfi/integrity_check/background_worker.py"
    try:
        with open(file_path, "r") as f:
            lines = f.readlines()

        new_lines = []
        i = 0
        while i < len(lines):
            line = lines[i]

            # Fix QThreadPool None checks
            if (
                "self._thread_pool." in line
                and "self._thread_pool is not None" not in line
            ):
                # Check if we're not already in an if block
                prev_line = lines[i - 1] if i > 0 else ""
                if "if " not in prev_line:
                    indent = len(line) - len(line.lstrip())
                    new_lines.append(
                        " " * indent + "if self._thread_pool is not None:\n"
                    )
                    new_lines.append(" " * (indent + 4) + line.strip() + "\n")
                    i += 1
                    continue

            new_lines.append(line)
            i += 1

        with open(file_path, "w") as f:
            f.writelines(new_lines)
        print(f"Fixed union attrs in {file_path}")
        fixes += 1
    except Exception as e:
        print(f"Error fixing {file_path}: {e}")

    # Fix user_feedback.py QListWidgetItem None check
    file_path = "goesvfi/integrity_check/user_feedback.py"
    try:
        with open(file_path, "r") as f:
            lines = f.readlines()

        new_lines = []
        for i, line in enumerate(lines):
            if (
                "item.setForeground" in line
                and "if item" not in lines[max(0, i - 3) : i]
            ):
                indent = len(line) - len(line.lstrip())
                new_lines.append(" " * indent + "if item is not None:\n")
                new_lines.append(" " * (indent + 4) + line.strip() + "\n")
            else:
                new_lines.append(line)

        with open(file_path, "w") as f:
            f.writelines(new_lines)
        print(f"Fixed union attrs in {file_path}")
        fixes += 1
    except Exception as e:
        print(f"Error fixing {file_path}: {e}")

    return fixes


def fix_type_annotations():
    """Add missing type annotations to functions."""
    fixes = 0

    # Fix background_worker.py type annotations
    file_path = "goesvfi/integrity_check/background_worker.py"
    try:
        with open(file_path, "r") as f:
            content = f.read()

        # Fix missing type parameters for Task and TaskResult
        content = re.sub(r"\bTask\b(?!\[)", "Task[Any]", content)
        content = re.sub(r"\bTaskResult\b(?!\[)", "TaskResult[Any]", content)

        # Add Any import if needed
        if "Task[Any]" in content or "TaskResult[Any]" in content:
            lines = content.splitlines()
            for i, line in enumerate(lines):
                if line.startswith("from typing import"):
                    if "Any" not in line:
                        imports = re.findall(r"from typing import (.+)", line)[0]
                        current = {imp.strip() for imp in imports.split(",")}
                        current.add("Any")
                        lines[i] = f"from typing import {', '.join(sorted(current))}"
                        content = "\n".join(lines) + "\n"
                    break

        with open(file_path, "w") as f:
            f.write(content)
        print(f"Fixed type annotations in {file_path}")
        fixes += 1
    except Exception as e:
        print(f"Error fixing {file_path}: {e}")

    return fixes


def fix_win10toast_import():
    """Fix win10toast import issue."""
    file_path = "goesvfi/integrity_check/user_feedback.py"
    try:
        with open(file_path, "r") as f:
            lines = f.readlines()

        new_lines = []
        for line in lines:
            # Wrap win10toast import in try/except
            if (
                "from win10toast import" in line
                and "try:" not in lines[max(0, lines.index(line) - 1)]
            ):
                indent = len(line) - len(line.lstrip())
                new_lines.append(" " * indent + "try:\n")
                new_lines.append(" " * (indent + 4) + line.strip() + "\n")
                new_lines.append(" " * indent + "except ImportError:\n")
                new_lines.append(
                    " " * (indent + 4) + "ToastNotifier = None  # type: ignore\n"
                )
            else:
                new_lines.append(line)

        with open(file_path, "w") as f:
            f.writelines(new_lines)
        print(f"Fixed win10toast import in {file_path}")
        return 1
    except Exception as e:
        print(f"Error fixing {file_path}: {e}")
        return 0


def fix_winsound_attrs():
    """Fix winsound attribute errors."""
    file_path = "goesvfi/integrity_check/user_feedback.py"
    try:
        with open(file_path, "r") as f:
            content = f.read()

        # Replace winsound.MessageBeep with proper attribute check
        content = re.sub(
            r"winsound\.MessageBeep\(winsound\.(MB_\w+)\)",
            r'winsound.MessageBeep(getattr(winsound, "\1", 0))',
            content,
        )

        with open(file_path, "w") as f:
            f.write(content)
        print(f"Fixed winsound attrs in {file_path}")
        return 1
    except Exception as e:
        print(f"Error fixing {file_path}: {e}")
        return 0


def main():
    """Main function."""
    print("Fixing remaining MyPy strict mode errors...\n")

    total_fixes = 0

    # 1. Fix specific missing imports
    print("1. Fixing missing imports...")
    total_fixes += fix_specific_missing_imports()

    # 2. Fix union attribute errors
    print("\n2. Fixing union attribute errors...")
    total_fixes += fix_union_attr_errors()

    # 3. Fix type annotations
    print("\n3. Fixing type annotations...")
    total_fixes += fix_type_annotations()

    # 4. Fix win10toast import
    print("\n4. Fixing win10toast import...")
    total_fixes += fix_win10toast_import()

    # 5. Fix winsound attributes
    print("\n5. Fixing winsound attributes...")
    total_fixes += fix_winsound_attrs()

    print(f"\nTotal fixes applied: {total_fixes}")

    # Re-run mypy to see remaining errors
    print("\n6. Re-running MyPy to check remaining errors...")
    result = subprocess.run(
        ["mypy", "--strict", "goesvfi/"], capture_output=True, text=True
    )

    error_lines = [line for line in result.stdout.splitlines() if ": error:" in line]
    remaining_errors = len(error_lines)
    print(f"\nRemaining errors: {remaining_errors}")

    if remaining_errors > 0:
        print("\nSummary of remaining error types:")
        error_types: Dict[str, int] = {}
        for line in error_lines:
            match = re.match(r"^.+?: error: .+? \[(.+?)\]$", line)
            if match:
                error_type = match.group(1)
                error_types[error_type] = error_types.get(error_type, 0) + 1

        for error_type, count in sorted(error_types.items(), key=lambda x: -x[1]):
            print(f"  {error_type}: {count}")

        # Show first few errors
        print("\nFirst 10 remaining errors:")
        for line in error_lines[:10]:
            print(f"  {line}")


if __name__ == "__main__":
    main()
