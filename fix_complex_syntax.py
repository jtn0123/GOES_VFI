#!/usr/bin/env python3
"""Fix more complex syntax errors in specific files."""

import ast
import re
import shutil
from pathlib import Path


def fix_file_manually(filepath):
    """Fix specific files with known issues."""

    if filepath.endswith("test_s3_band13.py"):
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # Fix line 208: remove extra quote
        if len(lines) > 207:
            lines[207] = lines[207].replace("{dest_path}\"'", '{dest_path}"')

        # Remove duplicate else on line 212
        if len(lines) > 211 and lines[211].strip() == "else:":
            lines.pop(211)
            # Remove the pass statement that follows
            if len(lines) > 211 and lines[211].strip() == "pass":
                lines.pop(211)

        # Write back
        with open(filepath, "w", encoding="utf-8") as f:
            f.writelines(lines)
        return True

    elif filepath.endswith("test_download_band13.py"):
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # Fix line 214: remove extra quote
        if len(lines) > 213:
            lines[213] = lines[213].replace("{dest_path}\"'", '{dest_path}"')

        # Look for and fix duplicate else statements
        i = 0
        while i < len(lines) - 1:
            if lines[i].strip() == "else:" and lines[i + 1].strip() == "else:":
                # Remove the duplicate
                lines.pop(i + 1)
                # Also remove any pass statement
                if i + 1 < len(lines) and lines[i + 1].strip() == "pass":
                    lines.pop(i + 1)
            i += 1

        # Write back
        with open(filepath, "w", encoding="utf-8") as f:
            f.writelines(lines)
        return True

    elif filepath.endswith("test_real_s3_store.py"):
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # Fix unterminated string on line 211
        content = re.sub(
            r'skipping download test"(?!\s*\))', r'skipping download test")', content
        )

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return True

    elif filepath.endswith("test_integrity_tab_performance.py"):
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # Fix f-string format: {variable:.2f} not {variable}:.2f
        content = re.sub(r"\{([^}]+)\}:(\.[\d]+f)", r"{\1\2}", content)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return True

    elif filepath.endswith("test_log.py"):
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # Find class definition and ensure proper indentation for pass
        for i in range(len(lines)):
            if lines[i].strip().startswith("class ") and lines[i].strip().endswith(":"):
                # Check next line
                if i + 1 < len(lines) and lines[i + 1].strip() == "pass":
                    # Fix indentation
                    indent = len(lines[i]) - len(lines[i].lstrip())
                    lines[i + 1] = " " * (indent + 4) + "pass\n"

        with open(filepath, "w", encoding="utf-8") as f:
            f.writelines(lines)
        return True

    return False


def main():
    """Fix specific files with complex syntax errors."""
    files_to_fix = [
        "tests/unit/test_s3_band13.py",
        "tests/unit/test_download_band13.py",
        "tests/unit/test_real_s3_store.py",
        "tests/integration/test_integrity_tab_performance.py",
        "tests/unit/test_log.py",
    ]

    for filepath in files_to_fix:
        if Path(filepath).exists():
            print(f"Fixing {filepath}...")
            # Backup first
            backup_path = filepath + ".complex_backup"
            shutil.copy2(filepath, backup_path)

            try:
                if fix_file_manually(filepath):
                    # Verify it's valid Python
                    with open(filepath, "r") as f:
                        content = f.read()
                    ast.parse(content)
                    print(f"  ✓ Fixed successfully")
                    Path(backup_path).unlink()  # Remove backup
                else:
                    print(f"  - No specific fix available")
            except SyntaxError as e:
                # Restore backup
                shutil.move(backup_path, filepath)
                print(f"  ✗ Still has errors: {e}")
            except Exception as e:
                # Restore backup
                if Path(backup_path).exists():
                    shutil.move(backup_path, filepath)
                print(f"  ✗ Error: {e}")
        else:
            print(f"⚠ File not found: {filepath}")


if __name__ == "__main__":
    main()
