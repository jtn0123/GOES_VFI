#!/usr/bin/env python3
"""Fix indentation issues in reconcile_manager_refactored.py."""

import re


def fix_reconcile_indentation():
    """Fix the indentation issues in reconcile_manager_refactored.py."""
    file_path = "goesvfi/integrity_check/reconcile_manager_refactored.py"

    with open(file_path, "r") as f:
        lines = f.readlines()

    # We're inside the _fetch_file_impl method starting around line 426
    # Everything after line 439 that has 16 spaces should have 12 spaces
    in_fetch_impl = False
    fixed_lines = []

    for i, line in enumerate(lines):
        if i >= 439 and i <= 520:  # The problematic region
            # If line starts with 16 spaces, reduce to 12
            if line.startswith("                ") and not line.startswith(
                "                    "
            ):
                line = line[4:]  # Remove 4 spaces

        fixed_lines.append(line)

    with open(file_path, "w") as f:
        f.writelines(fixed_lines)

    print("Fixed indentation in reconcile_manager_refactored.py")


if __name__ == "__main__":
    fix_reconcile_indentation()
