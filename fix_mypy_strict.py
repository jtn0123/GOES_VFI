#!/usr/bin/env python3
"""Script to fix MyPy strict mode errors."""

import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple


def get_mypy_errors() -> List[Tuple[str, int, str, str]]:
    """Run mypy and parse errors."""
    result = subprocess.run(
        ["mypy", "--strict", "goesvfi/"], capture_output=True, text=True
    )

    errors = []
    for line in result.stdout.splitlines():
        # Parse mypy output: file.py:line: error: message [error-code]
        match = re.match(r"^(.+?):(\d+): error: (.+?) \[(.+?)\]$", line)
        if match:
            file_path, line_num, message, error_code = match.groups()
            errors.append((file_path, int(line_num), message, error_code))
            # Also check for note lines that follow
            note_match = re.match(r"^(.+?):(\d+): note: (.+)", line)
            if note_match and "Did you forget to import" in note_match.group(3):
                # The note is associated with the previous error
                pass

    return errors


def extract_import_suggestion(errors: List[Tuple[str, int, str, str]], idx: int) -> str:
    """Extract import suggestion from error notes."""
    # Look ahead for a note with import suggestion
    if idx + 1 < len(errors):
        _, _, next_msg, _ = errors[idx + 1]
        if "Did you forget to import" in next_msg:
            import_match = re.search(r"from (\S+) import (\S+)", next_msg)
            if import_match:
                return f"from {import_match.group(1)} import {import_match.group(2)}"
    return ""


def fix_missing_imports(
    file_path: str, errors: List[Tuple[str, int, str, str]]
) -> bool:
    """Fix missing imports in a file."""
    # Collect all missing imports for this file
    missing_imports: Dict[str, Set[str]] = {}

    # First pass: collect from error messages with suggestions
    full_errors = []
    result = subprocess.run(
        ["mypy", "--strict", file_path], capture_output=True, text=True
    )

    lines = result.stdout.splitlines()
    i = 0
    while i < len(lines):
        if ": error:" in lines[i] and "[name-defined]" in lines[i]:
            error_match = re.match(
                r'^.+?:(\d+): error: Name "(.+?)" is not defined', lines[i]
            )
            if error_match:
                missing_name = error_match.group(2)
                # Check next line for suggestion
                if i + 1 < len(lines) and ": note:" in lines[i + 1]:
                    import_match = re.search(r"from (\S+) import (\S+)", lines[i + 1])
                    if import_match:
                        module = import_match.group(1)
                        if module not in missing_imports:
                            missing_imports[module] = set()
                        missing_imports[module].add(missing_name)
        i += 1

    if not missing_imports:
        return False

    # Read the file
    with open(file_path, "r") as f:
        lines = f.readlines()

    # Find the import section
    import_section_end = 0
    last_import = 0
    for i, line in enumerate(lines):
        if line.startswith(("import ", "from ")):
            last_import = i
        elif line.strip() and not line.startswith(("#", '"""', "'''")):
            if i > last_import + 1:  # Found non-import line after imports
                import_section_end = last_import + 1
                break

    if import_section_end == 0:
        import_section_end = last_import + 1

    # Check existing imports and add missing ones
    modified = False
    for module, names in missing_imports.items():
        # Check if we already have an import from this module
        existing_import_line = None
        for i, line in enumerate(lines[: import_section_end + 5]):  # Check a bit beyond
            if line.startswith(f"from {module} import"):
                existing_import_line = i
                break

        if existing_import_line is not None:
            # Add to existing import
            line = lines[existing_import_line]
            # Extract current imports
            match = re.match(r"from (.+?) import (.+)", line.strip())
            if match:
                current_imports = {name.strip() for name in match.group(2).split(",")}
                new_imports = current_imports | names
                if new_imports != current_imports:
                    sorted_imports = sorted(new_imports)
                    new_line = f'from {module} import {", ".join(sorted_imports)}\n'
                    lines[existing_import_line] = new_line
                    modified = True
        else:
            # Add new import line
            sorted_names = sorted(names)
            new_import = f'from {module} import {", ".join(sorted_names)}\n'
            # Insert after other imports
            lines.insert(import_section_end, new_import)
            modified = True

    if modified:
        with open(file_path, "w") as f:
            f.writelines(lines)

    return modified


def fix_tr_method_errors(
    file_path: str, errors: List[Tuple[str, int, str, str]]
) -> bool:
    """Fix .tr() method errors for non-Qt classes."""
    if "gui_helpers.py" not in file_path:
        return False

    tr_errors = []
    for err_file, line_num, message, error_code in errors:
        if (
            err_file == file_path
            and error_code == "attr-defined"
            and 'has no attribute "tr"' in message
        ):
            tr_errors.append(line_num)

    if not tr_errors:
        return False

    with open(file_path, "r") as f:
        lines = f.readlines()

    # Replace self.tr() with direct strings in RifeCapabilityManager
    modified = False
    for line_num in tr_errors:
        if line_num - 1 < len(lines):
            line = lines[line_num - 1]
            # Replace self.tr("...") with just "..."
            new_line = re.sub(r'self\.tr\([\s\n]*"([^"]+)"[\s\n]*\)', r'"\1"', line)
            if new_line != line:
                lines[line_num - 1] = new_line
                modified = True

    if modified:
        with open(file_path, "w") as f:
            f.writelines(lines)

    return modified


def main():
    """Main function."""
    print("Analyzing MyPy strict mode errors...")
    errors = get_mypy_errors()

    # Group errors by file
    errors_by_file: Dict[str, List[Tuple[str, int, str, str]]] = {}
    for error in errors:
        file_path = error[0]
        if file_path not in errors_by_file:
            errors_by_file[file_path] = []
        errors_by_file[file_path].append(error)

    print(f"Found {len(errors)} errors in {len(errors_by_file)} files")

    # Fix missing imports first
    print("\n1. Fixing missing imports...")
    import_fixes = 0

    # Process files with name-defined errors
    for file_path in sorted(errors_by_file.keys()):
        file_errors = errors_by_file[file_path]
        has_name_errors = any(err[3] == "name-defined" for err in file_errors)
        if has_name_errors and fix_missing_imports(file_path, file_errors):
            print(f"  Fixed imports in: {file_path}")
            import_fixes += 1

    print(f"  Fixed imports in {import_fixes} files")

    # Fix .tr() method errors
    print("\n2. Fixing .tr() method errors...")
    tr_fixes = 0
    for file_path in errors_by_file:
        if fix_tr_method_errors(file_path, errors_by_file[file_path]):
            print(f"  Fixed .tr() errors in: {file_path}")
            tr_fixes += 1

    print(f"  Fixed .tr() errors in {tr_fixes} files")

    # Re-run mypy to see remaining errors
    print("\n3. Re-running MyPy to check remaining errors...")
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

        # Show sample errors for the most common type
        print(f"\nSample errors for most common type:")
        sample_count = 0
        for line in result.stdout.splitlines():
            if ": error:" in line and f"[{list(error_types.keys())[0]}]" in line:
                print(f"  {line}")
                sample_count += 1
                if sample_count >= 5:
                    break


if __name__ == "__main__":
    main()
