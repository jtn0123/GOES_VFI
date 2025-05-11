#!/usr/bin/env python3
"""
Fix B907 f-string issues by replacing manually quoted variables with !r formatter.

This script safely refactors Python f-strings that manually place quotes around variables, 
replacing them with the !r conversion flag (which is more maintainable and safer).

Example conversion:
    from: f"Selected model '{self.current_model_key}' does not support tiling."
    to:   f"Selected model {self.current_model_key!r} does not support tiling."

Script features:
- Creates backups before any modifications
- Uses regex pattern matching for targeted replacements
- Safely handles complex expressions
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


def get_fstring_quote_issues(file_path: str) -> List[Tuple[int, str]]:
    """
    Find B907 issues in a file using flake8.
    Returns list of (line_number, error_message) tuples.
    """
    try:
        result = subprocess.run(
            ["flake8", "--select=B907", file_path],
            capture_output=True,
            text=True,
            check=False
        )
        
        issues = []
        for line in result.stdout.splitlines():
            match = re.search(r":(\d+):\d+: B907 '([^']+)' is manually surrounded by quotes", line)
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
    backup_path = path.with_suffix(path.suffix + ".fstring.bak")
    backup_path.write_text(path.read_text())
    return str(backup_path)


def fix_file_fstring_quotes(file_path: str, dry_run: bool = False) -> int:
    """
    Fix B907 issues in a single file.
    Returns the number of fixes applied.
    """
    print_colored(f"\nChecking for f-string issues in {file_path}", BLUE, bold=True)
    
    # Get issues using flake8
    issues = get_fstring_quote_issues(file_path)
    
    if not issues:
        print_colored("No B907 issues found.", GREEN)
        return 0
    
    print_colored(f"Found {len(issues)} f-string issues:", YELLOW)
    for line_num, var_name in issues:
        print(f"  Line {line_num}: Variable '{var_name}' is manually surrounded by quotes")
    
    if dry_run:
        print_colored("Dry run mode - no changes applied.", YELLOW, bold=True)
        return len(issues)
    
    # Create backup
    backup_path = create_backup(file_path)
    print_colored(f"Backup created at {backup_path}", BLUE)
    
    # Read the file
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Track lines that have been fixed
    fixed_count = 0
    
    # Map of variable names to their regex patterns
    # Using a dictionary to handle different cases of the same variable
    var_patterns = {}
    for _, var_name in issues:
        # Escape dots and other special regex characters in variable names
        escaped_var = re.escape(var_name)
        var_patterns[var_name] = escaped_var
    
    # Sort variable names by length (longest first) to handle nested variables correctly
    sorted_vars = sorted(var_patterns.keys(), key=len, reverse=True)
    
    # Process each variable
    for var_name in sorted_vars:
        escaped_var = var_patterns[var_name]
        
        # Pattern: find f-strings with manual quotes around this specific variable
        # This pattern is more precise than a general pattern to avoid false positives
        pattern = fr"f\"([^\"]*)'({escaped_var})'([^\"]*)\""
        
        # Function to replace matched patterns
        def replace_quotes(match):
            prefix = match.group(1)
            var_match = match.group(2)  # This should match var_name
            suffix = match.group(3)
            
            # Construct the new string with !r conversion flag
            return f'f"{prefix}{{{var_match}!r}}{suffix}"'
        
        # Apply the replacement and count changes
        new_content, count = re.subn(pattern, replace_quotes, content)
        if count > 0:
            content = new_content
            fixed_count += count
            print_colored(f"Fixed {count} instances of '{var_name}'", GREEN)
    
    if fixed_count > 0:
        # Write changes back to file
        with open(file_path, 'w') as f:
            f.write(content)
        
        print_colored(f"Fixed {fixed_count} f-string issues in {file_path}", GREEN, bold=True)
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
                total_fixed += fix_file_fstring_quotes(file_path, dry_run)
    return total_fixed


def main() -> int:
    """Main entry point for the script."""
    if len(sys.argv) < 2:
        print_colored("Usage:", BLUE)
        print("python fix_fstring_quotes_enhanced.py [--dry-run] path/to/file.py")
        print("python fix_fstring_quotes_enhanced.py [--dry-run] path/to/directory")
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
        fix_file_fstring_quotes(path, dry_run)
    elif os.path.isdir(path):
        total_fixed = process_directory(path, dry_run)
        print_colored(f"\nTotal f-string issues fixed: {total_fixed}", BLUE, bold=True)
    else:
        print_colored(f"Error: Path not found: {path}", RED)
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())