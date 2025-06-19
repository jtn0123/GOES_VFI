#!/usr/bin/env python3
"""Fix indentation errors by adding pass statements where needed."""

import re
import sys
from pathlib import Path
from typing import List, Tuple


def fix_indentation_errors(file_path: Path) -> int:
    """Fix IndentationError by adding pass statements."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return 0

    modified = False
    new_lines = []
    i = 0

    while i < len(lines):
        line = lines[i]
        new_lines.append(line)

        # Check if this line starts a block that needs indentation
        stripped = line.strip()
        if (
            stripped.endswith(":")
            and not stripped.startswith("#")
            and not stripped.startswith(('"""', "'''"))
        ):
            # Check if the next line exists and is properly indented
            if i + 1 < len(lines):
                next_line = lines[i + 1]
                next_stripped = next_line.strip()

                # Calculate expected indentation
                current_indent = len(line) - len(line.lstrip())
                expected_indent = current_indent + 4
                actual_indent = (
                    len(next_line) - len(next_line.lstrip()) if next_line.strip() else 0
                )

                # If next line is not indented properly or is empty, add pass
                if (
                    not next_line.strip()
                    or actual_indent <= current_indent
                    or (next_stripped and actual_indent != expected_indent)
                ):
                    # Add pass statement with proper indentation
                    pass_line = " " * expected_indent + "pass\n"
                    new_lines.append(pass_line)
                    modified = True
                    print(f"Added pass after line {i+1} in {file_path}")
            else:
                # End of file, add pass
                current_indent = len(line) - len(line.lstrip())
                pass_line = " " * (current_indent + 4) + "pass\n"
                new_lines.append(pass_line)
                modified = True
                print(f"Added pass at end of file in {file_path}")

        i += 1

    if modified:
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)
            return 1
        except Exception as e:
            print(f"Error writing {file_path}: {e}")
            return 0

    return 0


def main():
    """Main function to fix indentation errors in Python files."""
    # Get list of files with indentation errors from flake8 output
    files_with_errors = set()

    # Run flake8 to find E999 errors
    import subprocess

    try:
        result = subprocess.run(
            [sys.executable, "-m", "flake8", "--select=E999", "goesvfi", "tests"],
            capture_output=True,
            text=True,
        )

        for line in result.stdout.splitlines():
            if "E999" in line:
                # Extract file path
                match = re.match(r"^([^:]+):\d+:\d+: E999", line)
                if match:
                    files_with_errors.add(Path(match.group(1)))
    except Exception as e:
        print(f"Error running flake8: {e}")
        return 1

    print(f"Found {len(files_with_errors)} files with indentation errors")

    total_fixed = 0
    for file_path in sorted(files_with_errors):
        if file_path.exists():
            print(f"\nProcessing {file_path}...")
            fixed = fix_indentation_errors(file_path)
            total_fixed += fixed

    print(f"\nFixed indentation in {total_fixed} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
