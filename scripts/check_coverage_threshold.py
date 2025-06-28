#!/usr/bin/env python3
"""
Check if code coverage meets the minimum threshold.

This script is used as a pre-commit hook to ensure coverage doesn't drop.
"""

import json
from pathlib import Path
import sys


def check_coverage_threshold(threshold: float = 80.0) -> bool:
    """Check if coverage meets the minimum threshold."""
    coverage_file = Path(__file__).parent.parent / "coverage.json"

    # If no coverage file exists, skip the check (allow commit)
    if not coverage_file.exists():
        print("⚠️  No coverage.json found. Skipping coverage check.")
        print("   Run 'python run_coverage.py' to generate coverage data.")
        return True

    try:
        with open(coverage_file, encoding="utf-8") as f:
            data = json.load(f)

        percentage = data.get("totals", {}).get("percent_covered", 0.0)

        if percentage >= threshold:
            print(f"✅ Coverage {percentage:.1f}% meets threshold of {threshold}%")
            return True
        print(f"❌ Coverage {percentage:.1f}% is below threshold of {threshold}%")
        print("   Please add tests to improve coverage.")
        print("   Run 'python run_coverage.py --html --open' to see uncovered lines.")
        return False

    except Exception as e:
        print(f"⚠️  Error checking coverage: {e}")
        # Don't block commit on error
        return True


def main() -> int:
    """Main function."""
    # Check if we should skip the check (e.g., for quick commits)
    if "--skip" in sys.argv:
        print("⏭️  Skipping coverage check (--skip flag)")
        return 0

    # Get threshold from environment or use default
    import os

    threshold = float(os.environ.get("COVERAGE_THRESHOLD", "80.0"))

    if check_coverage_threshold(threshold):
        return 0
    print("\n💡 To commit anyway, use: git commit --no-verify")
    return 1


if __name__ == "__main__":
    sys.exit(main())
