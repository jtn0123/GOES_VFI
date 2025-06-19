# \!/usr/bin/env python3
"""Fix all remaining docstring import issues."""

import os
import re
from pathlib import Path


def fix_docstring_imports(file_path):
    """Fix imports that are incorrectly placed inside docstrings."""
    try:
        with open(file_path, "r") as f:
            content = f.read()

        # Pattern to find imports inside docstrings
        # Look for docstring at start of file with imports inside
        pattern = r'^("""[^"]*?)\n(from typing import[^\n]+)\n([^"]*?""")'

        # Check if this pattern exists
        if re.match(pattern, content, re.MULTILINE | re.DOTALL):
            # Extract the parts
            match = re.match(pattern, content, re.MULTILINE | re.DOTALL)
            if match:
                docstring_start = match.group(1)
                import_line = match.group(2)
                docstring_end = match.group(3)

                # Reconstruct with import outside docstring
                fixed_content = f"{docstring_start}\n{docstring_end}\n\n{import_line}\n"

                # Get the rest of the content
                rest_of_content = content[match.end() :]
                fixed_content += rest_of_content

                with open(file_path, "w") as f:
                    f.write(fixed_content)

                return True

        # Alternative pattern: multiline docstring with import on second line
        lines = content.splitlines()
        if len(lines) > 3 and lines[0] == '"""' and "from typing import" in lines[1]:
            # Find the closing """
            import_line = lines[1]
            new_lines = [lines[0]]  # Keep opening """

            # Skip the import line and reconstruct docstring
            i = 2
            while i < len(lines) and '"""' not in lines[i]:
                new_lines.append(lines[i])
                i += 1

            if i < len(lines):
                # Found closing """
                new_lines.append(lines[i])
                new_lines.append("")  # Empty line
                new_lines.append(import_line)  # Add import after docstring

                # Add rest of file
                new_lines.extend(lines[i + 1 :])

                with open(file_path, "w") as f:
                    f.write("\n".join(new_lines))

                return True

    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False

    return False


def main():
    """Fix all Python files with docstring import issues."""
    print("Scanning for files with imports inside docstrings...\n")

    fixed_files = []

    # Files identified with import issues
    problem_files = [
        "goesvfi/integrity_check/results_organization.py",
        "goesvfi/integrity_check/remote/base.py",
        "goesvfi/gui_backup.py",
        "goesvfi/integrity_check/remote/cdn_store.py",
        "goesvfi/integrity_check/optimized_timeline_tab.py",
        "goesvfi/integrity_check/goes_imagery_tab.py",
        "goesvfi/integrity_check/cache_db.py",
    ]

    # Also scan all Python files in the directory
    goesvfi_path = Path("goesvfi")
    if goesvfi_path.exists():
        for py_file in goesvfi_path.rglob("*.py"):
            if str(py_file) not in problem_files:
                problem_files.append(str(py_file))

    for file_path in problem_files:
        if os.path.exists(file_path):
            if fix_docstring_imports(file_path):
                fixed_files.append(file_path)
                print(f"Fixed: {file_path}")

    print(f"\nFixed {len(fixed_files)} files with docstring import issues")


if __name__ == "__main__":
    main()
