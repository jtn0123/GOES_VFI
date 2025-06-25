"""Performance and responsiveness tests for GOES VFI GUI."""

import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import psutil
import pytest
from PyQt6.QtCore import QObject, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QListWidget, QListWidgetItem, QProgressBar

from goesvfi.gui import MainWindow


class MemoryMonitor:
    """Monitor memory usage during tests."""

    def __init__(self):
        self.process = psutil.Process()
        self.baseline = None
        self.peak = None
        self.samples = []

    def start(self):
        self.baseline = self.process.memory_info().rss / 1024 / 1024  # MB
        self.peak = self.baseline
        self.samples = [self.baseline]

    def sample(self):
        current = self.process.memory_info().rss / 1024 / 1024  # MB
        self.samples.append(current)
        self.peak = max(self.peak, current)
        return current

    def get_increase(self):
        if self.baseline and self.samples:
            return self.samples[-1] - self.baseline
        return 0

    def get_peak_increase(self):
        if self.baseline and self.peak:
            return self.peak - self.baseline
        return 0


class PerformanceMonitor(QObject):
    """Monitor UI performance metrics."""

    frame_rendered = pyqtSignal(float)  # Frame time in ms

    def __init__(self):
        super().__init__()
        self.frame_times = []
        self.last_frame_time = None

    def start_frame(self):
        self.last_frame_time = time.perf_counter()

    def end_frame(self):
        if self.last_frame_time:
            frame_time = (time.perf_counter() - self.last_frame_time) * 1000  # ms
            self.frame_times.append(frame_time)
            self.frame_rendered.emit(frame_time)

    def get_average_fps(self):
        if self.frame_times:
            avg_frame_time = sum(self.frame_times) / len(self.frame_times)
            return 1000 / avg_frame_time if avg_frame_time > 0 else 0
        return 0

    def get_percentile(self, percentile):
        if self.frame_times:
            sorted_times = sorted(self.frame_times)
            index = int(len(sorted_times) * percentile / 100)
            return sorted_times[min(index, len(sorted_times) - 1)]
        return 0


class TestPerformanceUI:
    """Test UI performance and responsiveness."""

    @pytest.fixture
    def window(self, qtbot, mocker):
        """Create a MainWindow instance for testing."""
        # Mock heavy components
        mocker.patch("goesvfi.gui.CombinedIntegrityAndImageryTab")
        mocker.patch("goesvfi.integrity_check.enhanced_gui_tab.EnhancedImageryTab")

        window = MainWindow(debug_mode=True)
        qtbot.addWidget(window)
        window._post_init_setup()

        return window

    def test_ui_responsiveness_large_datasets(self, qtbot, window):
        """Test UI responsiveness with large datasets."""
        # Create large file list
        file_list = QListWidget()
        qtbot.addWidget(file_list)

        # Performance monitor
        perf_monitor = PerformanceMonitor()

        # Add many items
        num_items = 10000
        start_time = time.perf_counter()

        # Batch addition for better performance
        batch_size = 100
        for batch_start in range(0, num_items, batch_size):
            perf_monitor.start_frame()

            items = []
            for i in range(batch_start, min(batch_start + batch_size, num_items)):
                item = QListWidgetItem(f"File_{i:05d}.png")
                item.setData(Qt.ItemDataRole.UserRole, f"/path/to/file_{i:05d}.png")
                items.append(item)

            # Add batch
            for item in items:
                file_list.addItem(item)

            perf_monitor.end_frame()

            # Process events to keep UI responsive
            QApplication.processEvents()

        total_time = time.perf_counter() - start_time

        # Verify performance
        assert file_list.count() == num_items
        assert total_time < 5.0  # Should complete within 5 seconds

        # Check frame times
        avg_fps = perf_monitor.get_average_fps()
        p95_frame_time = perf_monitor.get_percentile(95)

        assert avg_fps > 30  # Should maintain 30+ FPS
        assert p95_frame_time < 100  # 95% of frames under 100ms

        # Test scrolling performance
        scroll_perf = PerformanceMonitor()

        # Simulate scrolling
        for _ in range(20):
            scroll_perf.start_frame()
            file_list.scrollToBottom()
            QApplication.processEvents()
            scroll_perf.end_frame()

            scroll_perf.start_frame()
            file_list.scrollToTop()
            QApplication.processEvents()
            scroll_perf.end_frame()

        # Verify scroll performance
        scroll_fps = scroll_perf.get_average_fps()
        assert scroll_fps > 30  # Smooth scrolling

    def test_non_blocking_progress_updates(self, qtbot, window):
        """Test that progress updates don't block the UI."""
        # Create progress UI
        progress_bar = QProgressBar()
        status_label = QLabel("Processing...")

        # UI responsiveness checker
        class ResponsivenessChecker(QThread):
            responsiveness_checked = pyqtSignal(bool)

            def __init__(self, widget):
                super().__init__()
                self.widget = widget
                self.is_responsive = True

            def run(self):
                # Try to interact with UI
                start = time.perf_counter()
                QApplication.postEvent(self.widget, QEvent(QEvent.Type.User))
                QApplication.processEvents()
                elapsed = time.perf_counter() - start

                # UI is responsive if event processed quickly
                self.is_responsive = elapsed < 0.1  # 100ms threshold
                self.responsiveness_checked.emit(self.is_responsive)

        # Heavy computation in worker thread
        class HeavyWorker(QThread):
            progress = pyqtSignal(int, str)

            def run(self):
                for i in range(100):
                    # Simulate heavy computation
                    time.sleep(0.01)

                    # Emit progress
                    self.progress.emit(i + 1, f"Processing item {i + 1}/100")

        # Connect worker
        worker = HeavyWorker()
        worker.progress.connect(lambda v, m: (progress_bar.setValue(v), status_label.setText(m)))

        # Responsiveness checks during processing
        responsiveness_results = []

        def check_responsiveness():
            checker = ResponsivenessChecker(window)
            checker.responsiveness_checked.connect(lambda r: responsiveness_results.append(r))
            checker.start()

        # Start worker
        worker.start()

        # Check responsiveness periodically
        for _ in range(5):
            qtbot.wait(200)
            check_responsiveness()

        # Wait for completion
        worker.wait()

        # Verify UI remained responsive
        assert all(responsiveness_results)
        assert progress_bar.value() == 100

    def test_memory_leak_prevention(self, qtbot, window):
        """Test that repeated operations don't leak memory."""
        mem_monitor = MemoryMonitor()
        mem_monitor.start()

        # Operation that could leak memory
        def create_and_destroy_widgets():
            widgets = []

            # Create many widgets
            for i in range(100):
                widget = QListWidget()
                for j in range(100):
                    widget.addItem(f"Item {i}-{j}")
                widgets.append(widget)

            # Process events
            QApplication.processEvents()

            # Explicitly delete widgets
            for widget in widgets:
                widget.deleteLater()

            # Force garbage collection
            QApplication.processEvents()

        # Initial memory
        initial_memory = mem_monitor.sample()

        # Repeat operation multiple times
        for iteration in range(10):
            create_and_destroy_widgets()

            # Sample memory
            current_memory = mem_monitor.sample()

            # Small wait between iterations
            qtbot.wait(100)

        # Final memory check
        final_memory = mem_monitor.sample()
        memory_increase = final_memory - initial_memory

        # Verify no significant memory leak
        # Allow up to 50MB increase (some growth is normal)
        assert memory_increase < 50, f"Memory increased by {memory_increase:.1f} MB"

        # Check for steady state (last few samples should be similar)
        last_samples = mem_monitor.samples[-5:]
        if len(last_samples) >= 5:
            variation = max(last_samples) - min(last_samples)
            assert variation < 10, "Memory usage not stable"

    def test_startup_performance(self, qtbot, mocker):
        """Test application startup performance."""
        # Mock heavy initialization
        init_times = {}

        def timed_init(name, func):
            start = time.perf_counter()
            result = func()
            init_times[name] = time.perf_counter() - start
            return result

        # Mock components with timing
        mocker.patch(
            "goesvfi.gui.CombinedIntegrityAndImageryTab",
            side_effect=lambda: timed_init("imagery_tab", MagicMock),
        )
        mocker.patch(
            "goesvfi.integrity_check.enhanced_gui_tab.EnhancedImageryTab",
            side_effect=lambda: timed_init("enhanced_tab", MagicMock),
        )

        # Time startup
        start_time = time.perf_counter()

        window = MainWindow(debug_mode=True)
        qtbot.addWidget(window)
        window._post_init_setup()

        total_startup_time = time.perf_counter() - start_time

        # Verify startup performance
        assert total_startup_time < 2.0, f"Startup took {total_startup_time:.2f}s"

        # Check individual component times
        for component, init_time in init_times.items():
            assert init_time < 0.5, f"{component} took {init_time:.2f}s to initialize"

        # Verify window is shown and responsive
        assert window.isVisible()

        # Test initial responsiveness
        qtbot.mouseClick(window.main_tab.in_dir_button, Qt.MouseButton.LeftButton)
        # Should respond immediately

    def test_animation_smoothness(self, qtbot, window):
        """Test UI animation smoothness."""

        # Create animated progress indicator
        class SmoothProgressBar(QProgressBar):
            def __init__(self):
                super().__init__()
                self.animation_timer = QTimer()
                self.animation_timer.timeout.connect(self.animate_step)
                self.target_value = 0
                self.current_smooth_value = 0.0
                self.animation_speed = 0.1  # Interpolation factor

            def set_target_value(self, value):
                self.target_value = value
                if not self.animation_timer.isActive():
                    self.animation_timer.start(16)  # ~60 FPS

            def animate_step(self):
                # Smooth interpolation
                diff = self.target_value - self.current_smooth_value
                self.current_smooth_value += diff * self.animation_speed

                # Update display
                self.setValue(int(self.current_smooth_value))

                # Stop when close enough
                if abs(diff) < 0.5:
                    self.current_smooth_value = self.target_value
                    self.setValue(self.target_value)
                    self.animation_timer.stop()

        # Create and test smooth progress
        smooth_bar = SmoothProgressBar()
        qtbot.addWidget(smooth_bar)

        # Monitor animation performance
        frame_times = []
        last_frame = time.perf_counter()

        def on_animation_frame():
            nonlocal last_frame
            current = time.perf_counter()
            frame_times.append((current - last_frame) * 1000)
            last_frame = current

        smooth_bar.animation_timer.timeout.connect(on_animation_frame)

        # Animate to different values
        test_values = [25, 75, 50, 100, 0]

        for target in test_values:
            smooth_bar.set_target_value(target)

            # Wait for animation to complete
            while smooth_bar.animation_timer.isActive():
                qtbot.wait(20)

        # Analyze animation performance
        if frame_times:
            avg_frame_time = sum(frame_times) / len(frame_times)
            max_frame_time = max(frame_times)

            # Should maintain smooth 60 FPS (16.67ms per frame)
            assert avg_frame_time < 20, f"Average frame time: {avg_frame_time:.1f}ms"
            assert max_frame_time < 33, f"Max frame time: {max_frame_time:.1f}ms"

    def test_thread_pool_management(self, qtbot, window):
        """Test thread pool management for concurrent operations."""

        # Thread pool monitor
        class ThreadPoolMonitor:
            def __init__(self, max_threads=4):
                self.max_threads = max_threads
                self.active_threads = 0
                self.completed_tasks = 0
                self.pending_tasks = []
                self.lock = threading.Lock()

            def submit_task(self, task_func):
                with self.lock:
                    if self.active_threads < self.max_threads:
                        self.active_threads += 1
                        self._run_task(task_func)
                    else:
                        self.pending_tasks.append(task_func)

            def _run_task(self, task_func):
                def wrapper():
                    try:
                        task_func()
                    finally:
                        with self.lock:
                            self.active_threads -= 1
                            self.completed_tasks += 1

                            # Start pending task if any
                            if self.pending_tasks:
                                next_task = self.pending_tasks.pop(0)
                                self.active_threads += 1
                                self._run_task(next_task)

                thread = threading.Thread(target=wrapper)
                thread.start()

        # Create monitor
        pool_monitor = ThreadPoolMonitor(max_threads=4)

        # Submit many tasks
        task_count = 20
        task_completed = threading.Event()
        completed_count = 0

        def dummy_task():
            nonlocal completed_count
            time.sleep(0.1)  # Simulate work
            completed_count += 1
            if completed_count == task_count:
                task_completed.set()

        # Submit all tasks
        start_time = time.perf_counter()

        for _ in range(task_count):
            pool_monitor.submit_task(dummy_task)

        # Wait for completion
        task_completed.wait(timeout=10)
        total_time = time.perf_counter() - start_time

        # Verify thread pool behavior
        assert pool_monitor.completed_tasks == task_count
        assert pool_monitor.active_threads == 0
        assert len(pool_monitor.pending_tasks) == 0

        # With 4 threads and 0.1s per task, should complete in ~0.5s
        assert total_time < 1.0, f"Tasks took {total_time:.2f}s"

    def test_lazy_loading_components(self, qtbot, window):
        """Test lazy loading of heavy components."""

        # Lazy loader implementation
        class LazyComponentLoader:
            def __init__(self):
                self.components = {}
                self.load_times = {}

            def get_component(self, name, factory_func):
                if name not in self.components:
                    start = time.perf_counter()
                    self.components[name] = factory_func()
                    self.load_times[name] = time.perf_counter() - start

                return self.components[name]

            def is_loaded(self, name):
                return name in self.components

        # Create loader
        loader = LazyComponentLoader()

        # Define heavy components
        def create_heavy_widget():
            widget = QListWidget()
            # Simulate heavy initialization
            for i in range(1000):
                widget.addItem(f"Heavy item {i}")
            return widget

        def create_heavy_model():
            # Simulate loading a large model
            time.sleep(0.2)
            return {"model": "loaded", "size": "100MB"}

        # Test lazy loading
        # Component not loaded initially
        assert not loader.is_loaded("heavy_widget")
        assert not loader.is_loaded("heavy_model")

        # First access triggers load
        start = time.perf_counter()
        widget = loader.get_component("heavy_widget", create_heavy_widget)
        first_load_time = time.perf_counter() - start

        assert loader.is_loaded("heavy_widget")
        assert isinstance(widget, QListWidget)
        assert widget.count() == 1000

        # Second access is instant
        start = time.perf_counter()
        widget2 = loader.get_component("heavy_widget", create_heavy_widget)
        second_load_time = time.perf_counter() - start

        assert widget2 is widget  # Same instance
        assert second_load_time < 0.001  # Near instant

        # Load another component
        model = loader.get_component("heavy_model", create_heavy_model)
        assert model["model"] == "loaded"
        assert loader.load_times["heavy_model"] >= 0.2

    def test_ui_freezing_prevention(self, qtbot, window):
        """Test prevention of UI freezing during heavy operations."""

        # Freezing detector
        class FreezeDetector(QObject):
            freeze_detected = pyqtSignal(float)  # Duration in seconds

            def __init__(self, threshold_ms=100):
                super().__init__()
                self.threshold_ms = threshold_ms
                self.timer = QTimer()
                self.timer.timeout.connect(self.check_responsiveness)
                self.last_check = time.perf_counter()
                self.is_frozen = False

            def start_monitoring(self):
                self.timer.start(50)  # Check every 50ms

            def stop_monitoring(self):
                self.timer.stop()

            def check_responsiveness(self):
                current = time.perf_counter()
                elapsed = (current - self.last_check) * 1000

                if elapsed > self.threshold_ms:
                    if not self.is_frozen:
                        self.is_frozen = True
                        self.freeze_detected.emit(elapsed / 1000)
                else:
                    self.is_frozen = False

                self.last_check = current

        # Create detector
        detector = FreezeDetector(threshold_ms=100)
        freezes = []
        detector.freeze_detected.connect(lambda d: freezes.append(d))

        # Start monitoring
        detector.start_monitoring()

        # Perform operations that could freeze UI
        # Good practice - process in chunks
        def process_large_data_good():
            total_items = 10000
            chunk_size = 100

            for i in range(0, total_items, chunk_size):
                # Process chunk
                for j in range(chunk_size):
                    # Simulate work
                    _ = sum(range(1000))

                # Let UI breathe
                QApplication.processEvents()

        # Execute good practice
        process_large_data_good()

        # Stop monitoring
        detector.stop_monitoring()

        # Verify no significant freezes
        assert len(freezes) == 0, f"Detected {len(freezes)} UI freezes"
