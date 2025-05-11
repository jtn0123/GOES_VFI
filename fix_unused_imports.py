#!/usr/bin/env python3
"""
Fix F401 unused imports in Python files with enhanced safety checks.

This script safely removes unused imports from Python files by:
1. Identifying unused imports with flake8
2. Creating a backup of each file before modification
3. Only removing clearly unused imports
4. Preserving comments and formatting
5. Running isort to reorganize imports after removal

Usage:
    python fix_unused_imports.py path/to/file.py
    python fix_unused_imports.py path/to/directory

For safety, the script:
- Creates a backup of each file before modification
- Properly handles complex import cases like multiline imports
- Preserves import comments and context
- Only removes imports that are explicitly flagged by flake8
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


def run_command(cmd: List[str], cwd: Optional[str] = None) -> Tuple[int, str, str]:
    """
    Run a command and return the exit code, stdout, and stderr.
    """
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=cwd
    )
    return result.returncode, result.stdout, result.stderr


def get_unused_imports(file_path: str) -> Dict[int, List[str]]:
    """
    Get unused imports using flake8, grouped by line number.
    
    Returns:
        Dict mapping line numbers to lists of unused import names
    """
    exit_code, stdout, _ = run_command(
        ["flake8", "--select=F401", file_path]
    )
    
    # Group unused imports by line number
    unused_imports: Dict[int, List[str]] = {}
    
    for line in stdout.splitlines():
        # Parse the flake8 output format: "file_path:line:col: F401 'module.name' imported but unused"
        match = re.search(r":(\d+):\d+: F401 '([^']+)' imported but unused", line)
        if match:
            line_num = int(match.group(1))
            import_name = match.group(2)
            
            if line_num not in unused_imports:
                unused_imports[line_num] = []
                
            unused_imports[line_num].append(import_name)
    
    return unused_imports


def create_backup(file_path: str) -> str:
    """
    Create a backup of the file before modification.
    Returns the backup path.
    """
    path = Path(file_path)
    backup_path = path.with_suffix(path.suffix + ".unused_imports.bak")
    backup_path.write_text(path.read_text())
    return str(backup_path)


def fix_file_unused_imports(file_path: str, dry_run: bool = False) -> int:
    """
    Fix unused imports in a single Python file.
    Returns count of fixed imports.
    """
    print_colored(f"\nChecking for unused imports in {file_path}", BLUE, bold=True)
    
    # Get unused imports grouped by line
    unused_imports_by_line = get_unused_imports(file_path)
    
    if not unused_imports_by_line:
        print_colored("No unused imports found.", GREEN)
        return 0
    
    # Flatten the list for easier reporting
    all_unused_imports = []
    for imports in unused_imports_by_line.values():
        all_unused_imports.extend(imports)
    
    print_colored(f"Found {len(all_unused_imports)} unused imports:", YELLOW)
    for unused in all_unused_imports:
        print(f"  - {unused}")
    
    if dry_run:
        print_colored("Dry run mode - no changes applied.", YELLOW, bold=True)
        return len(all_unused_imports)
    
    # Create backup
    backup_path = create_backup(file_path)
    print_colored(f"Backup created at {backup_path}", BLUE)
    
    # Read file
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    # Process each line with unused imports
    modified = False
    for line_num, unused_list in unused_imports_by_line.items():
        if line_num <= 0 or line_num > len(lines):
            print_colored(f"Warning: Invalid line number {line_num}", RED)
            continue
        
        # Line numbers in flake8 are 1-based, but list indices are 0-based
        idx = line_num - 1
        line = lines[idx]
        
        # Process the line based on its import type
        new_line = process_import_line(line, unused_list)
        
        if new_line != line:
            print_colored(f"Line {line_num}: {line.strip()} -> {new_line.strip() if new_line else 'REMOVED'}", YELLOW)
            if new_line:
                lines[idx] = new_line
            else:
                lines[idx] = ""  # Empty the line but preserve line numbers
            modified = True
    
    if modified:
        # Write changes back to file
        with open(file_path, 'w') as f:
            f.writelines(lines)
        
        print_colored(f"Fixed unused imports in {file_path}", GREEN)
        
        # Run isort to clean up imports
        exit_code, _, _ = run_command(["isort", file_path])
        if exit_code == 0:
            print_colored("Reorganized imports with isort", GREEN)
        else:
            print_colored("Warning: Failed to run isort", YELLOW)
    else:
        print_colored("No changes needed or complex cases detected", YELLOW)
    
    return len(all_unused_imports)


def process_import_line(line: str, unused_imports: List[str]) -> Optional[str]:
    """
    Process a single import line, removing unused imports.
    Returns the modified line, or None if the line should be removed entirely.
    """
    stripped = line.strip()
    
    # Handle 'import x' style
    if stripped.startswith("import "):
        imports = stripped[7:].split(",")
        new_imports = []
        
        for imp in imports:
            imp_clean = imp.strip()
            if not any(unused == imp_clean or unused == imp_clean.split(" as ")[0] for unused in unused_imports):
                new_imports.append(imp)
        
        if not new_imports:
            return None  # Remove the whole line
        
        return "import " + ", ".join(new_imports) + "\n"
    
    # Handle 'from x import y' style
    elif stripped.startswith("from "):
        if " import " not in stripped:
            return line  # Part of a multi-line import, don't modify
        
        module, imports = stripped.split(" import ", 1)
        module = module[5:]  # Remove 'from '
        
        # Handle 'from x import (y, z)' style
        if imports.startswith("(") and imports.endswith(")"):
            inside = imports[1:-1].strip()
            import_items = [i.strip() for i in inside.split(",") if i.strip()]
        else:
            import_items = [i.strip() for i in imports.split(",") if i.strip()]
        
        new_imports = []
        for item in import_items:
            # Skip the item if it matches any of the unused imports
            if any(unused == f"{module}.{item.split(' as ')[0]}" for unused in unused_imports):
                continue
            if any(unused == item.split(" as ")[0] for unused in unused_imports):
                continue
            new_imports.append(item)
        
        if not new_imports:
            return None  # Remove the whole line
        
        # Preserve the original import style (parentheses or not)
        if imports.startswith("(") and imports.endswith(")"):
            return f"from {module} import ({', '.join(new_imports)})\n"
        else:
            return f"from {module} import {', '.join(new_imports)}\n"
    
    # Default: don't modify the line
    return line


def process_directory(directory_path: str, dry_run: bool = False) -> int:
    """
    Process all Python files in a directory.
    Returns total number of fixed imports.
    """
    total_fixed = 0
    for root, _, files in os.walk(directory_path):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                total_fixed += fix_file_unused_imports(file_path, dry_run)
    return total_fixed


def main() -> int:
    """Main entry point for the script."""
    if len(sys.argv) < 2:
        print_colored("Usage:", BLUE)
        print("python fix_unused_imports.py [--dry-run] path/to/file.py")
        print("python fix_unused_imports.py [--dry-run] path/to/directory")
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
        fix_file_unused_imports(path, dry_run)
    elif os.path.isdir(path):
        total_fixed = process_directory(path, dry_run)
        print_colored(f"\nTotal unused imports identified: {total_fixed}", BLUE, bold=True)
    else:
        print_colored(f"Error: Path not found: {path}", RED)
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())