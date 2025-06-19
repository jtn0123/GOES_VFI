# \!/usr/bin/env python3
"""Fix all docstring issues in time_index_refactored.py"""

import re


def fix_docstrings():
    """Fix missing docstring quotes."""
    file_path = "goesvfi/integrity_check/time_index_refactored.py"

    with open(file_path, "r") as f:
        lines = f.readlines()

    i = 0
    while i < len(lines):
        line = lines[i].rstrip()

        # Check if this is a function definition
        if line.startswith("def ") and line.endswith(":"):
            # Check next line for docstring
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                # If next line doesn't start with """ but has text, it's a missing docstring quote
                if (
                    next_line
                    and not next_line.startswith('"""')
                    and not next_line.startswith("#")
                    and not next_line.startswith("return")
                    and not next_line.startswith("pass")
                ):
                    # This is likely a docstring without quotes
                    lines[i + 1] = lines[i + 1].replace(
                        next_line, f'    """{next_line}'
                    )

                    # Find the end of the docstring by looking for a line that ends the docstring block
                    j = i + 2
                    while j < len(lines):
                        current = lines[j].strip()
                        # Look for the start of the function body or a pattern that indicates end of docstring
                        if (
                            current.startswith("return")
                            or current.startswith("pass")
                            or current.startswith("#")
                            or current.startswith("raise")
                            or current.startswith("if ")
                            or current.startswith("for ")
                            or current.startswith("while ")
                            or current.startswith("try:")
                            or current.startswith("with ")
                            or (j > i + 2 and not current)
                        ):  # Empty line after docstring content
                            # Insert closing quotes on the line before
                            if lines[j - 1].strip() and not lines[
                                j - 1
                            ].strip().endswith('"""'):
                                lines[j - 1] = lines[j - 1].rstrip() + '\n    """\n'
                            break
                        j += 1
        i += 1

    with open(file_path, "w") as f:
        f.writelines(lines)

    print(f"Fixed docstrings in {file_path}")


if __name__ == "__main__":
    fix_docstrings()
