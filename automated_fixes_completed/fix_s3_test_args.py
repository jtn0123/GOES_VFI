#!/usr/bin/env python3
"""Fix S3Store test argument issues."""

import re
import sys
from pathlib import Path


def fix_file(file_path):
    """Fix S3Store method call arguments."""
    print(f"\nProcessing {file_path}...")

    with open(file_path, "r") as f:
        content = f.read()

    original_content = content

    # Fix download_file calls with keyword arguments
    # Pattern: download_file(ts=..., satellite=..., dest_path=...)
    # Replace with: download_file(..., ..., ...)
    pattern = r"download_file\(\s*ts\s*=\s*([^,]+),\s*satellite\s*=\s*([^,]+),\s*dest_path\s*=\s*([^)]+)\)"
    replacement = r"download_file(\1, \2, \3)"
    content = re.sub(pattern, replacement, content)

    # Fix check_file_exists calls with keyword arguments
    pattern = r"check_file_exists\(\s*ts\s*=\s*([^,]+),\s*satellite\s*=\s*([^)]+)\)"
    replacement = r"check_file_exists(\1, \2)"
    content = re.sub(pattern, replacement, content)

    if content != original_content:
        with open(file_path, "w") as f:
            f.write(content)
        print("  ✓ Fixed method call arguments")
        return True
    else:
        print("  ✓ No fixes needed")
        return False


def main():
    """Main function."""
    if len(sys.argv) > 1:
        files = [Path(f) for f in sys.argv[1:]]
    else:
        files = [
            Path("tests/unit/test_s3_store_critical.py"),
            Path("tests/unit/test_s3_retry_strategy.py"),
            Path("tests/unit/test_s3_retry_strategy_fixed.py"),
        ]

    fixed_count = 0
    for file_path in files:
        if file_path.exists():
            if fix_file(file_path):
                fixed_count += 1
        else:
            print(f"File not found: {file_path}")

    print(f"\n✓ Fixed {fixed_count} files")


if __name__ == "__main__":
    main()
