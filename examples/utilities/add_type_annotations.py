#!/usr/bin/env python3
"""
add_type_annotations.py - A utility script to add type annotations to functions.

This script adds basic type annotations to functions in a given file, focusing
on adding `-> None` to methods without return statements and basic parameter types.
"""
import re
import sys
from typing import Any, Dict, List, Optional, Set, Tuple


def read_file(file_path: str) -> str:
    """Read the content of a file."""
    with open(file_path, "r") as f:
        return f.read()


def write_file(file_path: str, content: str) -> None:
    """Write content to a file."""
    with open(file_path, "w") as f:
        f.write(content)


def find_function_defs(content: str) -> List[Tuple[int, str, str]]:
    """Find function definitions in the content.

    Returns:
        List of tuples: (line number, function signature, indentation)
    """
    function_defs = []
    lines = content.split("\n")

    for i, line in enumerate(lines):
        # Match function definitions
        match = re.match(r"^(\s*)def\s+([^(]+)\((.*)\):(.*)", line)
        if match:
            indent, func_name, params, return_type = match.groups()
            # Skip if already has return type annotation
            if "->" in return_type:
                continue
            function_defs.append((i, line, indent))

    return function_defs


def has_return_statement(content: str, start_line: int, indent: str) -> bool:
    """Check if a function has a return statement that returns a value."""
    lines = content.split("\n")
    func_indent_level = len(indent)

    # Find the end of the function
    for i in range(start_line + 1, len(lines)):
        line = lines[i]
        if line.strip() == "":
            continue

        # If we find a line with same or less indentation, we've exited the function
        if line.strip() and len(line) - len(line.lstrip()) <= func_indent_level:
            break

        # Check for return statements that return a value
        if re.match(r"\s*return\s+[^#\s]", line):
            return True

    return False


def guess_param_type(param_name: str) -> str:
    """Guess parameter type based on naming conventions."""
    if param_name in ("self", "cls"):
        return param_name

    # Common naming patterns
    if param_name.endswith("_path"):
        return f"{param_name}: Path"
    elif param_name in ("parent", "widget", "button", "label", "layout", "dialog"):
        return f"{param_name}: Optional[QWidget]"
    elif param_name.endswith("_widget"):
        return f"{param_name}: Optional[QWidget]"
    elif param_name.endswith("_layout"):
        return f"{param_name}: QLayout"
    elif param_name.endswith("_dict"):
        return f"{param_name}: Dict[str, Any]"
    elif param_name.endswith("_list"):
        return f"{param_name}: List[Any]"
    elif param_name.endswith("_str"):
        return f"{param_name}: str"
    elif param_name.endswith("_int"):
        return f"{param_name}: int"
    elif param_name.endswith("_bool"):
        return f"{param_name}: bool"
    elif param_name.endswith("_date") or param_name == "date":
        return f"{param_name}: datetime"
    elif "callback" in param_name or "handler" in param_name:
        return f"{param_name}: Callable[..., Any]"

    # Default cases
    if "=" in param_name:
        base_param, default = param_name.split("=", 1)
        base_param = base_param.strip()
        default = default.strip()

        if default == "None":
            if base_param.startswith(("is_", "has_")):
                return f"{base_param}: Optional[bool] = None"
            return f"{base_param}: Optional[Any] = None"
        elif default in ("True", "False"):
            return f"{base_param}: bool = {default}"
        elif default.isdigit():
            return f"{base_param}: int = {default}"
        elif default.startswith('"') or default.startswith("'"):
            return f"{base_param}: str = {default}"
        elif default.startswith("["):
            return f"{base_param}: List[Any] = {default}"
        elif default.startswith("{"):
            return f"{base_param}: Dict[str, Any] = {default}"

        # For other defaults, try to infer from the parameter name
        if base_param.startswith(("is_", "has_")):
            return f"{base_param}: bool = {default}"

        return param_name  # Keep as is if we can't infer

    # For parameters without defaults
    if param_name.startswith(("is_", "has_")):
        return f"{param_name}: bool"

    # If all else fails
    return f"{param_name}: Any"


def add_type_annotations(file_path: str, dry_run: bool = False) -> str:
    """Add type annotations to functions in a file.

    Args:
        file_path: Path to the file to process
        dry_run: If True, don't write changes to file

    Returns:
        Modified content of the file
    """
    content = read_file(file_path)
    function_defs = find_function_defs(content)

    # Process in reverse to avoid line number changes affecting other replacements
    function_defs.reverse()

    for line_num, line, indent in function_defs:
        # Parse the function signature
        match = re.match(r"^(\s*)def\s+([^(]+)\((.*)\):(.*)", line)
        if not match:
            continue

        indent, func_name, params_str, return_type = match.groups()

        # Add parameter type hints
        typed_params = []
        if params_str.strip():
            for param in params_str.split(","):
                param = param.strip()
                if param and not any(
                    tp in param
                    for tp in [": ", ":Optional[", ":List[", ":Dict[", ":Any"]
                ):
                    typed_params.append(guess_param_type(param))
                else:
                    typed_params.append(param)

        new_params_str = ", ".join(typed_params)

        # Determine return type
        has_return = has_return_statement(content, line_num, indent)
        return_annotation = " -> Any" if has_return else " -> None"

        # Build new function signature
        new_line = f"{indent}def {func_name}({new_params_str}):{return_annotation}:"

        # Replace in content
        lines = content.split("\n")
        lines[line_num] = new_line
        content = "\n".join(lines)

    if not dry_run:
        write_file(file_path, content)

    return content


def main() -> None:
    """Main function to run the script."""
    if len(sys.argv) < 2:
        print("Usage: python add_type_annotations.py <file_path> [--dry-run]")
        sys.exit(1)

    file_path = sys.argv[1]
    dry_run = "--dry-run" in sys.argv

    if dry_run:
        print(f"Performing dry run on {file_path}")
    else:
        print(f"Adding type annotations to {file_path}")

    modified_content = add_type_annotations(file_path, dry_run)

    if dry_run:
        print("\nModified content:")
        print(modified_content)
    else:
        print(f"Successfully added type annotations to {file_path}")


if __name__ == "__main__":
    main()
