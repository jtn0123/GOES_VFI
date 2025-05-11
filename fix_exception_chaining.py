#!/usr/bin/env python3
"""
Fix B904 errors by properly chaining exceptions in except blocks.

This script identifies and fixes improper exception raising in except blocks by:
- Converting `raise NewError(...)` to `raise NewError(...) from err`
- This maintains the exception chain and helps with debugging

Example conversion:
    from:
        except IOError as e:
            raise ValueError(f"Failed to read file: {e}")
    to:
        except IOError as e:
            raise ValueError(f"Failed to read file: {e}") from e

Script features:
- Creates backups before any modifications
- Safely handles different exception raising patterns
- Maintains original error messages and formatting
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


def get_exception_chain_issues(file_path: str) -> List[Tuple[int, str]]:
    """
    Find B904 issues in a file using flake8.
    Returns list of (line_number, error_message) tuples.
    """
    try:
        result = subprocess.run(
            ["flake8", "--select=B904", file_path],
            capture_output=True,
            text=True,
            check=False
        )
        
        issues = []
        for line in result.stdout.splitlines():
            match = re.search(r":(\d+):\d+: B904 ", line)
            if match:
                line_num = int(match.group(1))
                issues.append((line_num, "B904 exception chaining issue"))
        
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
    backup_path = path.with_suffix(path.suffix + ".exception.bak")
    backup_path.write_text(path.read_text())
    return str(backup_path)


def fix_file_exception_chaining(file_path: str, dry_run: bool = False) -> int:
    """
    Fix B904 issues in a single file.
    Returns the number of issues fixed.
    """
    print_colored(f"\nChecking for exception chaining issues in {file_path}", BLUE, bold=True)
    
    # Get issues
    issues = get_exception_chain_issues(file_path)
    
    if not issues:
        print_colored("No exception chaining issues found.", GREEN)
        return 0
    
    print_colored(f"Found {len(issues)} exception chaining issues:", YELLOW)
    for line_num, _ in issues:
        print(f"  Line {line_num}: exception chaining issue")
    
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
    
    # Sort issues by line number in reverse order to avoid index shifting
    sorted_issues = sorted(issues, key=lambda x: x[0], reverse=True)
    
    for line_num, _ in sorted_issues:
        if line_num <= 0 or line_num > len(lines):
            print_colored(f"Warning: Invalid line number {line_num}", RED)
            continue
        
        # Get the problematic line and check if it is within an except block
        idx = line_num - 1
        line = lines[idx]
        
        # Find the except statement that contains this line
        except_line_idx = None
        except_var_name = None
        
        # Search backwards for the enclosing except statement
        for i in range(idx, max(0, idx - 20), -1):
            if re.search(r'^\s*except\s+', lines[i]):
                except_line_idx = i
                # Extract the exception variable name
                except_match = re.search(r'except\s+[^:]+\s+as\s+(\w+):', lines[i])
                if except_match:
                    except_var_name = except_match.group(1)
                break
        
        if except_line_idx is None or except_var_name is None:
            print_colored(f"Warning: Could not find enclosing except block with variable for line {line_num}", YELLOW)
            continue
        
        # Now check if this line is raising an exception without chaining
        raise_match = re.search(r'^\s*raise\s+(\w+)\(', line)
        if raise_match:
            exception_type = raise_match.group(1)
            
            # Check if the line already has proper exception chaining
            if f"from {except_var_name}" in line or "from None" in line:
                print_colored(f"Line {line_num} already has proper exception chaining", YELLOW)
                continue
            
            # Fix it: Add the "from err" part right before the closing parenthesis or any comment
            # Handle common cases where raise might have multiple closing parentheses
            
            # Find the position of the last closing parenthesis before any comment
            orig_line = line
            comment_pos = line.find('#')
            close_paren_pos = line.rfind(')')
            
            if comment_pos != -1 and close_paren_pos > comment_pos:
                # Comment is inside a string in the exception message
                pass
            elif comment_pos != -1:
                # Only search for closing paren before the comment
                close_paren_pos = line[:comment_pos].rfind(')')
            
            if close_paren_pos == -1:
                print_colored(f"Warning: Could not find closing parenthesis in line {line_num}", RED)
                continue
            
            # Insert "from except_var_name" before the closing parenthesis
            fixed_line = line[:close_paren_pos] + f") from {except_var_name}" + line[close_paren_pos + 1:]
            
            lines[idx] = fixed_line
            fixed_count += 1
            
            print_colored(f"Fixed line {line_num}:", GREEN)
            print(f"  Original: {orig_line.strip()}")
            print(f"  Fixed: {fixed_line.strip()}")
    
    if fixed_count > 0:
        # Write changes back to file
        with open(file_path, 'w') as f:
            f.writelines(lines)
        
        print_colored(f"Fixed {fixed_count} exception chaining issues in {file_path}", GREEN, bold=True)
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
                total_fixed += fix_file_exception_chaining(file_path, dry_run)
    return total_fixed


def main() -> int:
    """Main entry point for the script."""
    if len(sys.argv) < 2:
        print_colored("Usage:", BLUE)
        print("python fix_exception_chaining.py [--dry-run] path/to/file.py")
        print("python fix_exception_chaining.py [--dry-run] path/to/directory")
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
        fix_file_exception_chaining(path, dry_run)
    elif os.path.isdir(path):
        total_fixed = process_directory(path, dry_run)
        print_colored(f"\nTotal exception chaining issues fixed: {total_fixed}", BLUE, bold=True)
    else:
        print_colored(f"Error: Path not found: {path}", RED)
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())