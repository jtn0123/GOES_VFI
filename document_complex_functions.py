#!/usr/bin/env python3
"""
Document complex functions (C901) with TODO comments for future refactoring.

This script identifies functions with high cyclomatic complexity (C901 errors)
and adds structured TODO comments that document refactoring options without
changing the function behavior or structure.

Example addition:
    # TODO: This function has high cyclomatic complexity (19) and should be refactored.
    # Consider breaking into smaller helper functions for:
    # 1. Settings validation logic
    # 2. UI state updates
    # 3. Configuration handling

Script features:
- Creates backups before any modifications
- Safely adds comments without changing function behavior
- Provides specific refactoring suggestions based on function name and content
- Can operate on specific files or entire directories
- Provides dry-run mode to preview changes
"""

import os
import re
import sys
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Union

# ANSI color constants
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"


def print_colored(message: str, color: str = RESET, bold: bool = False) -> None:
    """Print a message with color."""
    if bold:
        print(f"{BOLD}{color}{message}{RESET}")
    else:
        print(f"{color}{message}{RESET}")


def get_complex_functions(file_path: str) -> List[Tuple[int, str, int]]:
    """
    Find C901 issues in a file using flake8.
    Returns list of (line_number, function_name, complexity) tuples.
    """
    try:
        result = subprocess.run(
            ["flake8", "--select=C901", file_path],
            capture_output=True,
            text=True,
            check=False
        )
        
        issues = []
        for line in result.stdout.splitlines():
            match = re.search(r":(\d+):\d+: C901 '([^']+)' is too complex \((\d+)\)", line)
            if match:
                line_num = int(match.group(1))
                func_name = match.group(2)
                complexity = int(match.group(3))
                issues.append((line_num, func_name, complexity))
        
        return issues
    
    except Exception as e:
        print_colored(f"Error running flake8: {e}", RED)
        return []


def create_backup(file_path: str) -> str:
    """
    Create a backup of the file before modification.
    Returns the backup path.
    """
    path = Path(file_path)
    backup_path = path.with_suffix(path.suffix + ".complex_func.bak")
    backup_path.write_text(path.read_text())
    return str(backup_path)


def generate_refactoring_suggestions(func_name: str, file_content: str) -> List[str]:
    """
    Generate custom refactoring suggestions based on the function name and content.
    Returns a list of suggestion strings.
    """
    suggestions = []
    
    # Common patterns based on function name
    if "update" in func_name.lower():
        suggestions.append("Separate update logic for different components/states")
    
    if "check" in func_name.lower() or "validate" in func_name.lower():
        suggestions.append("Split validation logic into separate validators for each condition")
    
    if "save" in func_name.lower() or "load" in func_name.lower():
        suggestions.append("Separate serialization logic from business logic")
        suggestions.append("Create helper functions for different data categories")
    
    if "handle" in func_name.lower() or "on_" in func_name.lower():
        suggestions.append("Use a command pattern or state machine for event handling")
        suggestions.append("Extract specific handlers for different event types")
    
    if "gui" in func_name.lower() or "ui" in func_name.lower():
        suggestions.append("Extract UI component initialization into separate methods")
        suggestions.append("Separate layout management from state management")
    
    # Add some default suggestions if we couldn't generate any specific ones
    if not suggestions:
        # Common patterns for any complex function
        suggestions = [
            "Extract conditional blocks into separate helper functions",
            "Consider using helper classes to group related functionality",
            "Extract repeated code patterns into utility functions"
        ]
    
    return suggestions


def add_todo_comment(file_path: str, issues: List[Tuple[int, str, int]], dry_run: bool = False) -> int:
    """
    Add TODO comments to complex functions.
    Returns the number of functions documented.
    """
    # Read file
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    fixed_count = 0
    line_offset = 0  # Keep track of added lines
    
    for line_num, func_name, complexity in issues:
        # Adjust line number for any offset from previous additions
        adjusted_line = line_num + line_offset
        
        if adjusted_line <= 0 or adjusted_line > len(lines):
            print_colored(f"Warning: Invalid line number {adjusted_line}", RED)
            continue
        
        # Check if there's already a TODO comment for this function
        if adjusted_line > 1 and "TODO: This function has high cyclomatic complexity" in lines[adjusted_line - 2]:
            print_colored(f"Function '{func_name}' already has a TODO comment", YELLOW)
            continue
        
        # Generate refactoring suggestions
        file_content = "".join(lines)
        suggestions = generate_refactoring_suggestions(func_name, file_content)
        
        # Create the TODO comment
        todo_comment = [
            f"    # TODO: This function has high cyclomatic complexity ({complexity}) and should be refactored.\n",
            "    # Consider breaking into smaller helper functions for:\n"
        ]
        
        # Add numbered suggestions
        for i, suggestion in enumerate(suggestions, 1):
            todo_comment.append(f"    # {i}. {suggestion}\n")
        
        if dry_run:
            print_colored(f"Would add TODO comment for '{func_name}' at line {adjusted_line}:", BLUE)
            for line in todo_comment:
                print(line.strip())
            print()
            continue
        
        # Insert comments before the function definition
        for i, comment_line in enumerate(todo_comment):
            lines.insert(adjusted_line - 1, comment_line)
            line_offset += 1
        
        fixed_count += 1
        print_colored(f"Added TODO comment for function '{func_name}'", GREEN)
    
    if fixed_count > 0 and not dry_run:
        # Write changes back to file
        with open(file_path, 'w') as f:
            f.writelines(lines)
    
    return fixed_count


def fix_file_complex_functions(file_path: str, dry_run: bool = False) -> int:
    """
    Document complex functions in a single file.
    Returns the number of functions documented.
    """
    print_colored(f"\nChecking for complex functions in {file_path}", BLUE, bold=True)
    
    # Get complex functions
    issues = get_complex_functions(file_path)
    
    if not issues:
        print_colored("No complex functions found.", GREEN)
        return 0
    
    print_colored(f"Found {len(issues)} complex functions:", YELLOW)
    for line_num, func_name, complexity in issues:
        print(f"  Line {line_num}: '{func_name}' has complexity {complexity}")
    
    if dry_run:
        add_todo_comment(file_path, issues, dry_run=True)
        print_colored("Dry run mode - no changes applied.", YELLOW, bold=True)
        return len(issues)
    
    # Create backup
    backup_path = create_backup(file_path)
    print_colored(f"Backup created at {backup_path}", BLUE)
    
    # Add TODO comments
    fixed_count = add_todo_comment(file_path, issues, dry_run=False)
    
    if fixed_count > 0:
        print_colored(f"Added TODO comments to {fixed_count} functions in {file_path}", GREEN, bold=True)
    else:
        print_colored("No functions were modified", YELLOW)
    
    return fixed_count


def process_directory(directory_path: str, dry_run: bool = False) -> int:
    """
    Process all Python files in a directory.
    Returns total number of documented functions.
    """
    total_fixed = 0
    for root, _, files in os.walk(directory_path):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                total_fixed += fix_file_complex_functions(file_path, dry_run)
    return total_fixed


def main() -> int:
    """Main entry point for the script."""
    if len(sys.argv) < 2:
        print_colored("Usage:", BLUE)
        print("python document_complex_functions.py [--dry-run] path/to/file.py")
        print("python document_complex_functions.py [--dry-run] path/to/directory")
        return 1
    
    args = sys.argv[1:]
    dry_run = False
    
    if "--dry-run" in args:
        dry_run = True
        args.remove("--dry-run")
    
    if not args:
        print_colored("Error: No path specified", RED)
        return 1
    
    path = args[0]
    
    if os.path.isfile(path):
        fix_file_complex_functions(path, dry_run)
    elif os.path.isdir(path):
        total_fixed = process_directory(path, dry_run)
        print_colored(f"\nTotal complex functions documented: {total_fixed}", BLUE, bold=True)
    else:
        print_colored(f"Error: Path not found: {path}", RED)
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())