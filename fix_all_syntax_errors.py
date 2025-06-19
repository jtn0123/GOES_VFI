#!/usr/bin/env python
"""Fix common syntax error patterns in Python files."""

import re
from pathlib import Path
from typing import List, Tuple


def fix_file(file_path: Path) -> Tuple[bool, str]:
    """Fix common syntax errors in a Python file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        original_content = content

        # Fix pattern 1: Function calls split across lines with parentheses
        # Example: func() \n "arg" -> func("arg")
        content = re.sub(r'(\w+)\(\)\s*\n\s*(["\'])', r"\1(\2", content)

        # Fix pattern 2: Missing opening parenthesis before quote
        # Example: .get() \n "key" -> .get("key"
        content = re.sub(r'\.get\(\)\s*\n\s*(["\'])', r".get(\1", content)

        # Fix pattern 3: Unmatched closing parenthesis at start of line
        # Example: \n    ) -> remove the line
        content = re.sub(r"\n\s*\)\s*$", "", content, flags=re.MULTILINE)

        # Fix pattern 4: if/elif with () instead of ():
        content = re.sub(r"(if|elif)\s+\(\)\s*\n", r"\1 (\n", content)

        # Fix pattern 5: isinstance/all with split arguments
        content = re.sub(r"(isinstance|all)\(\)\s*\n\s+", r"\1(", content)

        # Fix pattern 6: Empty except blocks
        content = re.sub(
            r"except[^:]*:\s*\n(?=\s*(except|else|finally|class|def|\Z))",
            r"except Exception:\n    pass\n",
            content,
        )

        # Fix pattern 7: Docstring before imports
        # Move imports that appear in docstrings outside
        content = re.sub(r'"""[^"]*\nfrom\s+', r'"""\n\nfrom ', content)

        # Fix pattern 8: Fix PathLike import position
        content = re.sub(
            r'"""[^"]*from pathlib[^"]*"""',
            lambda m: m.group(0).replace("from pathlib", "").replace("from typing", ""),
            content,
        )

        if content != original_content:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            return True, "Fixed"
        return False, "No changes needed"

    except Exception as e:
        return False, f"Error: {str(e)}"


def main():
    """Fix syntax errors in all Python files."""
    project_root = Path(__file__).parent
    python_files = list(project_root.glob("goesvfi/**/*.py"))

    print(f"Attempting to fix {len(python_files)} Python files...")
    print("=" * 80)

    fixed_count = 0
    for file_path in sorted(python_files):
        success, message = fix_file(file_path)
        if success and message == "Fixed":
            fixed_count += 1
            rel_path = file_path.relative_to(project_root)
            print(f"✓ Fixed: {rel_path}")

    print("=" * 80)
    print(f"Fixed {fixed_count} files")


if __name__ == "__main__":
    main()
