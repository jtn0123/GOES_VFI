#!/usr/bin/env python3
"""
Targeted linting fix tool for GOES-VFI codebase.

This script fixes specific linting issues in the codebase:
1. Unused imports
2. Line length issues
3. f-string formatting issues
4. String literal quotes

Usage:
    python targeted_lint_fix.py clean-imports PATH
    python targeted_lint_fix.py fix-line-length PATH
    python targeted_lint_fix.py fix-fstrings PATH
    python targeted_lint_fix.py all PATH

Examples:
    python targeted_lint_fix.py clean-imports goesvfi/gui.py
    python targeted_lint_fix.py all goesvfi/gui.py
"""

import argparse
import importlib.util
import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

import isort
import pyflakes.api
import pyflakes.reporter


class ImportCollector:
    """Simple visitor to collect import statements that are unused."""

    def __init__(self):
        self.unused_imports = set()

    def record_unused_import(self, name):
        """Record an unused import."""
        self.unused_imports.add(name)


def get_unused_imports(file_path: str) -> Set[str]:
    """
    Get unused imports from a Python file using pyflakes.
    
    Args:
        file_path: Path to the Python file to check
        
    Returns:
        A set of unused import names
    """
    collector = ImportCollector()
    reporter = pyflakes.reporter.Reporter(collector.record_unused_import, None)
    pyflakes.api.checkPath(file_path, reporter)
    return collector.unused_imports


def clean_imports(file_path: str) -> int:
    """
    Remove unused imports from a Python file.
    
    Args:
        file_path: Path to the Python file to clean
        
    Returns:
        Number of imports removed
    """
    print(f"Cleaning imports in {file_path}...")
    
    # Make a backup
    path = Path(file_path)
    backup_path = path.with_suffix(path.suffix + ".bak")
    backup_path.write_text(path.read_text())
    print(f"Backup created at {backup_path}")
    
    # Get unused imports
    unused_imports = get_unused_imports(file_path)
    if not unused_imports:
        print("No unused imports found.")
        return 0
    
    # Read the file
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    # Process the lines to remove unused imports
    new_lines = []
    imports_removed = 0
    skip_next = False
    
    for i, line in enumerate(lines):
        if skip_next:
            skip_next = False
            continue
            
        # Handle simple import statements
        if re.match(r'^\s*import\s+', line):
            # Get all imported names
            match = re.match(r'^\s*import\s+(.*)', line)
            if match:
                imports = match.group(1).split(',')
                new_imports = []
                for imp in imports:
                    imp = imp.strip()
                    if imp not in unused_imports and imp.split('.')[0] not in unused_imports:
                        new_imports.append(imp)
                    else:
                        imports_removed += 1
                        print(f"Removing unused import: {imp}")
                
                if new_imports:
                    # Reconstruct import statement with remaining imports
                    new_lines.append(f"import {', '.join(new_imports)}\n")
                else:
                    # Skip this line if all imports are unused
                    imports_removed += 1
            else:
                new_lines.append(line)
                
        # Handle from ... import ... statements
        elif re.match(r'^\s*from\s+', line):
            # Handle multiline imports
            if '(' in line and ')' not in line:
                # This is a multiline import
                from_part = line
                imports_part = ""
                j = i + 1
                multiline_complete = False
                
                # Collect all lines until the closing parenthesis
                while j < len(lines) and not multiline_complete:
                    if ')' in lines[j]:
                        imports_part += lines[j].split(')')[0]
                        multiline_complete = True
                    else:
                        imports_part += lines[j]
                    j += 1
                
                if multiline_complete:
                    # Extract module name and imported names
                    module_match = re.match(r'^\s*from\s+([\w.]+)\s+import\s+\(\s*', from_part)
                    if module_match:
                        module_name = module_match.group(1)
                        
                        # Extract names from imports_part
                        names = re.findall(r'([A-Za-z0-9_]+)[,\s\n]*', imports_part)
                        new_names = []
                        
                        for name in names:
                            full_name = f"{module_name}.{name}"
                            if full_name not in unused_imports and name not in unused_imports:
                                new_names.append(name)
                            else:
                                imports_removed += 1
                                print(f"Removing unused import: {full_name}")
                        
                        if new_names:
                            # Reconstruct multiline import
                            if len(new_names) > 3:  # Keep multiline format if more than 3 imports
                                new_lines.append(f"from {module_name} import (\n")
                                for name in new_names[:-1]:
                                    new_lines.append(f"    {name},\n")
                                new_lines.append(f"    {new_names[-1]},\n")
                                new_lines.append(")\n")
                            else:  # Use inline format for few imports
                                new_lines.append(f"from {module_name} import {', '.join(new_names)}\n")
                        
                        # Skip the lines we've processed
                        skip_next = True
                        for _ in range(j - i - 1):
                            skip_next = True
                    else:
                        new_lines.append(line)
                else:
                    new_lines.append(line)
            else:
                # This is a single line import
                match = re.match(r'^\s*from\s+([\w.]+)\s+import\s+(.*)', line)
                if match:
                    module_name, imports_str = match.groups()
                    imports = [i.strip() for i in imports_str.split(',')]
                    
                    new_imports = []
                    for imp in imports:
                        full_name = f"{module_name}.{imp}"
                        if full_name not in unused_imports and imp not in unused_imports:
                            new_imports.append(imp)
                        else:
                            imports_removed += 1
                            print(f"Removing unused import: {full_name}")
                    
                    if new_imports:
                        new_lines.append(f"from {module_name} import {', '.join(new_imports)}\n")
                    else:
                        imports_removed += 1
                else:
                    new_lines.append(line)
        else:
            new_lines.append(line)
    
    # Write the file back
    with open(file_path, 'w') as f:
        f.writelines(new_lines)
    
    # Run isort to organize imports nicely
    isort.file(file_path)
    
    print(f"Removed {imports_removed} unused imports.")
    return imports_removed


def fix_line_length(file_path: str, max_length: int = 88) -> int:
    """
    Fix lines that are too long in a Python file.
    
    Args:
        file_path: Path to the Python file to fix
        max_length: Maximum line length (default: 88)
        
    Returns:
        Number of lines fixed
    """
    print(f"Fixing line length issues in {file_path}...")
    
    # Make a backup
    path = Path(file_path)
    backup_path = path.with_suffix(path.suffix + ".bak")
    backup_path.write_text(path.read_text())
    print(f"Backup created at {backup_path}")
    
    # Read the file
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    # Process the lines to fix line length issues
    new_lines = []
    lines_fixed = 0
    
    for line in lines:
        line_stripped = line.rstrip('\n')
        
        if len(line_stripped) <= max_length:
            new_lines.append(line)
            continue
        
        # Skip comment lines and strings - add noqa comment
        if line_stripped.strip().startswith('#') or '"""' in line_stripped or "'''" in line_stripped:
            if "# noqa" not in line_stripped:
                new_lines.append(line_stripped + "  # noqa: E501\n")
                lines_fixed += 1
            else:
                new_lines.append(line)
            continue
            
        # Handle function calls and expressions with commas
        if ',' in line_stripped and '(' in line_stripped and ')' in line_stripped:
            # Extract the indentation
            indent = len(line_stripped) - len(line_stripped.lstrip())
            additional_indent = 4  # Additional indentation for continuation lines
            
            # Split at commas
            parts = []
            current_part = ""
            in_string = False
            string_char = None
            
            for char in line_stripped:
                if char in ('"', "'") and (not in_string or string_char == char):
                    in_string = not in_string
                    if in_string:
                        string_char = char
                    else:
                        string_char = None
                
                if char == ',' and not in_string:
                    parts.append(current_part + char)
                    current_part = ""
                else:
                    current_part += char
                    
            if current_part:
                parts.append(current_part)
                
            # Reassemble with line breaks
            if parts:
                # Handle special case: function call
                if '(' in parts[0] and not parts[0].strip().startswith('('):
                    # Function call or similar structure
                    func_part = parts[0].split('(')[0] + '('
                    remainder = parts[0].split('(', 1)[1]
                    
                    new_lines.append(func_part + '\n')
                    
                    for i, part in enumerate(parts):
                        if i == 0:
                            part = remainder
                        
                        if i == len(parts) - 1:
                            new_lines.append(' ' * (indent + additional_indent) + part.lstrip() + '\n')
                        else:
                            new_lines.append(' ' * (indent + additional_indent) + part.lstrip() + '\n')
                else:
                    # Regular line with commas
                    for i, part in enumerate(parts):
                        if i == 0:
                            new_lines.append(part + '\n')
                        else:
                            new_lines.append(' ' * (indent + additional_indent) + part.lstrip() + '\n')
                            
                lines_fixed += 1
            else:
                new_lines.append(line)
        elif '=' in line_stripped and not line_stripped.strip().startswith('#'):
            # Variable assignment
            before_eq, after_eq = line_stripped.split('=', 1)
            
            # Extract indentation
            indent = len(line_stripped) - len(line_stripped.lstrip())
            
            new_lines.append(before_eq + '=\n')
            new_lines.append(' ' * (indent + 4) + after_eq.lstrip() + '\n')
            lines_fixed += 1
        else:
            # Add noqa comment
            if "# noqa" not in line_stripped:
                new_lines.append(line_stripped + "  # noqa: E501\n")
                lines_fixed += 1
            else:
                new_lines.append(line)
    
    # Write the file back
    with open(file_path, 'w') as f:
        f.writelines(new_lines)
    
    print(f"Fixed {lines_fixed} line length issues.")
    return lines_fixed


def fix_fstrings(file_path: str) -> int:
    """
    Fix f-string formatting issues in a Python file.
    
    Args:
        file_path: Path to the Python file to fix
        
    Returns:
        Number of f-strings fixed
    """
    print(f"Fixing f-string formatting in {file_path}...")
    
    # Make a backup
    path = Path(file_path)
    backup_path = path.with_suffix(path.suffix + ".bak")
    backup_path.write_text(path.read_text())
    print(f"Backup created at {backup_path}")
    
    # Read the file
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Fix f-strings with manually quoted variables
    # Example: f"Found {len(results)} items for '{query}'" -> f"Found {len(results)} items for {query!r}"
    pattern = r"f([\"'])(.*?)['](.*?)([\"'])(.*?)\\1"
    replacement = r"f\1\2{\3!r}\5\1"
    
    # First, gather all matches to avoid nested replacements
    matches = list(re.finditer(pattern, content))
    fstrings_fixed = 0
    
    # Apply replacements from the end to avoid indices changing
    for match in reversed(matches):
        var_name = match.group(3)
        
        # Make sure it's a valid variable name
        if re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', var_name):
            start, end = match.span()
            new_str = re.sub(
                r"['](.*?)[']", 
                r"{\1!r}", 
                match.group(0)
            )
            content = content[:start] + new_str + content[end:]
            fstrings_fixed += 1
    
    # Write the file back
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"Fixed {fstrings_fixed} f-string formatting issues.")
    return fstrings_fixed


def main() -> None:
    """Main function."""
    parser = argparse.ArgumentParser(description="Fix linting issues in Python files")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Clean imports command
    clean_imports_parser = subparsers.add_parser("clean-imports", help="Remove unused imports")
    clean_imports_parser.add_argument("path", help="Path to the Python file or directory")
    
    # Fix line length command
    fix_line_length_parser = subparsers.add_parser("fix-line-length", help="Fix lines that are too long")
    fix_line_length_parser.add_argument("path", help="Path to the Python file or directory")
    fix_line_length_parser.add_argument("--max-length", type=int, default=88, help="Maximum line length")
    
    # Fix f-strings command
    fix_fstrings_parser = subparsers.add_parser("fix-fstrings", help="Fix f-string formatting issues")
    fix_fstrings_parser.add_argument("path", help="Path to the Python file or directory")
    
    # All command
    all_parser = subparsers.add_parser("all", help="Run all fixes")
    all_parser.add_argument("path", help="Path to the Python file or directory")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    path = Path(args.path)
    
    if not path.exists():
        print(f"Path does not exist: {path}")
        return
    
    files = []
    if path.is_file():
        files = [path]
    elif path.is_dir():
        files = list(path.glob("**/*.py"))
    
    if not files:
        print(f"No Python files found at {path}")
        return
    
    for file in files:
        print(f"\nProcessing {file}...")
        
        if args.command == "clean-imports" or args.command == "all":
            clean_imports(str(file))
        
        if args.command == "fix-line-length" or args.command == "all":
            max_length = getattr(args, "max_length", 88)
            fix_line_length(str(file), max_length)
        
        if args.command == "fix-fstrings" or args.command == "all":
            fix_fstrings(str(file))


if __name__ == "__main__":
    main()