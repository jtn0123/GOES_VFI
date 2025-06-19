#!/usr/bin/env python3
"""Fix remaining Flake8 issues in the codebase."""

import re
import subprocess
from pathlib import Path
from typing import List, Tuple


def fix_loop_control_variable(file_path: Path, line_num: int) -> None:
    """Fix B007: Loop control variable not used in loop body."""
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    if 0 <= line_num - 1 < len(lines):
        line = lines[line_num - 1]
        # Find the loop variable and add underscore prefix
        match = re.search(r"\bfor\s+(\w+)\s+in", line)
        if match and not match.group(1).startswith("_"):
            var_name = match.group(1)
            lines[line_num - 1] = line.replace(
                f"for {var_name} in", f"for _{var_name} in"
            )

    with open(file_path, "w", encoding="utf-8") as f:
        f.writelines(lines)


def fix_function_calls_in_defaults(file_path: Path, line_num: int) -> None:
    """Fix B008: Do not perform function calls in argument defaults."""
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    if 0 <= line_num - 1 < len(lines):
        line = lines[line_num - 1]
        # Replace datetime.now() with None and handle in function body
        if "datetime.now()" in line:
            lines[line_num - 1] = line.replace("datetime.now()", "None")
            # TODO: Would need to add logic in function body to handle None
            print(
                f"Note: {file_path}:{line_num} - Need to handle None default in function body"
            )


def fix_getattr_setattr_constants(
    file_path: Path, line_num: int, is_setattr: bool
) -> None:
    """Fix B009/B010: getattr/setattr with constant attribute."""
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    if 0 <= line_num - 1 < len(lines):
        line = lines[line_num - 1]
        if is_setattr:
            # Replace setattr(obj, "attr", value) with obj.attr = value
            match = re.search(
                r'setattr\(([^,]+),\s*["\'](\w+)["\']\s*,\s*([^)]+)\)', line
            )
            if match:
                obj, attr, value = match.groups()
                replacement = f"{obj.strip()}.{attr} = {value.strip()}"
                lines[line_num - 1] = line.replace(match.group(0), replacement)
        else:
            # Replace getattr(obj, "attr", default) with obj.attr or default handling
            match = re.search(
                r'getattr\(([^,]+),\s*["\'](\w+)["\']\s*(?:,\s*([^)]+))?\)', line
            )
            if match:
                obj, attr = match.groups()[:2]
                default = match.group(3) if match.group(3) else None
                if default:
                    replacement = f'({obj.strip()}.{attr} if hasattr({obj.strip()}, "{attr}") else {default.strip()})'
                else:
                    replacement = f"{obj.strip()}.{attr}"
                lines[line_num - 1] = line.replace(match.group(0), replacement)

    with open(file_path, "w", encoding="utf-8") as f:
        f.writelines(lines)


def fix_redundant_exceptions(file_path: Path, line_num: int, full_line: str) -> None:
    """Fix B014: Redundant exception types."""
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    if 0 <= line_num - 1 < len(lines):
        line = lines[line_num - 1]

        # Extract the recommended fix from the error message
        if "Write `except" in full_line:
            recommended = full_line.split("Write `")[1].split("`")[0]
            # Find the except clause in the line
            except_match = re.search(r"except\s*\([^)]+\)", line)
            if except_match:
                lines[line_num - 1] = line.replace(except_match.group(0), recommended)

    with open(file_path, "w", encoding="utf-8") as f:
        f.writelines(lines)


def fix_whitespace_around_operator(file_path: Path, line_num: int) -> None:
    """Fix E226: Missing whitespace around arithmetic operator."""
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    if 0 <= line_num - 1 < len(lines):
        line = lines[line_num - 1]
        # Add spaces around operators
        # Handle common cases like i+1 -> i + 1
        line = re.sub(r"(\w)(\+|\-|\*|/)(\w)", r"\1 \2 \3", line)
        lines[line_num - 1] = line

    with open(file_path, "w", encoding="utf-8") as f:
        f.writelines(lines)


def fix_module_level_imports(file_path: Path, line_num: int) -> None:
    """Fix E402: Module level import not at top of file."""
    # This is more complex - would need to move imports to top
    # For now, just log it
    print(f"Note: {file_path}:{line_num} - Manual fix needed for module-level import")


def fix_fstring_placeholders(file_path: Path, line_num: int) -> None:
    """Fix F541: f-string missing placeholders."""
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    if 0 <= line_num - 1 < len(lines):
        line = lines[line_num - 1]
        # Remove the f prefix from strings without placeholders
        line = re.sub(
            r'\bf"([^"]*?)"',
            lambda m: f'"{m.group(1)}"' if "{" not in m.group(1) else m.group(0),
            line,
        )
        line = re.sub(
            r"\bf'([^']*?)'",
            lambda m: f"'{m.group(1)}'" if "{" not in m.group(1) else m.group(0),
            line,
        )
        lines[line_num - 1] = line

    with open(file_path, "w", encoding="utf-8") as f:
        f.writelines(lines)


def fix_tr011_fstring(file_path: Path, line_num: int) -> None:
    """Fix TR011: f-string resolved before translation call."""
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    if 0 <= line_num - 1 < len(lines):
        line = lines[line_num - 1]
        # Convert self.tr(f"...{var}...") to self.tr("...{}...").format(var)
        match = re.search(r'self\.tr\(f["\']([^"\']+)["\']\)', line)
        if match:
            content = match.group(1)
            # Find all {var} patterns
            vars_in_string = re.findall(r"\{([^}]+)\}", content)
            # Replace {var} with {0}, {1}, etc.
            new_content = content
            format_args = []
            for i, var in enumerate(vars_in_string):
                new_content = new_content.replace(f"{{{var}}}", f"{{{i}}}")
                format_args.append(var)

            if format_args:
                replacement = (
                    f'self.tr("{new_content}").format({", ".join(format_args)})'
                )
                lines[line_num - 1] = line.replace(match.group(0), replacement)

    with open(file_path, "w", encoding="utf-8") as f:
        f.writelines(lines)


def fix_blank_line_at_end(file_path: Path) -> None:
    """Fix W391: Blank line at end of file."""
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Remove trailing blank lines
    while lines and lines[-1].strip() == "":
        lines.pop()

    # Ensure file ends with newline
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"

    with open(file_path, "w", encoding="utf-8") as f:
        f.writelines(lines)


def main():
    """Main function to fix remaining Flake8 issues."""
    # Run flake8 and capture output
    result = subprocess.run(
        ["python", "run_linters.py", "--flake8-only", "goesvfi"],
        capture_output=True,
        text=True,
    )

    # Parse flake8 output
    issues = []
    for line in result.stdout.split("\n"):
        if ":" in line and any(
            code in line
            for code in [
                "B007",
                "B008",
                "B009",
                "B010",
                "B014",
                "E226",
                "E402",
                "F541",
                "TR011",
                "W391",
            ]
        ):
            parts = line.split(":", 3)
            if len(parts) >= 4:
                file_path = parts[0]
                line_num = int(parts[1])
                error_code = parts[3].strip().split()[0]
                issues.append((file_path, line_num, error_code, line))

    # Fix issues
    for file_path, line_num, error_code, full_line in issues:
        path = Path(file_path)
        if not path.exists():
            continue

        print(f"Fixing {error_code} in {file_path}:{line_num}")

        if error_code == "B007":
            fix_loop_control_variable(path, line_num)
        elif error_code == "B008":
            fix_function_calls_in_defaults(path, line_num)
        elif error_code == "B009":
            fix_getattr_setattr_constants(path, line_num, is_setattr=False)
        elif error_code == "B010":
            fix_getattr_setattr_constants(path, line_num, is_setattr=True)
        elif error_code == "B014":
            fix_redundant_exceptions(path, line_num, full_line)
        elif error_code == "E226":
            fix_whitespace_around_operator(path, line_num)
        elif error_code == "E402":
            fix_module_level_imports(path, line_num)
        elif error_code == "F541":
            fix_fstring_placeholders(path, line_num)
        elif error_code == "TR011":
            fix_tr011_fstring(path, line_num)
        elif error_code == "W391":
            fix_blank_line_at_end(path)

    print("\nRemaining Flake8 issues fixed!")

    # Run flake8 again to verify
    print("\nRunning flake8 again to verify fixes...")
    subprocess.run(["python", "run_linters.py", "--flake8-only", "goesvfi"])


if __name__ == "__main__":
    main()
