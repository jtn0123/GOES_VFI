#!/usr/bin/env python3
"""Final targeted fixes for remaining syntax errors."""

import ast
import re
import shutil
from pathlib import Path


def fix_test_download_band13(filepath):
    """Fix test_download_band13.py specific issues."""
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Fix line 214: remove extra quote
    for i in range(len(lines)):
        if "{dest_path}\"'" in lines[i]:
            lines[i] = lines[i].replace("{dest_path}\"'", '{dest_path}"')

    # Fix duplicate else statements
    i = 0
    while i < len(lines) - 1:
        if (
            lines[i].strip() == "else:"
            and i + 1 < len(lines)
            and lines[i + 1].strip() == "else:"
        ):
            # Remove the duplicate and the pass that follows
            lines.pop(i + 1)
            if i + 1 < len(lines) and lines[i + 1].strip() == "pass":
                lines.pop(i + 1)
        i += 1

    # Also check around line 297-299 for the same issue
    for i in range(len(lines)):
        if i < len(lines) and "{dest_path}\"'" in lines[i]:
            lines[i] = lines[i].replace("{dest_path}\"'", '{dest_path}"')

    with open(filepath, "w", encoding="utf-8") as f:
        f.writelines(lines)


def fix_test_real_s3_store(filepath):
    """Fix test_real_s3_store.py specific issues."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Fix the unterminated string on line 211
    # The issue is a missing opening quote before "skipping"
    content = re.sub(r'skipping download test"', r'"skipping download test"', content)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)


def fix_test_integrity_tab_performance(filepath):
    """Fix test_integrity_tab_performance.py specific issues."""
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Fix line 498: missing f-string prefix
    for i in range(len(lines)):
        if i < len(lines) and "{metrics['peak_memory']:.2f} MB (peak)\"" in lines[i]:
            # Add f prefix to the string
            lines[i] = lines[i].replace(
                "{metrics['peak_memory']:.2f} MB (peak)\"",
                "f\"{metrics['peak_memory']:.2f} MB (peak)\"",
            )

    with open(filepath, "w", encoding="utf-8") as f:
        f.writelines(lines)


def main():
    """Fix the remaining syntax errors."""
    fixes = [
        ("tests/unit/test_download_band13.py", fix_test_download_band13),
        ("tests/unit/test_real_s3_store.py", fix_test_real_s3_store),
        (
            "tests/integration/test_integrity_tab_performance.py",
            fix_test_integrity_tab_performance,
        ),
    ]

    for filepath, fix_func in fixes:
        if Path(filepath).exists():
            print(f"Fixing {filepath}...")

            # Backup
            backup_path = filepath + ".final_backup"
            shutil.copy2(filepath, backup_path)

            try:
                # Apply fix
                fix_func(filepath)

                # Verify
                with open(filepath, "r") as f:
                    content = f.read()
                ast.parse(content)

                print(f"  ✓ Fixed successfully")
                Path(backup_path).unlink()

            except SyntaxError as e:
                # Restore backup
                shutil.move(backup_path, filepath)
                print(f"  ✗ Still has errors: {e}")
                print(f"    Line {e.lineno}: {e.msg}")
                if e.text:
                    print(f"    {e.text.strip()}")
            except Exception as e:
                # Restore backup
                if Path(backup_path).exists():
                    shutil.move(backup_path, filepath)
                print(f"  ✗ Error: {e}")
        else:
            print(f"⚠ File not found: {filepath}")


if __name__ == "__main__":
    main()
