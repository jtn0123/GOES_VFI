#!/usr/bin/env python3
"""
Test runner that dynamically discovers and runs non-GUI tests.
This version automatically finds all non-GUI tests instead of using a hardcoded list.
"""

import argparse
import os
import subprocess
import sys


def main():
    """Run non-GUI tests suitable for CI environments."""
    parser = argparse.ArgumentParser(description="Run non-GUI tests")
    parser.add_argument("--quiet", "-q", action="store_true", help="Quiet mode")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose mode")
    parser.add_argument("--parallel", "-p", type=int, help="Run tests in parallel")
    args = parser.parse_args()

    # Set environment for headless operation
    os.environ["CI"] = "true"
    os.environ["QT_QPA_PLATFORM"] = "offscreen"

    # Build pytest command
    cmd = [sys.executable, "-m", "pytest"]

    # Add test paths, excluding GUI tests
    cmd.extend(["tests/unit", "tests/integration"])
    cmd.extend(["--ignore=tests/gui"])

    # Add verbosity
    if args.quiet:
        cmd.append("-q")
    elif args.verbose:
        cmd.append("-vv")
    else:
        cmd.append("-v")

    # Add parallel execution
    if args.parallel:
        cmd.extend(["-n", str(args.parallel)])

    # Run tests
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, check=False)

    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
