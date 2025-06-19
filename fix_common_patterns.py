#!/usr/bin/env python3
"""Fix common syntax error patterns across many files."""

import ast
import re
import shutil
from pathlib import Path
from typing import List, Tuple


def get_files_with_errors() -> List[Path]:
    """Find all Python files with syntax errors."""
    files_with_errors = []

    for root, dirs, files in os.walk("."):
        # Skip hidden directories and venv
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != ".venv"]

        for file in files:
            if file.endswith(".py"):
                filepath = Path(root) / file
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        content = f.read()
                    ast.parse(content)
                except SyntaxError:
                    files_with_errors.append(filepath)
                except:
                    pass

    return files_with_errors


def fix_common_patterns(content: str) -> Tuple[str, List[str]]:
    """Fix common syntax error patterns. Returns fixed content and list of fixes applied."""
    fixes_applied = []
    original = content

    # Pattern 1: Orphaned closing parentheses
    lines = content.split("\n")
    fixed_lines = []
    for i, line in enumerate(lines):
        if line.strip() == ")" and i > 0:
            prev_line = fixed_lines[-1] if fixed_lines else ""
            # Check if previous line has unclosed parenthesis
            if prev_line.count("(") > prev_line.count(")"):
                # Append to previous line
                fixed_lines[-1] = prev_line.rstrip() + ")"
                continue
        fixed_lines.append(line)

    if "\n".join(fixed_lines) != content:
        content = "\n".join(fixed_lines)
        fixes_applied.append("Fixed orphaned closing parentheses")

    # Pattern 2: Fix split function calls - func()\n"string"
    content = re.sub(r'(\w+)\(\)\s*\n\s*(["\'])', r"\1(\2", content)
    if content != original:
        fixes_applied.append("Fixed split function calls")

    # Pattern 3: Fix logger format strings - "format", var:,)
    content = re.sub(r"(\w+):,\)", r"\1)", content)
    if content != original:
        fixes_applied.append("Fixed logger format syntax")

    # Pattern 4: Fix unterminated strings
    lines = content.split("\n")
    fixed_lines = []
    for line in lines:
        # Check for unterminated f-strings
        if 'f"' in line and line.count('"') % 2 == 1:
            # Check if it ends with "'
            if line.rstrip().endswith("'"):
                line = line.rstrip()[:-1]
        fixed_lines.append(line)

    if "\n".join(fixed_lines) != content:
        content = "\n".join(fixed_lines)
        fixes_applied.append("Fixed unterminated strings")

    # Pattern 5: Fix missing colons in lambda
    content = re.sub(
        r"lambda\s+(\w+)\s*,\s*$", r"lambda \1:", content, flags=re.MULTILINE
    )
    if content != original:
        fixes_applied.append("Fixed lambda syntax")

    # Pattern 6: Fix malformed import statements
    content = re.sub(r"from\s+([\w\.]+)\s+import\s*\(\s*\)", "", content)
    if content != original:
        fixes_applied.append("Removed empty imports")

    # Pattern 7: Fix docstring/code mixing
    lines = content.split("\n")
    fixed_lines = []
    in_docstring = False
    for i, line in enumerate(lines):
        if '"""' in line:
            count = line.count('"""')
            if count == 1:
                in_docstring = not in_docstring

        # If we see imports while in docstring, close the docstring
        if in_docstring and (
            line.strip().startswith("from ") or line.strip().startswith("import ")
        ):
            # Insert closing quotes before this line
            if i > 0:
                fixed_lines[-1] = fixed_lines[-1] + '"""'
            in_docstring = False
            fixed_lines.append("")  # Add blank line
            fixes_applied.append("Fixed docstring/import mixing")

        fixed_lines.append(line)

    content = "\n".join(fixed_lines)

    return content, fixes_applied


def process_file(filepath: Path) -> bool:
    """Process a single file and return True if fixed."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            original_content = f.read()

        # Apply fixes
        fixed_content, fixes = fix_common_patterns(original_content)

        if fixed_content != original_content:
            # Backup
            backup_path = str(filepath) + ".pattern_backup"
            shutil.copy2(filepath, backup_path)

            # Write fixed content
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(fixed_content)

            # Verify it's valid Python
            try:
                ast.parse(fixed_content)
                print(f"✓ Fixed {filepath}: {', '.join(fixes)}")
                Path(backup_path).unlink()
                return True
            except SyntaxError as e:
                # Restore backup
                shutil.move(backup_path, filepath)
                print(
                    f"✗ Failed to fix {filepath}: Still has syntax error on line {e.lineno}"
                )
                return False

        return False

    except Exception as e:
        print(f"✗ Error processing {filepath}: {e}")
        return False


def main():
    """Fix common patterns in all files with syntax errors."""
    import os

    print("Finding files with syntax errors...")
    error_files = get_files_with_errors()
    print(f"Found {len(error_files)} files with syntax errors")

    if not error_files:
        print("No files with syntax errors found!")
        return

    fixed_count = 0

    print("\nApplying common pattern fixes...")
    for filepath in error_files:
        if process_file(filepath):
            fixed_count += 1

    print(f"\nFixed {fixed_count} out of {len(error_files)} files")

    # Check remaining errors
    remaining_errors = get_files_with_errors()
    print(f"Remaining files with syntax errors: {len(remaining_errors)}")


if __name__ == "__main__":
    import os

    main()
