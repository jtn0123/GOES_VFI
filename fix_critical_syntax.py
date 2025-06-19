#!/usr/bin/env python
"""Fix syntax errors in the most critical files to get tests running."""

import re
from pathlib import Path


def fix_ffmpeg_settings_tab():
    """Fix ffmpeg_settings_tab.py"""
    path = Path("goesvfi/gui_tabs/ffmpeg_settings_tab.py")
    content = path.read_text()

    # Fix the specific syntax error on line 758
    # Look for common patterns in this file
    lines = content.split("\n")
    fixed_lines = []

    for i, line in enumerate(lines):
        # Fix empty imports
        if "from PyQt6.QtWidgets import ()" in line:
            line = "from PyQt6.QtWidgets import QWidget"
        # Fix other patterns
        if line.strip() == ")" and i > 0:
            # Check if previous line needs it
            prev = fixed_lines[-1] if fixed_lines else ""
            if "(" in prev and prev.count("(") > prev.count(")"):
                fixed_lines[-1] = prev.rstrip() + ")"
                continue
        fixed_lines.append(line)

    path.write_text("\n".join(fixed_lines))
    print(f"Fixed {path}")


def fix_settings_manager():
    """Fix settings_manager.py"""
    path = Path("goesvfi/gui_components/settings_manager.py")
    if not path.exists():
        print(f"Skipping {path} - not found")
        return

    content = path.read_text()

    # Fix unterminated triple-quoted strings
    # Count """ occurrences
    triple_quotes = content.count('"""')
    if triple_quotes % 2 == 1:
        # Find the last occurrence and close it
        lines = content.split("\n")
        for i in range(len(lines) - 1, -1, -1):
            if '"""' in lines[i] and not lines[i].strip().endswith('"""'):
                lines[i] = lines[i] + '"""'
                break
        content = "\n".join(lines)

    # Fix empty except blocks
    content = re.sub(
        r"except\s+\w+.*:\s*\n\s*except",
        r"except Exception as e:\n        pass\n    except",
        content,
    )

    path.write_text(content)
    print(f"Fixed {path}")


def fix_base_py():
    """Fix integrity_check/remote/base.py"""
    path = Path("goesvfi/integrity_check/remote/base.py")
    content = path.read_text()

    # Fix unterminated string literals
    lines = content.split("\n")
    fixed_lines = []

    for i, line in enumerate(lines):
        # Check for unterminated f-strings
        if line.count('f"') % 2 == 1 or line.count("f'") % 2 == 1:
            if not line.rstrip().endswith('"') and 'f"' in line:
                line = line.rstrip() + '"'
            elif not line.rstrip().endswith("'") and "f'" in line:
                line = line.rstrip() + "'"
        fixed_lines.append(line)

    path.write_text("\n".join(fixed_lines))
    print(f"Fixed {path}")


def fix_all_files():
    """Fix all files with syntax errors."""
    # First, let's fix the pattern of split function calls
    files_to_fix = [
        "goesvfi/date_sorter/gui_tab.py",
        "goesvfi/date_sorter/sorter.py",
        "goesvfi/date_sorter/view_model.py",
        "goesvfi/gui_components/crop_manager.py",
        "goesvfi/gui_components/preview_manager.py",
        "goesvfi/gui_enhancements_integration.py",
        "goesvfi/gui_integration_patch.py",
        "goesvfi/integrity_check/auto_detection.py",
        "goesvfi/integrity_check/background_worker.py",
        "goesvfi/integrity_check/cache_db.py",
        "goesvfi/integrity_check/gui_tab.py",
        "goesvfi/integrity_check/view_model.py",
        "goesvfi/pipeline/batch_queue.py",
        "goesvfi/utils/log.py",
        "goesvfi/utils/security.py",
        "goesvfi/utils/ui_improvements.py",
    ]

    for file_path in files_to_fix:
        path = Path(file_path)
        if not path.exists():
            continue

        try:
            content = path.read_text()
            original = content

            # Fix empty imports
            content = re.sub(r"from\s+[\w.]+\s+import\s+\(\s*\)\s*\n", "", content)

            # Fix split function calls
            content = re.sub(r'(\w+)\(\)\s*\n\s*(["\'])', r"\1(\2", content)
            content = re.sub(r'\.(\w+)\(\)\s*\n\s*(["\'])', r".\1(\2", content)
            content = re.sub(r'(raise\s+\w+)\(\)\s*\n\s*(["\'])', r"\1(\2", content)

            # Fix unmatched parentheses
            lines = content.split("\n")
            fixed_lines = []
            for i, line in enumerate(lines):
                if line.strip() == ")" and i > 0 and fixed_lines:
                    prev = fixed_lines[-1]
                    if "(" in prev and prev.count("(") > prev.count(")"):
                        fixed_lines[-1] = prev.rstrip() + ")"
                        continue
                fixed_lines.append(line)
            content = "\n".join(fixed_lines)

            # Fix f-string format errors in logging
            content = re.sub(
                r'%s([^"]*)", ([^:]+):\.(\d+)f\)', r'%.\3f\1", \2)', content
            )

            if content != original:
                path.write_text(content)
                print(f"Fixed {path}")

        except Exception as e:
            print(f"Error fixing {path}: {e}")


def main():
    """Main function."""
    print("Fixing critical syntax errors...")
    print("=" * 80)

    # Fix specific problematic files
    fix_ffmpeg_settings_tab()
    fix_settings_manager()
    fix_base_py()

    # Fix common patterns in all files
    fix_all_files()

    print("=" * 80)
    print("Done. Run tests to see if imports work now.")


if __name__ == "__main__":
    main()
