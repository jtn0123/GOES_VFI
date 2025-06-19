#!/usr/bin/env python3
"""Fix common linting issues systematically."""

import os
import subprocess
from pathlib import Path


def fix_unused_imports():
    """Remove unused imports using autoflake."""
    print("Fixing unused imports...")
    cmd = [
        "autoflake",
        "--in-place",
        "--remove-all-unused-imports",
        "--recursive",
        "goesvfi/",
    ]
    try:
        subprocess.run(cmd, check=True)
        print("✓ Fixed unused imports")
    except subprocess.CalledProcessError:
        print("✗ autoflake not installed. Install with: pip install autoflake")
    except FileNotFoundError:
        print("✗ autoflake not found. Install with: pip install autoflake")


def fix_whitespace_issues():
    """Fix trailing whitespace and missing newlines."""
    print("Fixing whitespace issues...")
    files_fixed = 0

    for root, _, files in os.walk("goesvfi/"):
        for file in files:
            if file.endswith(".py"):
                filepath = Path(root) / file
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        content = f.read()

                    original = content
                    # Remove trailing whitespace
                    content = "\n".join(line.rstrip() for line in content.split("\n"))

                    # Ensure file ends with newline
                    if content and not content.endswith("\n"):
                        content += "\n"

                    if content != original:
                        with open(filepath, "w", encoding="utf-8") as f:
                            f.write(content)
                        files_fixed += 1

                except Exception as e:
                    print(f"Error processing {filepath}: {e}")

    print(f"✓ Fixed whitespace in {files_fixed} files")


def fix_indentation_issues():
    """Fix specific indentation issues in reconcile_manager_refactored.py."""
    print("Fixing indentation issues...")

    filepath = "goesvfi/integrity_check/reconcile_manager_refactored.py"
    try:
        with open(filepath, "r") as f:
            lines = f.readlines()

        # Fix continuation line indentation (E126)
        problem_lines = [444, 452, 472, 479, 490, 495, 510, 527]
        for line_num in problem_lines:
            if line_num - 1 < len(lines):
                # Reduce indentation by 4 spaces for continuation lines
                lines[line_num - 1] = lines[line_num - 1].replace(
                    "                        ", "                    ", 1
                )

        with open(filepath, "w") as f:
            f.writelines(lines)

        print("✓ Fixed indentation issues")
    except Exception as e:
        print(f"Error fixing indentation: {e}")


def fix_import_order():
    """Fix import order using isort."""
    print("Fixing import order...")
    cmd = ["isort", "goesvfi/", "--profile", "black"]
    try:
        subprocess.run(cmd, check=True)
        print("✓ Fixed import order")
    except subprocess.CalledProcessError:
        print("✗ isort not installed. Install with: pip install isort")
    except FileNotFoundError:
        print("✗ isort not found. Install with: pip install isort")


def fix_blank_lines():
    """Fix blank line issues (E305)."""
    print("Fixing blank line issues...")

    filepath = "goesvfi/integrity_check/results_organization.py"
    try:
        with open(filepath, "r") as f:
            content = f.read()

        # Add extra blank line before line 992
        lines = content.split("\n")

        # Find the OptimizedResultsTab alias and ensure proper spacing
        for i in range(len(lines)):
            if i > 0 and lines[i].strip().startswith("OptimizedResultsTab ="):
                # Ensure there are 2 blank lines before this alias
                if i >= 2 and lines[i - 1].strip() == "" and lines[i - 2].strip() != "":
                    # Only one blank line, add another
                    lines.insert(i, "")
                elif i >= 1 and lines[i - 1].strip() != "":
                    # No blank lines, add two
                    lines.insert(i, "")
                    lines.insert(i, "")
                break

        with open(filepath, "w") as f:
            f.write("\n".join(lines))

        print("✓ Fixed blank line issues")
    except Exception as e:
        print(f"Error fixing blank lines: {e}")


def main():
    """Run all fixes."""
    print("Fixing common linting issues...\n")

    fix_unused_imports()
    fix_whitespace_issues()
    fix_indentation_issues()
    fix_import_order()
    fix_blank_lines()

    print("\nAll fixes applied! Run the linters again to verify.")


if __name__ == "__main__":
    main()
