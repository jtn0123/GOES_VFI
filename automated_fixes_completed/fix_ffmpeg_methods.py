#!/usr/bin/env python3
"""Fix FFmpeg method name mismatches in tests."""

import re
import sys
from pathlib import Path


def fix_file(file_path):
    """Fix FFmpeg method name issues in a test file."""
    print(f"\nProcessing {file_path}...")

    with open(file_path, "r") as f:
        content = f.read()

    original_content = content
    changes_made = []

    # Fix: set_pixel_format -> set_pix_fmt
    if "set_pixel_format" in content:
        content = content.replace("set_pixel_format", "set_pix_fmt")
        changes_made.append("Changed set_pixel_format to set_pix_fmt")

    # Fix other potential method name issues
    method_fixes = {
        "set_input_file": "set_input",
        "set_output_file": "set_output",
        "set_frame_rate": "set_framerate",
    }

    for old_method, new_method in method_fixes.items():
        if old_method in content:
            content = content.replace(old_method, new_method)
            changes_made.append(f"Changed {old_method} to {new_method}")

    if content != original_content:
        with open(file_path, "w") as f:
            f.write(content)
        print(f"  ✓ Applied {len(changes_made)} fixes:")
        for change in changes_made:
            print(f"    - {change}")
        return True
    else:
        print("  ✓ No fixes needed")
        return False


def main():
    """Main function."""
    if len(sys.argv) > 1:
        files = [Path(f) for f in sys.argv[1:]]
    else:
        # Find test files that use FFmpeg
        files = [
            Path("tests/unit/test_encode.py"),
            Path("tests/unit/test_ffmpeg_builder.py"),
            Path("tests/unit/test_ffmpeg_builder_critical.py"),
        ]

    fixed_count = 0
    for file_path in files:
        if file_path.exists():
            try:
                if fix_file(file_path):
                    fixed_count += 1
            except Exception as e:
                print(f"  ✗ Error processing file: {e}")
        else:
            print(f"File not found: {file_path}")

    print(f"\n✓ Fixed {fixed_count} files")


if __name__ == "__main__":
    main()
