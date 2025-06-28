#!/usr/bin/env python3
"""
Careful workflow for optimizing tests with validation at each step.
This ensures we don't break test coverage while improving performance.
"""

import subprocess
import sys
import os
from pathlib import Path
from datetime import datetime
import json


class TestOptimizationWorkflow:
    """Manage the careful optimization of test files."""

    def __init__(self):
        self.baseline_file = None
        self.optimization_log = []

    def run_command(self, cmd: list) -> tuple[int, str]:
        """Run a command and return (returncode, output)."""
        print(f"🔧 Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode, result.stdout + result.stderr

    def step1_create_baseline(self):
        """Step 1: Create a baseline of current test results."""
        print("\n" + "="*80)
        print("📊 STEP 1: Creating baseline of current test results")
        print("="*80)

        # Run tests and save baseline
        cmd = ["python3", "run_all_tests.py", "--no-json", "--save-baseline", "--show-timing"]
        returncode, output = self.run_command(cmd)

        # Extract baseline filename from output
        for line in output.split('\n'):
            if "Baseline saved to:" in line:
                self.baseline_file = line.split("Baseline saved to:")[-1].strip()
                print(f"✅ Baseline saved: {self.baseline_file}")
                break

        return returncode == 0

    def step2_identify_slow_tests(self):
        """Step 2: Identify the slowest tests to optimize."""
        print("\n" + "="*80)
        print("🔍 STEP 2: Identifying slow tests")
        print("="*80)

        if not self.baseline_file or not os.path.exists(self.baseline_file):
            print("❌ No baseline file found!")
            return []

        with open(self.baseline_file, 'r') as f:
            baseline_data = json.load(f)

        # Find slow tests
        slow_tests = []
        for result in baseline_data["results"]:
            if result["duration"] > 5.0:  # Tests taking more than 5 seconds
                slow_tests.append({
                    "path": result["path"],
                    "duration": result["duration"],
                    "status": result["status"]
                })

        # Sort by duration
        slow_tests.sort(key=lambda x: x["duration"], reverse=True)

        print(f"\nFound {len(slow_tests)} slow tests (>5s):")
        for i, test in enumerate(slow_tests[:10], 1):
            print(f"{i:2d}. {test['duration']:6.2f}s - {test['path']} ({test['status']})")

        return slow_tests

    def step3_optimize_single_test(self, test_path: str):
        """Step 3: Optimize a single test file carefully."""
        print("\n" + "="*80)
        print(f"🔧 STEP 3: Optimizing {test_path}")
        print("="*80)

        # Check if test exists
        if not Path(test_path).exists():
            print(f"❌ Test file not found: {test_path}")
            return False

        # Analyze the test
        print("\n1️⃣ Analyzing test for optimization opportunities...")
        cmd = ["python3", "optimize_slow_tests.py", test_path]
        returncode, output = self.run_command(cmd)

        if returncode != 0:
            print("❌ Analysis failed")
            return False

        # Show analysis results
        print("\n" + output)

        # Ask user to proceed
        response = input("\n❓ Apply safe optimizations? (y/n): ")
        if response.lower() != 'y':
            print("⏭️  Skipping optimization")
            return False

        # Create optimized version
        optimized_path = Path(test_path).parent / f"{Path(test_path).stem}_optimized.py"

        # Apply safe optimizations manually (user should edit)
        print(f"\n2️⃣ Please manually apply optimizations to: {test_path}")
        print("   Following the patterns in: tests/utils/safe_test_optimizations.py")
        print(f"   Save as: {optimized_path}")
        input("\n   Press Enter when done...")

        if not optimized_path.exists():
            print("❌ Optimized file not found")
            return False

        return True

    def step4_validate_optimization(self, original_path: str, optimized_path: str):
        """Step 4: Validate that optimization didn't break tests."""
        print("\n" + "="*80)
        print("🔍 STEP 4: Validating optimization")
        print("="*80)

        # Run original test
        print("\n1️⃣ Running original test...")
        cmd = ["python3", "-m", "pytest", original_path, "-v", "--tb=short"]
        orig_return, orig_output = self.run_command(cmd)

        # Run optimized test  
        print("\n2️⃣ Running optimized test...")
        cmd = ["python3", "-m", "pytest", optimized_path, "-v", "--tb=short"]
        opt_return, opt_output = self.run_command(cmd)

        # Compare results
        print("\n3️⃣ Comparing results...")

        # Extract test counts
        import re

        def extract_counts(output):
            passed = len(re.findall(r'PASSED', output))
            failed = len(re.findall(r'FAILED', output))
            return passed, failed

        orig_passed, orig_failed = extract_counts(orig_output)
        opt_passed, opt_failed = extract_counts(opt_output)

        print(f"\nOriginal: {orig_passed} passed, {orig_failed} failed")
        print(f"Optimized: {opt_passed} passed, {opt_failed} failed")

        if orig_passed == opt_passed and orig_failed == opt_failed:
            print("✅ Test results match!")
            return True
        else:
            print("❌ Test results differ! Optimization may have broken tests.")
            return False

    def step5_measure_improvement(self):
        """Step 5: Measure performance improvement."""
        print("\n" + "="*80)
        print("📊 STEP 5: Measuring improvement")
        print("="*80)

        # Run all tests with current optimizations
        cmd = ["python3", "run_all_tests.py", "--no-json", "--compare-with", self.baseline_file]
        returncode, output = self.run_command(cmd)

        print("\nResults will show timing improvements and any regressions.")

        return returncode == 0

    def step6_commit_optimization(self, original_path: str, optimized_path: str):
        """Step 6: Replace original with optimized version."""
        print("\n" + "="*80)
        print("💾 STEP 6: Committing optimization")
        print("="*80)

        # Backup original
        backup_path = f"{original_path}.backup"
        print(f"\n1️⃣ Backing up original to: {backup_path}")
        Path(original_path).rename(backup_path)

        # Move optimized to original location
        print(f"2️⃣ Replacing with optimized version")
        Path(optimized_path).rename(original_path)

        # Update PROBLEMATIC_TESTS if needed
        print("\n3️⃣ Remember to remove from PROBLEMATIC_TESTS in run_all_tests.py if test now passes!")

        # Log the optimization
        self.optimization_log.append({
            "timestamp": datetime.now().isoformat(),
            "test": original_path,
            "backup": backup_path
        })

        return True

    def run_workflow(self):
        """Run the complete optimization workflow."""
        print("🚀 TEST OPTIMIZATION WORKFLOW")
        print("This will help you safely optimize slow tests with validation.\n")

        # Step 1: Create baseline
        if not self.step1_create_baseline():
            print("❌ Failed to create baseline. Fix test issues first!")
            return

        # Step 2: Identify slow tests
        slow_tests = self.step2_identify_slow_tests()
        if not slow_tests:
            print("✅ No slow tests found!")
            return

        # Ask which test to optimize
        print("\n" + "="*80)
        print("📋 SELECT TEST TO OPTIMIZE")
        print("="*80)

        for i, test in enumerate(slow_tests[:10], 1):
            print(f"{i}. {test['path']} ({test['duration']:.2f}s)")

        try:
            choice = int(input("\nSelect test number (or 0 to exit): "))
            if choice == 0:
                return

            selected_test = slow_tests[choice - 1]
        except (ValueError, IndexError):
            print("❌ Invalid selection")
            return

        # Step 3: Optimize the test
        test_path = selected_test["path"]
        if not self.step3_optimize_single_test(test_path):
            return

        # Step 4: Validate optimization
        optimized_path = Path(test_path).parent / f"{Path(test_path).stem}_optimized.py"
        if not self.step4_validate_optimization(test_path, str(optimized_path)):
            print("\n⚠️  Optimization validation failed!")
            print("Please review and fix the optimized test.")
            return

        # Step 5: Measure improvement
        self.step5_measure_improvement()

        # Step 6: Ask to commit
        response = input("\n❓ Commit this optimization? (y/n): ")
        if response.lower() == 'y':
            self.step6_commit_optimization(test_path, str(optimized_path))
            print("\n✅ Optimization complete!")
        else:
            print("\n⏭️  Optimization not committed")

        # Ask to continue
        response = input("\n❓ Optimize another test? (y/n): ")
        if response.lower() == 'y':
            self.run_workflow()


def main():
    """Main entry point."""
    workflow = TestOptimizationWorkflow()

    try:
        workflow.run_workflow()
    except KeyboardInterrupt:
        print("\n\n⏹️  Workflow interrupted")

    if workflow.optimization_log:
        print("\n📋 Optimization Summary:")
        for entry in workflow.optimization_log:
            print(f"  - {entry['test']} (backup: {entry['backup']})")


if __name__ == "__main__":
    main()