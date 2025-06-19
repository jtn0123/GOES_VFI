#!/usr/bin/env python3
"""
Fix B008 function call in argument defaults issues.
"""

import re
import subprocess
import sys
from pathlib import Path


def get_b008_issues():
    """Get files with B008 issues."""
    try:
        result = subprocess.run(
            [sys.executable, "run_linters.py", "--flake8-only"],
            capture_output=True,
            text=True,
            cwd=".",
        )
        issues = []
        for line in result.stdout.split("\n"):
            if (
                "B008" in line
                and "Do not perform function calls in argument defaults" in line
            ):
                parts = line.split(":")
                if len(parts) >= 3:
                    file_path = parts[0]
                    line_num = int(parts[1])
                    issues.append((file_path, line_num))
        return issues
    except Exception as e:
        print(f"Error getting issues: {e}")
        return []


def fix_qmodelindex_defaults(file_path: str, line_numbers: list):
    """Fix QModelIndex() in default arguments."""
    path = Path(file_path)
    if not path.exists():
        return 0

    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        lines = content.split("\n")
        fixed_count = 0

        for line_num in line_numbers:
            if 1 <= line_num <= len(lines):
                line = lines[line_num - 1]
                original = line

                # Fix QModelIndex() default
                if "QModelIndex()" in line and "=" in line:
                    # Replace QModelIndex() with None in defaults
                    line = re.sub(
                        r"([a-zA-Z_]\w*:\s*QModelIndex)\s*=\s*QModelIndex\(\)",
                        r"\1 = None",
                        line,
                    )

                # Fix datetime.now() or similar calls
                elif "datetime.now()" in line and "=" in line:
                    line = re.sub(
                        r"([a-zA-Z_]\w*:\s*datetime)\s*=\s*datetime\.now\(\)",
                        r"\1 = None",
                        line,
                    )

                # Fix pathlib.Path() calls
                elif "pathlib.Path()" in line and "=" in line:
                    line = re.sub(
                        r"([a-zA-Z_]\w*:\s*Path)\s*=\s*pathlib\.Path\(\)",
                        r"\1 = None",
                        line,
                    )
                elif "Path()" in line and "=" in line:
                    line = re.sub(
                        r"([a-zA-Z_]\w*:\s*Path)\s*=\s*Path\(\)", r"\1 = None", line
                    )

                if line != original:
                    lines[line_num - 1] = line
                    fixed_count += 1
                    print(f"  Fixed line {line_num}")
                    print(f"    Before: {original.strip()}")
                    print(f"    After:  {line.strip()}")

        if fixed_count > 0:
            # Now add the None checks at the beginning of the functions
            new_lines = []
            i = 0
            while i < len(lines):
                line = lines[i]
                new_lines.append(line)

                # Check if this line is a function definition with fixed defaults
                if (
                    line.strip().startswith("def ")
                    and (i + 1) in line_numbers
                    and "= None" in line
                ):
                    # Find the function body start
                    j = i + 1
                    while j < len(lines) and not lines[j].strip():
                        new_lines.append(lines[j])
                        j += 1

                    # Add docstring if present
                    if j < len(lines) and ('"""' in lines[j] or "'''" in lines[j]):
                        # Skip docstring
                        quote_type = '"""' if '"""' in lines[j] else "'''"
                        new_lines.append(lines[j])
                        j += 1
                        if (
                            quote_type not in lines[j - 1]
                            or lines[j - 1].count(quote_type) == 1
                        ):
                            while j < len(lines) and quote_type not in lines[j]:
                                new_lines.append(lines[j])
                                j += 1
                            if j < len(lines):
                                new_lines.append(lines[j])
                                j += 1

                    # Add None checks
                    indent = "        "  # Typical function body indent
                    if "parent: QModelIndex = None" in line:
                        new_lines.append(f"{indent}if parent is None:")
                        new_lines.append(f"{indent}    parent = QModelIndex()")
                    elif "start_time: datetime = None" in line:
                        new_lines.append(f"{indent}if start_time is None:")
                        new_lines.append(f"{indent}    start_time = datetime.now()")
                    elif "base_path: Path = None" in line:
                        new_lines.append(f"{indent}if base_path is None:")
                        new_lines.append(f"{indent}    base_path = Path()")

                    # Continue with rest of function
                    i = j - 1

                i += 1

            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(new_lines))
            print(f"Fixed {fixed_count} B008 issues in {file_path}")

        return fixed_count
    except Exception as e:
        print(f"Error fixing {file_path}: {e}")
        return 0


def main():
    """Main function."""
    print("Fixing B008 function call in defaults issues...")

    issues = get_b008_issues()
    if not issues:
        print("No B008 issues found.")
        return

    print(f"Found {len(issues)} B008 issues")

    # Group by file
    file_lines = {}
    for file_path, line_num in issues:
        if file_path not in file_lines:
            file_lines[file_path] = []
        file_lines[file_path].append(line_num)

    total_fixed = 0
    for file_path, line_numbers in file_lines.items():
        print(f"\nFixing {file_path}...")
        total_fixed += fix_qmodelindex_defaults(file_path, line_numbers)

    print(f"\nFixed {total_fixed} total B008 issues")


if __name__ == "__main__":
    main()
