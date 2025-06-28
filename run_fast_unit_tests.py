#!/usr/bin/env python3
"""Script to run new fast unit tests for high-value components."""

from pathlib import Path
import subprocess
import sys
import time


def run_test_suite(test_files, description):
    """Run a suite of tests and report results."""
    total_time = 0
    results = []

    for test_file in test_files:
        if not Path(test_file).exists():
            continue

        start_time = time.time()
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", test_file, "-v", "--tb=short"],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )

            end_time = time.time()
            duration = end_time - start_time
            total_time += duration

            if result.returncode == 0:
                # Count total tests from pytest output
                passed_count = result.stdout.count(" PASSED")
                total_line = [line for line in result.stdout.split("\n") if "passed" in line and "in" in line]
                if total_line:
                    # Try to extract actual test count from summary line
                    import re

                    match = re.search(r"(\d+) passed", total_line[-1])
                    if match:
                        passed_count = int(match.group(1))
                results.append((test_file, "PASSED", duration, passed_count))
            else:
                result.stdout.count(" FAILED") + result.stdout.count(" ERROR")
                # Extract failed count from summary
                import re

                summary_lines = [line for line in result.stdout.split("\n") if "failed" in line]
                if summary_lines:
                    match = re.search(r"(\d+) failed", summary_lines[-1])
                    if match:
                        int(match.group(1))
                results.append((test_file, "FAILED", duration, 0))

        except subprocess.TimeoutExpired:
            results.append((test_file, "TIMEOUT", 30.0, 0))
        except Exception:
            results.append((test_file, "ERROR", 0.0, 0))

    return results, total_time


def main() -> int:
    """Run high-value fast unit tests."""
    # Define test suites by priority
    critical_tests = [
        "tests/unit/test_settings_persistence.py",
        "tests/unit/test_validation_pipeline.py",
        "tests/unit/test_worker_factory.py",
        "tests/unit/test_config_management.py",
    ]

    important_tests = [
        "tests/unit/test_error_handler_chain.py",
        "tests/unit/test_processing_state_management.py",
        "tests/unit/test_resource_manager_fast.py",
        "tests/unit/test_error_classifier_fast.py",
    ]

    # Run critical tests first
    critical_results, critical_time = run_test_suite(critical_tests, "Critical Business Logic Tests")

    # Run important tests
    important_results, important_time = run_test_suite(important_tests, "Important Infrastructure Tests")

    # Overall summary

    all_results = critical_results + important_results
    total_time = critical_time + important_time

    total_tests = 0
    passed_tests = 0

    for _test_file, status, _duration, test_count in all_results:
        total_tests += test_count
        if status == "PASSED":
            passed_tests += test_count

    # Speed assessment
    if total_time < 10 or total_time < 30:
        pass
    else:
        pass

    # Coverage assessment
    coverage_areas = [
        "Settings & Configuration Management",
        "Input Validation Pipeline",
        "Parameter Mapping & Conversion",
        "Error Handling & Recovery",
        "State Management & Workflows",
        "System Resource Management",
        "Error Classification & Routing",
        "TOML Configuration Loading & Validation",
    ]

    for _area in coverage_areas:
        pass

    return 0 if passed_tests == total_tests else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
