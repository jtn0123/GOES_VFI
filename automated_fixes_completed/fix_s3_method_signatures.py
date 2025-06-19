#!/usr/bin/env python3
"""Fix S3Store method signatures to remove unsupported parameters."""

import re
import sys
from pathlib import Path


def fix_file(file_path):
    """Fix S3Store method calls with unsupported parameters."""
    print(f"\nProcessing {file_path}...")

    with open(file_path, "r") as f:
        content = f.read()

    original_content = content

    # Fix download_file calls - remove product_type and band parameters
    # Handle multi-line calls by using DOTALL flag
    # Pattern: download_file(..., product_type=..., band=...)
    pattern = r"(download_file\(\s*[^,]+,\s*[^,]+,\s*[^,)]+),\s*product_type=[^,)]+(?:,\s*band=[^,)]+)?(\s*\))"
    content = re.sub(pattern, r"\1\2", content, flags=re.DOTALL)

    # Also fix the case where only product_type is present
    pattern = (
        r"(download_file\(\s*[^,]+,\s*[^,]+,\s*[^,)]+),\s*product_type=[^,)]+(\s*\))"
    )
    content = re.sub(pattern, r"\1\2", content, flags=re.DOTALL)

    # Also fix the case where only band is present
    pattern = r"(download_file\(\s*[^,]+,\s*[^,]+,\s*[^,)]+),\s*band=[^,)]+(\s*\))"
    content = re.sub(pattern, r"\1\2", content, flags=re.DOTALL)

    # Fix check_file_exists calls - remove product_type and band parameters
    pattern = r"(check_file_exists\(\s*[^,]+,\s*[^,)]+),\s*product_type=[^,)]+(?:,\s*band=[^,)]+)?(\s*\))"
    content = re.sub(pattern, r"\1\2", content, flags=re.DOTALL)

    # Also fix cases where only one parameter is present
    pattern = r"(check_file_exists\(\s*[^,]+,\s*[^,)]+),\s*product_type=[^,)]+(\s*\))"
    content = re.sub(pattern, r"\1\2", content, flags=re.DOTALL)

    pattern = r"(check_file_exists\(\s*[^,]+,\s*[^,)]+),\s*band=[^,)]+(\s*\))"
    content = re.sub(pattern, r"\1\2", content, flags=re.DOTALL)

    if content != original_content:
        with open(file_path, "w") as f:
            f.write(content)
        print("  ✓ Fixed S3Store method signatures")
        return True
    else:
        print("  ✓ No S3Store signature fixes needed")
        return False


def main():
    """Main function."""
    if len(sys.argv) > 1:
        files = [Path(f) for f in sys.argv[1:]]
    else:
        files = [
            Path("tests/unit/test_real_s3_store.py"),
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
