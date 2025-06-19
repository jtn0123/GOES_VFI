#!/usr/bin/env python3
"""Automatically fix common syntax errors in Python files - Enhanced version."""

import ast
import os
import re
import sys
from pathlib import Path


def fix_split_imports(content):
    """Fix split import statements with unmatched parentheses."""
    lines = content.split("\n")
    fixed_lines = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Check for a line that has only a closing parenthesis after imports
        if i > 0 and line.strip() == ")" and "from" in lines[i - 1]:
            # Look back to find the import statement
            j = i - 1
            while j >= 0 and not lines[j].strip().startswith("from"):
                j -= 1

            if j >= 0:
                # Collect all lines of the import
                import_lines = []
                for k in range(j, i):
                    import_lines.append(lines[k])

                # Merge them properly
                merged = " ".join(line.strip() for line in import_lines if line.strip())
                if not merged.endswith("("):
                    merged = merged.replace(" ()", " (")
                    if "(" in merged and ")" not in merged:
                        merged += ")"

                # Skip the lines we just processed
                fixed_lines = fixed_lines[: -(i - j - 1)]  # Remove lines we added
                fixed_lines.append(merged)
                i += 1
                continue

        # Check for imports missing opening parenthesis
        if line.strip() and not line.strip().startswith("#"):
            # Pattern: from module import ()
            if re.match(r"^from\s+[\w\.]+\s+import\s+\(\s*\)$", line.strip()):
                # Skip empty imports
                i += 1
                continue

            # Pattern: lines that start with module names after from...import without (
            if (
                i > 0
                and re.match(r"^[A-Za-z]\w*", line.strip())
                and "from" in lines[i - 1]
            ):
                prev_line = lines[i - 1].strip()
                if prev_line.endswith("import") or prev_line.endswith("import "):
                    # Add opening parenthesis
                    fixed_lines[-1] = fixed_lines[-1] + " ("

        fixed_lines.append(line)
        i += 1

    return "\n".join(fixed_lines)


def fix_split_function_definitions(content):
    """Fix split function definitions like def func(:) on separate lines."""
    lines = content.split("\n")
    fixed_lines = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Check for function/method definitions ending with (:)
        if re.match(r"^\s*(def|async def)\s+\w+\(\s*:\s*\)?\s*$", line):
            # This is a malformed function definition
            if i + 1 < len(lines):
                next_line = lines[i + 1]
                # Check if next line contains parameters
                if re.match(r"^\s*(self|cls|\w+)", next_line.strip()):
                    # Merge the lines
                    func_match = re.match(r"^(\s*)(def|async def)\s+(\w+)\(", line)
                    if func_match:
                        indent = func_match.group(1)
                        def_type = func_match.group(2)
                        func_name = func_match.group(3)
                        # Reconstruct the function definition
                        fixed_lines.append(
                            f"{indent}{def_type} {func_name}({next_line.strip()}"
                        )
                        i += 2
                        continue

        # Also check for lines that have just "def funcname(:"
        if re.match(r"^\s*(def|async def)\s+\w+\(\s*:$", line):
            if i + 1 < len(lines):
                next_line = lines[i + 1]
                # Remove the colon and merge
                fixed_line = line.replace("(:", "(")
                fixed_lines.append(fixed_line + next_line.strip())
                i += 2
                continue

        fixed_lines.append(line)
        i += 1

    return "\n".join(fixed_lines)


def fix_docstring_placement(content):
    """Fix docstrings that appear in wrong places."""
    lines = content.split("\n")
    fixed_lines = []

    for i, line in enumerate(lines):
        # Check if this line is between imports and looks like it should be part of docstring
        if i > 0 and i < len(lines) - 1:
            prev_line = lines[i - 1].strip()
            next_line = lines[i + 1].strip() if i + 1 < len(lines) else ""

            # If current line contains text without quotes and is between import-like statements
            if (
                not line.strip().startswith('"')
                and not line.strip().startswith("'")
                and line.strip()
                and not line.strip().startswith("#")
                and ("from" in prev_line or "import" in prev_line)
                and '"""' in next_line
            ):
                # This line should be part of the docstring
                continue

        fixed_lines.append(line)

    return "\n".join(fixed_lines)


def fix_unterminated_strings(content):
    """Fix unterminated string literals."""
    lines = content.split("\n")
    fixed_lines = []

    for line in lines:
        if line.strip():
            # Count quotes (excluding escaped ones)
            # For f-strings
            if 'f"' in line or "f'" in line:
                # Count unescaped quotes
                double_quotes = 0
                single_quotes = 0
                i = 0
                while i < len(line):
                    if i > 0 and line[i - 1] == "\\":
                        i += 1
                        continue
                    if line[i] == '"':
                        double_quotes += 1
                    elif line[i] == "'":
                        single_quotes += 1
                    i += 1

                # Fix unterminated strings
                if double_quotes % 2 == 1:
                    line = line.rstrip() + '"'
                elif single_quotes % 2 == 1:
                    line = line.rstrip() + "'"

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
            # Look ahead to find the next non-empty, non-comment line
            j = i + 1
            next_code_line_indent = None

            while j < len(lines):
                next_line = lines[j]
                # Skip empty lines and comments
                if next_line.strip() and not next_line.strip().startswith("#"):
                    next_code_line_indent = len(next_line) - len(next_line.lstrip())
                    break
                j += 1

            current_indent = len(line) - len(line.lstrip())
            expected_indent = current_indent + 4

            # If no next code line or it's not indented properly, add pass
            if next_code_line_indent is None or next_code_line_indent <= current_indent:
                # Check if the immediate next line is empty or comment
                if i + 1 < len(lines):
                    immediate_next = lines[i + 1]
                    if not immediate_next.strip() or immediate_next.strip().startswith(
                        "#"
                    ):
                        # Don't add pass yet, will be handled in next iteration
                        pass
                    else:
                        fixed_lines.append(" " * expected_indent + "pass")
                else:
                    fixed_lines.append(" " * expected_indent + "pass")

    return "\n".join(fixed_lines)


def fix_invalid_syntax_patterns(content):
    """Fix various invalid syntax patterns."""
    # Fix "text %s", var:.1f patterns
    content = re.sub(r'"([^"]*%[sd])"[,\s]+(\w+):(\.?\d+[fd])', r'"\1\3", \2', content)

    # Fix empty except blocks
    content = re.sub(
        r"(\s*except[^:]+:)\s*$", r"\1\n    pass", content, flags=re.MULTILINE
    )

    # Fix empty if/else blocks
    content = re.sub(
        r"(\s*(?:if|else|elif)[^:]+:)\s*$", r"\1\n    pass", content, flags=re.MULTILINE
    )

    return content


def fix_indentation_errors(content):
    """Fix indentation errors more intelligently."""
    lines = content.split("\n")
    fixed_lines = []
    indent_stack = [0]

    for i, line in enumerate(lines):
        if not line.strip():
            fixed_lines.append(line)
            continue

        current_indent = len(line) - len(line.lstrip())

        # Check previous non-empty line
        prev_line_idx = i - 1
        while prev_line_idx >= 0 and not lines[prev_line_idx].strip():
            prev_line_idx -= 1

        if prev_line_idx >= 0:
            prev_line = lines[prev_line_idx]
            prev_indent = len(prev_line) - len(prev_line.lstrip())

            # If previous line ends with colon, expect indent
            if prev_line.strip().endswith(":"):
                expected_indent = prev_indent + 4
                if current_indent != expected_indent:
                    line = " " * expected_indent + line.lstrip()
                # Update indent stack
                if expected_indent not in indent_stack:
                    indent_stack.append(expected_indent)
            else:
                # Find appropriate indent level from stack
                while indent_stack and current_indent < indent_stack[-1]:
                    indent_stack.pop()

                if indent_stack and current_indent not in indent_stack:
                    # Adjust to nearest valid indent
                    valid_indents = [
                        ind for ind in indent_stack if ind <= current_indent
                    ]
                    if valid_indents:
                        line = " " * valid_indents[-1] + line.lstrip()

        fixed_lines.append(line)

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
    content = fix_split_imports(content)
    content = fix_split_function_definitions(content)
    content = fix_docstring_placement(content)
    content = fix_unterminated_strings(content)
    content = fix_invalid_syntax_patterns(content)
    content = fix_indentation_errors(content)
    content = fix_empty_blocks(content)

    # Check if the content changed
    if content != original_content:
        # Try to parse and see if it's better
        try:
            ast.parse(content)
            # If valid, write back
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"Fixed: {filepath}")
            return True
        except SyntaxError as e:
            # Still has errors, but might be improved
            # Write it back if we think it's better
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"Partially fixed: {filepath} (still has: {e})")
            return True

    return False


def main():
    """Main function to fix syntax errors in all Python files."""
    import subprocess

    # Get list of files with syntax errors using find command
    print("Finding files with syntax errors...")

    # Run python3 -m py_compile on each .py file to find syntax errors
    error_files = []

    for root, dirs, files in os.walk("."):
        # Skip virtual environments
        dirs[:] = [d for d in dirs if d not in {".venv", "venv", "__pycache__", ".git"}]

        for file in files:
            if file.endswith(".py"):
                filepath = os.path.join(root, file)
                # Try to compile the file
                result = subprocess.run(
                    [sys.executable, "-m", "py_compile", filepath],
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    error_files.append(filepath)

    print(f"Found {len(error_files)} files with syntax errors")

    fixed_count = 0
    for filepath in error_files:
        if fix_syntax_errors(filepath):
            fixed_count += 1

    print(f"\nFixed {fixed_count} out of {len(error_files)} files")

    # Check again
    remaining = 0
    for filepath in error_files:
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", filepath],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            remaining += 1
            if remaining <= 10:
                print(f"Still has errors: {filepath}")

    print(f"\nRemaining files with syntax errors: {remaining}")


if __name__ == "__main__":
    main()
