#!/usr/bin/env python3
"""
More comprehensive unused import removal script.
"""

import ast
import subprocess
import sys
from pathlib import Path
from typing import List, Set


def run_flake8() -> List[str]:
    """Run flake8 and return unused import lines."""
    try:
        result = subprocess.run(
            [sys.executable, "run_linters.py", "--flake8-only"],
            capture_output=True,
            text=True,
            cwd=".",
        )
        # Extract just F401 unused import lines
        lines = []
        for line in result.stdout.split("\n"):
            line = line.strip()
            if (
                line.startswith("/")
                and "F401" in line
                and "imported but unused" in line
            ):
                lines.append(line)
        return lines
    except Exception as e:
        print(f"Error running flake8: {e}")
        return []


def extract_unused_imports_from_line(line: str) -> tuple[str, str]:
    """Extract file path and import name from flake8 F401 line."""
    # Format: /path/file.py:line:col: F401 'import.name' imported but unused
    parts = line.split(": F401 ")
    if len(parts) != 2:
        return "", ""

    file_path = parts[0].split(":")[0]
    import_part = parts[1]

    # Extract the import name from the quotes
    if "'" in import_part:
        import_name = import_part.split("'")[1]
        return file_path, import_name

    return "", ""


def remove_unused_import_from_file(file_path: Path, unused_import: str) -> bool:
    """Remove a specific unused import from a file."""
    if not file_path.exists():
        return False

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        new_lines = []
        removed = False

        for line in lines:
            # Check different import patterns
            should_remove = False

            # Pattern 1: import module
            if line.strip() == f"import {unused_import}":
                should_remove = True

            # Pattern 2: from module import name
            elif line.strip().startswith("from ") and f" {unused_import}" in line:
                # Check if it's importing this specific item
                if line.strip().endswith(f" {unused_import}"):
                    should_remove = True
                # Check if it's part of a multi-import line
                elif f", {unused_import}" in line or f"{unused_import}," in line:
                    # Remove just this import from the line
                    if f", {unused_import}" in line:
                        line = line.replace(f", {unused_import}", "")
                    elif f"{unused_import}," in line:
                        line = line.replace(f"{unused_import}, ", "")
                    # Don't remove the whole line, just modify it

            # Pattern 3: import module.submodule as alias
            elif line.strip() == f"import {unused_import}":
                should_remove = True

            # Pattern 4: Handle typing imports specially
            elif "typing." in unused_import and line.strip().startswith(
                "from typing import"
            ):
                base_name = unused_import.split(".")[-1]
                if f" {base_name}" in line:
                    if line.strip().endswith(f" {base_name}"):
                        should_remove = True
                    elif f", {base_name}" in line:
                        line = line.replace(f", {base_name}", "")
                    elif f"{base_name}," in line:
                        line = line.replace(f"{base_name}, ", "")

            if not should_remove:
                new_lines.append(line)
            else:
                removed = True
                print(f"  Removed: {unused_import}")

        if removed:
            with open(file_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)

        return removed
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False


def main():
    """Main function."""
    print("Fixing remaining unused imports...")

    issues = run_flake8()
    if not issues:
        print("No unused import issues found.")
        return

    print(f"Found {len(issues)} unused import issues")

    # Group by file
    file_imports = {}
    for issue in issues:
        file_path, import_name = extract_unused_imports_from_line(issue)
        if file_path and import_name:
            path_obj = Path(file_path)
            if path_obj not in file_imports:
                file_imports[path_obj] = []
            file_imports[path_obj].append(import_name)

    total_fixed = 0
    for file_path, imports in file_imports.items():
        print(f"\nProcessing {file_path}...")
        for import_name in imports:
            if remove_unused_import_from_file(file_path, import_name):
                total_fixed += 1

    print(f"\nFixed {total_fixed} unused imports")

    # Check remaining
    remaining = run_flake8()
    print(f"Remaining unused import issues: {len(remaining)}")


if __name__ == "__main__":
    main()
