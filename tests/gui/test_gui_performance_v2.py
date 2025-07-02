"""GUI performance testing for GOES_VFI application.

This module tests the performance characteristics of GUI components
and overall GUI test execution times.
"""

import os
from pathlib import Path
import subprocess  # noqa: S404
import sys
import time

import psutil
from PyQt6.QtWidgets import QApplication, QMainWindow, QPushButton, QWidget
import pytest


class TestGUIPerformance:
    """Test suite for GUI performance characteristics."""

    @staticmethod
    @pytest.fixture()
    def performance_test_cases() -> list[str]:
        """Provide representative GUI test cases for performance testing.

        Returns:
            list[str]: List of test paths for performance testing.
        """
        return [
            "tests/gui/test_main_window_v2.py::TestMainWindowCore::test_initial_state",
            "tests/gui/test_gui_component_validation_v2.py::TestGUIComponentValidation::test_main_window_creation",
            "tests/gui/test_button_advanced_v2.py::TestAdvancedButtonBehavior::test_start_button_click_scenarios",
        ]

    @staticmethod
    def run_single_gui_test(test_path: str) -> tuple[float, str]:
        """Run a single GUI test and measure its execution time.

        Args:
            test_path: Path to the test to run

        Returns:
            Tuple of (duration_seconds, status)
        """
        start_time = time.time()

        try:
            result = subprocess.run(  # noqa: S603
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    test_path,
                    "-v",
                    "--tb=short",
                    "--timeout=60",
                ],
                capture_output=True,
                text=True,
                timeout=70,
                check=False,
            )

            end_time = time.time()
            duration = end_time - start_time

            if result.returncode == 0:
                return duration, "PASSED"
            return duration, "FAILED"  # noqa: TRY300

        except subprocess.TimeoutExpired:
            return 70.0, "TIMEOUT"
        except Exception:  # noqa: BLE001
            return 0.0, "ERROR"

    def test_gui_test_execution_performance(self, performance_test_cases: list[str]) -> None:
        """Test that GUI tests execute within reasonable time limits."""
        results = []
        total_time = 0.0
        passed_count = 0

        for test_case in performance_test_cases:
            # Check if test file exists (handle both file paths and test paths)
            test_file = test_case.split("::")[0]
            if not Path(test_file).exists():
                continue

            duration, status = self.run_single_gui_test(test_case)
            results.append((test_case, duration, status))
            total_time += duration

            if status == "PASSED":
                passed_count += 1

        # Performance assertions
        assert len(results) > 0, "No GUI tests were found to measure"

        # Individual test performance thresholds
        for test_case, duration, _status in results:
            assert duration < 60.0, f"Test {test_case} took too long: {duration:.2f}s"

        # Average performance threshold
        avg_time = total_time / len(results)
        assert avg_time < 30.0, f"Average GUI test time too slow: {avg_time:.2f}s"

        # At least some tests should pass
        assert passed_count > 0, "No GUI tests passed during performance testing"

    @pytest.mark.parametrize("timeout_threshold", [30, 45, 60])
    def test_gui_test_timeout_thresholds(self, performance_test_cases: list[str], timeout_threshold: int) -> None:
        """Test GUI tests complete within various timeout thresholds."""
        if not performance_test_cases:
            pytest.skip("No performance test cases available")

        # Test first available test case
        test_case = performance_test_cases[0]
        test_file = test_case.split("::")[0]

        if not Path(test_file).exists():
            pytest.skip(f"Test file not found: {test_file}")

        duration, status = self.run_single_gui_test(test_case)

        # Assert test completes within threshold
        assert duration < timeout_threshold, f"Test exceeded {timeout_threshold}s threshold: {duration:.2f}s"

        # Test should not timeout or error
        assert status != "TIMEOUT", f"Test timed out after {duration:.2f}s"
        assert status != "ERROR", "Test encountered an error during execution"

    @staticmethod
    def test_gui_component_responsiveness() -> None:
        """Test that GUI components can be created quickly."""
        # Ensure we have a QApplication
        QApplication.instance() or QApplication([])

        start_time = time.time()

        # Create basic GUI components
        window = QMainWindow()
        button = QPushButton("Test Button")
        window.setCentralWidget(button)

        creation_time = time.time() - start_time

        # Clean up
        window.close()

        # Component creation should be very fast
        assert creation_time < 1.0, f"GUI component creation too slow: {creation_time:.3f}s"

    @staticmethod
    def test_memory_usage_reasonable() -> None:
        """Test that GUI tests don't consume excessive memory."""
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Create and destroy some GUI components
        QApplication.instance() or QApplication([])

        components = []
        for _ in range(10):
            window = QMainWindow()
            widget = QWidget()
            window.setCentralWidget(widget)
            components.append(window)

        # Clean up
        for component in components:
            component.close()

        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory

        # Memory increase should be reasonable (less than 100MB for basic components)
        assert memory_increase < 100, f"Excessive memory usage: {memory_increase:.1f}MB"
