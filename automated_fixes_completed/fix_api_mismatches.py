#!/usr/bin/env python3
"""Script to fix common API mismatches in test files."""

import re
import sys
from pathlib import Path

# API changes mapping
API_CHANGES = {
    # S3Store/CDNStore method name changes
    r"\.exists\(": ".check_file_exists(",
    r"\.download\(": ".download_file(",
    r"mock\.exists": "mock.check_file_exists",
    r"mock\.download": "mock.download_file",
    # AsyncMock fixes
    r"AsyncMock\(\)\.return_value": "AsyncMock(return_value=True)",
    # Common mock attribute fixes
    r"mock_s3_store\.exists": "mock_s3_store.check_file_exists",
    r"mock_cdn_store\.exists": "mock_cdn_store.check_file_exists",
}


def fix_file(file_path):
    """Fix API mismatches in a single file."""
    print(f"\nProcessing {file_path}...")

    with open(file_path, "r") as f:
        content = f.read()

    original_content = content
    changes_made = []

    for pattern, replacement in API_CHANGES.items():
        new_content = re.sub(pattern, replacement, content)
        if new_content != content:
            # Count how many replacements were made
            count = len(re.findall(pattern, content))
            changes_made.append(
                f"  - Replaced {count} instances of '{pattern}' with '{replacement}'"
            )
            content = new_content

    if content != original_content:
        with open(file_path, "w") as f:
            f.write(content)
        print(f"  ✓ Fixed {len(changes_made)} API patterns:")
        for change in changes_made:
            print(change)
        return True
    else:
        print("  ✓ No API mismatches found")
        return False


def main():
    """Main function."""
    if len(sys.argv) > 1:
        files = [Path(f) for f in sys.argv[1:]]
    else:
        # Default files with known API issues
        files = [
            Path("tests/unit/test_remote_stores.py"),
            Path("tests/unit/test_s3_store_critical.py"),
            Path("tests/unit/test_enhanced_view_model.py"),
            Path("tests/unit/test_s3_retry_strategy.py"),
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
