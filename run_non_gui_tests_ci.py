#!/usr/bin/env python3
"""
Test runner for CI that excludes GUI tests on non-Linux platforms.
This avoids Qt-related crashes on macOS and Windows in CI.
"""

import argparse
import os
import sys
import unittest
from pathlib import Path

# Add the project root to Python path
repo_root = Path(__file__).parent
sys.path.insert(0, str(repo_root))

# List of test modules that don't require Qt/GUI
NON_GUI_TESTS = [
    # Unit tests that don't need Qt
    "tests.unit.test_basic_time_index",
    "tests.unit.test_batch_queue",
    "tests.unit.test_cache",
    "tests.unit.test_concurrent_operations",
    "tests.unit.test_config",
    "tests.unit.test_corrupt_file_handling",
    "tests.unit.test_date_utils",
    "tests.unit.test_edge_case_timezone",
    "tests.unit.test_encode",
    "tests.unit.test_ffmpeg_builder",
    "tests.unit.test_ffmpeg_builder_critical",
    "tests.unit.test_file_sorter_refactored",
    "tests.unit.test_image_cropper",
    "tests.unit.test_image_saver",
    "tests.unit.test_interpolate",
    "tests.unit.test_loader",
    "tests.unit.test_log",
    "tests.unit.test_memory_management",
    "tests.unit.test_netcdf_channel_extraction",
    "tests.unit.test_netcdf_render",
    "tests.unit.test_netcdf_renderer",
    "tests.unit.test_progress_reporting",
    "tests.unit.test_raw_encoder",
    "tests.unit.test_real_s3_path",
    "tests.unit.test_real_s3_patterns",
    "tests.unit.test_real_s3_store_fixed",
    "tests.unit.test_rife_analyzer",
    "tests.unit.test_run_vfi",
    "tests.unit.test_run_vfi_fixed",
    "tests.unit.test_run_vfi_refactored",
    "tests.unit.test_run_vfi_simple",
    "tests.unit.test_s3_band13",
    "tests.unit.test_s3_download_stats",
    "tests.unit.test_s3_download_stats_fixed",
    "tests.unit.test_s3_error_handling",
    "tests.unit.test_s3_retry_strategy",
    "tests.unit.test_s3_retry_strategy_fixed",
    "tests.unit.test_s3_store_critical",
    "tests.unit.test_s3_threadlocal_integration",
    "tests.unit.test_s3_unsigned_access",
    "tests.unit.test_sanchez_health",
    "tests.unit.test_thread_cache_db",
    "tests.unit.test_tiler",
    "tests.unit.test_time_index",
    "tests.unit.test_time_index_refactored",
]


def main():
    """Run non-GUI tests suitable for CI environments."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Run non-GUI tests for CI")
    parser.add_argument(
        "--quiet", "-q", action="store_true", help="Quiet mode - minimal output"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose mode")
    parser.add_argument(
        "--maxfail", type=int, default=0, help="Stop after N failures (0 = no limit)"
    )
    args = parser.parse_args()

    # Set environment variable to indicate we're in CI
    os.environ["CI"] = "true"
    os.environ["QT_QPA_PLATFORM"] = "offscreen"

    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    tests_loaded = 0
    failed_modules = []

    if not args.quiet:
        print("Loading test modules...")
    for test_module in NON_GUI_TESTS:
        try:
            module_suite = loader.loadTestsFromName(test_module)
            if module_suite.countTestCases() > 0:
                suite.addTest(module_suite)
                tests_loaded += module_suite.countTestCases()
                if not args.quiet:
                    print(
                        f"[OK] Loaded {test_module}: {module_suite.countTestCases()} tests"
                    )
        except Exception as e:
            failed_modules.append((test_module, str(e)))
            if not args.quiet:
                print(f"[FAIL] Failed to load {test_module}: {e}")

    if not args.quiet:
        print(f"\nTotal tests loaded: {tests_loaded}")
        if failed_modules:
            print(f"Failed to load {len(failed_modules)} modules")

    # Determine verbosity
    if args.quiet:
        verbosity = 0
    elif args.verbose:
        verbosity = 2
    else:
        verbosity = 1

    # Create custom test runner that can stop after N failures
    class StoppingTextTestRunner(unittest.TextTestRunner):
        def __init__(self, maxfail=0, **kwargs):
            super().__init__(**kwargs)
            self.maxfail = maxfail
            self.failures_count = 0

        def run(self, test):
            result = super().run(test)
            # Count failures and errors
            self.failures_count = len(result.failures) + len(result.errors)
            return result

    # Run tests
    runner = StoppingTextTestRunner(
        verbosity=verbosity,
        maxfail=args.maxfail,
        stream=sys.stdout if not args.quiet else open(os.devnull, "w"),
    )

    result = runner.run(suite)

    # Print summary in quiet mode
    if args.quiet:
        total = result.testsRun
        failures = len(result.failures)
        errors = len(result.errors)
        skipped = len(result.skipped)

        if result.wasSuccessful():
            print(f"[PASS] All {total} tests passed")
        else:
            print(
                f"[FAIL] Tests failed: {total} run, {failures} failures, {errors} errors, {skipped} skipped"
            )

            # Show first few failures
            if failures > 0:
                print("\nFirst failures:")
                for test, traceback in result.failures[:3]:
                    print(f"  - {test}: {traceback.split(chr(10))[-2]}")

            if errors > 0:
                print("\nFirst errors:")
                for test, traceback in result.errors[:3]:
                    print(f"  - {test}: {traceback.split(chr(10))[-2]}")

    # Exit with appropriate code
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
