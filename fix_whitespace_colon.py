#!/usr/bin/env python3
"""
Fix E203 errors (whitespace before colon) in Python slices.

This script fixes the improper formatting of slice notation with whitespace before colons.
It's a common linting issue especially with older code or mixed formatting styles.

Example conversion:
    from: canvas[y : y + h, x : x + w] += tile * alpha
    to:   canvas[y:y + h, x:x + w] += tile * alpha

Script features:
- Creates backups before any modifications
- Safely handles slice notation in array indexing
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


def get_whitespace_colon_issues(file_path: str) -> List[Tuple[int, str]]:
    """
    Find E203 issues in a file using flake8.
    Returns list of (line_number, error_message) tuples.
    """
    try:
        result = subprocess.run(
            ["flake8", "--select=E203", file_path],
            capture_output=True,
            text=True,
            check=False
        )
        
        issues = []
        for line in result.stdout.splitlines():
            match = re.search(r":(\d+):\d+: E203 ", line)
            if match:
                line_num = int(match.group(1))
                issues.append((line_num, "E203 whitespace before colon"))
        
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
    backup_path = path.with_suffix(path.suffix + ".colon.bak")
    backup_path.write_text(path.read_text())
    return str(backup_path)


def fix_single_line(line: str) -> str:
    """
    Fix whitespace issues before colons in a single line.
    Handles array slices safely.
    """
    # Fix whitespace before colon in slices
    # Look for patterns like "x : y" inside square brackets
    # but be careful not to modify dictionary literals, type hints, etc.
    
    def fix_slices_in_brackets(match):
        bracket_content = match.group(1)
        # Replace whitespace+colon with just colon in bracket content
        fixed_content = re.sub(r'\s+:', ':', bracket_content)
        return '[' + fixed_content + ']'
    
    # Find and fix content inside square brackets
    fixed_line = re.sub(r'\[(.*?)\]', fix_slices_in_brackets, line)
    
    return fixed_line


def fix_file_whitespace_colon(file_path: str, dry_run: bool = False) -> int:
    """
    Fix E203 issues in a single file.
    Returns the number of issues fixed.
    """
    print_colored(f"\nChecking for whitespace before colon issues in {file_path}", BLUE, bold=True)
    
    # Get issues
    issues = get_whitespace_colon_issues(file_path)
    
    if not issues:
        print_colored("No whitespace before colon issues found.", GREEN)
        return 0
    
    print_colored(f"Found {len(issues)} whitespace before colon issues:", YELLOW)
    for line_num, _ in issues:
        print(f"  Line {line_num}: whitespace before colon")
    
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
    
    for line_num, _ in sorted(issues):
        if line_num <= 0 or line_num > len(lines):
            print_colored(f"Warning: Invalid line number {line_num}", RED)
            continue
        
        idx = line_num - 1
        original_line = lines[idx]
        fixed_line = fix_single_line(original_line)
        
        if fixed_line != original_line:
            lines[idx] = fixed_line
            fixed_count += 1
            
            print_colored(f"Fixed line {line_num}:", GREEN)
            print(f"  Original: {original_line.strip()}")
            print(f"  Fixed: {fixed_line.strip()}")
    
    if fixed_count > 0:
        # Write changes back to file
        with open(file_path, 'w') as f:
            f.writelines(lines)
        
        print_colored(f"Fixed {fixed_count} whitespace before colon issues in {file_path}", GREEN, bold=True)
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
                total_fixed += fix_file_whitespace_colon(file_path, dry_run)
    return total_fixed


def main() -> int:
    """Main entry point for the script."""
    if len(sys.argv) < 2:
        print_colored("Usage:", BLUE)
        print("python fix_whitespace_colon.py [--dry-run] path/to/file.py")
        print("python fix_whitespace_colon.py [--dry-run] path/to/directory")
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
        fix_file_whitespace_colon(path, dry_run)
    elif os.path.isdir(path):
        total_fixed = process_directory(path, dry_run)
        print_colored(f"\nTotal whitespace before colon issues fixed: {total_fixed}", BLUE, bold=True)
    else:
        print_colored(f"Error: Path not found: {path}", RED)
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())