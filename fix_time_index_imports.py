# \!/usr/bin/env python3
"""Fix time_index_refactored.py typing imports."""


def fix_time_index_imports():
    """Fix the imports in time_index_refactored.py"""
    file_path = "goesvfi/integrity_check/time_index_refactored.py"

    with open(file_path, "r") as f:
        content = f.read()

    # The imports were incorrectly placed in the docstring
    # Move them outside
    lines = content.splitlines()

    # Find the end of the docstring
    new_lines = []
    in_docstring = False
    docstring_count = 0

    for i, line in enumerate(lines):
        if line.strip() == '"""':
            docstring_count += 1
            if docstring_count == 1:
                # Start of docstring
                new_lines.append(line)
                in_docstring = True
            elif docstring_count == 2:
                # End of docstring - this is where we insert imports
                new_lines.append(line)
                new_lines.append("")
                new_lines.append(
                    "from typing import Dict, List, Optional, Pattern, Tuple"
                )
                in_docstring = False
        elif in_docstring and "from typing import" in line:
            # Skip the import line inside docstring
            continue
        else:
            new_lines.append(line)

    content = "\n".join(new_lines)

    # Also fix the COMPILED_PATTERNS type annotation
    content = content.replace(
        "COMPILED_PATTERNS = {", "COMPILED_PATTERNS: Dict[str, Pattern[str]] = {"
    )

    with open(file_path, "w") as f:
        f.write(content)

    print(f"Fixed {file_path}")


if __name__ == "__main__":
    fix_time_index_imports()
