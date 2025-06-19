#!/usr/bin/env python3
"""Fix all indentation issues in reconcile_manager_refactored.py."""


def fix_reconcile_indentation():
    """Fix the indentation issues in reconcile_manager_refactored.py."""
    file_path = "goesvfi/integrity_check/reconcile_manager_refactored.py"

    with open(file_path, "r") as f:
        lines = f.readlines()

    fixed_lines = []

    for i, line in enumerate(lines):
        # For lines in the problematic range (439-550)
        if i >= 442 and i <= 550:
            # Lines with exactly 20 spaces should have 16
            if line.startswith("                    ") and not line.startswith(
                "                        "
            ):
                line = "                " + line[20:]  # Replace 20 spaces with 16
            # Lines that currently have 16 spaces should have 12
            elif line.startswith("                ") and not line.startswith(
                "                    "
            ):
                line = "            " + line[16:]  # Replace 16 spaces with 12

        # Special handling for except blocks
        if i >= 500 and i <= 522:
            if line.strip().startswith("except"):
                # except blocks should be at same level as try (12 spaces)
                line = "        " + line.lstrip()
            elif i == 506 and "Handle known errors" in line:
                # This comment should be indented inside except
                line = "            # Handle known errors\n"

        fixed_lines.append(line)

    with open(file_path, "w") as f:
        f.writelines(fixed_lines)

    print("Fixed indentation in reconcile_manager_refactored.py")


if __name__ == "__main__":
    fix_reconcile_indentation()
