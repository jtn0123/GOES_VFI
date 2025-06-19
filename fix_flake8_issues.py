#!/usr/bin/env python3
"""Fix Flake8 issues in the codebase."""

import ast
import re
import sys
from pathlib import Path
from typing import List, Set, Tuple


def get_unused_imports(file_path: Path) -> List[Tuple[str, int]]:
    """Get unused imports from a file."""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Parse AST
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []

    # Get all imports
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add((alias.name, alias.asname or alias.name, node.lineno))
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                full_name = f"{node.module}.{alias.name}" if node.module else alias.name
                imports.add((full_name, alias.asname or alias.name, node.lineno))

    # Check usage
    unused = []
    lines = content.split("\n")

    for import_name, alias, lineno in imports:
        # Check if the alias is used anywhere after the import
        used = False
        for i in range(lineno, len(lines)):
            line = lines[i]
            # Skip the import line itself
            if i == lineno - 1:
                continue
            # Skip comments and strings
            if "#" in line:
                line = line[: line.index("#")]
            # Simple check for usage
            if re.search(r"\b" + re.escape(alias) + r"\b", line):
                used = True
                break

        if not used:
            unused.append((import_name, lineno))

    return unused


def fix_unused_imports(file_path: Path, unused_imports: List[Tuple[str, int]]) -> None:
    """Remove unused imports from a file."""
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Sort by line number in reverse to avoid index shifting
    unused_imports.sort(key=lambda x: x[1], reverse=True)

    for import_name, lineno in unused_imports:
        # Remove the import line
        if 0 <= lineno - 1 < len(lines):
            line = lines[lineno - 1]
            # Check if it's a multi-import line
            if "," in line and "import" in line:
                # Handle multi-imports more carefully
                parts = []
                for part in line.split(","):
                    if import_name not in part and not (
                        import_name.split(".")[-1] in part and "import" in part
                    ):
                        parts.append(part)
                if parts:
                    lines[lineno - 1] = ",".join(parts) + "\n"
                else:
                    lines[lineno - 1] = ""
            else:
                lines[lineno - 1] = ""

    # Remove empty lines at the beginning of the file
    while lines and lines[0].strip() == "":
        lines.pop(0)

    # Write back
    with open(file_path, "w", encoding="utf-8") as f:
        f.writelines(lines)


def fix_loop_control_variable(file_path: Path, line_num: int) -> None:
    """Fix loop control variable not used in loop body."""
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    if 0 <= line_num - 1 < len(lines):
        line = lines[line_num - 1]
        # Replace loop variable with underscore
        lines[line_num - 1] = re.sub(r"\bfor\s+(\w+)\s+in", r"for _\1 in", line)

    with open(file_path, "w", encoding="utf-8") as f:
        f.writelines(lines)


def fix_tr011_fstring(file_path: Path, line_num: int) -> None:
    """Fix f-string resolved before translation call."""
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    if 0 <= line_num - 1 < len(lines):
        line = lines[line_num - 1]
        # Replace self.tr(f"...") with self.tr("...").format(...)
        # This is a simplified fix - might need manual review
        if 'self.tr(f"' in line or "self.tr(f'" in line:
            # Extract the f-string content
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

                # Build the new line
                if format_args:
                    replacement = (
                        f'self.tr("{new_content}").format({", ".join(format_args)})'
                    )
                    lines[line_num - 1] = line.replace(match.group(0), replacement)

    with open(file_path, "w", encoding="utf-8") as f:
        f.writelines(lines)


def main():
    """Main function to fix Flake8 issues."""
    # Run flake8 and capture output
    import subprocess

    result = subprocess.run(
        ["python", "run_linters.py", "--flake8-only", "goesvfi"],
        capture_output=True,
        text=True,
    )

    # Parse flake8 output
    issues = []
    for line in result.stdout.split("\n"):
        if ":" in line and any(code in line for code in ["F401", "B007", "TR011"]):
            parts = line.split(":")
            if len(parts) >= 4:
                file_path = parts[0]
                line_num = int(parts[1])
                col_num = int(parts[2])
                error_code = parts[3].strip().split()[0]
                issues.append((file_path, line_num, col_num, error_code, line))

    # Group issues by file
    files_to_fix = {}
    for file_path, line_num, col_num, error_code, full_line in issues:
        if file_path not in files_to_fix:
            files_to_fix[file_path] = []
        files_to_fix[file_path].append((line_num, col_num, error_code, full_line))

    # Fix issues
    for file_path, file_issues in files_to_fix.items():
        path = Path(file_path)
        if not path.exists():
            continue

        print(f"Fixing {file_path}...")

        # Handle F401 (unused imports) separately
        f401_issues = [
            (line_num, full_line)
            for line_num, _, code, full_line in file_issues
            if code == "F401"
        ]
        if f401_issues:
            # Use autoflake for more reliable import removal
            subprocess.run(
                [
                    "python",
                    "-m",
                    "autoflake",
                    "--in-place",
                    "--remove-unused-variables",
                    "--remove-all-unused-imports",
                    str(path),
                ]
            )

        # Handle other issues
        for line_num, col_num, error_code, full_line in sorted(
            file_issues, key=lambda x: x[0], reverse=True
        ):
            if error_code == "B007":
                fix_loop_control_variable(path, line_num)
            elif error_code == "TR011":
                fix_tr011_fstring(path, line_num)

    print("\nFlake8 issues fixed!")

    # Run flake8 again to verify
    print("\nRunning flake8 again to verify fixes...")
    subprocess.run(["python", "run_linters.py", "--flake8-only", "goesvfi"])


if __name__ == "__main__":
    main()
