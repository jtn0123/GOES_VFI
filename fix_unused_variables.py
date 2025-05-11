#!/usr/bin/env python3
"""
Fix F841 errors (local variable assigned but never used) in Python files.

This script identifies local variables that are assigned but never used
and comments them out or prepends with an underscore to suppress the warning.

Example conversion:
    from: rife_exe = config.find_rife_executable(...)
    to:   # Unused: rife_exe = config.find_rife_executable(...)
    or:   _rife_exe = config.find_rife_executable(...)

Script features:
- Creates backups before any modifications
- Safely handles variable assignments without breaking code
- Uses flake8 to identify unused variables
- Can operate on specific files or entire directories
- Provides dry-run mode to preview changes
"""

import os
import re
import sys
import subprocess
from pathlib import Path
from typing import List, Optional, Set, Tuple

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


def get_unused_variables(file_path: str) -> List[Tuple[int, str]]:
    """
    Find F841 issues in a file using flake8.
    Returns list of (line_number, variable_name) tuples.
    """
    try:
        result = subprocess.run(
            ["flake8", "--select=F841", file_path],
            capture_output=True,
            text=True,
            check=False
        )
        
        issues = []
        for line in result.stdout.splitlines():
            match = re.search(r":(\d+):\d+: F841 local variable '([^']+)' is assigned to but never used", line)
            if match:
                line_num = int(match.group(1))
                var_name = match.group(2)
                issues.append((line_num, var_name))
        
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
    backup_path = path.with_suffix(path.suffix + ".unused_vars.bak")
    backup_path.write_text(path.read_text())
    return str(backup_path)


def fix_file_unused_variables(file_path: str, dry_run: bool = False, comment_style: bool = False) -> int:
    """
    Fix F841 issues in a single file.
    
    Args:
        file_path: Path to the file to process
        dry_run: If True, don't actually change the file
        comment_style: If True, comment out unused variables; if False, prefix with underscore
        
    Returns:
        The number of fixes applied
    """
    print_colored(f"\nChecking for unused variables in {file_path}", BLUE, bold=True)
    
    # Get unused variables
    issues = get_unused_variables(file_path)
    
    if not issues:
        print_colored("No unused variables found.", GREEN)
        return 0
    
    print_colored(f"Found {len(issues)} unused variables:", YELLOW)
    for line_num, var_name in issues:
        print(f"  Line {line_num}: '{var_name}'")
    
    if dry_run:
        print_colored("Dry run mode - no changes applied.", YELLOW, bold=True)
        return len(issues)
    
    # Create backup
    backup_path = create_backup(file_path)
    print_colored(f"Backup created at {backup_path}", BLUE)
    
    # Read the file as lines
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    # Process each issue
    fixed_count = 0
    for line_num, var_name in issues:
        if line_num <= 0 or line_num > len(lines):
            print_colored(f"Warning: Invalid line number {line_num}", RED)
            continue
        
        # Convert line number to 0-based index
        idx = line_num - 1
        line = lines[idx]
        
        # Check if variable is directly assigned (not part of a tuple/list unpacking)
        direct_assign_pattern = fr"(\s*)({var_name}\s*=\s*.+)"
        match = re.search(direct_assign_pattern, line)
        
        if match:
            indentation = match.group(1)
            assignment = match.group(2)
            
            if comment_style:
                # Comment out the unused variable
                new_line = f"{indentation}# Unused: {assignment}\n"
            else:
                # Prepend underscore to variable name
                new_line = re.sub(fr"\b{var_name}\b", f"_{var_name}", line)
            
            lines[idx] = new_line
            fixed_count += 1
            print_colored(f"Fixed line {line_num}: {line.strip()} -> {new_line.strip()}", GREEN)
        else:
            # Handle more complex cases (tuple unpacking, etc.)
            print_colored(f"Complex variable assignment at line {line_num}, manual review required", YELLOW)
            print(f"  {line.strip()}")
    
    if fixed_count > 0:
        # Write changes back to file
        with open(file_path, 'w') as f:
            f.writelines(lines)
        
        print_colored(f"Fixed {fixed_count} unused variables in {file_path}", GREEN, bold=True)
    else:
        print_colored("No changes made - complex variable assignments require manual review", YELLOW)
    
    return fixed_count


def process_directory(directory_path: str, dry_run: bool = False, comment_style: bool = False) -> int:
    """
    Process all Python files in a directory.
    Returns total number of fixes applied.
    """
    total_fixed = 0
    for root, _, files in os.walk(directory_path):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                total_fixed += fix_file_unused_variables(file_path, dry_run, comment_style)
    return total_fixed


def main() -> int:
    """Main entry point for the script."""
    if len(sys.argv) < 2:
        print_colored("Usage:", BLUE)
        print("python fix_unused_variables.py [--dry-run] [--comment] path/to/file.py")
        print("python fix_unused_variables.py [--dry-run] [--comment] path/to/directory")
        print("\nOptions:")
        print("  --dry-run  : Show changes without applying them")
        print("  --comment  : Comment out unused variables instead of prefixing with underscore")
        return 1
    
    args = sys.argv[1:]
    dry_run = False
    comment_style = False
    
    if "--dry-run" in args:
        dry_run = True
        args.remove("--dry-run")
    
    if "--comment" in args:
        comment_style = True
        args.remove("--comment")
    
    if not args:
        print_colored("Error: No path specified", RED)
        return 1
    
    path = args[0]
    
    if os.path.isfile(path):
        fix_file_unused_variables(path, dry_run, comment_style)
    elif os.path.isdir(path):
        total_fixed = process_directory(path, dry_run, comment_style)
        print_colored(f"\nTotal unused variables fixed: {total_fixed}", BLUE, bold=True)
    else:
        print_colored(f"Error: Path not found: {path}", RED)
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())