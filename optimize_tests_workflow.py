#!/usr/bin/env python3
"""Careful workflow for optimizing tests with validation at each step.
This ensures we don't break test coverage while improving performance.
"""

import contextlib
from datetime import datetime
import json
import operator
import os
from pathlib import Path
import subprocess


class TestOptimizationWorkflow:
    """Manage the careful optimization of test files."""

    def __init__(self) -> None:
        self.baseline_file = None
        self.optimization_log = []

    def run_command(self, cmd: list) -> tuple[int, str]:
        """Run a command and return (returncode, output)."""
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return result.returncode, result.stdout + result.stderr

    def step1_create_baseline(self):
        """Step 1: Create a baseline of current test results."""
        # Run tests and save baseline
        cmd = ["python3", "run_all_tests.py", "--no-json", "--save-baseline", "--show-timing"]
        returncode, output = self.run_command(cmd)

        # Extract baseline filename from output
        for line in output.split("\n"):
            if "Baseline saved to:" in line:
                self.baseline_file = line.split("Baseline saved to:")[-1].strip()
                break

        return returncode == 0

    def step2_identify_slow_tests(self):
        """Step 2: Identify the slowest tests to optimize."""
        if not self.baseline_file or not os.path.exists(self.baseline_file):
            return []

        with open(self.baseline_file, encoding="utf-8") as f:
            baseline_data = json.load(f)

        # Find slow tests
        # Tests taking more than 5 seconds
        slow_tests = [
            {"path": result["path"], "duration": result["duration"], "status": result["status"]}
            for result in baseline_data["results"]
            if result["duration"] > 5.0
        ]

        # Sort by duration
        slow_tests.sort(key=operator.itemgetter("duration"), reverse=True)

        for _i, _test in enumerate(slow_tests[:10], 1):
            pass

        return slow_tests

    def step3_optimize_single_test(self, test_path: str) -> bool:
        """Step 3: Optimize a single test file carefully."""
        # Check if test exists
        if not Path(test_path).exists():
            return False

        # Analyze the test
        cmd = ["python3", "optimize_slow_tests.py", test_path]
        returncode, _output = self.run_command(cmd)

        if returncode != 0:
            return False

        # Show analysis results

        # Ask user to proceed
        response = input("\n❓ Apply safe optimizations? (y/n): ")
        if response.lower() != "y":
            return False

        # Create optimized version
        optimized_path = Path(test_path).parent / f"{Path(test_path).stem}_optimized.py"

        # Apply safe optimizations manually (user should edit)
        input("\n   Press Enter when done...")

        return optimized_path.exists()

    def step4_validate_optimization(self, original_path: str, optimized_path: str) -> bool:
        """Step 4: Validate that optimization didn't break tests."""
        # Run original test
        cmd = ["python3", "-m", "pytest", original_path, "-v", "--tb=short"]
        _orig_return, orig_output = self.run_command(cmd)

        # Run optimized test
        cmd = ["python3", "-m", "pytest", optimized_path, "-v", "--tb=short"]
        _opt_return, opt_output = self.run_command(cmd)

        # Compare results

        # Extract test counts
        import re

        def extract_counts(output):
            passed = len(re.findall(r"PASSED", output))
            failed = len(re.findall(r"FAILED", output))
            return passed, failed

        orig_passed, orig_failed = extract_counts(orig_output)
        opt_passed, opt_failed = extract_counts(opt_output)

        return bool(orig_passed == opt_passed and orig_failed == opt_failed)

    def step5_measure_improvement(self):
        """Step 5: Measure performance improvement."""
        # Run all tests with current optimizations
        cmd = ["python3", "run_all_tests.py", "--no-json", "--compare-with", self.baseline_file]
        returncode, _output = self.run_command(cmd)

        return returncode == 0

    def step6_commit_optimization(self, original_path: str, optimized_path: str) -> bool:
        """Step 6: Replace original with optimized version."""
        # Backup original
        backup_path = f"{original_path}.backup"
        Path(original_path).rename(backup_path)

        # Move optimized to original location
        Path(optimized_path).rename(original_path)

        # Update PROBLEMATIC_TESTS if needed

        # Log the optimization
        self.optimization_log.append({
            "timestamp": datetime.now().isoformat(),
            "test": original_path,
            "backup": backup_path,
        })

        return True

    def run_workflow(self) -> None:
        """Run the complete optimization workflow."""
        # Step 1: Create baseline
        if not self.step1_create_baseline():
            return

        # Step 2: Identify slow tests
        slow_tests = self.step2_identify_slow_tests()
        if not slow_tests:
            return

        # Ask which test to optimize

        for _i, _test in enumerate(slow_tests[:10], 1):
            pass

        try:
            choice = int(input("\nSelect test number (or 0 to exit): "))
            if choice == 0:
                return

            selected_test = slow_tests[choice - 1]
        except (ValueError, IndexError):
            return

        # Step 3: Optimize the test
        test_path = selected_test["path"]
        if not self.step3_optimize_single_test(test_path):
            return

        # Step 4: Validate optimization
        optimized_path = Path(test_path).parent / f"{Path(test_path).stem}_optimized.py"
        if not self.step4_validate_optimization(test_path, str(optimized_path)):
            return

        # Step 5: Measure improvement
        self.step5_measure_improvement()

        # Step 6: Ask to commit
        response = input("\n❓ Commit this optimization? (y/n): ")
        if response.lower() == "y":
            self.step6_commit_optimization(test_path, str(optimized_path))
        else:
            pass

        # Ask to continue
        response = input("\n❓ Optimize another test? (y/n): ")
        if response.lower() == "y":
            self.run_workflow()


def main() -> None:
    """Main entry point."""
    workflow = TestOptimizationWorkflow()

    with contextlib.suppress(KeyboardInterrupt):
        workflow.run_workflow()

    if workflow.optimization_log:
        for _entry in workflow.optimization_log:
            pass


if __name__ == "__main__":
    main()
