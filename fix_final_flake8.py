#!/usr/bin/env python3
"""Fix final remaining Flake8 issues."""

import re
from pathlib import Path


def fix_b007_loop_variable(file_path: Path, line_num: int, var_name: str) -> None:
    """Fix B007: Loop control variable not used in loop body."""
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    if 0 <= line_num - 1 < len(lines):
        line = lines[line_num - 1]
        # Add underscore prefix to the variable
        pattern = rf"\bfor\s+{re.escape(var_name)}\s+in"
        replacement = f"for _{var_name} in"
        lines[line_num - 1] = re.sub(pattern, replacement, line)

    with open(file_path, "w", encoding="utf-8") as f:
        f.writelines(lines)


def fix_b008_datetime_default(file_path: Path, line_num: int) -> None:
    """Fix B008: datetime.now() in argument defaults."""
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    if 0 <= line_num - 1 < len(lines):
        line = lines[line_num - 1]
        # Replace datetime.now() with None
        lines[line_num - 1] = line.replace("datetime.now()", "None")
        print(
            f"Note: Need to handle None default in function body at {file_path}:{line_num}"
        )

    with open(file_path, "w", encoding="utf-8") as f:
        f.writelines(lines)


def fix_b014_redundant_exceptions(file_path: Path, line_num: int) -> None:
    """Fix B014: Redundant exception types."""
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    if 0 <= line_num - 1 < len(lines):
        line = lines[line_num - 1]
        # Remove IOError when OSError is present (IOError is alias for OSError in Python 3)
        line = re.sub(r"IOError,\s*", "", line)
        # Remove FileNotFoundError when OSError is present (FileNotFoundError is subclass of OSError)
        line = re.sub(r"FileNotFoundError,\s*", "", line)
        lines[line_num - 1] = line

    with open(file_path, "w", encoding="utf-8") as f:
        f.writelines(lines)


def fix_e226_whitespace(file_path: Path, line_num: int) -> None:
    """Fix E226: Missing whitespace around arithmetic operator."""
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    if 0 <= line_num - 1 < len(lines):
        line = lines[line_num - 1]
        # Add spaces around operators
        line = re.sub(r"(\w)//(\w)", r"\1 // \2", line)
        line = re.sub(r"(\w)\+(\w)", r"\1 + \2", line)
        lines[line_num - 1] = line

    with open(file_path, "w", encoding="utf-8") as f:
        f.writelines(lines)


def fix_tr011_translation(file_path: Path, line_num: int) -> None:
    """Fix TR011: f-string resolved before translation call."""
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    if 0 <= line_num - 1 < len(lines):
        line = lines[line_num - 1]
        # Find self.tr(f"...") patterns
        match = re.search(r'self\.tr\(f["\']([^"\']+)["\']\)', line)
        if match:
            content = match.group(1)
            # Extract variables from f-string
            vars_found = re.findall(r"\{([^}]+)\}", content)
            # Replace with indexed placeholders
            new_content = content
            for i, var in enumerate(vars_found):
                new_content = new_content.replace(f"{{{var}}}", f"{{{i}}}")
            # Build replacement
            if vars_found:
                replacement = (
                    f'self.tr("{new_content}").format({", ".join(vars_found)})'
                )
                lines[line_num - 1] = line.replace(match.group(0), replacement)

    with open(file_path, "w", encoding="utf-8") as f:
        f.writelines(lines)


def main():
    """Fix specific remaining issues."""

    # Fix B007 issues
    fix_b007_loop_variable(Path("goesvfi/gui_backup.py"), 3086, "i")
    fix_b007_loop_variable(
        Path("goesvfi/integrity_check/visualization_manager.py"), 487, "title"
    )
    fix_b007_loop_variable(Path("goesvfi/utils/enhanced_log.py"), 117, "timings")
    fix_b007_loop_variable(Path("goesvfi/utils/ui_enhancements.py"), 437, "name")

    # Fix B008 issues in operation_history_tab.py
    fix_b008_datetime_default(Path("goesvfi/gui_tabs/operation_history_tab.py"), 54)
    fix_b008_datetime_default(Path("goesvfi/gui_tabs/operation_history_tab.py"), 58)
    fix_b008_datetime_default(Path("goesvfi/gui_tabs/operation_history_tab.py"), 145)
    fix_b008_datetime_default(Path("goesvfi/gui_tabs/operation_history_tab.py"), 149)

    # Fix B014 issues
    fix_b014_redundant_exceptions(
        Path("goesvfi/integrity_check/remote/s3_store.py"), 1629
    )
    fix_b014_redundant_exceptions(
        Path("goesvfi/integrity_check/remote/s3_store.py"), 1974
    )
    fix_b014_redundant_exceptions(Path("goesvfi/pipeline/run_vfi.py"), 1825)

    # Fix E226 issue
    fix_e226_whitespace(Path("goesvfi/pipeline/run_vfi.py"), 935)

    # Fix TR011 issues
    fix_tr011_translation(Path("goesvfi/gui_tabs/main_tab.py"), 2897)
    fix_tr011_translation(Path("goesvfi/gui_tabs/main_tab.py"), 2924)

    # For E402 (module level imports), we need manual fixes
    print("\nNeed manual fixes for E402 (module level imports) in:")
    print("- goesvfi/utils/debug_mode.py:277")
    print("- goesvfi/utils/operation_history.py:364, 367, 369")

    print("\nDone!")


if __name__ == "__main__":
    main()
