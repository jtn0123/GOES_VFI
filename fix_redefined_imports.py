#!/usr/bin/env python3
"""
Fix F811 errors (redefinition of unused imports) in Python files.

This script identifies and fixes cases where an import is redefined elsewhere in the file:
- Removes redundant imports that redefine modules already imported earlier
- Comments out the redundant imports to make them easy to identify

Example conversion:
    from:
        import logging
        ...
        import logging  # F811 redefinition of unused 'logging' from line 12
    to:
        import logging
        ...
        # Removed redundant import: import logging

Script features:
- Creates backups before any modifications
- Identifies duplicate imports in the same file
- Uses comments to mark removed imports for clarity
- Provides dry-run mode to preview changes
"""

import os
import re
import sys
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

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


def get_redefined_imports(file_path: str) -> List[Tuple[int, str, int]]:
    """
    Find F811 issues in a file using flake8.
    Returns list of (line_number, import_name, original_line) tuples.
    """
    try:
        result = subprocess.run(
            ["flake8", "--select=F811", file_path],
            capture_output=True,
            text=True,
            check=False
        )
        
        issues = []
        for line in result.stdout.splitlines():
            match = re.search(r":(\d+):\d+: F811 redefinition of unused '([^']+)' from line (\d+)", line)
            if match:
                line_num = int(match.group(1))
                import_name = match.group(2)
                original_line = int(match.group(3))
                issues.append((line_num, import_name, original_line))
        
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
    backup_path = path.with_suffix(path.suffix + ".f811.bak")
    backup_path.write_text(path.read_text())
    return str(backup_path)


def fix_file_redefined_imports(file_path: str, dry_run: bool = False) -> int:
    """
    Fix F811 issues in a single file.
    Returns the number of issues fixed.
    """
    print_colored(f"\nChecking for redefined import issues in {file_path}", BLUE, bold=True)
    
    # Get issues
    issues = get_redefined_imports(file_path)
    
    if not issues:
        print_colored("No redefined import issues found.", GREEN)
        return 0
    
    print_colored(f"Found {len(issues)} redefined import issues:", YELLOW)
    for line_num, import_name, original_line in issues:
        print(f"  Line {line_num}: redefinition of unused '{import_name}' from line {original_line}")
    
    if dry_run:
        print_colored("Dry run mode - no changes applied.", YELLOW, bold=True)
        return len(issues)
    
    # Create backup
    backup_path = create_backup(file_path)
    print_colored(f"Backup created at {backup_path}", BLUE)
    
    # Read the file
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    # Process issues
    fixed_count = 0
    
    # Process lines from bottom to top to avoid index shifting issues
    for line_num, import_name, original_line in sorted(issues, key=lambda x: x[0], reverse=True):
        if line_num <= 0 or line_num > len(lines):
            print_colored(f"Warning: Invalid line number {line_num}", RED)
            continue
        
        idx = line_num - 1
        original_line_content = lines[idx]
        
        # Check if this is a direct import like "import logging"
        direct_import_match = re.search(rf"\bimport\s+{re.escape(import_name)}\b", original_line_content)
        
        # Check if this is a from-import like "from module import name"
        from_import_match = re.search(rf"from\s+([^\s]+)\s+import\s+.*\b{re.escape(import_name)}\b", original_line_content)
        
        # If neither pattern matched, try to handle mixed imports like "from x import (a, b, c)"
        if not direct_import_match and not from_import_match:
            # Try to handle various import forms as best we can
            comment = f"# Removed redundant import of '{import_name}' (original import at line {original_line})"
            
            # Just comment out the whole line as fallback
            new_line = f"# {original_line_content.rstrip()}  {comment}\n"
            
            lines[idx] = new_line
            fixed_count += 1
            
            print_colored(f"Fixed line {line_num}:", GREEN)
            print(f"  Original: {original_line_content.strip()}")
            print(f"  Fixed: {new_line.strip()}")
        else:
            # Handle direct imports or from-imports
            comment = f"# Removed redundant import of '{import_name}' (original import at line {original_line})"
            
            if direct_import_match:
                new_line = f"{comment}\n"
            else:
                # For from-imports, we need to be more careful
                # Just comment out the whole line for now
                new_line = f"# {original_line_content.rstrip()}  {comment}\n"
            
            lines[idx] = new_line
            fixed_count += 1
            
            print_colored(f"Fixed line {line_num}:", GREEN)
            print(f"  Original: {original_line_content.strip()}")
            print(f"  Fixed: {new_line.strip()}")
    
    if fixed_count > 0:
        # Write changes back to file
        with open(file_path, 'w') as f:
            f.writelines(lines)
        
        print_colored(f"Fixed {fixed_count} redefined import issues in {file_path}", GREEN, bold=True)
    else:
        print_colored("No changes needed or issues couldn't be automatically fixed", YELLOW)
    
    return fixed_count


def process_directory(directory_path: str, dry_run: bool = False) -> int:
    """
    Process all Python files in a directory.
    Returns total number of issues fixed.
    """
    total_fixed = 0
    for root, _, files in os.walk(directory_path):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                total_fixed += fix_file_redefined_imports(file_path, dry_run)
    return total_fixed


def main() -> int:
    """Main entry point for the script."""
    if len(sys.argv) < 2:
        print_colored("Usage:", BLUE)
        print("python fix_redefined_imports.py [--dry-run] path/to/file.py")
        print("python fix_redefined_imports.py [--dry-run] path/to/directory")
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
        fix_file_redefined_imports(path, dry_run)
    elif os.path.isdir(path):
        total_fixed = process_directory(path, dry_run)
        print_colored(f"\nTotal redefined import issues fixed: {total_fixed}", BLUE, bold=True)
    else:
        print_colored(f"Error: Path not found: {path}", RED)
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())