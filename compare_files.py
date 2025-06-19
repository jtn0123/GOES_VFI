#!/usr/bin/env python3
"""Compare files between local and reference repository."""

import os
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple


def get_modified_files() -> List[str]:
    """Get list of modified files from git status."""
    result = subprocess.run(
        ["git", "status", "--porcelain"], capture_output=True, text=True
    )

    modified_files = []
    for line in result.stdout.strip().split("\n"):
        if line:
            # Extract filename (skip status flags)
            parts = line.strip().split(maxsplit=1)
            if len(parts) > 1:
                filename = parts[1].strip('"')
                # Skip files that don't exist in reference
                if not filename.startswith("??"):
                    modified_files.append(filename)

    return modified_files


def compare_file(local_path: str, ref_path: str) -> Tuple[bool, List[str]]:
    """Compare two files and return differences."""
    if not os.path.exists(ref_path):
        return False, ["File doesn't exist in reference repository"]

    result = subprocess.run(
        ["diff", "-u", ref_path, local_path], capture_output=True, text=True
    )

    if result.returncode == 0:
        return True, []
    else:
        return False, result.stdout.split("\n")


def main():
    """Main function to compare files."""
    ref_dir = Path("temp_reference")

    if not ref_dir.exists():
        print("Error: Reference repository not found in temp_reference/")
        sys.exit(1)

    # Get modified files
    modified_files = get_modified_files()

    if not modified_files:
        print("No modified files found.")
        return

    print(f"Found {len(modified_files)} modified files.\n")

    # Compare each file
    for i, file_path in enumerate(modified_files, 1):
        print(f"\n{'='*60}")
        print(f"File {i}/{len(modified_files)}: {file_path}")
        print("=" * 60)

        local_file = Path(file_path)
        ref_file = ref_dir / file_path

        if local_file.exists():
            identical, differences = compare_file(str(local_file), str(ref_file))

            if identical:
                print("✓ File is identical to reference")
            else:
                print("✗ File has differences:")
                if len(differences) > 50:
                    print(f"  (Showing first 50 lines of {len(differences)} total)")
                    for line in differences[:50]:
                        print(f"  {line}")
                else:
                    for line in differences:
                        print(f"  {line}")
        else:
            print("✗ File exists locally but not in current directory")


if __name__ == "__main__":
    main()
