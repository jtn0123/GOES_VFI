#!/usr/bin/env python3
"""Fix files one by one by copying from reference repository."""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional


def get_modified_files() -> List[str]:
    """Get list of modified files from git status."""
    result = subprocess.run(
        ["git", "status", "--porcelain"], capture_output=True, text=True
    )

    modified_files = []
    for line in result.stdout.strip().split("\n"):
        if line and line.strip():
            # Extract filename (skip status flags)
            parts = line.strip().split(maxsplit=1)
            if len(parts) > 1:
                status = parts[0]
                filename = parts[1].strip('"')
                # Only include modified files (M flag), not new files (??)
                if "M" in status:
                    modified_files.append(filename)

    return modified_files


def show_diff(local_path: str, ref_path: str) -> bool:
    """Show diff between files and return True if they differ."""
    if not os.path.exists(ref_path):
        print(f"  ✗ File doesn't exist in reference repository")
        return False

    result = subprocess.run(
        ["diff", "-u", ref_path, local_path], capture_output=True, text=True
    )

    if result.returncode == 0:
        return False
    else:
        lines = result.stdout.split("\n")
        if len(lines) > 20:
            print(f"  Showing first 20 lines of {len(lines)} total differences:")
            for line in lines[:20]:
                print(f"  {line}")
            print("  ...")
        else:
            for line in lines:
                print(f"  {line}")
        return True


def fix_file(local_path: str, ref_path: str) -> bool:
    """Copy file from reference to local."""
    try:
        shutil.copy2(ref_path, local_path)
        print(f"  ✓ File fixed successfully")
        return True
    except Exception as e:
        print(f"  ✗ Error fixing file: {e}")
        return False


def process_file(
    file_path: str, ref_dir: Path, auto_fix: bool = False
) -> Optional[bool]:
    """Process a single file."""
    local_file = Path(file_path)
    ref_file = ref_dir / file_path

    print(f"\n{'='*60}")
    print(f"File: {file_path}")
    print("=" * 60)

    if not local_file.exists():
        print("  ✗ Local file doesn't exist")
        return None

    if not ref_file.exists():
        print("  ✗ Reference file doesn't exist")
        return None

    # Check if files differ
    has_diff = show_diff(str(local_file), str(ref_file))

    if not has_diff:
        print("  ✓ Files are identical")
        return True

    if auto_fix:
        return fix_file(str(local_file), str(ref_file))
    else:
        # Ask user
        while True:
            response = input("\n  Fix this file? [y/n/q]: ").lower().strip()
            if response == "y":
                return fix_file(str(local_file), str(ref_file))
            elif response == "n":
                print("  Skipped")
                return False
            elif response == "q":
                return None
            else:
                print("  Please enter y, n, or q")


def main():
    """Main function."""
    ref_dir = Path("temp_reference")

    if not ref_dir.exists():
        print("Error: Reference repository not found in temp_reference/")
        print("Please ensure the reference repo has been cloned.")
        sys.exit(1)

    # Get modified files
    modified_files = get_modified_files()

    if not modified_files:
        print("No modified files found.")
        return

    print(f"Found {len(modified_files)} modified files.")

    # Ask for mode
    print("\nOptions:")
    print("1. Interactive mode (review each file)")
    print("2. Auto-fix all files")
    print("3. List files only")

    mode = input("\nSelect mode [1/2/3]: ").strip()

    if mode == "3":
        print("\nModified files:")
        for i, file_path in enumerate(modified_files, 1):
            print(f"{i:3d}. {file_path}")
        return

    auto_fix = mode == "2"

    # Process files
    fixed_count = 0
    skipped_count = 0

    for i, file_path in enumerate(modified_files, 1):
        print(f"\nProgress: {i}/{len(modified_files)}")

        result = process_file(file_path, ref_dir, auto_fix)

        if result is None:
            if not auto_fix:
                print("\nQuitting...")
                break
        elif result:
            fixed_count += 1
        else:
            skipped_count += 1

    # Summary
    print(f"\n{'='*60}")
    print("Summary:")
    print(f"  Fixed: {fixed_count}")
    print(f"  Skipped: {skipped_count}")
    print(f"  Total: {len(modified_files)}")


if __name__ == "__main__":
    main()
