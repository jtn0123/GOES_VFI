#!/usr/bin/env python3
"""
Compare performance between original and optimized tests.

This script runs a sample of tests to demonstrate performance improvements.
"""

import subprocess
import time
from pathlib import Path


def run_test_with_timing(test_file: str, label: str) -> float:
    """Run a test file and return execution time."""
    print(f"\n{'='*60}")
    print(f"Running {label}: {test_file}")
    print('='*60)

    start_time = time.time()

    # Run pytest with minimal output
    cmd = [
        "python3", "-m", "pytest",
        test_file,
        "-v",
        "--tb=short",
        "-p", "no:warnings",
        "--no-header"
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        elapsed = time.time() - start_time

        # Extract test count from output
        output_lines = result.stdout.split('\n')
        test_count = 0
        for line in output_lines:
            if " passed" in line or " PASSED" in line:
                test_count += 1

        print(f"✓ Completed in {elapsed:.2f}s")
        print(f"✓ {test_count} tests executed")

        # Show summary line
        for line in output_lines[-10:]:
            if "passed" in line and "in" in line:
                print(f"✓ {line.strip()}")
                break

        return elapsed
    except Exception as e:
        print(f"✗ Error running test: {e}")
        return 0.0


def main():
    """Compare test performance."""
    print("🚀 Test Performance Comparison")
    print("=" * 80)

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
        print(f"\n\n{'#'*80}")
        print(f"# {comparison['name']}")
        print('#'*80)

        # Check if files exist
        original_path = Path(comparison["original"])
        optimized_path = Path(comparison["optimized"])

        if not original_path.exists():
            print(f"✗ Original test not found: {comparison['original']}")
            continue

        if not optimized_path.exists():
            print(f"✗ Optimized test not found: {comparison['optimized']}")
            continue

        # Run original
        original_time = run_test_with_timing(comparison["original"], "ORIGINAL")
        total_original_time += original_time

        # Run optimized
        optimized_time = run_test_with_timing(comparison["optimized"], "OPTIMIZED V2")
        total_optimized_time += optimized_time

        # Calculate improvement
        if original_time > 0:
            improvement = ((original_time - optimized_time) / original_time) * 100
            speedup = original_time / optimized_time if optimized_time > 0 else 0

            print(f"\n📊 Performance Summary for {comparison['name']}:")
            print(f"  • Original: {original_time:.2f}s")
            print(f"  • Optimized: {optimized_time:.2f}s")
            print(f"  • Improvement: {improvement:.1f}%")
            print(f"  • Speedup: {speedup:.1f}x faster")

    # Overall summary
    print("\n\n" + "="*80)
    print("📈 OVERALL SUMMARY")
    print("="*80)

    if total_original_time > 0:
        total_improvement = ((total_original_time - total_optimized_time) / total_original_time) * 100
        total_speedup = total_original_time / total_optimized_time if total_optimized_time > 0 else 0

        print(f"\nTotal Original Time: {total_original_time:.2f}s")
        print(f"Total Optimized Time: {total_optimized_time:.2f}s")
        print(f"Total Time Saved: {total_original_time - total_optimized_time:.2f}s")
        print(f"Overall Improvement: {total_improvement:.1f}%")
        print(f"Overall Speedup: {total_speedup:.1f}x faster")

        # Extrapolate to full test suite
        print(f"\n💡 Projected Impact on Full Test Suite:")
        print(f"  • If all 144 test files achieve similar {total_improvement:.0f}% improvement")
        print(f"  • A 30-minute test suite would run in ~{30 * (1 - total_improvement/100):.0f} minutes")
        print(f"  • Saving approximately {30 * total_improvement/100:.0f} minutes per run")

    print("\n✅ Performance comparison complete!")


if __name__ == "__main__":
    main()