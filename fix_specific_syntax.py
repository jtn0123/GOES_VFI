#!/usr/bin/env python3
"""Fix specific syntax errors found in the codebase."""

import ast
import os
import re
import shutil
from pathlib import Path


def fix_logger_format_error(content):
    """Fix logger.info("format", var:,) syntax errors."""
    # Pattern: variable:,) should be variable)
    content = re.sub(r"(\w+):,\)", r"\1)", content)
    return content


def fix_unterminated_strings(content):
    """Fix unterminated string literals with extra quotes."""
    # Pattern: "string content"' at end of line or before )
    content = re.sub(r'("[^"]*")\'\s*\)', r"\1)", content)
    content = re.sub(r'("[^"]*")\'\s*$', r"\1", content, flags=re.MULTILINE)
    # Also for f-strings
    content = re.sub(r'(f"[^"]*")\'\s*\)', r"\1)", content)
    content = re.sub(r'(f"[^"]*")\'\s*$', r"\1", content, flags=re.MULTILINE)
    return content


def fix_fstring_decimals(content):
    """Fix f-string decimal format errors."""
    # Pattern: {variable}:.2f should be {variable:.2f}
    lines = content.split("\n")
    fixed_lines = []

    for line in lines:
        # Find f-strings with format issues
        if re.search(r"\{[^}]+\}:\.\d+f", line):
            # Fix the format
            line = re.sub(r"\{([^}]+)\}:(\.[\d]+f)", r"{\1\2}", line)
        fixed_lines.append(line)

    return "\n".join(fixed_lines)


def fix_unterminated_multiline_strings(content):
    """Fix unterminated multiline string literals."""
    lines = content.split("\n")
    fixed_lines = []
    in_string = False
    string_delimiter = None

    for i, line in enumerate(lines):
        # Check for string start
        if not in_string:
            if '"""' in line and line.count('"""') == 1:
                in_string = True
                string_delimiter = '"""'
            elif "'''" in line and line.count("'''") == 1:
                in_string = True
                string_delimiter = "'''"
        elif in_string:
            # Check if string ends on this line
            if string_delimiter in line:
                in_string = False
                string_delimiter = None

        fixed_lines.append(line)

    # If we ended with an open string, close it
    if in_string and string_delimiter:
        fixed_lines.append(string_delimiter)

    return "\n".join(fixed_lines)


def fix_class_indentation(content):
    """Fix missing indentation after class definitions."""
    lines = content.split("\n")
    fixed_lines = []

    for i, line in enumerate(lines):
        fixed_lines.append(line)

        # Check if this is a class definition
        if re.match(r"^class\s+\w+.*:$", line.strip()) and i + 1 < len(lines):
            next_line = lines[i + 1]
            # If next line is 'pass' without proper indentation
            if next_line.strip() == "pass" and not next_line.startswith("    "):
                # Skip the incorrectly indented pass
                continue

    return "\n".join(fixed_lines)


def fix_single_file(filepath):
    """Fix syntax errors in a single file."""
    try:
        print(f"Processing: {filepath}")

        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        original_content = content

        # Apply fixes
        content = fix_logger_format_error(content)
        content = fix_unterminated_strings(content)
        content = fix_fstring_decimals(content)
        content = fix_unterminated_multiline_strings(content)
        content = fix_class_indentation(content)

        if content != original_content:
            # Backup original
            backup_path = filepath + ".syntax_backup2"
            shutil.copy2(filepath, backup_path)

            # Write fixed content
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)

            # Try to parse
            try:
                ast.parse(content)
                print(f"  ✓ Fixed successfully")
                os.remove(backup_path)  # Remove backup if successful
                return True
            except SyntaxError as e:
                # Restore from backup
                shutil.move(backup_path, filepath)
                print(f"  ✗ Still has errors: {e}")
                return False
        else:
            print(f"  - No changes needed")
            return None

    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


def main():
    """Main function to fix specific syntax errors."""
    # Specific files with known patterns
    files_to_fix = [
        # Logger format errors
        "tests/unit/test_download_all_products.py",
        "tests/unit/test_download_mesoscale.py",
        "tests/unit/test_download_full_disk.py",
        # Unterminated strings
        "tests/unit/test_s3_band13.py",
        "tests/unit/test_download_band13.py",
        "tests/unit/test_real_s3_store.py",
        # F-string decimal errors
        "tests/integration/test_integrity_tab_performance.py",
        # Class indentation
        "tests/unit/test_log.py",
    ]

    fixed = 0
    failed = 0
    unchanged = 0

    for filepath in files_to_fix:
        if os.path.exists(filepath):
            result = fix_single_file(filepath)
            if result is True:
                fixed += 1
            elif result is False:
                failed += 1
            else:
                unchanged += 1
        else:
            print(f"⚠ File not found: {filepath}")

    print(f"\nSummary:")
    print(f"  Fixed: {fixed}")
    print(f"  Failed: {failed}")
    print(f"  Unchanged: {unchanged}")


if __name__ == "__main__":
    main()
