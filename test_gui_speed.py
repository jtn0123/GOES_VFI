#!/usr/bin/env python3
"""Script to test GUI test speed improvements."""

from pathlib import Path
import subprocess
import sys
import time


def run_single_gui_test(test_path):
    """Run a single GUI test and measure its execution time."""
    start_time = time.time()

    # Run the test with timeout
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                test_path,
                "-v",
                "--tb=short",
                "--timeout=60",  # 60 second timeout
            ],
            capture_output=True,
            text=True,
            timeout=70,
            check=False,  # Give subprocess a bit more time
        )

        end_time = time.time()
        duration = end_time - start_time

        if result.returncode == 0:
            return duration, "PASSED"
        return duration, "FAILED"

    except subprocess.TimeoutExpired:
        return 70.0, "TIMEOUT"
    except Exception:
        return 0.0, "ERROR"


def main() -> None:
    """Test GUI test speed improvements."""
    # Find a few representative GUI tests
    gui_tests = [
        "tests/gui/test_main_window.py::test_initial_state",
        "tests/gui/test_gui_component_validation.py::test_main_window_creation",
        "tests/gui/test_button_advanced.py::test_start_button_click_scenarios",
    ]

    results = []

    for test in gui_tests:
        test_path = Path(test)
        if test_path.exists() or "::" in test:
            duration, status = run_single_gui_test(test)
            results.append((test, duration, status))
        else:
            pass

    # Summary

    total_time = 0
    passed_count = 0

    for test, duration, status in results:
        total_time += duration
        if status == "PASSED":
            passed_count += 1

    # Speed assessment
    avg_time = total_time / len(results) if results else 0
    if avg_time < 10 or avg_time < 30 or avg_time < 60:
        pass
    else:
        pass


if __name__ == "__main__":
    main()
