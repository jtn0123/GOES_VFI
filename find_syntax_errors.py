#!/usr/bin/env python3
"""Find files with syntax errors (E999) in the codebase."""

import ast
import os
import sys
from pathlib import Path


def check_file_syntax(filepath):
    """Check if a Python file has syntax errors."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        ast.parse(content)
        return None
    except SyntaxError as e:
        return {
            "file": filepath,
            "line": e.lineno,
            "offset": e.offset,
            "text": e.text,
            "msg": e.msg,
        }


def find_syntax_errors(directory="."):
    """Find all Python files with syntax errors."""
    errors = []

    for root, dirs, files in os.walk(directory):
        # Skip hidden directories and venv
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != ".venv"]

        for file in files:
            if file.endswith(".py"):
                filepath = os.path.join(root, file)
                error = check_file_syntax(filepath)
                if error:
                    errors.append(error)

    return errors


def main():
    """Main function to find and report syntax errors."""
    print("Searching for Python files with syntax errors...")

    errors = find_syntax_errors()

    if not errors:
        print("\nNo syntax errors found!")
        return

    print(f"\nFound {len(errors)} files with syntax errors:\n")

    for error in errors:
        print(f"File: {error['file']}")
        print(f"  Line {error['line']}: {error['msg']}")
        if error["text"]:
            print(f"  Code: {error['text'].strip()}")
        if error["offset"]:
            print(f"  " + " " * 6 + " " * (error["offset"] - 1) + "^")
        print()


if __name__ == "__main__":
    main()
