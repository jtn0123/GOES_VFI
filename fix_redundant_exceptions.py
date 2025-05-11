#!/usr/bin/env python3
"""
Fix B014 errors (redundant exception types) in Python except blocks.

This script identifies and fixes redundant exception types in except blocks by:
- Simplifying exception tuples where one type is a subclass of another
- Following the guidance "Write `except BaseType:`, which catches exactly the same exceptions."

Example conversion:
    from: except (IOError, BrokenPipeError):
    to:   except IOError:  # BrokenPipeError is a subclass of IOError

Script features:
- Creates backups before any modifications
- Analyzes exception hierarchies to find redundancies
- Adds helpful comments explaining the simplification
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


def get_redundant_exception_issues(file_path: str) -> List[Tuple[int, str]]:
    """
    Find B014 issues in a file using flake8.
    Returns list of (line_number, error_message) tuples.
    """
    try:
        result = subprocess.run(
            ["flake8", "--select=B014", file_path],
            capture_output=True,
            text=True,
            check=False
        )
        
        issues = []
        for line in result.stdout.splitlines():
            match = re.search(r":(\d+):\d+: B014 Redundant exception types in `(.+?)`", line)
            if match:
                line_num = int(match.group(1))
                error_msg = match.group(2)
                issues.append((line_num, error_msg))
        
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
    backup_path = path.with_suffix(path.suffix + ".exceptions.bak")
    backup_path.write_text(path.read_text())
    return str(backup_path)


def parse_exception_message(message: str) -> Tuple[str, str, str]:
    """
    Parse the flake8 error message to extract the exception types and recommendation.
    
    Example input: "except (IOError, BrokenPipeError):. Write `except IOError:`, which catches exactly the same exceptions."
    Returns: ("except (IOError, BrokenPipeError):", "IOError", "BrokenPipeError")
    """
    # Extract the original except clause
    original_except = message.split(".")[0].strip()
    
    # Extract the recommended exception type
    match = re.search(r"Write `except ([^:]+):", message)
    if match:
        recommended_type = match.group(1)
    else:
        recommended_type = ""
    
    # Extract the redundant exception type
    match = re.search(r"except \(([^,]+),\s*([^)]+)\)", original_except)
    if match:
        # If we can't determine which is redundant, assume the second one is redundant
        redundant_type = match.group(2).strip()
    else:
        redundant_type = ""
    
    return original_except, recommended_type, redundant_type


def fix_file_redundant_exceptions(file_path: str, dry_run: bool = False) -> int:
    """
    Fix B014 issues in a single file.
    Returns the number of issues fixed.
    """
    print_colored(f"\nChecking for redundant exception types in {file_path}", BLUE, bold=True)
    
    # Get issues
    issues = get_redundant_exception_issues(file_path)
    
    if not issues:
        print_colored("No redundant exception types found.", GREEN)
        return 0
    
    print_colored(f"Found {len(issues)} redundant exception type issues:", YELLOW)
    for line_num, error_msg in issues:
        print(f"  Line {line_num}: {error_msg}")
    
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
    for line_num, error_msg in sorted(issues, key=lambda x: x[0], reverse=True):
        if line_num <= 0 or line_num > len(lines):
            print_colored(f"Warning: Invalid line number {line_num}", RED)
            continue
        
        idx = line_num - 1
        original_line = lines[idx]
        
        # Parse the error message to extract pattern and recommendation
        except_clause, recommended_type, redundant_type = parse_exception_message(error_msg)
        
        # Check if the pattern is in the line
        if except_clause in original_line:
            # Replace the pattern with the recommended except statement
            # Also add a comment about the redundant exception
            comment = f"  # {redundant_type} is a subclass of {recommended_type}"
            fixed_line = original_line.replace(except_clause, f"except {recommended_type}:") 
            
            # Add the comment if it doesn't already end with a comment
            if "#" not in fixed_line:
                # Insert the comment before any trailing whitespace and newline
                fixed_line = fixed_line.rstrip() + comment + "\n"
            
            lines[idx] = fixed_line
            fixed_count += 1
            
            print_colored(f"Fixed line {line_num}:", GREEN)
            print(f"  Original: {original_line.strip()}")
            print(f"  Fixed: {fixed_line.strip()}")
        else:
            print_colored(f"Warning: Could not match pattern '{except_clause}' in line {line_num}", YELLOW)
            print(f"  Line content: {original_line.strip()}")
    
    if fixed_count > 0:
        # Write changes back to file
        with open(file_path, 'w') as f:
            f.writelines(lines)
        
        print_colored(f"Fixed {fixed_count} redundant exception type issues in {file_path}", GREEN, bold=True)
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
                total_fixed += fix_file_redundant_exceptions(file_path, dry_run)
    return total_fixed


def main() -> int:
    """Main entry point for the script."""
    if len(sys.argv) < 2:
        print_colored("Usage:", BLUE)
        print("python fix_redundant_exceptions.py [--dry-run] path/to/file.py")
        print("python fix_redundant_exceptions.py [--dry-run] path/to/directory")
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
        fix_file_redundant_exceptions(path, dry_run)
    elif os.path.isdir(path):
        total_fixed = process_directory(path, dry_run)
        print_colored(f"\nTotal redundant exception type issues fixed: {total_fixed}", BLUE, bold=True)
    else:
        print_colored(f"Error: Path not found: {path}", RED)
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())