#!/usr/bin/env python3
"""Fix final linting issues."""


def fix_blank_lines():
    """Fix too many blank lines issues."""
    files_to_fix = [
        ("goesvfi/pipeline/cache.py", 22, 6),
        ("goesvfi/pipeline/interpolate.py", 23, 5),
        ("goesvfi/pipeline/loader.py", 12, 3),
        ("goesvfi/pipeline/tiler.py", 14, 5),
    ]

    for filepath, line_num, extra_lines in files_to_fix:
        print(f"Fixing {filepath} line {line_num} ({extra_lines} extra lines)...")

        with open(filepath, "r") as f:
            lines = f.readlines()

        # Remove extra blank lines before the specified line
        # We need to keep 2 blank lines, so remove (extra_lines - 2)
        remove_count = extra_lines - 2

        # Find the position to start removing
        start = line_num - extra_lines
        for i in range(remove_count):
            if start < len(lines) and lines[start].strip() == "":
                lines.pop(start)

        with open(filepath, "w") as f:
            f.writelines(lines)

    print("✓ Fixed all blank line issues")


if __name__ == "__main__":
    fix_blank_lines()
