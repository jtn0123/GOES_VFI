#!/usr/bin/env python3
"""Script to run linters on the GOES_VFI codebase, aligned with pre-commit configuration.
This provides a consistent way to lint the code and can be integrated with CI/CD.
"""

import argparse
from pathlib import Path
import subprocess
import sys

# Default directories to check
DEFAULT_PATHS = [
    "goesvfi",
    "tests",
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
        pass
    else:
        pass


def run_command(cmd: list[str]) -> tuple[int, str]:
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


def run_flake8(paths: list[str], jobs: int | None = None) -> tuple[int, str, int]:
    """Run flake8 on the given paths.

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
        print_colored(f"Flake8 found {issue_count} issues. ❌", RED)

    return exit_code, output, issue_count


def run_flake8_qt(paths: list[str]) -> tuple[int, str, int]:
    """DISABLED: flake8-qt-tr functionality removed due to configuration issues.

    Returns:
        Tuple of (exit_code, output, issue_count)
    """
    print_colored(
        "Flake8-Qt-TR disabled (removed due to configuration issues) ⚠️",
        YELLOW,
        bold=True,
    )
    return 0, "flake8-qt-tr disabled", 0


def run_vulture(paths: list[str]) -> tuple[int, str, int]:
    """DEPRECATED: Vulture is not included in pre-commit hooks.
    Dead code detection is partially covered by ruff.
    """
    print_colored(
        "Vulture is not included in pre-commit hooks. Dead code detection is partially covered by ruff.",
        YELLOW,
        bold=True,
    )
    return 0, "Vulture not in pre-commit configuration", 0


def run_flake8_bugbear(paths: list[str]) -> tuple[int, str, int]:
    """Run flake8 with bugbear plugin specifically enabled.

    Returns:
        Tuple of (exit_code, output, issue_count)
    """
    # Check if flake8 and bugbear are installed
    exit_code, _ = run_command(["flake8", "--help"])
    if exit_code != 0:
        print_colored("Flake8 is not installed. Skipping bugbear check.", YELLOW)
        return 0, "Flake8 not installed", 0

    # Check if bugbear plugin is available
    _, plugins_output = run_command(["flake8", "--version"])
    if "flake8-bugbear" not in plugins_output:
        print_colored(
            "Flake8-bugbear plugin not found. Install with 'pip install flake8-bugbear'",
            YELLOW,
        )
        return 0, "flake8-bugbear not installed", 0

    print_colored(f"\n{BOLD}Running Flake8-Bugbear (Bug Detection)...{RESET}", BLUE, bold=True)

    # Build flake8 command with bugbear-specific settings
    cmd = [
        "flake8",
        "--select=B",  # Select only bugbear errors (B001-B999)
        "--statistics",
    ]
    cmd.extend(paths)

    exit_code, output = run_command(cmd)

    # Count issues by counting lines with actual error reports
    issue_count = len([
        line for line in output.split("\n") if ":" in line and any(f"B{i:03d}" in line for i in range(1, 999))
    ])

    if exit_code == 0 and issue_count == 0:
        print_colored("Flake8-Bugbear found no bugs! ✅", GREEN, bold=True)
    elif issue_count > 0:
        print_colored(f"Flake8-Bugbear found {issue_count} potential bugs. ❌", RED)
    else:
        print_colored("Flake8-Bugbear completed with warnings.", YELLOW)

    return exit_code, output, issue_count


def run_mypy(paths: list[str], strict: bool = False) -> tuple[int, str, int]:
    """Run mypy type checking on the given paths.

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
        pass

    # Display summary based on the results
    if exit_code == 0:
        print_colored("Mypy found no type errors! ✅", GREEN, bold=True)
    else:
        print_colored(f"Mypy found {issue_count} type errors. ❌", RED)

    return exit_code, output, issue_count


def run_ruff_format(paths: list[str], check_only: bool = True) -> tuple[int, str, int]:
    """Run Ruff formatter on the given paths.

    Args:
        paths: List of file or directory paths to format
        check_only: Whether to only check for formatting issues without modifying files

    Returns:
        Tuple of (exit_code, output, issue_count)
    """
    print_colored(f"\n{BOLD}Running Ruff Formatter...{RESET}", BLUE, bold=True)

    # Check if ruff is available
    exit_code, _ = run_command(["ruff", "--version"])
    if exit_code != 0:
        print_colored("Ruff is not installed. Skipping ruff format check.", YELLOW)
        return 0, "Ruff not installed", 0

    # Build ruff format command
    cmd = ["ruff", "format"]

    # If we're only checking, add the --check flag
    if check_only:
        cmd.extend(("--check", "--diff"))  # Show the differences

    # Add paths
    cmd.extend(paths)

    exit_code, output = run_command(cmd)

    # Count issues by checking files that would be reformatted
    issue_count = output.count("would be reformatted") if output else 0

    # Print ruff output
    if output:
        pass

    # Display summary based on the results
    if exit_code == 0:
        print_colored("Ruff formatting check passed! ✅", GREEN, bold=True)
    elif check_only:
        print_colored(f"Ruff would reformat {issue_count} files. ❌", RED)
        print_colored(
            "Run with --format flag to apply the formatting changes",
            YELLOW,
            bold=True,
        )
    else:
        print_colored(f"Ruff reformatted {issue_count} files. ✅", GREEN)

    return exit_code, output, issue_count


# Keep black function for backward compatibility
def run_black(paths: list[str], check_only: bool = True) -> tuple[int, str, int]:
    """DEPRECATED: Black functionality is now handled by ruff format.
    This function redirects to ruff format for backward compatibility.
    """
    print_colored(
        "Black is deprecated in favor of Ruff. Using Ruff format instead...",
        YELLOW,
        bold=True,
    )
    return run_ruff_format(paths, check_only)


# Note: isort functionality is now handled by ruff
# Keeping this function as a stub for backward compatibility
def run_isort(paths: list[str], check_only: bool = True) -> tuple[int, str, int]:
    """DEPRECATED: Import sorting is now handled by ruff.
    This function is kept for backward compatibility.
    """
    print_colored(
        "Import sorting is now handled by Ruff. Use --ruff-only instead.",
        YELLOW,
        bold=True,
    )
    return 0, "isort functionality moved to ruff", 0


def run_ruff(paths: list[str], fix: bool = False) -> tuple[int, str, int]:
    """Run ruff linter on the given paths.

    Args:
        paths: List of file or directory paths to lint
        fix: Whether to automatically fix issues

    Returns:
        Tuple of (exit_code, output, issue_count)
    """
    print_colored(f"\n{BOLD}Running Ruff Linter...{RESET}", BLUE, bold=True)

    # Check if ruff is available
    exit_code, _ = run_command(["ruff", "--version"])
    if exit_code != 0:
        print_colored("Ruff is not installed. Skipping ruff check.", YELLOW)
        return 0, "Ruff not installed", 0

    # Build ruff command
    cmd = ["ruff", "check", "--output-format=concise"]

    if fix:
        cmd.extend(["--fix", "--exit-non-zero-on-fix"])

    cmd.extend(paths)

    exit_code, output = run_command(cmd)

    # Count issues by counting lines with file paths
    issue_count = len([line for line in output.split("\n") if line.strip() and ":" in line])

    if exit_code == 0:
        print_colored("Ruff found no issues! ✅", GREEN, bold=True)
    elif fix:
        print_colored(f"Ruff fixed {issue_count} issues. ✅", GREEN)
    else:
        print_colored(f"Ruff found {issue_count} issues. ❌", RED)

    return exit_code, output, issue_count


def run_pyright(paths: list[str]) -> tuple[int, str, int]:
    """Run pyright type checker on the given paths.

    Returns:
        Tuple of (exit_code, output, issue_count)
    """
    print_colored(f"\n{BOLD}Running Pyright Type Checker...{RESET}", BLUE, bold=True)

    # Check if pyright is available
    exit_code, _ = run_command(["pyright", "--version"])
    if exit_code != 0:
        print_colored("Pyright is not installed. Skipping pyright check.", YELLOW)
        return 0, "Pyright not installed", 0

    # Build pyright command
    cmd = ["pyright", *paths]

    exit_code, output = run_command(cmd)

    # Count issues by looking for error/warning lines
    issue_count = 0
    if output:
        for line in output.splitlines():
            if "error:" in line or "warning:" in line:
                issue_count += 1

    if exit_code == 0:
        print_colored("Pyright found no type errors! ✅", GREEN, bold=True)
    else:
        print_colored(f"Pyright found {issue_count} type issues. ❌", RED)

    return exit_code, output, issue_count


def run_bandit(paths: list[str]) -> tuple[int, str, int]:
    """Run bandit security scanner on the given paths.

    Returns:
        Tuple of (exit_code, output, issue_count)
    """
    print_colored(f"\n{BOLD}Running Bandit Security Scanner...{RESET}", BLUE, bold=True)

    # Check if bandit is available
    exit_code, _ = run_command(["bandit", "--version"])
    if exit_code != 0:
        print_colored("Bandit is not installed. Skipping security scan.", YELLOW)
        return 0, "Bandit not installed", 0

    # Build bandit command
    cmd = ["bandit", "-r", "-f", "txt"]
    cmd.extend(paths)

    exit_code, output = run_command(cmd)

    # Count issues by looking for "Issue:" lines
    issue_count = output.count("Issue:") if output else 0

    if exit_code == 0:
        print_colored("Bandit found no security issues! ✅", GREEN, bold=True)
    else:
        print_colored(f"Bandit found {issue_count} security issues. ❌", RED)

    return exit_code, output, issue_count


def run_safety() -> tuple[int, str, int]:
    """DEPRECATED: Safety is not included in pre-commit hooks.
    It only supports Poetry, not setuptools-based projects.
    """
    print_colored(
        "Safety is not included in pre-commit hooks (only supports Poetry).",
        YELLOW,
        bold=True,
    )
    return 0, "Safety not supported for setuptools projects", 0


def run_xenon(paths: list[str]) -> tuple[int, str, int]:
    """Run xenon complexity checker on the given paths.

    Returns:
        Tuple of (exit_code, output, issue_count)
    """
    print_colored(f"\n{BOLD}Running Xenon Complexity Checker...{RESET}", BLUE, bold=True)

    # Check if xenon is available
    exit_code, _ = run_command(["xenon", "--version"])
    if exit_code != 0:
        print_colored("Xenon is not installed. Skipping complexity check.", YELLOW)
        return 0, "Xenon not installed", 0

    # Build xenon command - matching pre-commit config
    cmd = ["xenon", "--max-absolute", "C"]

    # Filter to only check goesvfi files, matching pre-commit config
    filtered_paths = [path for path in paths if "goesvfi" in path or path == "goesvfi"]

    if not filtered_paths:
        print_colored("No goesvfi files to check for complexity.", YELLOW)
        return 0, "No goesvfi files", 0

    cmd.extend(filtered_paths)

    exit_code, output = run_command(cmd)

    # Count issues by looking for complexity grades worse than C
    issue_count = 0
    if output:
        for line in output.splitlines():
            if any(grade in line for grade in [" D ", " E ", " F "]):
                issue_count += 1

    if exit_code == 0:
        print_colored("Xenon found no high complexity code! ✅", GREEN, bold=True)
    else:
        print_colored(f"Xenon found {issue_count} high complexity functions. ❌", RED)

    return exit_code, output, issue_count


def run_pylint(paths: list[str], jobs: int | None = None) -> tuple[int, str, int]:
    """DEPRECATED: Pylint is not included in pre-commit hooks.
    Consider using ruff instead, which covers most pylint checks.
    """
    print_colored(
        "Pylint is not included in pre-commit hooks. Consider using ruff instead.",
        YELLOW,
        bold=True,
    )
    return 0, "Pylint not in pre-commit configuration", 0


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Run linters on GOES_VFI codebase")
    parser.add_argument(
        "paths",
        nargs="*",
        default=DEFAULT_PATHS,
        help=f"Paths to lint (default: {' '.join(DEFAULT_PATHS)})",
    )
    parser.add_argument("--jobs", "-j", type=int, help="Number of parallel jobs (default: auto)")
    parser.add_argument("--flake8-only", action="store_true", help="Run only flake8")
    parser.add_argument("--bugbear-only", action="store_true", help="Run only flake8-bugbear")
    parser.add_argument(
        "--vulture-only",
        action="store_true",
        help="Run only vulture (dead code finder)",
    )
    parser.add_argument("--pylint-only", action="store_true", help="Run only pylint")
    parser.add_argument("--mypy-only", action="store_true", help="Run only mypy type checking")
    parser.add_argument("--black-only", action="store_true", help="Run only Black code formatter")
    parser.add_argument("--isort-only", action="store_true", help="Run only isort import sorting")
    parser.add_argument("--ruff-only", action="store_true", help="Run only Ruff linter")
    parser.add_argument("--pyright-only", action="store_true", help="Run only Pyright type checker")
    parser.add_argument("--bandit-only", action="store_true", help="Run only Bandit security scanner")
    parser.add_argument("--safety-only", action="store_true", help="Run only Safety dependency scanner")
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
    parser.add_argument("--fix", action="store_true", help="Try to auto-fix issues (limited support)")
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
    print_colored("             GOES_VFI LINTER RUNNER                ", BLUE, bold=True)
    print_colored("=" * 70 + "\n", BLUE)

    # Run linters based on options
    if args.flake8_only:
        exit_code, _, issue_count = run_flake8(paths, args.jobs)
        linter_results.append(("Flake8", exit_code, issue_count))
    elif args.bugbear_only:
        exit_code, _, issue_count = run_flake8_bugbear(paths)
        linter_results.append(("Flake8-Bugbear", exit_code, issue_count))
    elif args.vulture_only:
        exit_code, _, issue_count = run_vulture(paths)
        linter_results.append(("Vulture", exit_code, issue_count))
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
    elif args.ruff_only:
        exit_code, _, issue_count = run_ruff(paths)
        linter_results.append(("Ruff", exit_code, issue_count))
    elif args.pyright_only:
        exit_code, _, issue_count = run_pyright(paths)
        linter_results.append(("Pyright", exit_code, issue_count))
    elif args.bandit_only:
        exit_code, _, issue_count = run_bandit(paths)
        linter_results.append(("Bandit", exit_code, issue_count))
    elif args.safety_only:
        exit_code, _, issue_count = run_safety()
        linter_results.append(("Safety", exit_code, issue_count))
    else:
        # Run all linters - first run static analyzers, then formatting tools
        flake8_code, _, flake8_count = run_flake8(paths, args.jobs)
        ruff_code, _, ruff_count = run_ruff(paths)
        bugbear_code, _, bugbear_count = run_flake8_bugbear(paths)
        vulture_code, _, vulture_count = run_vulture(paths)
        pylint_code, _, pylint_count = run_pylint(paths, args.jobs)
        mypy_code, _, mypy_count = run_mypy(paths, args.strict)
        pyright_code, _, pyright_count = run_pyright(paths)
        bandit_code, _, bandit_count = run_bandit(paths)
        safety_code, _, safety_count = run_safety()
        black_code, _, black_count = run_black(paths, check_only)
        isort_code, _, isort_count = run_isort(paths, check_only)

        linter_results.extend([
            ("Flake8", flake8_code, flake8_count),
            ("Ruff", ruff_code, ruff_count),
            ("Flake8-Bugbear", bugbear_code, bugbear_count),
            ("Vulture", vulture_code, vulture_count),
            ("Pylint", pylint_code, pylint_count),
            ("Mypy", mypy_code, mypy_count),
            ("Pyright", pyright_code, pyright_count),
            ("Bandit", bandit_code, bandit_count),
            ("Safety", safety_code, safety_count),
            ("Black", black_code, black_count),
            ("isort", isort_code, isort_count),
        ])

    # Print summary
    print_colored("\n" + "=" * 70, BLUE)
    print_colored("                   SUMMARY                      ", BLUE, bold=True)
    print_colored("=" * 70, BLUE)

    # Calculate total issues and display results by linter
    total_issues = 0
    exit_codes = []

    for linter_name, exit_code, issue_count in linter_results:
        total_issues += issue_count
        exit_codes.append(exit_code)

        # Choose color based on issue count
        color = GREEN if issue_count == 0 else YELLOW if issue_count < 10 else RED
        print_colored(f"{linter_name}: {issue_count} issues", color)

    # Display total and final result
    if all(code == 0 for code in exit_codes) and total_issues == 0:
        print_colored(f"Total: {total_issues} issues - All linters passed! 🎉", GREEN, bold=True)
        return 0
    color = YELLOW if total_issues < 20 else RED
    print_colored(
        f"Total: {total_issues} issues found - Check output above for details ⚠️",
        color,
        bold=True,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
