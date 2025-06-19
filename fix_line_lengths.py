#!/usr/bin/env python3
"""
Script to analyze and fix line length issues in Python files.
This script focuses on finding and categorizing lines that exceed 88 characters.
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Colors for terminal output
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"

MAX_LINE_LENGTH = 88
DIRECTORIES = [
    "goesvfi/date_sorter",
    "goesvfi/file_sorter",
    "goesvfi/gui_tabs",
    "goesvfi/integrity_check",
    "goesvfi/pipeline",
    "goesvfi/utils",
    "goesvfi/view_models",
]

# Pattern categories for line length issues
PATTERNS = {
    "imports": re.compile(r"^\s*(?:from|import)\s+.*$"),
    "function_call": re.compile(r".*\([^)]*\).*"),
    "dictionary": re.compile(r".*\{.*\}.*"),
    "list": re.compile(r".*\[.*\].*"),
    "string": re.compile(r'.*["\']{1,3}.*["\']{1,3}.*'),
    "comments": re.compile(r"^\s*#.*$"),
    "assignment": re.compile(r".*=.*"),
}


def print_colored(message: str, color: str = RESET, bold: bool = False) -> None:
    """Print a message with color."""
    if bold:
        print(f"{BOLD}{color}{message}{RESET}")
    else:
        print(f"{color}{message}{RESET}")


def analyze_file(file_path: str) -> Dict[str, List[Tuple[int, str]]]:
    """
    Analyze a file for line length issues and categorize them.

    Args:
        file_path: Path to the Python file to analyze

    Returns:
        Dictionary mapping categories to lists of (line_number, line_content) tuples
    """
    results = {
        "imports": [],
        "function_call": [],
        "dictionary": [],
        "list": [],
        "string": [],
        "comments": [],
        "assignment": [],
        "other": [],
    }

    with open(file_path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            # Skip empty lines
            if not line.strip():
                continue

            # Check if line exceeds max length
            if len(line.rstrip()) > MAX_LINE_LENGTH:
                categorized = False

                # Categorize the line
                for category, pattern in PATTERNS.items():
                    if pattern.match(line):
                        results[category].append((i, line.rstrip()))
                        categorized = True
                        break

                # If no category matched, put in "other"
                if not categorized:
                    results["other"].append((i, line.rstrip()))

    # Remove empty categories
    return {k: v for k, v in results.items() if v}


def analyze_directory(directory: str) -> Dict[str, Dict[str, List[Tuple[int, str]]]]:
    """
    Analyze all Python files in a directory for line length issues.

    Args:
        directory: Directory to analyze

    Returns:
        Dictionary mapping file paths to their analysis results
    """
    results = {}

    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                file_results = analyze_file(file_path)

                if file_results:  # Only include files with issues
                    results[file_path] = file_results

    return results


def count_issues_by_category(
    results: Dict[str, Dict[str, List[Tuple[int, str]]]]
) -> Dict[str, int]:
    """Count issues by category across all analyzed files."""
    counts = {"total": 0}

    for file_path, file_results in results.items():
        for category, issues in file_results.items():
            counts[category] = counts.get(category, 0) + len(issues)
            counts["total"] += len(issues)

    return counts


def count_issues_by_file(
    results: Dict[str, Dict[str, List[Tuple[int, str]]]]
) -> Dict[str, int]:
    """Count total issues for each file."""
    counts = {}

    for file_path, file_results in results.items():
        file_count = 0
        for issues in file_results.values():
            file_count += len(issues)
        counts[file_path] = file_count

    return counts


def print_summary(results: Dict[str, Dict[str, List[Tuple[int, str]]]]) -> None:
    """Print a summary of the analysis results."""
    category_counts = count_issues_by_category(results)
    file_counts = count_issues_by_file(results)

    print_colored("\n======== LINE LENGTH ISSUES SUMMARY ========", BLUE, bold=True)

    # Print category breakdown
    print_colored("\nIssues by Category:", BLUE, bold=True)
    for category, count in sorted(category_counts.items(), key=lambda x: -x[1]):
        if category != "total":
            color = GREEN if count < 10 else YELLOW if count < 50 else RED
            print_colored(f"  {category}: {count} issues", color)

    # Print overall total
    total = category_counts["total"]
    color = GREEN if total < 20 else YELLOW if total < 100 else RED
    print_colored(
        f"\nTotal: {total} line length issues across {len(results)} files",
        color,
        bold=True,
    )

    # Print file breakdown (top 10 most problematic files)
    print_colored("\nTop 10 Files With Most Issues:", BLUE, bold=True)
    for file_path, count in sorted(file_counts.items(), key=lambda x: -x[1])[:10]:
        color = GREEN if count < 5 else YELLOW if count < 20 else RED
        rel_path = os.path.relpath(file_path)
        print_colored(f"  {rel_path}: {count} issues", color)


def fix_imports(line: str) -> str:
    """Fix import statements that exceed the max line length."""
    line = line.rstrip()

    if "," in line:
        # Split imports that use multiple items in one line
        parts = line.split("import ")
        if len(parts) == 2:
            prefix, imports = parts
            import_items = [item.strip() for item in imports.split(",")]

            # If there are more than 3 items, use parentheses wrapping
            if len(import_items) > 3:
                wrapped = (
                    prefix + "import (\n    " + ",\n    ".join(import_items) + "\n)"
                )
                return wrapped
            else:
                # Otherwise, put each import on its own line
                lines = []
                for item in import_items:
                    lines.append(f"{prefix}import {item}")
                return "\n".join(lines)

    # For long single imports, wrap in parentheses
    if " as " in line:
        parts = line.split(" as ")
        if len(parts) == 2:
            module, alias = parts
            if len(module) > MAX_LINE_LENGTH - 10:  # Subtract for " as alias"
                wrapped = f"{module} as (\n    {alias}\n)"
                return wrapped

    # Default handling: multiline with trailing backslash
    if len(line) > MAX_LINE_LENGTH:
        split_point = MAX_LINE_LENGTH - 1
        return line[:split_point] + "\\\n" + line[split_point:]

    return line


def fix_function_call(line: str) -> str:
    """Fix function calls that exceed the max line length."""
    line = line.rstrip()

    # Find opening and closing parentheses
    open_idx = line.find("(")
    close_idx = line.rfind(")")

    if open_idx > 0 and close_idx > open_idx:
        # Extract the function name and arguments
        func_name = line[:open_idx].strip()
        args_str = line[open_idx + 1 : close_idx].strip()
        after_call = line[close_idx + 1 :].strip()

        # If arguments contain commas, we can split them
        if "," in args_str:
            args = []
            current_arg = ""
            in_quote = False
            quote_char = None
            paren_level = 0
            bracket_level = 0
            brace_level = 0

            # Parse arguments with awareness of nested structures
            for char in args_str:
                if char in "'\"" and (not quote_char or char == quote_char):
                    in_quote = not in_quote
                    if in_quote:
                        quote_char = char
                    else:
                        quote_char = None
                elif not in_quote:
                    if char == "(":
                        paren_level += 1
                    elif char == ")":
                        paren_level -= 1
                    elif char == "[":
                        bracket_level += 1
                    elif char == "]":
                        bracket_level -= 1
                    elif char == "{":
                        brace_level += 1
                    elif char == "}":
                        brace_level -= 1

                current_arg += char

                # If at a comma outside of quotes and nested structures, split the argument
                if (
                    char == ","
                    and not in_quote
                    and paren_level == 0
                    and bracket_level == 0
                    and brace_level == 0
                ):
                    args.append(current_arg[:-1].strip())  # Remove trailing comma
                    current_arg = ""

            # Add the last argument if there is one
            if current_arg.strip():
                args.append(current_arg.strip())

            # Format the arguments
            if len(args) > 1:
                indent = " " * (len(func_name) + 1)  # Align with the opening paren
                formatted_args = ",\n".join(f"{indent}{arg.strip()}" for arg in args)
                return f"{func_name}(\n{formatted_args}\n){after_call}"

    # Default handling: try to split at the opening parenthesis
    if len(line) > MAX_LINE_LENGTH and "(" in line:
        parts = line.split("(", 1)
        if len(parts) == 2:
            return f"{parts[0]}(\n    {parts[1]}"

    return line


def fix_dictionary(line: str) -> str:
    """Fix dictionary definitions that exceed the max line length."""
    line = line.rstrip()

    # Find opening and closing braces
    open_idx = line.find("{")
    close_idx = line.rfind("}")

    if open_idx > 0 and close_idx > open_idx:
        before_dict = line[:open_idx].strip()
        dict_content = line[open_idx + 1 : close_idx].strip()
        after_dict = line[close_idx + 1 :].strip()

        # If dict content contains commas, we can split it
        if "," in dict_content:
            entries = []
            current_entry = ""
            in_quote = False
            quote_char = None
            paren_level = 0
            bracket_level = 0
            brace_level = 0

            # Parse dict entries with awareness of nested structures
            for char in dict_content:
                if char in "'\"" and (not quote_char or char == quote_char):
                    in_quote = not in_quote
                    if in_quote:
                        quote_char = char
                    else:
                        quote_char = None
                elif not in_quote:
                    if char == "(":
                        paren_level += 1
                    elif char == ")":
                        paren_level -= 1
                    elif char == "[":
                        bracket_level += 1
                    elif char == "]":
                        bracket_level -= 1
                    elif char == "{":
                        brace_level += 1
                    elif char == "}":
                        brace_level -= 1

                current_entry += char

                # If at a comma outside of quotes and nested structures, split the entry
                if (
                    char == ","
                    and not in_quote
                    and paren_level == 0
                    and bracket_level == 0
                    and brace_level == 0
                ):
                    entries.append(current_entry[:-1].strip())  # Remove trailing comma
                    current_entry = ""

            # Add the last entry if there is one
            if current_entry.strip():
                entries.append(current_entry.strip())

            # Format the dictionary
            if len(entries) > 1:
                indent = "    "  # Standard indentation
                formatted_entries = ",\n".join(f"{indent}{entry}" for entry in entries)
                return f"{before_dict}{{\n{formatted_entries}\n}}{after_dict}"

    return line


def fix_list(line: str) -> str:
    """Fix list definitions that exceed the max line length."""
    line = line.rstrip()

    # Find opening and closing brackets
    open_idx = line.find("[")
    close_idx = line.rfind("]")

    if open_idx >= 0 and close_idx > open_idx:
        before_list = line[:open_idx].strip()
        list_content = line[open_idx + 1 : close_idx].strip()
        after_list = line[close_idx + 1 :].strip()

        # If list content contains commas, we can split it
        if "," in list_content:
            items = []
            current_item = ""
            in_quote = False
            quote_char = None
            paren_level = 0
            bracket_level = 0
            brace_level = 0

            # Parse list items with awareness of nested structures
            for char in list_content:
                if char in "'\"" and (not quote_char or char == quote_char):
                    in_quote = not in_quote
                    if in_quote:
                        quote_char = char
                    else:
                        quote_char = None
                elif not in_quote:
                    if char == "(":
                        paren_level += 1
                    elif char == ")":
                        paren_level -= 1
                    elif char == "[":
                        bracket_level += 1
                    elif char == "]":
                        bracket_level -= 1
                    elif char == "{":
                        brace_level += 1
                    elif char == "}":
                        brace_level -= 1

                current_item += char

                # If at a comma outside of quotes and nested structures, split the item
                if (
                    char == ","
                    and not in_quote
                    and paren_level == 0
                    and bracket_level == 0
                    and brace_level == 0
                ):
                    items.append(current_item[:-1].strip())  # Remove trailing comma
                    current_item = ""

            # Add the last item if there is one
            if current_item.strip():
                items.append(current_item.strip())

            # Format the list
            if len(items) > 1:
                indent = "    "  # Standard indentation
                formatted_items = ",\n".join(f"{indent}{item}" for item in items)
                return f"{before_list}[\n{formatted_items}\n]{after_list}"

    return line


def fix_string(line: str) -> str:
    """Fix string literals that exceed the max line length."""
    line = line.rstrip()

    # Identify string literals
    # Look for triple quoted strings first
    triple_match = re.search(r'([\'"])(?:\1{2})(.+?)(?:\1{3})', line)
    if triple_match:
        # Triple quoted strings can have newlines, so leave them as is for now
        return line

    # Look for string assignments - these can be split into multiple strings
    string_assignment = re.search(r'(.+?=\s*)(["\'])(.+?)(\2)(.*)', line)
    if string_assignment and len(line) > MAX_LINE_LENGTH:
        prefix = string_assignment.group(1)
        quote = string_assignment.group(2)
        content = string_assignment.group(3)
        suffix = string_assignment.group(5)

        # Split the string every 60 characters or so
        pieces = []
        chunk_size = 60
        for i in range(0, len(content), chunk_size):
            pieces.append(content[i : i + chunk_size])

        if len(pieces) > 1:
            joined = f" {quote} +\n    {quote}".join(pieces)
            return f"{prefix}{quote}{joined}{quote}{suffix}"

    # For strings in function calls, etc., we rely on the other fixers
    return line


def fix_comments(line: str) -> str:
    """Fix comments that exceed the max line length."""
    line = line.rstrip()

    # If it's a docstring, leave it for now (needs special handling)
    if line.lstrip().startswith('"""') or line.lstrip().startswith("'''"):
        return line

    # For regular comments, wrap at MAX_LINE_LENGTH
    if line.lstrip().startswith("#") and len(line) > MAX_LINE_LENGTH:
        indent = re.match(r"^(\s*)", line).group(1)
        comment = line.lstrip()

        # Split the comment into words
        words = comment[1:].strip().split()

        # Rebuild the comment with proper line wrapping
        new_lines = []
        current_line = f"{indent}#"

        for word in words:
            # If adding this word would exceed the limit, start a new line
            if len(current_line + " " + word) > MAX_LINE_LENGTH:
                new_lines.append(current_line)
                current_line = f"{indent}# {word}"
            else:
                current_line += f" {word}" if current_line[-1] != "#" else f" {word}"

        # Add the last line if it's not empty
        if current_line != f"{indent}#":
            new_lines.append(current_line)

        return "\n".join(new_lines)

    return line


def fix_assignment(line: str) -> str:
    """Fix assignment statements that exceed the max line length."""
    line = line.rstrip()

    if "=" in line and not re.search(r"[=!<>]=", line):  # Avoid comparison operators
        parts = line.split("=", 1)
        if len(parts) == 2:
            var_name = parts[0].rstrip()
            value = parts[1].lstrip()

            # If the value is a complex expression, try to split it
            if len(line) > MAX_LINE_LENGTH:
                # For function calls, dictionaries, lists
                if "(" in value or "{" in value or "[" in value:
                    # Let the other fixers handle these cases
                    return line

                # For long expressions with operators, split on operators
                operators = [" + ", " - ", " * ", " / ", " // ", " % ", " ** "]
                for op in operators:
                    if op in value:
                        op_parts = value.split(op)
                        if len(op_parts) > 1:
                            indent = " " * (len(var_name) + 2)  # var_name= plus space
                            joined = f"{op}\\\n{indent}".join(op_parts)
                            return f"{var_name}= {joined}"

    return line


def fix_line_length(file_path: str, dry_run: bool = True) -> Tuple[int, int]:
    """
    Fix line length issues in a file.

    Args:
        file_path: Path to the Python file to fix
        dry_run: If True, don't actually write changes

    Returns:
        Tuple of (fixed_count, total_issues)
    """
    analysis = analyze_file(file_path)
    total_issues = sum(len(issues) for issues in analysis.values())

    if total_issues == 0:
        return 0, 0

    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    fixed_count = 0
    modified_lines = set()

    # Process categories in a specific order to handle nested structures correctly
    category_order = [
        "imports",
        "dictionary",
        "list",
        "function_call",
        "string",
        "assignment",
        "comments",
        "other",
    ]

    for category in category_order:
        if category in analysis:
            for line_num, line_content in analysis[category]:
                idx = line_num - 1  # Convert to 0-based index

                # Skip lines that were already fixed by another category
                if idx in modified_lines:
                    continue

                original_line = lines[idx]

                # Apply the appropriate fixer based on category
                if category == "imports":
                    lines[idx] = fix_imports(lines[idx])
                elif category == "function_call":
                    lines[idx] = fix_function_call(lines[idx])
                elif category == "dictionary":
                    lines[idx] = fix_dictionary(lines[idx])
                elif category == "list":
                    lines[idx] = fix_list(lines[idx])
                elif category == "string":
                    lines[idx] = fix_string(lines[idx])
                elif category == "comments":
                    lines[idx] = fix_comments(lines[idx])
                elif category == "assignment":
                    lines[idx] = fix_assignment(lines[idx])

                # Check if the line was fixed
                if lines[idx] != original_line:
                    fixed_count += 1
                    modified_lines.add(idx)

                    # If the fix resulted in multiple lines, update the line count
                    if lines[idx].count("\n") > original_line.count("\n"):
                        # We need to reanalyze the file after these multi-line fixes
                        if not dry_run:
                            with open(file_path, "w", encoding="utf-8") as f:
                                f.writelines(lines)
                            analysis = analyze_file(file_path)
                            with open(file_path, "r", encoding="utf-8") as f:
                                lines = f.readlines()

    # Make sure all lines end with a newline
    for i in range(len(lines)):
        if not lines[i].endswith("\n"):
            lines[i] += "\n"

    # Write the fixed file
    if not dry_run and fixed_count > 0:
        with open(file_path, "w", encoding="utf-8") as f:
            f.writelines(lines)

    return fixed_count, total_issues


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Analyze and fix line length issues")
    parser.add_argument(
        "paths",
        nargs="*",
        default=DIRECTORIES,
        help="Paths to analyze (default: core directories)",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Fix line length issues (defaults to analysis only)",
    )
    parser.add_argument(
        "--max-length",
        type=int,
        default=MAX_LINE_LENGTH,
        help=f"Maximum line length (default: {MAX_LINE_LENGTH})",
    )
    return parser.parse_args()


def main() -> int:
    """Main entry point."""
    args = parse_args()

    # Update global max line length if specified
    global MAX_LINE_LENGTH
    MAX_LINE_LENGTH = args.max_length

    # Process each specified directory
    all_results = {}
    for path in args.paths:
        if os.path.isdir(path):
            print_colored(f"Analyzing {path}...", BLUE)
            results = analyze_directory(path)
            all_results.update(results)
        elif os.path.isfile(path) and path.endswith(".py"):
            print_colored(f"Analyzing {path}...", BLUE)
            results = analyze_file(path)
            if results:
                all_results[path] = results

    # Print summary
    print_summary(all_results)

    # Fix issues if requested
    if args.fix:
        print_colored("\nFixing line length issues...", BLUE, bold=True)
        total_fixed = 0
        total_issues = 0

        for file_path in sorted(all_results.keys()):
            fixed, issues = fix_line_length(file_path, dry_run=False)
            total_fixed += fixed
            total_issues += issues

            if fixed > 0:
                print_colored(f"  Fixed {fixed}/{issues} issues in {file_path}", GREEN)

        print_colored(
            f"\nTotal: Fixed {total_fixed}/{total_issues} line length issues",
            GREEN,
            bold=True,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
