#!/usr/bin/env python3
"""Simple script to run pylint on a single file and print the score."""

import re
import subprocess
import sys
from pathlib import Path


def run_pylint_on_file(file_path: str) -> float:
    """
    Run pylint on a single file and return the score.

    Args:
        file_path: Path to the file to lint

    Returns:
        The pylint score as a float or 0.0 if there was an error
    """
    try:
        # Run pylint with capturing stdout/stderr
        result = subprocess.run(
            ["python3", "-m", "pylint", file_path],
            capture_output=True,
            text=True,
            check=False,
        )

        # Extract score using regex
        score_match = re.search(
            r"Your code has been rated at (-?\d+\.\d+)/10", result.stdout
        )

        if score_match:
            return float(score_match.group(1))

        # Try stderr if not found in stdout
        score_match = re.search(
            r"Your code has been rated at (-?\d+\.\d+)/10", result.stderr
        )

        if score_match:
            return float(score_match.group(1))

        print("Pylint score not found in output")
        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)
        return 0.0

    except Exception as e:
        print(f"Error running pylint: {e}")
        return 0.0


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <file_path>")
        sys.exit(1)

    file_path = sys.argv[1]
    if not Path(file_path).exists():
        print(f"Error: File not found: {file_path}")
        sys.exit(1)

    score = run_pylint_on_file(file_path)
    print(f"Pylint score: {score}/10")


if __name__ == "__main__":
    main()
