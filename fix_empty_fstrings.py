#!/usr/bin/env python3
"""
Fix F541 errors (f-strings without any placeholders) by replacing them with regular strings.

This script safely converts f-strings that don't have any variables or expressions
to regular strings, which is more efficient and clearer.

Example conversion:
    from: f"This will cause settings to be saved in different locations!"
    to:   "This will cause settings to be saved in different locations!"

Script features:
- Creates backups before any modifications
- Uses regex pattern matching for targeted replacements
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


def get_empty_fstring_issues(file_path: str) -> List[Tuple[int, str]]:
    """
    Find F541 issues in a file using flake8.
    Returns list of (line_number, error_description) tuples.
    """
    try:
        result = subprocess.run(
            ["flake8", "--select=F541", file_path],
            capture_output=True,
            text=True,
            check=False
        )
        
        issues = []
        for line in result.stdout.splitlines():
            match = re.search(r":(\d+):\d+: F541 f-string is missing placeholders", line)
            if match:
                line_num = int(match.group(1))
                issues.append((line_num, "f-string is missing placeholders"))
        
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
    backup_path = path.with_suffix(path.suffix + ".empty_fstring.bak")
    backup_path.write_text(path.read_text())
    return str(backup_path)


def fix_file_empty_fstrings(file_path: str, dry_run: bool = False) -> int:
    """
    Fix F541 issues in a single file.
    Returns the number of fixes applied.
    """
    print_colored(f"\nChecking for empty f-string issues in {file_path}", BLUE, bold=True)
    
    # Get issues using flake8
    issues = get_empty_fstring_issues(file_path)
    
    if not issues:
        print_colored("No F541 issues found.", GREEN)
        return 0
    
    print_colored(f"Found {len(issues)} empty f-string issues:", YELLOW)
    for line_num, desc in issues:
        print(f"  Line {line_num}: {desc}")
    
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
    for line_num, _ in issues:
        if line_num <= 0 or line_num > len(lines):
            print_colored(f"Warning: Invalid line number {line_num}", RED)
            continue
        
        # Convert line number to 0-based index
        idx = line_num - 1
        line = lines[idx]
        
        # Replace f-strings without placeholders with regular strings
        # Two common patterns:
        # 1. f"text without {} placeholders"
        # 2. f'text without {} placeholders'
        
        # Handle double-quoted f-strings
        pattern_double = r'f"([^{}"]*)"'
        new_line, count1 = re.subn(pattern_double, r'"\1"', line)
        
        # Handle single-quoted f-strings
        pattern_single = r"f'([^{}']*)')"
        new_line, count2 = re.subn(pattern_single, r"'\1')", new_line)
        
        # Only update if we made changes
        if count1 > 0 or count2 > 0:
            lines[idx] = new_line
            fixed_count += 1
            print_colored(f"Fixed line {line_num}: {line.strip()} -> {new_line.strip()}", GREEN)
    
    if fixed_count > 0:
        # Write changes back to file
        with open(file_path, 'w') as f:
            f.writelines(lines)
        
        print_colored(f"Fixed {fixed_count} empty f-string issues in {file_path}", GREEN, bold=True)
    else:
        print_colored("No changes needed or issues couldn't be automatically fixed", YELLOW)
    
    return fixed_count


def process_directory(directory_path: str, dry_run: bool = False) -> int:
    """
    Process all Python files in a directory.
    Returns total number of fixed issues.
    """
    total_fixed = 0
    for root, _, files in os.walk(directory_path):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                total_fixed += fix_file_empty_fstrings(file_path, dry_run)
    return total_fixed


def main() -> int:
    """Main entry point for the script."""
    if len(sys.argv) < 2:
        print_colored("Usage:", BLUE)
        print("python fix_empty_fstrings.py [--dry-run] path/to/file.py")
        print("python fix_empty_fstrings.py [--dry-run] path/to/directory")
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
        fix_file_empty_fstrings(path, dry_run)
    elif os.path.isdir(path):
        total_fixed = process_directory(path, dry_run)
        print_colored(f"\nTotal empty f-string issues fixed: {total_fixed}", BLUE, bold=True)
    else:
        print_colored(f"Error: Path not found: {path}", RED)
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())