#!/usr/bin/env python3
"""Automatically fix common syntax errors in Python files."""

import ast
import os
import re
import sys
from pathlib import Path


def fix_empty_imports(content):
    """Fix empty import statements like 'from module import ()'."""
    # Pattern: from module import ()
    pattern = r"from\s+[\w\.]+\s+import\s*\(\s*\)"
    content = re.sub(pattern, "", content)

    # Also fix trailing commas in imports that result in empty imports
    pattern = r"from\s+([\w\.]+)\s+import\s*\([^)]*,\s*\)"
    content = re.sub(pattern, r"from \1 import ()", content)

    return content


def fix_split_function_calls(content):
    """Fix split function calls like func()\n    "arg"."""
    lines = content.split("\n")
    fixed_lines = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Check if the current line ends with () and next line starts with quotes
        if i + 1 < len(lines) and line.strip().endswith("()"):
            next_line = lines[i + 1]
            if next_line.strip() and (next_line.strip()[0] in ['"', "'", 'f"', "f'"]):
                # Merge the lines
                fixed_lines.append(line.rstrip() + "(" + next_line.strip() + ")")
                i += 2
                continue

        fixed_lines.append(line)
        i += 1

    return "\n".join(fixed_lines)


def fix_unmatched_parentheses(content):
    """Fix unmatched parentheses in import statements."""
    lines = content.split("\n")
    fixed_lines = []
    in_import = False
    import_lines = []

    for line in lines:
        # Check if this is the start of an import statement
        if re.match(r"^\s*from\s+[\w\.]+\s+import\s*\(", line):
            in_import = True
            import_lines = [line]
        elif in_import:
            import_lines.append(line)
            # Check if this completes the import
            if ")" in line:
                in_import = False
                # Process the complete import
                import_text = "\n".join(import_lines)

                # Count parentheses
                open_count = import_text.count("(")
                close_count = import_text.count(")")

                if open_count > close_count:
                    # Add missing closing parenthesis
                    import_lines[-1] = import_lines[-1].rstrip() + ")"
                elif close_count > open_count:
                    # Remove extra closing parenthesis
                    import_lines[-1] = import_lines[-1].replace(
                        ")", "", close_count - open_count
                    )

                fixed_lines.extend(import_lines)
                import_lines = []
        else:
            fixed_lines.append(line)

    # Handle unclosed import at end of file
    if import_lines:
        import_lines[-1] = import_lines[-1].rstrip() + ")"
        fixed_lines.extend(import_lines)

    return "\n".join(fixed_lines)


def fix_fstring_format_errors(content):
    """Fix f-string format errors."""
    # Pattern: "text %s", var:.1f should be "text %.1f", var
    pattern = r'"([^"]*%[sd])"[,\s]+(\w+):(\.?\d+[fd])'
    content = re.sub(pattern, r'"\1\3", \2', content)

    # Fix unterminated f-string literals
    lines = content.split("\n")
    fixed_lines = []

    for line in lines:
        # Check for unterminated f-string
        if 'f"' in line or "f'" in line:
            # Count quotes
            double_quotes = line.count('"') - line.count('\\"')
            single_quotes = line.count("'") - line.count("\\'")

            # If odd number of quotes, add closing quote
            if 'f"' in line and double_quotes % 2 == 1:
                line = line.rstrip() + '"'
            elif "f'" in line and single_quotes % 2 == 1:
                line = line.rstrip() + "'"

        fixed_lines.append(line)

    return "\n".join(fixed_lines)


def fix_ordinal_numbers(content):
    """Fix ordinal numbers in docstrings causing 'invalid decimal literal'."""
    # Replace patterns like 1st, 2nd, 3rd, 4th, etc. in docstrings
    lines = content.split("\n")
    fixed_lines = []
    in_docstring = False
    docstring_type = None

    for line in lines:
        # Check for docstring start
        if not in_docstring:
            if '"""' in line:
                in_docstring = True
                docstring_type = '"""'
            elif "'''" in line:
                in_docstring = True
                docstring_type = "'''"

        # If in docstring, fix ordinal numbers
        if in_docstring:
            # Fix ordinals like 1st, 2nd, 3rd, 4th, etc.
            line = re.sub(r"\b(\d+)(st|nd|rd|th)\b", r"\1\2", line)

        # Check for docstring end
        if in_docstring and docstring_type in line:
            # Count occurrences
            count = line.count(docstring_type)
            if count >= 2 or (
                count == 1 and not line.strip().startswith(docstring_type)
            ):
                in_docstring = False

        fixed_lines.append(line)

    return "\n".join(fixed_lines)


def fix_duplicate_except(content):
    """Fix duplicate except statements."""
    lines = content.split("\n")
    fixed_lines = []
    seen_excepts = set()

    for i, line in enumerate(lines):
        # Check if this is an except line
        match = re.match(r"^(\s*)except\s+(\w+(?:\.\w+)*)\s*(as\s+\w+)?\s*:", line)
        if match:
            indent = match.group(1)
            exception = match.group(2)
            alias = match.group(3) or ""

            # Create a key for this except block
            key = (indent, exception)

            if key in seen_excepts:
                # This is a duplicate, skip it and its body
                continue
            else:
                seen_excepts.add(key)

        fixed_lines.append(line)

    return "\n".join(fixed_lines)


def fix_missing_indentation(content):
    """Fix missing indentation after colons."""
    lines = content.split("\n")
    fixed_lines = []

    for i, line in enumerate(lines):
        fixed_lines.append(line)

        # Check if line ends with colon and next line exists
        if line.strip() and line.strip().endswith(":") and i + 1 < len(lines):
            next_line = lines[i + 1]

            # If next line is not indented more than current line
            current_indent = len(line) - len(line.lstrip())
            next_indent = len(next_line) - len(next_line.lstrip())

            if next_line.strip() and next_indent <= current_indent:
                # Add a pass statement
                fixed_lines.append(" " * (current_indent + 4) + "pass")

    return "\n".join(fixed_lines)


def fix_unexpected_indent(content):
    """Fix unexpected indent errors."""
    lines = content.split("\n")
    fixed_lines = []
    expected_indent = 0
    indent_stack = [0]

    for line in lines:
        if not line.strip():
            # Empty line, preserve it
            fixed_lines.append(line)
            continue

        current_indent = len(line) - len(line.lstrip())

        # Check if previous line ends with colon
        if fixed_lines and fixed_lines[-1].strip().endswith(":"):
            # Expect increased indentation
            expected_indent = indent_stack[-1] + 4
            if current_indent > indent_stack[-1]:
                indent_stack.append(current_indent)
        else:
            # Find the correct indentation level
            while indent_stack and current_indent < indent_stack[-1]:
                indent_stack.pop()

            if indent_stack:
                expected_indent = indent_stack[-1]
            else:
                expected_indent = 0

        # Fix the indentation if needed
        if current_indent != expected_indent and line.strip():
            line = " " * expected_indent + line.lstrip()

        fixed_lines.append(line)

    return "\n".join(fixed_lines)


def fix_empty_blocks(content):
    """Add pass statements to empty blocks."""
    lines = content.split("\n")
    fixed_lines = []

    for i, line in enumerate(lines):
        fixed_lines.append(line)

        # Check if this line ends with a colon
        if line.strip().endswith(":"):
            # Look ahead to see if the next non-empty line has less or equal indentation
            current_indent = len(line) - len(line.lstrip())
            j = i + 1

            # Skip empty lines
            while j < len(lines) and not lines[j].strip():
                j += 1

            # If we reached end of file or next line has less/equal indentation, add pass
            if j >= len(lines) or (
                lines[j].strip()
                and len(lines[j]) - len(lines[j].lstrip()) <= current_indent
            ):
                fixed_lines.append(" " * (current_indent + 4) + "pass")

    return "\n".join(fixed_lines)


def fix_syntax_errors(filepath):
    """Apply all syntax fixes to a file."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return False

    original_content = content

    # Apply fixes in order
    content = fix_empty_imports(content)
    content = fix_split_function_calls(content)
    content = fix_unmatched_parentheses(content)
    content = fix_fstring_format_errors(content)
    content = fix_ordinal_numbers(content)
    content = fix_duplicate_except(content)
    content = fix_unexpected_indent(content)
    content = fix_missing_indentation(content)
    content = fix_empty_blocks(content)

    # Check if the content changed
    if content != original_content:
        # Verify the fixed content is valid Python
        try:
            ast.parse(content)
            # If valid, write back
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"Fixed: {filepath}")
            return True
        except SyntaxError as e:
            print(f"Still has syntax errors after fixes: {filepath}: {e}")
            # Try to write it anyway if it's an improvement
            try:
                # Count errors before and after
                try:
                    ast.parse(original_content)
                    original_errors = 0
                except:
                    original_errors = 1

                try:
                    ast.parse(content)
                    new_errors = 0
                except:
                    new_errors = 1

                # If we reduced errors, keep the changes
                if new_errors < original_errors:
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(content)
                    print(f"Partially fixed: {filepath}")
                    return True
            except:
                pass

    return False


def main():
    """Main function to fix syntax errors in all Python files."""
    fixed_count = 0

    # First, find all files with syntax errors
    print("Finding files with syntax errors...")
    from find_syntax_errors import find_syntax_errors

    files_with_errors = find_syntax_errors()

    print(f"\nAttempting to fix {len(files_with_errors)} files...")

    for filepath, error in files_with_errors:
        if fix_syntax_errors(filepath):
            fixed_count += 1

    print(f"\nFixed {fixed_count} out of {len(files_with_errors)} files")

    # Run the check again to see remaining errors
    print("\nChecking for remaining syntax errors...")
    remaining_errors = find_syntax_errors()
    print(f"\nRemaining files with syntax errors: {len(remaining_errors)}")


if __name__ == "__main__":
    main()
