#!/usr/bin/env python3
"""
Test runner for CI environments that runs non-GUI tests with coverage.
This version is specifically designed for GitHub Actions and other CI systems.
"""

import argparse
import os
import subprocess
import sys


def main():
    """Run non-GUI tests with coverage for CI environments."""
    parser = argparse.ArgumentParser(description="Run non-GUI tests in CI")
    parser.add_argument("--quiet", "-q", action="store_true", help="Quiet mode")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose mode")
    parser.add_argument("--maxfail", type=int, default=10, help="Stop after N failures")
    parser.add_argument("--parallel", "-p", type=int, help="Run tests in parallel")
    args = parser.parse_args()

    # Set environment for headless operation
    os.environ["CI"] = "true"
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    os.environ["PYTHONIOENCODING"] = "utf-8"
    os.environ["PYTHONUTF8"] = "1"

    # Build pytest command with coverage
    cmd = [sys.executable, "-m", "pytest"]

    # Disable caching for CI
    cmd.append("-p")
    cmd.append("no:cacheprovider")

    # Override pytest.ini to ensure coverage is enabled
    cmd.append("--override-ini=addopts=-v --color=yes")

    # Add coverage options
    cmd.extend(
        [
            "--cov=goesvfi",
            "--cov-report=xml",
            "--cov-report=html",
            "--junit-xml=test-results.xml",
        ]
    )

    # Add test reporting options
    cmd.extend(["--tb=short", "--no-header", "--disable-warnings"])

    # Add maxfail option
    cmd.extend(["--maxfail", str(args.maxfail)])

    # Add test paths, excluding GUI tests and problematic integration tests
    cmd.extend(
        [
            "--ignore=tests/gui/",
            "--ignore=tests/integration/test_goes_imagery_tab.py",
            "tests/",
        ]
    )

    # Add verbosity
    if args.quiet:
        cmd.append("--quiet")
    elif args.verbose:
        cmd.append("-vv")

    # Add parallel execution
    if args.parallel:
        cmd.extend(["-n", str(args.parallel)])

    # Run tests
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, check=False)

    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
