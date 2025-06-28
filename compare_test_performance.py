#!/usr/bin/env python3
"""Compare performance between original and optimized tests.

This script runs a sample of tests to demonstrate performance improvements.
"""

from pathlib import Path
import subprocess
import time


def run_test_with_timing(test_file: str, label: str) -> float:
    """Run a test file and return execution time."""
    start_time = time.time()

    # Run pytest with minimal output
    cmd = ["python3", "-m", "pytest", test_file, "-v", "--tb=short", "-p", "no:warnings", "--no-header"]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        elapsed = time.time() - start_time

        # Extract test count from output
        output_lines = result.stdout.split("\n")
        test_count = 0
        for line in output_lines:
            if " passed" in line or " PASSED" in line:
                test_count += 1

        # Show summary line
        for line in output_lines[-10:]:
            if "passed" in line and "in" in line:
                break

        return elapsed
    except Exception:
        return 0.0


def main() -> None:
    """Compare test performance."""
    # Test pairs to compare
    comparisons = [
        {
            "name": "GUI Component Test (MainTab)",
            "original": "tests/unit/test_main_tab.py",
            "optimized": "tests/unit/test_main_tab_optimized_v2.py",
        },
        {
            "name": "Security Validation Test",
            "original": "tests/unit/test_security.py",
            "optimized": "tests/unit/test_security_optimized_v2.py",
        },
    ]

    total_original_time = 0
    total_optimized_time = 0

    for comparison in comparisons:
        # Check if files exist
        original_path = Path(comparison["original"])
        optimized_path = Path(comparison["optimized"])

        if not original_path.exists():
            continue

        if not optimized_path.exists():
            continue

        # Run original
        original_time = run_test_with_timing(comparison["original"], "ORIGINAL")
        total_original_time += original_time

        # Run optimized
        optimized_time = run_test_with_timing(comparison["optimized"], "OPTIMIZED V2")
        total_optimized_time += optimized_time

        # Calculate improvement
        if original_time > 0:
            ((original_time - optimized_time) / original_time) * 100
            original_time / optimized_time if optimized_time > 0 else 0

    # Overall summary

    if total_original_time > 0:
        ((total_original_time - total_optimized_time) / total_original_time) * 100
        total_original_time / total_optimized_time if total_optimized_time > 0 else 0

        # Extrapolate to full test suite


if __name__ == "__main__":
    main()
