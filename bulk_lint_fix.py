#!/usr/bin/env python3
"""
Bulk linting fix script for GOES-VFI codebase.

This script automates fixing common linting issues across the codebase:
1. Trailing whitespace
2. Missing final newlines
3. Import sorting using isort
4. Code formatting using Black
5. Basic flake8 issues where possible

Usage:
    python bulk_lint_fix.py [--directory DIR] [--backup] [--dry-run]

Options:
    --directory DIR  Process only files in this directory (default: goesvfi)
    --backup         Create backups of modified files
    --dry-run        Show what would be fixed without making changes
"""

import argparse
import os
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Fix common linting issues")
    parser.add_argument(
        "--directory", "-d", default="goesvfi", help="Directory to process"
    )
    parser.add_argument(
        "--backup", "-b", action="store_true", help="Create backups before fixing"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Just print what would be fixed"
    )
    return parser.parse_args()


def find_python_files(directory: str) -> List[Path]:
    """Find all Python files in the given directory."""
    directory_path = Path(directory)
    return sorted(directory_path.glob("**/*.py"))


def create_backup(file_path: Path, backup_dir: str = "linting_backups") -> None:
    """Create a backup of the file before modifying it."""
    backup_path = Path(backup_dir) / file_path.relative_to(file_path.anchor)
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(file_path, backup_path)
    print(f"Created backup: {backup_path}")


def run_command(
    command: List[str], dry_run: bool = False
) -> Tuple[bool, Optional[str]]:
    """Run a command and return its success status and output."""
    cmd_str = " ".join(command)
    if dry_run:
        print(f"Would run: {cmd_str}")
        return True, None

    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error running {cmd_str}: {e}")
        print(f"stdout: {e.stdout}")
        print(f"stderr: {e.stderr}")
        return False, None


def fix_trailing_whitespace(file_path: Path, dry_run: bool) -> bool:
    """Fix trailing whitespace in a file."""
    if dry_run:
        print(f"Would fix trailing whitespace in {file_path}")
        return True

    try:
        with open(file_path, "r") as f:
            content = f.read()

        # Fix trailing whitespace
        fixed_content = "\n".join(line.rstrip() for line in content.splitlines())

        # Ensure file ends with a newline
        if not fixed_content.endswith("\n"):
            fixed_content += "\n"

        if fixed_content != content:
            with open(file_path, "w") as f:
                f.write(fixed_content)
            print(f"Fixed whitespace issues in {file_path}")
            return True
        return False
    except Exception as e:
        print(f"Error fixing whitespace in {file_path}: {e}")
        return False


def fix_file(file_path: Path, backup: bool, dry_run: bool) -> None:
    """Apply all fixes to a single file."""
    if backup:
        create_backup(file_path)

    # Fix whitespace issues
    fix_trailing_whitespace(file_path, dry_run)

    # Run isort
    run_command(["isort", "--profile", "black", str(file_path)], dry_run)

    # Run black
    run_command(["black", "--line-length=88", str(file_path)], dry_run)


def main() -> None:
    """Main function to process files and apply fixes."""
    args = parse_args()

    # Ensure backup directory exists if needed
    if args.backup:
        os.makedirs("linting_backups", exist_ok=True)

    # Find Python files
    files = find_python_files(args.directory)
    print(f"Found {len(files)} Python files in {args.directory}")

    # Process each file
    for file_path in files:
        print(f"Processing {file_path}")
        fix_file(file_path, args.backup, args.dry_run)

    print("Done!")


if __name__ == "__main__":
    main()
