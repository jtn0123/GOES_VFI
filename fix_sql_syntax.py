#!/usr/bin/env python3
"""Fix SQL syntax errors and other specific patterns."""

import ast
import re
import shutil
from pathlib import Path


def fix_test_concurrent_operations(filepath):
    """Fix specific issues in test_concurrent_operations.py."""
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    fixed_lines = []

    for i, line in enumerate(lines):
        # Fix line 430 - add missing quote
        if i == 429 and '"INSERT OR REPLACE INTO cache (filepath,' in line:
            fixed_lines.append(line.rstrip() + ' "\n')
        # Fix line 433 - close the string
        elif i == 432 and "timestamp) VALUES (?," in line:
            fixed_lines.append(line.rstrip()[:-1] + '", \n')
        else:
            fixed_lines.append(line)

    return "".join(fixed_lines)


def fix_test_large_dataset(filepath):
    """Fix specific issues in test_large_dataset_processing.py."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Fix lambda syntax - lambda s, should be lambda s:
    content = re.sub(
        r"lambda\s+(\w+),\s*$", r"lambda \1: None", content, flags=re.MULTILINE
    )

    return content


def fix_pipeline_files(filepath):
    """Fix pipeline files with unmatched parentheses."""
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    fixed_lines = []
    skip_next_paren = False

    for i, line in enumerate(lines):
        # Skip standalone closing parens after pass statements
        if line.strip() == ")" and i > 0:
            prev_line = lines[i - 1].strip()
            if prev_line == "pass" or prev_line.endswith(","):
                continue

        fixed_lines.append(line)

    return "".join(fixed_lines)


def fix_sanchez_processor(filepath):
    """Fix sanchez_processor.py escape sequences."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Replace \! with just ! (it's not a valid escape sequence)
    content = content.replace("\\!", "!")

    return content


def main():
    """Fix specific syntax errors in known problem files."""
    fixes = [
        ("tests/unit/test_concurrent_operations.py", fix_test_concurrent_operations),
        ("tests/integration/test_large_dataset_processing.py", fix_test_large_dataset),
        ("goesvfi/pipeline/encode.py", fix_pipeline_files),
        ("goesvfi/pipeline/ffmpeg_builder.py", fix_pipeline_files),
        ("goesvfi/pipeline/image_loader.py", fix_pipeline_files),
        ("goesvfi/pipeline/loader.py", fix_pipeline_files),
        ("goesvfi/pipeline/sanchez_processor.py", fix_sanchez_processor),
        ("goesvfi/pipeline/interpolate.py", fix_pipeline_files),
        ("goesvfi/run_vfi.py", fix_pipeline_files),
        ("goesvfi/gui_integration_patch.py", fix_pipeline_files),
        ("goesvfi/gui_enhancements_integration.py", fix_pipeline_files),
    ]

    fixed = 0
    failed = 0

    for filepath, fix_func in fixes:
        if Path(filepath).exists():
            print(f"Fixing {filepath}...")

            # Backup
            backup_path = filepath + ".sql_backup"
            shutil.copy2(filepath, backup_path)

            try:
                # Apply fix
                content = fix_func(filepath)

                # Write back
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(content)

                # Verify
                with open(filepath, "r") as f:
                    verify_content = f.read()
                ast.parse(verify_content)

                print(f"  ✓ Fixed successfully")
                Path(backup_path).unlink()
                fixed += 1

            except SyntaxError as e:
                # Restore backup
                shutil.move(backup_path, filepath)
                print(f"  ✗ Still has errors: {e}")
                print(f"    Line {e.lineno}: {e.msg}")
                failed += 1
            except Exception as e:
                # Restore backup
                if Path(backup_path).exists():
                    shutil.move(backup_path, filepath)
                print(f"  ✗ Error: {e}")
                failed += 1
        else:
            print(f"⚠ File not found: {filepath}")

    print(f"\nSummary:")
    print(f"  Fixed: {fixed}")
    print(f"  Failed: {failed}")


if __name__ == "__main__":
    main()
