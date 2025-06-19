#!/usr/bin/env python3
"""Selectively fix files by copying from reference repository."""

import os
import shutil
import sys
from pathlib import Path
from typing import List


def fix_files(file_paths: List[str], ref_dir: Path = Path("temp_reference")) -> None:
    """Fix specific files by copying from reference repository."""
    if not ref_dir.exists():
        print(f"Error: Reference directory {ref_dir} not found!")
        sys.exit(1)

    success_count = 0
    fail_count = 0

    for file_path in file_paths:
        local_file = Path(file_path)
        ref_file = ref_dir / file_path

        print(f"\nProcessing: {file_path}")

        if not ref_file.exists():
            print(f"  ✗ Not found in reference repository")
            fail_count += 1
            continue

        try:
            # Create parent directory if needed
            local_file.parent.mkdir(parents=True, exist_ok=True)

            # Copy file
            shutil.copy2(ref_file, local_file)
            print(f"  ✓ Fixed successfully")
            success_count += 1
        except Exception as e:
            print(f"  ✗ Error: {e}")
            fail_count += 1

    print(f"\n{'='*60}")
    print(f"Summary: {success_count} fixed, {fail_count} failed")


def main():
    """Main function with predefined file groups."""

    # Define file groups
    critical_files = [
        ".github/workflows/ci.yml",
        "CLAUDE.md",
        "README.md",
        "requirements.txt",
    ]

    test_config_files = ["pytest.ini", "test-requirements.txt", "run_all_tests.py"]

    if len(sys.argv) > 1:
        if sys.argv[1] == "critical":
            print("Fixing critical configuration files...")
            fix_files(critical_files)
        elif sys.argv[1] == "test-config":
            print("Fixing test configuration files...")
            fix_files(test_config_files)
        elif sys.argv[1] == "list":
            print("Available groups:")
            print(
                "  critical    - Critical config files (ci.yml, CLAUDE.md, README.md, requirements.txt)"
            )
            print(
                "  test-config - Test configuration (pytest.ini, test-requirements.txt, run_all_tests.py)"
            )
        else:
            # Treat as individual files
            print(f"Fixing specified files...")
            fix_files(sys.argv[1:])
    else:
        print("Usage:")
        print("  python selective_fix.py critical      # Fix critical config files")
        print("  python selective_fix.py test-config   # Fix test config files")
        print("  python selective_fix.py list          # List available groups")
        print("  python selective_fix.py file1 file2  # Fix specific files")


if __name__ == "__main__":
    main()
