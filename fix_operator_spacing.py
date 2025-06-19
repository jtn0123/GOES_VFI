#!/usr/bin/env python3
"""
Fix remaining operator spacing issues.
"""

import re
import subprocess
import sys
from pathlib import Path


def get_operator_issues():
    """Get files with operator spacing issues."""
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
                "E226" in line
                and "missing whitespace around arithmetic operator" in line
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


def fix_operator_spacing(file_path: str, line_numbers: list):
    """Fix operator spacing in specific lines."""
    path = Path(file_path)
    if not path.exists():
        return 0

    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        fixed_count = 0
        for line_num in line_numbers:
            if 1 <= line_num <= len(lines):
                line = lines[line_num - 1]
                original = line

                # Fix arithmetic operators - be more specific
                line = re.sub(r"(\w)(\+)(\w)", r"\1 \2 \3", line)
                line = re.sub(r"(\w)(\-)(\w)", r"\1 \2 \3", line)
                line = re.sub(r"(\w)(\*)(\w)", r"\1 \2 \3", line)
                line = re.sub(r"(\w)(/)(\w)", r"\1 \2 \3", line)
                line = re.sub(r"(\w)(%)(\w)", r"\1 \2 \3", line)

                # Fix cases like x*1024 -> x * 1024
                line = re.sub(r"(\w)(\*)(\d)", r"\1 \2 \3", line)
                line = re.sub(r"(\d)(\*)(\w)", r"\1 \2 \3", line)
                line = re.sub(r"(\d)(\+)(\d)", r"\1 \2 \3", line)
                line = re.sub(r"(\d)(/)(\d)", r"\1 \2 \3", line)

                if line != original:
                    lines[line_num - 1] = line
                    fixed_count += 1
                    print(
                        f"  Fixed line {line_num}: {original.strip()} -> {line.strip()}"
                    )

        if fixed_count > 0:
            with open(path, "w", encoding="utf-8") as f:
                f.writelines(lines)
            print(f"Fixed {fixed_count} operator spacing issues in {file_path}")

        return fixed_count
    except Exception as e:
        print(f"Error fixing {file_path}: {e}")
        return 0


def main():
    """Main function."""
    print("Fixing operator spacing issues...")

    issues = get_operator_issues()
    if not issues:
        print("No operator spacing issues found.")
        return

    print(f"Found {len(issues)} operator spacing issues")

    # Group by file
    file_lines = {}
    for file_path, line_num in issues:
        if file_path not in file_lines:
            file_lines[file_path] = []
        file_lines[file_path].append(line_num)

    total_fixed = 0
    for file_path, line_numbers in file_lines.items():
        print(f"\nFixing {file_path}...")
        total_fixed += fix_operator_spacing(file_path, line_numbers)

    print(f"\nFixed {total_fixed} total operator spacing issues")


if __name__ == "__main__":
    main()
