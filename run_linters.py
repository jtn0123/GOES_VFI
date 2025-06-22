#!/usr/bin/env python3
"""
Script to run Flake8, Flake8-Qt, and Pylint linters on the GOES_VFI codebase.
This provides a consistent way to lint the code and can be integrated with CI/CD.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple

# Default directories to check
DEFAULT_PATHS = [
    "goesvfi",
    "tests",
    "examples",
]

# Colors for terminal output
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"


def print_colored(message: str, color: str = RESET, bold: bool = False) -> None:
    """Print a message with color."""
    if bold:
        print(f"{BOLD}{color}{message}{RESET}")
    else:
        print(f"{color}{message}{RESET}")


def run_command(cmd: List[str]) -> Tuple[int, str]:
    """Run a command and return the exit code and output."""
    try:
        result = subprocess.run(
            cmd,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        return result.returncode, result.stdout
    except Exception as e:
        return 1, str(e)


def run_flake8(paths: List[str], jobs: Optional[int] = None) -> Tuple[int, str, int]:
    """
    Run flake8 on the given paths.

    Returns:
        Tuple of (exit_code, output, issue_count)
    """
    print_colored(f"\n{BOLD}Running Flake8...{RESET}", BLUE, bold=True)

    cmd = ["flake8", "--statistics"]
    if jobs:
        cmd.extend(["--jobs", str(jobs)])
    cmd.extend(paths)

    exit_code, output = run_command(cmd)

    # Parse output for actual count of issues
    issue_count = 0
    if output:
        # Count issues by looking for file paths reported
        issue_count = output.count(": ") if ":" in output else 0

    if exit_code == 0:
        print_colored("Flake8 found no issues! ✅", GREEN, bold=True)
        issue_count = 0  # Force to 0 if exit code is 0
    else:
        print(output)
        print_colored(f"Flake8 found {issue_count} issues. ❌", RED)

    return exit_code, output, issue_count


def run_flake8_qt(paths: List[str]) -> Tuple[int, str, int]:
    """
    Run flake8-qt-tr on the given paths focusing on PyQt files.

    Returns:
        Tuple of (exit_code, output, issue_count)
    """
    # Check if flake8 is installed
    exit_code, _ = run_command(["flake8", "--help"])
    if exit_code != 0:
        print_colored("Flake8 is not installed. Skipping Flake8-Qt-TR.", YELLOW)
        return 0, "Flake8 not installed", 0

    # Look for PyQt-specific plugins
    _, plugins_output = run_command(["flake8", "--version"])
    if "flake8-qt-tr" not in plugins_output:
        print_colored(
            "WARNING: flake8-qt-tr plugin not found. Install with 'pip install flake8-qt-tr'",
            YELLOW,
            bold=True,
        )
        return 0, "flake8-qt-tr plugin not found", 0

    print_colored(
        f"\n{BOLD}Running Flake8-Qt-TR for PyQt files...{RESET}", BLUE, bold=True
    )

    # Filter for PyQt files
    qt_paths = []
    for path in paths:
        # If path is a directory, include all Python files in it
        if os.path.isdir(path):
            for root, _, files in os.walk(path):
                for file in files:
                    if file.endswith(".py"):
                        qt_file_path = os.path.join(root, file)
                        qt_paths.append(qt_file_path)
        # If path is a file and it's a Python file, include it directly
        elif os.path.isfile(path) and path.endswith(".py"):
            qt_paths.append(path)

    if not qt_paths:
        print_colored("No PyQt files found to check.", BLUE)
        return 0, "No Qt files found", 0

    # First run with verbose output to check for silent failures
    verbose_cmd = [
        "flake8",
        "--select=TR",  # Select only Qt translation errors (TR001-TR999)
        "--verbose",  # Get verbose output to detect silent failures
    ]
    verbose_cmd.extend(qt_paths)

    _, verbose_output = run_command(verbose_cmd)

    # Check if the verbose output indicates issues were found but not reported
    silent_issues = 0
    if "Found a total of" in verbose_output:
        try:
            # Extract issue count from verbose output
            issue_part = (
                verbose_output.split("Found a total of")[1]
                .split("violations")[0]
                .strip()
            )
            silent_issues = int(issue_part)
        except (IndexError, ValueError):
            pass

    # Now run the standard command to get output for the user
    cmd = [
        "flake8",
        "--select=TR",  # Select only Qt translation errors (TR001-TR999)
        "--statistics",  # Show statistics
    ]
    cmd.extend(qt_paths)

    exit_code, output = run_command(cmd)

    # Count the actual issues reported in the output
    reported_issues = output.count("\n") if output else 0

    # Use the higher of the two counts
    issue_count = max(silent_issues, reported_issues)

    if exit_code == 0 and issue_count == 0:
        print_colored(
            "Flake8-Qt-TR found no translation issues in PyQt files! ✅",
            GREEN,
            bold=True,
        )
    elif exit_code == 0 and issue_count > 0:
        # This means we detected issues that weren't being reported - a plugin problem
        print_colored(
            f"⚠️ Flake8-Qt-TR found {issue_count} issues but didn't report them properly.",
            YELLOW,
            bold=True,
        )
        # Print the verbose output to help debug
        print_colored("Verbose output:", YELLOW)
        print(verbose_output)
        # Force exit code to be non-zero
        exit_code = 1
    else:
        print(output)
        print_colored(
            f"Flake8-Qt-TR found {issue_count} translation issues in PyQt files. ❌",
            RED,
        )

    return exit_code, output, issue_count


def run_mypy(paths: List[str], strict: bool = False) -> Tuple[int, str, int]:
    """
    Run mypy type checking on the given paths.

    Args:
        paths: List of file or directory paths to check
        strict: Whether to use strict mode for type checking

    Returns:
        Tuple of (exit_code, output, issue_count)
    """
    print_colored(f"\n{BOLD}Running Mypy Type Checking...{RESET}", BLUE, bold=True)

    # Check if mypy is available
    try:
        # Just check if we can import it without storing the module
        __import__("mypy")
    except ImportError:
        print_colored(
            "⚠️ Mypy is not properly installed in your environment. Skipping mypy checks.",
            YELLOW,
            bold=True,
        )
        print_colored("To install mypy: pip install mypy", YELLOW)
        return 1, "Mypy not installed", 1

    # Basic command with common options
    cmd = [".venv/bin/python", "-m", "mypy", "--disable-error-code=import-untyped"]

    if strict:
        cmd.append("--strict")

    cmd.extend(paths)

    exit_code, output = run_command(cmd)

    # Count issues by checking for error lines in the output
    issue_count = 0
    if output:
        for line in output.splitlines():
            if ": error:" in line:
                issue_count += 1

    # Print mypy output
    if output:
        print(output)

    # Display summary based on the results
    if exit_code == 0:
        print_colored("Mypy found no type errors! ✅", GREEN, bold=True)
    else:
        print_colored(f"Mypy found {issue_count} type errors. ❌", RED)

    return exit_code, output, issue_count


def run_black(paths: List[str], check_only: bool = True) -> Tuple[int, str, int]:
    """
    Run Black code formatter on the given paths.

    Args:
        paths: List of file or directory paths to format
        check_only: Whether to only check for formatting issues without modifying files

    Returns:
        Tuple of (exit_code, output, issue_count)
    """
    print_colored(f"\n{BOLD}Running Black Code Formatter...{RESET}", BLUE, bold=True)

    # Check if black is available
    try:
        # Just check if we can import it without storing the module
        __import__("black")
    except ImportError:
        print_colored(
            "⚠️ Black is not properly installed in your environment. Skipping Black checks.",
            YELLOW,
            bold=True,
        )
        print_colored("To install Black: pip install black", YELLOW)
        return 1, "Black not installed", 1

    # Basic command
    cmd = [".venv/bin/python", "-m", "black", "--line-length=120"]

    # If we're only checking, add the --check flag
    if check_only:
        cmd.append("--check")
        cmd.append("--diff")  # Show the differences

    # Add paths
    cmd.extend(paths)

    exit_code, output = run_command(cmd)

    # Count issues by checking files that would be reformatted
    issue_count = output.count("would be reformatted") if output else 0

    # Print black output
    if output:
        print(output)

    # Display summary based on the results
    if exit_code == 0:
        print_colored("Black formatting check passed! ✅", GREEN, bold=True)
    else:
        if check_only:
            print_colored(f"Black would reformat {issue_count} files. ❌", RED)
            print_colored(
                "Run with --format flag to apply the formatting changes",
                YELLOW,
                bold=True,
            )
        else:
            print_colored(f"Black reformatted {issue_count} files. ✅", GREEN)

    return exit_code, output, issue_count


def run_isort(paths: List[str], check_only: bool = True) -> Tuple[int, str, int]:
    """
    Run isort import sorter on the given paths.

    Args:
        paths: List of file or directory paths to sort imports in
        check_only: Whether to only check for sorting issues without modifying files

    Returns:
        Tuple of (exit_code, output, issue_count)
    """
    print_colored(f"\n{BOLD}Running isort Import Sorter...{RESET}", BLUE, bold=True)

    # Check if isort is available
    try:
        # Just check if we can import it without storing the module
        __import__("isort")
    except ImportError:
        print_colored(
            "⚠️ isort is not properly installed in your environment. Skipping isort checks.",
            YELLOW,
            bold=True,
        )
        print_colored("To install isort: pip install isort", YELLOW)
        return 1, "isort not installed", 1

    # Basic command - using same settings as pre-commit
    cmd = [".venv/bin/python", "-m", "isort"]

    # If we're only checking, add the --check flag
    if check_only:
        cmd.append("--check")
        cmd.append("--diff")  # Show the differences

    # Add paths
    cmd.extend(paths)

    exit_code, output = run_command(cmd)

    # Count issues by checking for "ERROR" lines in the output
    issue_count = 0
    if output:
        for line in output.splitlines():
            if "ERROR:" in line or "Skipped" in line:
                issue_count += 1

    # Print isort output
    if output:
        print(output)

    # Display summary based on the results
    if exit_code == 0:
        print_colored("isort import sorting check passed! ✅", GREEN, bold=True)
    else:
        if check_only:
            print_colored(f"isort would fix imports in {issue_count} files. ❌", RED)
            print_colored(
                "Run with --format flag to apply the import sorting changes",
                YELLOW,
                bold=True,
            )
        else:
            print_colored(f"isort fixed imports in {issue_count} files. ✅", GREEN)

    return exit_code, output, issue_count


def run_pylint(paths: List[str], jobs: Optional[int] = None) -> Tuple[int, str, int]:
    """
    Run pylint on the given paths.

    Returns:
        Tuple of (exit_code, output, issue_count)
    """
    print_colored(f"\n{BOLD}Running Pylint...{RESET}", BLUE, bold=True)

    # Check if pylint is available and handle any potential issues
    try:
        # Try to import pylint modules
        __import__("pylint")

        # Also check for the dill import issue
        try:
            # Check for dill import issues without storing the module
            __import__("dill")
        except ImportError as e:
            if "circular import" in str(e):
                print_colored(
                    "⚠️ Pylint has a dependency issue that prevents it from running correctly.",
                    YELLOW,
                    bold=True,
                )
                print_colored(
                    "This is a known issue with the dill package that pylint depends on.",
                    YELLOW,
                )
                print_colored(
                    "SOLUTION: Use ./run_only_flake8.py instead for linting with flake8 only:",
                    YELLOW,
                    bold=True,
                )
                print_colored(f"    python run_only_flake8.py {' '.join(paths)}", GREEN)
                return 1, "Circular import in dill package", 1
    except ImportError:
        print_colored(
            "⚠️ Pylint is not properly installed in your environment. Skipping pylint checks.",
            YELLOW,
            bold=True,
        )
        print_colored("To install pylint: pip install pylint", YELLOW)
        print_colored("Or use run_only_flake8.py which doesn't require pylint:", YELLOW)
        print_colored(f"    python run_only_flake8.py {' '.join(paths)}", GREEN)
        return 1, "Pylint not installed", 1

    cmd = ["pylint", "--output-format=parseable"]
    if jobs:
        cmd.extend(["--jobs", str(jobs)])
    cmd.extend(paths)

    exit_code, output = run_command(cmd)

    # Count the number of issues by counting lines in the output that match the pylint pattern
    issue_count = output.count(": ") if output else 0

    # Print pylint output
    print(output)

    # Pylint exit codes: 0=no issues, 1-15=increasing severity of issues
    if exit_code == 0:
        print_colored("Pylint found no issues! ✅", GREEN, bold=True)
    elif exit_code < 4:  # Convention/refactor issues only
        print_colored(
            f"Pylint found {issue_count} minor issues. Exit code: {exit_code} ⚠️",
            YELLOW,
        )
    elif exit_code < 8:  # Warning issues
        print_colored(
            f"Pylint found {issue_count} warnings. Exit code: {exit_code} ⚠️", YELLOW
        )
    else:  # Error/fatal issues
        print_colored(
            f"Pylint found {issue_count} significant issues. Exit code: {exit_code} ❌",
            RED,
        )

    # Normalize exit code to 0 or 1
    exit_code = min(exit_code, 1)

    return exit_code, output, issue_count


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Run linters on GOES_VFI codebase")
    parser.add_argument(
        "paths",
        nargs="*",
        default=DEFAULT_PATHS,
        help=f"Paths to lint (default: {' '.join(DEFAULT_PATHS)})",
    )
    parser.add_argument(
        "--jobs", "-j", type=int, help="Number of parallel jobs (default: auto)"
    )
    parser.add_argument("--flake8-only", action="store_true", help="Run only flake8")
    parser.add_argument(
        "--flake8-qt-only",
        action="store_true",
        help="Run only flake8-qt for PyQt files",
    )
    parser.add_argument("--pylint-only", action="store_true", help="Run only pylint")
    parser.add_argument(
        "--mypy-only", action="store_true", help="Run only mypy type checking"
    )
    parser.add_argument(
        "--black-only", action="store_true", help="Run only Black code formatter"
    )
    parser.add_argument(
        "--isort-only", action="store_true", help="Run only isort import sorting"
    )
    parser.add_argument("--strict", action="store_true", help="Run mypy in strict mode")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Only check formatting with Black/isort without modifying files (default)",
    )
    parser.add_argument(
        "--format",
        action="store_true",
        help="Apply formatting changes with Black/isort (will modify files)",
    )
    parser.add_argument(
        "--fix", action="store_true", help="Try to auto-fix issues (limited support)"
    )
    return parser.parse_args()


def main() -> int:
    """Run the linters and return an exit code."""
    args = parse_args()

    # Convert paths to absolute paths
    repo_root = Path(__file__).parent.absolute()
    paths = [str(repo_root / path) for path in args.paths]

    # Determine formatting mode (check only by default)
    # If neither --check nor --format is provided, default to check only
    # If both are provided, formatting wins
    check_only = True
    if args.format:
        check_only = False
    elif args.check:
        check_only = True

    # Track linter results and issue counts
    linter_results = []  # List of (linter_name, exit_code, issue_count) tuples

    # Print header
    print_colored("\n" + "=" * 70, BLUE)
    print_colored(
        "             GOES_VFI LINTER RUNNER                ", BLUE, bold=True
    )
    print_colored("=" * 70 + "\n", BLUE)

    # Run linters based on options
    if args.flake8_only:
        exit_code, _, issue_count = run_flake8(paths, args.jobs)
        linter_results.append(("Flake8", exit_code, issue_count))
    elif args.flake8_qt_only:
        exit_code, _, issue_count = run_flake8_qt(paths)
        linter_results.append(("Flake8-Qt-TR", exit_code, issue_count))
    elif args.pylint_only:
        exit_code, _, issue_count = run_pylint(paths, args.jobs)
        linter_results.append(("Pylint", exit_code, issue_count))
    elif args.mypy_only:
        exit_code, _, issue_count = run_mypy(paths, args.strict)
        linter_results.append(("Mypy", exit_code, issue_count))
    elif args.black_only:
        exit_code, _, issue_count = run_black(paths, check_only)
        linter_results.append(("Black", exit_code, issue_count))
    elif args.isort_only:
        exit_code, _, issue_count = run_isort(paths, check_only)
        linter_results.append(("isort", exit_code, issue_count))
    else:
        # Run all linters - first run static analyzers, then formatting tools
        flake8_code, _, flake8_count = run_flake8(paths, args.jobs)
        flake8_qt_code, _, flake8_qt_count = run_flake8_qt(paths)
        pylint_code, _, pylint_count = run_pylint(paths, args.jobs)
        mypy_code, _, mypy_count = run_mypy(paths, args.strict)
        black_code, _, black_count = run_black(paths, check_only)
        isort_code, _, isort_count = run_isort(paths, check_only)

        linter_results.extend(
            [
                ("Flake8", flake8_code, flake8_count),
                ("Flake8-Qt-TR", flake8_qt_code, flake8_qt_count),
                ("Pylint", pylint_code, pylint_count),
                ("Mypy", mypy_code, mypy_count),
                ("Black", black_code, black_count),
                ("isort", isort_code, isort_count),
            ]
        )

    # Print summary
    print_colored("\n" + "=" * 70, BLUE)
    print_colored("                   SUMMARY                      ", BLUE, bold=True)
    print_colored("=" * 70, BLUE)

    # Calculate total issues and display results by linter
    total_issues = 0
    exit_codes = []

    print()  # Add a blank line
    for linter_name, exit_code, issue_count in linter_results:
        total_issues += issue_count
        exit_codes.append(exit_code)

        # Choose color based on issue count
        color = GREEN if issue_count == 0 else YELLOW if issue_count < 10 else RED
        print_colored(f"{linter_name}: {issue_count} issues", color)

    print()  # Add another blank line

    # Display total and final result
    if all(code == 0 for code in exit_codes) and total_issues == 0:
        print_colored(
            f"Total: {total_issues} issues - All linters passed! 🎉", GREEN, bold=True
        )
        return 0
    else:
        color = YELLOW if total_issues < 20 else RED
        print_colored(
            f"Total: {total_issues} issues found - Check output above for details ⚠️",
            color,
            bold=True,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
