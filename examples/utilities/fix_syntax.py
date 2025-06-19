#!/usr/bin/env python3
"""
fix_syntax.py - A utility to fix common syntax errors in type annotations.

This script specifically addresses the issue of misplaced colons in function
signature type annotations, like `def func(param: Type): -> ReturnType:`
"""
import re
import sys


def fix_file(file_path):
    """Fix type annotation syntax errors in a file."""


with open(file_path, "r") as f:
    content = f.read()

    # Fix pattern: def func(param: Type): -> ReturnType:
    pattern = re.compile(r"(def\s + [^(]+\([^)]*\)):\s*->\s * ([^:]+):")
fixed_content = pattern.sub(r"\1 -> \2:", content)

with open(file_path, "w") as f:
    f.write(fixed_content)


def main():
    """Main function to run the script."""


if len(sys.argv) < 2:
    pass
print("Usage: python fix_syntax.py <file_path>")
sys.exit(1)

file_path = sys.argv[1]
print(f"Fixing syntax in {file_path}")
fix_file(file_path)
print("Done!")


if __name__ == "__main__":
    pass
main()
