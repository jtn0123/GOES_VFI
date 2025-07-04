"""
Comprehensive performance regression and benchmark testing.

Tests performance benchmarking over time, regression detection, and threshold
validation that users experience as application responsiveness degradation.
Focuses on UI responsiveness, memory efficiency, and operation speed.
"""

import json
import statistics
import time
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import patch
import tempfile

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication
import pytest

from goesvfi.gui import MainWindow


class TestPerformanceRegression:
    """Test performance regression and benchmark validation."""

    @pytest.fixture()
    def performance_benchmarker(self):
        """Performance benchmarking utilities."""

        class PerformanceBenchmarker:
            def __init__(self):
                self.benchmarks = {}
                self.baselines = {}
                self.performance_history = []

            def record_baseline(self, operation_name: str, duration: float, memory_mb: float = 0):
                """Record baseline performance for an operation."""
                self.baselines[operation_name] = {
                    "duration": duration,
                    "memory_mb": memory_mb,
                    "timestamp": time.time(),
                    "samples": 1,
                }

            def benchmark_operation(self, operation_name: str) -> "OperationBenchmark":
                """Context manager for benchmarking operations."""
                return OperationBenchmark(self, operation_name)

            def record_performance(self, operation_name: str, duration: float, memory_mb: float = 0):
                """Record performance measurement."""
                if operation_name not in self.benchmarks:
                    self.benchmarks[operation_name] = []

                measurement = {"duration": duration, "memory_mb": memory_mb, "timestamp": time.time()}

                self.benchmarks[operation_name].append(measurement)
                self.performance_history.append({"operation": operation_name, **measurement})

            def check_regression(self, operation_name: str, tolerance_percent: float = 20.0) -> Dict[str, Any]:
                """Check for performance regression against baseline."""
                if operation_name not in self.benchmarks or operation_name not in self.baselines:
                    return {"regression_detected": False, "reason": "No baseline or measurements"}

                baseline = self.baselines[operation_name]
                measurements = self.benchmarks[operation_name]

                if not measurements:
                    return {"regression_detected": False, "reason": "No measurements"}

                # Calculate statistics
                recent_durations = [m["duration"] for m in measurements[-5:]]  # Last 5 measurements
                avg_duration = statistics.mean(recent_durations)
                baseline_duration = baseline["duration"]

                # Check for regression
                regression_threshold = baseline_duration * (1 + tolerance_percent / 100)
                regression_detected = avg_duration > regression_threshold

                regression_percent = ((avg_duration - baseline_duration) / baseline_duration) * 100

                return {
                    "regression_detected": regression_detected,
                    "baseline_duration": baseline_duration,
                    "current_avg_duration": avg_duration,
                    "regression_percent": regression_percent,
                    "threshold_duration": regression_threshold,
                    "sample_count": len(measurements),
                    "recent_samples": len(recent_durations),
                }

            def get_performance_summary(self) -> Dict[str, Any]:
                """Get comprehensive performance summary."""
                summary = {
                    "total_operations": len(self.benchmarks),
                    "total_measurements": sum(len(measurements) for measurements in self.benchmarks.values()),
                    "operations": {},
                }

                for op_name, measurements in self.benchmarks.items():
                    if measurements:
                        durations = [m["duration"] for m in measurements]
                        summary["operations"][op_name] = {
                            "count": len(measurements),
                            "avg_duration": statistics.mean(durations),
                            "min_duration": min(durations),
                            "max_duration": max(durations),
                            "std_duration": statistics.stdev(durations) if len(durations) > 1 else 0,
                            "regression_check": self.check_regression(op_name),
                        }

                return summary

            def save_benchmark_data(self, filepath: Path):
                """Save benchmark data for future regression testing."""
                data = {
                    "baselines": self.baselines,
                    "benchmarks": {k: v for k, v in self.benchmarks.items()},
                    "performance_history": self.performance_history,
                    "metadata": {"save_time": time.time(), "total_operations": len(self.benchmarks)},
                }

                filepath.write_text(json.dumps(data, indent=2))

            def load_benchmark_data(self, filepath: Path):
                """Load benchmark data from previous runs."""
                if not filepath.exists():
                    return

                data = json.loads(filepath.read_text())
                self.baselines.update(data.get("baselines", {}))

                # Load historical data for trend analysis
                for op_name, measurements in data.get("benchmarks", {}).items():
                    if op_name not in self.benchmarks:
                        self.benchmarks[op_name] = []
                    # Don't duplicate, just reference for baseline comparison

        class OperationBenchmark:
            def __init__(self, benchmarker: PerformanceBenchmarker, operation_name: str):
                self.benchmarker = benchmarker
                self.operation_name = operation_name
                self.start_time = None

            def __enter__(self):
                self.start_time = time.perf_counter()
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                if self.start_time is not None:
                    duration = time.perf_counter() - self.start_time
                    self.benchmarker.record_performance(self.operation_name, duration)

        return PerformanceBenchmarker()

    @pytest.fixture()
    def main_window(self, qtbot):
        """Create MainWindow for performance testing."""
        with patch("goesvfi.gui.QSettings"):
            window = MainWindow(debug_mode=True)
            qtbot.addWidget(window)
            window._post_init_setup()
            return window

    def test_application_startup_performance(self, qtbot, performance_benchmarker):
        """Test application startup time regression."""
        # Set baseline (typical startup time)
        performance_benchmarker.record_baseline("app_startup", 8.0)  # 8 seconds baseline for complex GUI app

        # Benchmark multiple startups
        for iteration in range(3):
            with performance_benchmarker.benchmark_operation("app_startup"):
                with patch("goesvfi.gui.QSettings"):
                    window = MainWindow(debug_mode=True)
                    qtbot.addWidget(window)
                    window._post_init_setup()
                    window.show()
                    qtbot.wait(100)  # Wait for initialization
                    window.close()

        # Check for regression
        regression_result = performance_benchmarker.check_regression("app_startup", tolerance_percent=50.0)

        # Startup should not regress significantly
        assert not regression_result["regression_detected"], (
            f"Startup performance regression detected: {regression_result}"
        )

    def test_preview_loading_performance(self, qtbot, main_window, performance_benchmarker):
        """Test preview loading performance regression."""
        window = main_window
        preview_manager = window.main_view_model.preview_manager

        # Set baseline for preview loading
        performance_benchmarker.record_baseline("preview_loading", 0.5)  # 500ms baseline

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create test images
            for i in range(5):
                test_file = temp_path / f"test_{i:03d}.png"
                test_file.write_bytes(b"fake_png_data")

            # Benchmark preview loading multiple times
            for iteration in range(5):
                with performance_benchmarker.benchmark_operation("preview_loading"):
                    success = preview_manager.load_preview_thumbnails(temp_path, crop_rect=None, apply_sanchez=False)

                # Clear between iterations
                preview_manager.clear_previews()
                preview_manager.clear_cache()
                qtbot.wait(10)

        # Check for regression
        regression_result = performance_benchmarker.check_regression("preview_loading", tolerance_percent=30.0)

        # Preview loading should remain performant
        assert not regression_result["regression_detected"], (
            f"Preview loading performance regression: {regression_result}"
        )

    def test_ui_responsiveness_during_operations(self, qtbot, main_window, performance_benchmarker):
        """Test UI responsiveness during simulated operations."""
        window = main_window

        # Set baseline for UI responsiveness
        performance_benchmarker.record_baseline("ui_response_time", 0.1)  # 100ms baseline

        # Test UI responsiveness during various operations
        operations = [
            ("tab_switching", lambda: self._simulate_tab_switching(window, qtbot)),
            ("progress_updates", lambda: self._simulate_progress_updates(window, qtbot)),
            ("settings_changes", lambda: self._simulate_settings_changes(window, qtbot)),
            ("preview_updates", lambda: self._simulate_preview_updates(window, qtbot)),
        ]

        for operation_name, operation_func in operations:
            for iteration in range(3):
                with performance_benchmarker.benchmark_operation(f"ui_response_{operation_name}"):
                    operation_func()

                qtbot.wait(50)  # Brief pause between iterations

        # Check UI responsiveness
        for operation_name, _ in operations:
            full_op_name = f"ui_response_{operation_name}"
            regression_result = performance_benchmarker.check_regression(full_op_name, tolerance_percent=25.0)

            assert not regression_result["regression_detected"], (
                f"UI responsiveness regression in {operation_name}: {regression_result}"
            )

    def test_memory_efficiency_benchmarks(self, qtbot, main_window, performance_benchmarker):
        """Test memory efficiency performance regression."""
        window = main_window

        # Set baseline memory usage (in MB)
        performance_benchmarker.record_baseline("memory_usage", 0, memory_mb=100.0)  # 100MB baseline

        # Simulate memory-intensive operations
        operations = [
            ("repeated_preview_loading", lambda: self._simulate_repeated_preview_loading(window, qtbot)),
            ("multiple_tab_operations", lambda: self._simulate_multiple_tab_operations(window, qtbot)),
            ("settings_persistence", lambda: self._simulate_settings_persistence(window, qtbot)),
        ]

        for operation_name, operation_func in operations:
            # Get memory before operation
            import psutil

            process = psutil.Process()
            memory_before = process.memory_info().rss / 1024 / 1024  # MB

            start_time = time.perf_counter()
            operation_func()
            duration = time.perf_counter() - start_time

            # Get memory after operation
            memory_after = process.memory_info().rss / 1024 / 1024  # MB
            memory_delta = memory_after - memory_before

            performance_benchmarker.record_performance(f"memory_{operation_name}", duration, memory_mb=memory_delta)

        # Check for memory regression
        for operation_name, _ in operations:
            full_op_name = f"memory_{operation_name}"
            if full_op_name in performance_benchmarker.benchmarks:
                measurements = performance_benchmarker.benchmarks[full_op_name]
                if measurements:
                    avg_memory = statistics.mean([m["memory_mb"] for m in measurements])
                    # Memory usage should not grow excessively
                    assert avg_memory < 50.0, f"Memory usage too high for {operation_name}: {avg_memory:.2f}MB"

    def test_batch_operation_scaling(self, qtbot, main_window, performance_benchmarker):
        """Test batch operation performance scaling."""
        window = main_window

        # Test different batch sizes
        batch_sizes = [1, 5, 10, 20]

        for batch_size in batch_sizes:
            operation_name = f"batch_operation_{batch_size}"
            performance_benchmarker.record_baseline(operation_name, batch_size * 0.1)  # Linear baseline

            for iteration in range(2):
                with performance_benchmarker.benchmark_operation(operation_name):
                    # Simulate batch operations
                    for _ in range(batch_size):
                        # Simulate individual operation
                        window.status_bar.showMessage(f"Processing item {_}")
                        qtbot.wait(5)

        # Check scaling efficiency
        scaling_results = {}
        for batch_size in batch_sizes:
            operation_name = f"batch_operation_{batch_size}"
            if operation_name in performance_benchmarker.benchmarks:
                measurements = performance_benchmarker.benchmarks[operation_name]
                if measurements:
                    avg_duration = statistics.mean([m["duration"] for m in measurements])
                    scaling_results[batch_size] = avg_duration

        # Verify scaling is reasonable (not exponential)
        if len(scaling_results) >= 2:
            batch_sizes_sorted = sorted(scaling_results.keys())
            for i in range(1, len(batch_sizes_sorted)):
                current_size = batch_sizes_sorted[i]
                previous_size = batch_sizes_sorted[i - 1]

                current_time = scaling_results[current_size]
                previous_time = scaling_results[previous_size]

                size_ratio = current_size / previous_size
                time_ratio = current_time / previous_time

                # Time should scale roughly linearly (not exponentially)
                efficiency_ratio = time_ratio / size_ratio
                assert efficiency_ratio < 3.0, (
                    f"Poor scaling efficiency: {efficiency_ratio:.2f} for batch size {current_size}"
                )

    def test_long_running_stability(self, qtbot, main_window, performance_benchmarker):
        """Test performance stability over extended operations."""
        window = main_window

        # Set baseline for long operations
        performance_benchmarker.record_baseline("long_operation_cycle", 0.05)  # 50ms per cycle

        # Simulate long-running operation
        total_cycles = 50
        measurement_interval = 10

        for cycle in range(0, total_cycles, measurement_interval):
            with performance_benchmarker.benchmark_operation("long_operation_cycle"):
                # Simulate work over measurement interval
                for sub_cycle in range(measurement_interval):
                    progress = int(((cycle + sub_cycle) / total_cycles) * 100)
                    window._on_processing_progress(progress, 100, 5.0)
                    window.status_bar.showMessage(f"Long operation: {progress}%")
                    qtbot.wait(2)  # Small delay to simulate work

        # Check for performance degradation over time
        measurements = performance_benchmarker.benchmarks["long_operation_cycle"]
        if len(measurements) >= 3:
            # Compare first third vs last third
            first_third = measurements[: len(measurements) // 3]
            last_third = measurements[-len(measurements) // 3 :]

            avg_first = statistics.mean([m["duration"] for m in first_third])
            avg_last = statistics.mean([m["duration"] for m in last_third])

            degradation_percent = ((avg_last - avg_first) / avg_first) * 100

            # Performance should not degrade significantly over time
            assert degradation_percent < 50.0, f"Performance degradation over time: {degradation_percent:.2f}%"

    def test_benchmark_data_persistence(self, performance_benchmarker, qtbot):
        """Test benchmark data saving and loading."""
        # Record some sample benchmarks
        performance_benchmarker.record_baseline("test_operation", 1.0)
        performance_benchmarker.record_performance("test_operation", 1.1)
        performance_benchmarker.record_performance("test_operation", 0.9)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as temp_file:
            temp_path = Path(temp_file.name)

        try:
            # Save benchmark data
            performance_benchmarker.save_benchmark_data(temp_path)
            assert temp_path.exists(), "Benchmark data should be saved"

            # Create new benchmarker and load data
            # Re-create the fixture manually
            class PerformanceBenchmarker:
                def __init__(self):
                    self.benchmarks = {}
                    self.baselines = {}
                    self.performance_history = []

                def load_benchmark_data(self, filepath):
                    if not filepath.exists():
                        return
                    import json

                    data = json.loads(filepath.read_text())
                    self.baselines.update(data.get("baselines", {}))

                def record_performance(self, operation_name, duration, memory_mb=0):
                    if operation_name not in self.benchmarks:
                        self.benchmarks[operation_name] = []
                    measurement = {"duration": duration, "memory_mb": memory_mb, "timestamp": 0}
                    self.benchmarks[operation_name].append(measurement)

                def check_regression(self, operation_name, tolerance_percent=20.0):
                    if operation_name not in self.benchmarks or operation_name not in self.baselines:
                        return {"regression_detected": False, "reason": "No baseline or measurements"}
                    baseline = self.baselines[operation_name]
                    measurements = self.benchmarks[operation_name]
                    if not measurements:
                        return {"regression_detected": False, "reason": "No measurements"}
                    import statistics

                    recent_durations = [m["duration"] for m in measurements[-5:]]
                    avg_duration = statistics.mean(recent_durations)
                    baseline_duration = baseline["duration"]
                    regression_threshold = baseline_duration * (1 + tolerance_percent / 100)
                    regression_detected = avg_duration > regression_threshold
                    return {"regression_detected": regression_detected}

            new_benchmarker = PerformanceBenchmarker()
            new_benchmarker.load_benchmark_data(temp_path)

            # Verify data was loaded
            assert "test_operation" in new_benchmarker.baselines, "Baseline should be loaded"

            # Test regression detection with loaded baseline
            new_benchmarker.record_performance("test_operation", 2.0)  # Slow performance
            regression_result = new_benchmarker.check_regression("test_operation", tolerance_percent=10.0)

            assert regression_result["regression_detected"], "Should detect regression against loaded baseline"

        finally:
            temp_path.unlink(missing_ok=True)

    # Helper methods for simulating operations
    def _simulate_tab_switching(self, window, qtbot):
        """Simulate rapid tab switching."""
        tab_widget = window.tab_widget
        original_tab = tab_widget.currentIndex()

        for i in range(tab_widget.count()):
            tab_widget.setCurrentIndex(i)
            qtbot.wait(5)

        tab_widget.setCurrentIndex(original_tab)

    def _simulate_progress_updates(self, window, qtbot):
        """Simulate rapid progress updates."""
        for progress in range(0, 101, 10):
            window._on_processing_progress(progress, 100, 5.0)
            qtbot.wait(2)

    def _simulate_settings_changes(self, window, qtbot):
        """Simulate rapid settings changes."""
        original_fps = window.main_tab.fps_spinbox.value()

        for fps in [24, 30, 60, 120]:
            window.main_tab.fps_spinbox.setValue(fps)
            qtbot.wait(2)

        window.main_tab.fps_spinbox.setValue(original_fps)

    def _simulate_preview_updates(self, window, qtbot):
        """Simulate preview update requests."""
        for _ in range(5):
            window.request_main_window_update("preview")
            qtbot.wait(5)

    def _simulate_repeated_preview_loading(self, window, qtbot):
        """Simulate repeated preview loading for memory testing."""
        preview_manager = window.main_view_model.preview_manager

        for _ in range(3):
            preview_manager.clear_cache()
            qtbot.wait(10)

    def _simulate_multiple_tab_operations(self, window, qtbot):
        """Simulate multiple tab operations for memory testing."""
        self._simulate_tab_switching(window, qtbot)
        self._simulate_settings_changes(window, qtbot)

    def _simulate_settings_persistence(self, window, qtbot):
        """Simulate settings save/load operations for memory testing."""
        for _ in range(3):
            window.saveSettings()
            qtbot.wait(5)
