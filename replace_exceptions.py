#!/usr/bin/env python3
"""Replace broad exception handlers with specific ones based on TODO comments."""

import re
from pathlib import Path
from typing import List, Tuple


def parse_todo_exceptions(todo_comment: str) -> List[str]:
    """Extract suggested exceptions from TODO comment."""
    # Look for pattern like "TODO: Replace with specific exceptions: X, Y, Z"
    match = re.search(r"TODO.*specific exceptions?:\s*([^\\n]+)", todo_comment)
    if match:
        exceptions_str = match.group(1)
        # Extract exception names
        exceptions = []
        for exc in exceptions_str.split(","):
            exc = exc.strip()
            # Remove any trailing comments or parentheses
            exc = exc.split("(")[0].strip()
            if exc and exc[0].isupper():  # Basic check for exception name
                exceptions.append(exc)
        return exceptions
    return []


def replace_broad_exceptions(filepath: Path) -> int:
    """Replace broad exception handlers with specific ones."""
    if not filepath.exists():
        return 0

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.split("\n")
    new_lines = []
    replacements = 0
    i = 0

    while i < len(lines):
        line = lines[i]

        # Check if this is a TODO comment about exceptions
        if "TODO: Replace with specific exceptions:" in line and i + 1 < len(lines):
            todo_line = line
            next_line = lines[i + 1] if i + 1 < len(lines) else ""

            # Check if next line is "except Exception"
            if "except Exception" in next_line:
                # Extract suggested exceptions
                exceptions = parse_todo_exceptions(todo_line)

                if exceptions:
                    # Get the indentation and "as" clause if present
                    indent = len(next_line) - len(next_line.lstrip())
                    indent_str = next_line[:indent]

                    # Check for "as" clause
                    as_match = re.search(r"except Exception(\s+as\s+\w+)?:", next_line)
                    as_clause = (
                        as_match.group(1) if as_match and as_match.group(1) else ""
                    )

                    # Create new except line
                    if len(exceptions) == 1:
                        new_except = f"{indent_str}except {exceptions[0]}{as_clause}:"
                    else:
                        new_except = (
                            f"{indent_str}except ({', '.join(exceptions)}){as_clause}:"
                        )

                    # Skip the TODO comment and replace the except line
                    i += 1  # Skip TODO
                    new_lines.append(new_except)
                    replacements += 1
                    i += 1  # Skip the old except line
                    continue

        new_lines.append(line)
        i += 1

    if replacements > 0:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(new_lines))
        print(f"Replaced {replacements} exception handlers in {filepath}")

    return replacements


def main():
    """Replace exceptions in files that have TODO comments."""
    files_to_fix = [
        "goesvfi/pipeline/run_vfi.py",
        "goesvfi/integrity_check/remote/s3_store.py",
        "goesvfi/integrity_check/sample_processor.py",
        "goesvfi/integrity_check/goes_imagery.py",
        "goesvfi/integrity_check/render/netcdf.py",
    ]

    total_replaced = 0

    for filepath in files_to_fix:
        path = Path(filepath)
        if path.exists():
            replaced = replace_broad_exceptions(path)
            total_replaced += replaced

    print(f"\nTotal exception handlers replaced: {total_replaced}")


if __name__ == "__main__":
    main()
