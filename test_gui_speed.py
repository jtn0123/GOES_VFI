#!/usr/bin/env python3
"""Script to test GUI test speed improvements."""

import time
import subprocess
import sys
from pathlib import Path

def run_single_gui_test(test_path):
    """Run a single GUI test and measure its execution time."""
    print(f"\n🧪 Testing: {test_path}")

    start_time = time.time()

    # Run the test with timeout
    try:
        result = subprocess.run([
            sys.executable, "-m", "pytest", 
            test_path,
            "-v",
            "--tb=short",
            "--timeout=60"  # 60 second timeout 
        ], 
        capture_output=True, 
        text=True,
        timeout=70  # Give subprocess a bit more time
        )

        end_time = time.time()
        duration = end_time - start_time

        if result.returncode == 0:
            print(f"✅ PASSED in {duration:.1f}s")
            return duration, "PASSED"
        else:
            print(f"❌ FAILED in {duration:.1f}s")
            print("STDERR:", result.stderr[-500:])  # Last 500 chars
            return duration, "FAILED"

    except subprocess.TimeoutExpired:
        print(f"⏰ TIMEOUT after 70s")
        return 70.0, "TIMEOUT"
    except Exception as e:
        print(f"💥 ERROR: {e}")
        return 0.0, "ERROR"

def main():
    """Test GUI test speed improvements."""
    print("🚀 Testing GUI Test Speed Improvements")
    print("=" * 50)

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
            print(f"⚠️  Test not found: {test}")

    # Summary
    print("\n" + "=" * 50)
    print("📊 RESULTS SUMMARY")
    print("=" * 50)

    total_time = 0
    passed_count = 0

    for test, duration, status in results:
        print(f"{status:8} | {duration:6.1f}s | {test}")
        total_time += duration
        if status == "PASSED":
            passed_count += 1

    print("-" * 50)
    print(f"Total time: {total_time:.1f}s")
    print(f"Average per test: {total_time / len(results):.1f}s")
    print(f"Passed: {passed_count}/{len(results)}")

    # Speed assessment
    avg_time = total_time / len(results) if results else 0
    if avg_time < 10:
        print("🎉 EXCELLENT: Tests are running fast!")
    elif avg_time < 30:
        print("✅ GOOD: Significant improvement from 157s!")
    elif avg_time < 60:
        print("⚠️  MODERATE: Better but still room for improvement")
    else:
        print("❌ SLOW: Tests still taking too long")

if __name__ == "__main__":
    main()