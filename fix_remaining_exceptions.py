#!/usr/bin/env python3
"""Fix remaining broad exception handlers."""

import re
from pathlib import Path


def fix_specific_exception(
    filepath: Path, line_num: int, exceptions: list, context: str = ""
) -> bool:
    """Fix a specific exception at a given line."""
    with open(filepath, "r") as f:
        lines = f.readlines()

    # Find the except line
    for i in range(max(0, line_num - 5), min(len(lines), line_num + 5)):
        if "except Exception" in lines[i]:
            # Get indentation and as clause
            indent = len(lines[i]) - len(lines[i].lstrip())
            indent_str = " " * indent

            as_match = re.search(r"except Exception(\s+as\s+\w+)?:", lines[i])
            if as_match:
                as_clause = as_match.group(1) or ""

                # Build new except line
                if len(exceptions) == 1:
                    new_line = f"{indent_str}except {exceptions[0]}{as_clause}:\n"
                else:
                    new_line = (
                        f"{indent_str}except ({', '.join(exceptions)}){as_clause}:\n"
                    )

                lines[i] = new_line

                with open(filepath, "w") as f:
                    f.writelines(lines)

                print(f"Fixed exception at line {i+1} in {filepath}")
                return True

    return False


def main():
    """Fix the remaining exceptions."""

    # Remaining broad exceptions to fix
    fixes = [
        # run_vfi.py
        (
            "goesvfi/pipeline/run_vfi.py",
            336,
            ["KeyError", "RuntimeError", "ValueError", "subprocess.CalledProcessError"],
        ),
        ("goesvfi/pipeline/run_vfi.py", 381, ["IOError", "OSError"]),
        (
            "goesvfi/pipeline/run_vfi.py",
            507,
            ["IOError", "ValueError", "AttributeError"],
        ),
        ("goesvfi/pipeline/run_vfi.py", 565, ["OSError", "PermissionError"]),
        (
            "goesvfi/pipeline/run_vfi.py",
            573,
            ["subprocess.CalledProcessError", "IOError", "RuntimeError"],
        ),
        ("goesvfi/pipeline/run_vfi.py", 604, ["ValueError", "TypeError"]),
        (
            "goesvfi/pipeline/run_vfi.py",
            817,
            ["TypeError", "ValueError", "AttributeError"],
        ),
        (
            "goesvfi/pipeline/run_vfi.py",
            1083,
            ["FileNotFoundError", "IOError", "OSError"],
        ),
        ("goesvfi/pipeline/run_vfi.py", 1231, ["OSError", "AttributeError"]),
        ("goesvfi/pipeline/run_vfi.py", 1249, ["IOError", "OSError"]),
        (
            "goesvfi/pipeline/run_vfi.py",
            1369,
            ["FileNotFoundError", "IOError", "OSError"],
        ),
        (
            "goesvfi/pipeline/run_vfi.py",
            1393,
            ["FileNotFoundError", "IOError", "OSError"],
        ),
        ("goesvfi/pipeline/run_vfi.py", 1431, ["IOError", "OSError"]),
        (
            "goesvfi/pipeline/run_vfi.py",
            1601,
            ["FileNotFoundError", "IOError", "OSError"],
        ),
        (
            "goesvfi/pipeline/run_vfi.py",
            1641,
            ["FileNotFoundError", "IOError", "OSError", "RuntimeError"],
        ),
        (
            "goesvfi/pipeline/run_vfi.py",
            1663,
            [
                "FileNotFoundError",
                "IOError",
                "OSError",
                "subprocess.CalledProcessError",
                "RuntimeError",
            ],
        ),
    ]

    fixed_count = 0

    for filepath, line_num, exceptions in fixes:
        path = Path(filepath)
        if path.exists():
            if fix_specific_exception(path, line_num, exceptions):
                fixed_count += 1

    print(f"\nTotal exceptions fixed: {fixed_count}")

    # Check what's still remaining
    print("\nChecking for remaining broad exceptions...")
    for filepath in [
        "goesvfi/pipeline/run_vfi.py",
        "goesvfi/integrity_check/remote/s3_store.py",
    ]:
        path = Path(filepath)
        if path.exists():
            with open(path, "r") as f:
                content = f.read()

            count = content.count("except Exception")
            if count > 0:
                print(f"{filepath}: {count} broad exceptions remaining")


if __name__ == "__main__":
    main()
