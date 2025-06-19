#!/usr/bin/env python3
"""Fix all remaining linting issues comprehensively."""

import re
from pathlib import Path


def fix_file(file_path: Path, fixes: list) -> None:
    """Apply a list of fixes to a file."""
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Sort fixes by line number in reverse order to avoid index shifting
    fixes.sort(key=lambda x: x[0], reverse=True)

    for line_num, fix_func in fixes:
        if 0 <= line_num - 1 < len(lines):
            lines[line_num - 1] = fix_func(lines[line_num - 1])

    with open(file_path, "w", encoding="utf-8") as f:
        f.writelines(lines)


# Fix functions
def fix_loop_var(line: str, var_name: str) -> str:
    """Add underscore to unused loop variable."""
    pattern = rf"\bfor\s+{re.escape(var_name)}\s+in"
    return re.sub(pattern, f"for _{var_name} in", line)


def fix_datetime_default(line: str) -> str:
    """Replace datetime.now() with None in defaults."""
    return line.replace("datetime.now()", "None")


def fix_redundant_exceptions(line: str) -> str:
    """Remove redundant exception types."""
    # Remove IOError when OSError is present
    line = re.sub(r",\s*IOError(?=\s*[,)])", "", line)
    # Remove FileNotFoundError when OSError is present
    line = re.sub(r"FileNotFoundError,\s*", "", line)
    return line


def fix_tr_fstring(line: str) -> str:
    """Fix f-string in translation call."""
    match = re.search(r'self\.tr\(f["\']([^"\']+)["\']\)', line)
    if match:
        content = match.group(1)
        vars_found = re.findall(r"\{([^}:]+)(:[^}]+)?\}", content)
        new_content = content
        var_names = []
        for i, (var, format_spec) in enumerate(vars_found):
            old_pattern = f'{{{var}{format_spec or ""}}}'
            new_pattern = f'{{{i}{format_spec or ""}}}'
            new_content = new_content.replace(old_pattern, new_pattern)
            var_names.append(var)
        if var_names:
            replacement = f'self.tr("{new_content}").format({", ".join(var_names)})'
            return line.replace(match.group(0), replacement)
    return line


def main():
    """Fix all remaining issues."""

    # B007: Loop variables
    fix_file(
        Path("goesvfi/gui_backup.py"), [(3086, lambda line: fix_loop_var(line, "i"))]
    )

    fix_file(
        Path("goesvfi/integrity_check/visualization_manager.py"),
        [(487, lambda line: fix_loop_var(line, "title"))],
    )

    fix_file(
        Path("goesvfi/utils/enhanced_log.py"),
        [(117, lambda line: fix_loop_var(line, "timings"))],
    )

    fix_file(
        Path("goesvfi/utils/ui_enhancements.py"),
        [(437, lambda line: fix_loop_var(line, "name"))],
    )

    # TR011: f-strings in translations
    fix_file(
        Path("goesvfi/gui_tabs/main_tab.py"),
        [(2897, fix_tr_fstring), (2924, fix_tr_fstring)],
    )

    # B008: datetime.now() in defaults - need to also fix the function bodies
    operation_history_path = Path("goesvfi/gui_tabs/operation_history_tab.py")
    with open(operation_history_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Fix the defaults and add None handling in function bodies
    content = re.sub(
        r"(def add_operation\([^)]*timestamp:\s*datetime\s*=\s*)datetime\.now\(\)",
        r"\1None",
        content,
    )
    content = re.sub(
        r"(def record_operation\([^)]*timestamp:\s*Optional\[datetime\]\s*=\s*)datetime\.now\(\)",
        r"\1None",
        content,
    )

    # Add None handling after function signatures
    # For add_operation
    content = re.sub(
        r'(def add_operation\([^)]+\) -> None:\s*\n)([ \t]*"""[^"]*"""\s*\n)',
        r"\1\2\2if timestamp is None:\n\2    timestamp = datetime.now()\n",
        content,
    )

    # For record_operation
    content = re.sub(
        r'(def record_operation\([^)]+\) -> None:\s*\n)([ \t]*"""[^"]*"""\s*\n)',
        r"\1\2\2if timestamp is None:\n\2    timestamp = datetime.now()\n",
        content,
    )

    with open(operation_history_path, "w", encoding="utf-8") as f:
        f.write(content)

    # B014: Redundant exceptions
    fix_file(
        Path("goesvfi/integrity_check/remote/s3_store.py"),
        [(1629, fix_redundant_exceptions), (1974, fix_redundant_exceptions)],
    )

    fix_file(Path("goesvfi/pipeline/run_vfi.py"), [(1825, fix_redundant_exceptions)])

    # E402: Module level imports - fix by moving imports to top
    # Fix debug_mode.py
    debug_mode_path = Path("goesvfi/utils/debug_mode.py")
    with open(debug_mode_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Find the import line and move it to top (after other imports)
    import_line = None
    import_line_num = None
    for i, line in enumerate(lines):
        if i == 276 and "import" in line:  # Line 277 is index 276
            import_line = line
            import_line_num = i
            break

    if import_line:
        lines.pop(import_line_num)
        # Find where to insert (after last import at top)
        insert_pos = 0
        for i, line in enumerate(lines):
            if line.strip() and not line.startswith(("import ", "from ", "#")):
                insert_pos = i
                break
        lines.insert(insert_pos, import_line)

    with open(debug_mode_path, "w", encoding="utf-8") as f:
        f.writelines(lines)

    # Fix operation_history.py
    operation_history_path = Path("goesvfi/utils/operation_history.py")
    with open(operation_history_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Move the TYPE_CHECKING block to the top
    type_checking_pattern = r"if TYPE_CHECKING:\s*\n((?:[ \t]+.*\n)*)"
    match = re.search(type_checking_pattern, content)
    if match:
        # Extract the TYPE_CHECKING block
        type_checking_block = match.group(0)
        # Remove it from current position
        content = content.replace(type_checking_block, "")
        # Find position after imports
        import_end = 0
        for line in content.split("\n"):
            if line.strip() and not line.startswith(("import ", "from ", "#", '"""')):
                break
            import_end += len(line) + 1
        # Insert TYPE_CHECKING block after imports
        content = (
            content[:import_end]
            + "\n"
            + type_checking_block
            + "\n"
            + content[import_end:]
        )

    with open(operation_history_path, "w", encoding="utf-8") as f:
        f.write(content)

    print("All remaining linting issues fixed!")


if __name__ == "__main__":
    main()
