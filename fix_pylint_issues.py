#!/usr/bin/env python3
"""
Script to automatically fix common Pylint issues.
"""

import os
import re
import sys
from pathlib import Path
from typing import List, Tuple


def fix_trailing_whitespace(content: str) -> str:
    """Remove trailing whitespace from lines."""
    lines = content.split("\n")
    fixed_lines = [line.rstrip() for line in lines]
    return "\n".join(fixed_lines)


def fix_logging_fstring(content: str) -> str:
    """Convert f-string logging to % formatting."""
    # Pattern to match logger.xxx(f"...") or LOGGER.xxx(f"...")
    pattern = r'((?:logger|LOGGER)\.\w+)\(f["\']([^"\']+)["\']\)'

    def replace_fstring(match):
        method = match.group(1)
        fstring_content = match.group(2)

        # Find all {var} patterns
        var_pattern = r"\{([^}]+)\}"
        variables = re.findall(var_pattern, fstring_content)

        if not variables:
            # No variables, just remove the f
            return f'{method}("{fstring_content}")'

        # Replace {var} with %s
        format_string = re.sub(var_pattern, "%s", fstring_content)

        # Build the variable list
        var_list = ", ".join(variables)

        return f'{method}("{format_string}", {var_list})'

    return re.sub(pattern, replace_fstring, content)


def fix_long_lines(content: str, max_length: int = 100) -> str:
    """Fix lines that are too long by breaking them appropriately."""
    lines = content.split("\n")
    fixed_lines = []

    for line in lines:
        if len(line) <= max_length:
            fixed_lines.append(line)
            continue

        # Skip lines that are just long strings or comments
        stripped = line.strip()
        if (
            stripped.startswith("#")
            or stripped.startswith('"""')
            or stripped.startswith("'''")
        ):
            fixed_lines.append(line)
            continue

        # Try to break at logical points
        indent = len(line) - len(line.lstrip())
        indent_str = " " * indent

        # For long function calls, break at commas
        if "(" in line and ")" in line and "," in line:
            # Find the opening parenthesis
            paren_pos = line.find("(")
            if paren_pos > 0 and paren_pos < max_length - 10:
                # Break after commas
                parts = line.split(",")
                if len(parts) > 1:
                    first_line = parts[0] + ","
                    fixed_lines.append(first_line)

                    # Calculate proper indentation for continuation
                    cont_indent = " " * (paren_pos + 1)

                    for i, part in enumerate(parts[1:]):
                        if i == len(parts) - 2:  # Last part
                            fixed_lines.append(cont_indent + part.strip())
                        else:
                            fixed_lines.append(cont_indent + part.strip() + ",")
                    continue

        # For long strings with +, break at +
        if " + " in line:
            parts = line.split(" + ")
            if len(parts) > 1:
                fixed_lines.append(parts[0] + " +")
                for part in parts[1:]:
                    fixed_lines.append(indent_str + "    " + part.strip())
                continue

        # Default: just add the line as is
        fixed_lines.append(line)

    return "\n".join(fixed_lines)


def fix_unnecessary_lambda(content: str) -> str:
    """Fix unnecessary lambda expressions."""
    # Pattern: lambda: func() -> func
    pattern1 = r"lambda\s*:\s*(\w+)\(\)"
    content = re.sub(pattern1, r"\1", content)

    # Pattern: lambda x: func(x) -> func
    pattern2 = r"lambda\s+(\w+)\s*:\s*(\w+)\(\1\)"
    content = re.sub(pattern2, r"\2", content)

    return content


def fix_no_else_return(content: str) -> str:
    """Remove unnecessary else after return."""
    lines = content.split("\n")
    fixed_lines = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Check if this line has a return statement
        if "return" in line.strip() and not line.strip().startswith("#"):
            # Check if next line is else:
            if i + 1 < len(lines):
                next_line = lines[i + 1]
                if re.match(r"^\s*else\s*:", next_line):
                    # Get the indentation of the else
                    else_indent = len(next_line) - len(next_line.lstrip())

                    # Add the return line
                    fixed_lines.append(line)

                    # Skip the else line
                    i += 1

                    # De-indent all following lines that were in the else block
                    i += 1
                    while i < len(lines):
                        current_line = lines[i]
                        current_indent = len(current_line) - len(current_line.lstrip())

                        if current_line.strip() and current_indent > else_indent:
                            # This line was in the else block, de-indent it
                            new_line = " " * else_indent + current_line.lstrip()
                            fixed_lines.append(new_line)
                        else:
                            # End of else block
                            fixed_lines.append(current_line)
                            break
                        i += 1

                    continue

        fixed_lines.append(line)
        i += 1

    return "\n".join(fixed_lines)


def process_file(filepath: Path) -> Tuple[bool, List[str]]:
    """Process a single file to fix Pylint issues."""
    changes = []

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            original_content = f.read()
    except Exception as e:
        return False, [f"Error reading file: {e}"]

    content = original_content

    # Apply fixes
    new_content = fix_trailing_whitespace(content)
    if new_content != content:
        changes.append("Fixed trailing whitespace")
        content = new_content

    new_content = fix_logging_fstring(content)
    if new_content != content:
        changes.append("Fixed f-string logging")
        content = new_content

    new_content = fix_long_lines(content)
    if new_content != content:
        changes.append("Fixed long lines")
        content = new_content

    new_content = fix_unnecessary_lambda(content)
    if new_content != content:
        changes.append("Fixed unnecessary lambda")
        content = new_content

    new_content = fix_no_else_return(content)
    if new_content != content:
        changes.append("Fixed no-else-return")
        content = new_content

    # Write back if changed
    if content != original_content:
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            return True, changes
        except Exception as e:
            return False, [f"Error writing file: {e}"]

    return False, []


def main():
    """Main function."""
    # Find all Python files in goesvfi directory
    goesvfi_dir = Path(__file__).parent / "goesvfi"
    python_files = list(goesvfi_dir.rglob("*.py"))

    print(f"Found {len(python_files)} Python files to process")

    total_fixed = 0
    for filepath in python_files:
        fixed, changes = process_file(filepath)
        if fixed:
            total_fixed += 1
            print(
                f"✓ Fixed {filepath.relative_to(Path(__file__).parent)}: {', '.join(changes)}"
            )

    print(f"\nFixed {total_fixed} files")

    # Also process test files
    test_dir = Path(__file__).parent / "tests"
    if test_dir.exists():
        test_files = list(test_dir.rglob("*.py"))
        print(f"\nFound {len(test_files)} test files to process")

        test_fixed = 0
        for filepath in test_files:
            fixed, changes = process_file(filepath)
            if fixed:
                test_fixed += 1
                print(
                    f"✓ Fixed {filepath.relative_to(Path(__file__).parent)}: {', '.join(changes)}"
                )

        print(f"\nFixed {test_fixed} test files")


if __name__ == "__main__":
    main()
