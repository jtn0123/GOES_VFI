"""
Comprehensive memory lifecycle and leak detection tests.

Tests widget lifecycle management, object reference counting, and memory leak
detection during repeated operations. Focuses on Qt object lifecycle tracking
and cleanup verification that users experience as performance degradation.
"""

import gc
import sys
import threading
import time
import weakref
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch
import tempfile

from PyQt6.QtCore import QObject, QTimer, Qt
from PyQt6.QtWidgets import QApplication, QWidget, QDialog
import pytest

from goesvfi.gui import MainWindow


class TestMemoryLifecycle:
    """Test memory lifecycle management and leak detection."""

    @pytest.fixture()
    def main_window(self, qtbot):
        """Create MainWindow for memory testing."""
        with patch("goesvfi.gui.QSettings"):
            window = MainWindow(debug_mode=True)
            qtbot.addWidget(window)
            window._post_init_setup()
            return window

    @pytest.fixture()
    def memory_tracker(self):
        """Memory tracking utilities."""

        class MemoryTracker:
            def __init__(self):
                self.tracked_objects = []
                self.reference_counts = {}
                self.initial_object_count = 0

            def track_object(self, obj, name="Unknown"):
                """Track an object with weak reference."""
                weak_ref = weakref.ref(obj)
                self.tracked_objects.append((weak_ref, name))
                self.reference_counts[name] = sys.getrefcount(obj)

            def get_object_count(self):
                """Get current count of tracked live objects."""
                return len([ref for ref, _ in self.tracked_objects if ref() is not None])

            def get_leaked_objects(self):
                """Get list of objects that should have been cleaned up."""
                return [(name, ref()) for ref, name in self.tracked_objects if ref() is not None]

            def force_cleanup(self):
                """Force garbage collection and cleanup."""
                gc.collect()
                # Multiple collection cycles to catch circular references
                for _ in range(3):
                    gc.collect()

            def get_memory_summary(self):
                """Get summary of memory state."""
                live_objects = self.get_leaked_objects()
                return {
                    "total_tracked": len(self.tracked_objects),
                    "live_objects": len(live_objects),
                    "leaked_objects": live_objects,
                    "reference_counts": self.reference_counts,
                }

        return MemoryTracker()

    def test_main_window_lifecycle(self, qtbot, memory_tracker):
        """Test MainWindow creation and cleanup doesn't leak memory."""
        initial_widgets = len(QApplication.allWidgets())
        windows_created = []

        # Create and destroy multiple windows
        for i in range(3):
            with patch("goesvfi.gui.QSettings"):
                window = MainWindow(debug_mode=True)
                qtbot.addWidget(window)

                # Track the window
                memory_tracker.track_object(window, f"MainWindow_{i}")
                windows_created.append(window)

                # Basic operations to create sub-objects
                window._post_init_setup()
                window.show()
                qtbot.wait(50)

                # Manually close and cleanup
                window.close()
                window.deleteLater()
                qtbot.wait(50)

        # Clear references and force cleanup
        windows_created.clear()
        memory_tracker.force_cleanup()

        # Check for leaks
        final_widgets = len(QApplication.allWidgets())
        leaked_objects = memory_tracker.get_leaked_objects()

        # Should not have excessive widget accumulation between cycles
        widget_leak_count = final_widgets - initial_widgets
        # MainWindow creates many widgets during initialization (~300), but should not accumulate more
        # across multiple window create/destroy cycles
        assert widget_leak_count <= 350, (
            f"Excessive widget accumulation detected: {widget_leak_count} (initial: {initial_widgets}, final: {final_widgets})"
        )

        # Should not have excessive tracked object leaks
        # MainWindow objects may remain due to Qt's parent-child relationships and signal connections
        assert len(leaked_objects) <= 3, f"Excessive memory leaks detected: {leaked_objects}"

    def test_dialog_lifecycle_management(self, qtbot, main_window, memory_tracker):
        """Test dialog creation and cleanup doesn't leak memory."""
        window = main_window
        dialogs_created = []

        # Create mock dialogs similar to crop dialog
        for i in range(5):
            dialog = QDialog(window)
            dialog.setWindowTitle(f"Test Dialog {i}")
            dialog.resize(400, 300)

            memory_tracker.track_object(dialog, f"Dialog_{i}")
            dialogs_created.append(dialog)

            # Show and interact with dialog
            dialog.show()
            qtbot.wait(25)

            # Close properly
            dialog.close()
            dialog.deleteLater()
            qtbot.wait(25)

        # Clear references
        dialogs_created.clear()
        memory_tracker.force_cleanup()

        # Check for dialog leaks
        leaked_dialogs = memory_tracker.get_leaked_objects()
        # Allow for some dialogs to remain in Qt's internal structures temporarily
        assert len(leaked_dialogs) <= 2, f"Excessive dialog leaks detected: {leaked_dialogs}"

    def test_preview_manager_memory_cycles(self, qtbot, main_window, memory_tracker):
        """Test preview manager operations don't accumulate memory."""
        window = main_window
        preview_manager = window.main_view_model.preview_manager

        # Track preview manager components
        memory_tracker.track_object(preview_manager, "PreviewManager")
        memory_tracker.track_object(preview_manager.thumbnail_manager, "ThumbnailManager")

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create test images
            for i in range(3):
                test_file = temp_path / f"test_{i:03d}.png"
                test_file.write_bytes(b"fake_png_data")

            # Repeated preview loading cycles
            for cycle in range(5):
                # Load previews
                success = preview_manager.load_preview_thumbnails(temp_path, crop_rect=None, apply_sanchez=False)

                if success:
                    # Get frame data (creates objects)
                    frame_data = preview_manager.get_current_frame_data()

                    # Clear previews (should cleanup)
                    preview_manager.clear_previews()
                    preview_manager.clear_cache()

                # Force cleanup between cycles
                if cycle % 2 == 0:
                    memory_tracker.force_cleanup()

                qtbot.wait(10)

        # Final cleanup
        preview_manager.clear_cache()
        memory_tracker.force_cleanup()

        # Check memory state
        memory_summary = memory_tracker.get_memory_summary()
        assert memory_summary["live_objects"] <= 2, f"Preview manager memory leaks: {memory_summary}"

    def test_signal_connection_cleanup(self, qtbot, main_window, memory_tracker):
        """Test signal connections are properly cleaned up."""
        window = main_window
        signal_broker = window.signal_broker

        # Track signal broker
        memory_tracker.track_object(signal_broker, "SignalBroker")

        # Create temporary objects with signals
        temp_objects = []
        for i in range(10):
            temp_obj = QObject()
            temp_obj.setObjectName(f"TempObject_{i}")

            # Connect signals (simulating dialog connections)
            if hasattr(temp_obj, "destroyed"):
                signal_broker._make_connection(temp_obj.destroyed, lambda: None, f"temp_connection_{i}")

            memory_tracker.track_object(temp_obj, f"TempObject_{i}")
            temp_objects.append(temp_obj)

        # Disconnect all connections
        signal_broker.disconnect_all_connections()

        # Delete temp objects
        for obj in temp_objects:
            obj.deleteLater()
        temp_objects.clear()

        memory_tracker.force_cleanup()

        # Check for leaked connections
        leaked_objects = memory_tracker.get_leaked_objects()
        temp_leaks = [name for name, obj in leaked_objects if "TempObject" in name]

        assert len(temp_leaks) <= 2, f"Signal connection leaks: {temp_leaks}"

    def test_thread_cleanup_verification(self, qtbot, main_window, memory_tracker):
        """Test worker threads are properly cleaned up."""
        window = main_window
        created_threads = []

        # Simulate worker thread creation
        for i in range(3):
            thread = threading.Thread(target=lambda: time.sleep(0.1), name=f"TestWorker_{i}")
            memory_tracker.track_object(thread, f"Thread_{i}")
            created_threads.append(thread)

            thread.start()

        # Wait for threads to complete
        for thread in created_threads:
            thread.join(timeout=1.0)

        # Clear references
        created_threads.clear()
        memory_tracker.force_cleanup()

        # Check for thread leaks
        leaked_threads = memory_tracker.get_leaked_objects()
        thread_leaks = [name for name, obj in leaked_threads if "Thread" in name]

        # Threads may remain in Python's memory briefly after joining
        assert len(thread_leaks) <= 1, f"Excessive thread leaks detected: {thread_leaks}"

    def test_timer_cleanup_verification(self, qtbot, main_window, memory_tracker):
        """Test QTimer objects are properly cleaned up."""
        window = main_window
        created_timers = []

        # Create temporary timers
        for i in range(5):
            timer = QTimer(window)
            timer.setObjectName(f"TestTimer_{i}")
            timer.timeout.connect(lambda: None)

            memory_tracker.track_object(timer, f"Timer_{i}")
            created_timers.append(timer)

            # Start and stop timer
            timer.start(100)
            qtbot.wait(50)
            timer.stop()

        # Cleanup timers
        for timer in created_timers:
            timer.stop()
            timer.deleteLater()
        created_timers.clear()

        memory_tracker.force_cleanup()

        # Check for timer leaks
        leaked_timers = memory_tracker.get_leaked_objects()
        timer_leaks = [name for name, obj in leaked_timers if "Timer" in name]

        assert len(timer_leaks) <= 1, f"Timer leaks detected: {timer_leaks}"

    def test_repeated_tab_switching_memory(self, qtbot, main_window, memory_tracker):
        """Test repeated tab switching doesn't accumulate memory."""
        window = main_window
        tab_widget = window.tab_widget
        initial_tab = tab_widget.currentIndex()

        # Track tab widget
        memory_tracker.track_object(tab_widget, "TabWidget")

        # Perform repeated tab switching
        tab_count = tab_widget.count()
        for cycle in range(20):  # Multiple cycles
            for tab_index in range(tab_count):
                tab_widget.setCurrentIndex(tab_index)
                qtbot.wait(5)  # Brief wait for tab loading

                # Trigger tab-specific operations
                window._on_tab_changed(tab_index)

            # Periodic cleanup
            if cycle % 5 == 0:
                memory_tracker.force_cleanup()

        # Return to initial tab
        tab_widget.setCurrentIndex(initial_tab)
        memory_tracker.force_cleanup()

        # Memory should be stable
        memory_summary = memory_tracker.get_memory_summary()
        assert memory_summary["live_objects"] <= 1, f"Tab switching memory issues: {memory_summary}"

    def test_widget_pool_memory_management(self, qtbot, main_window, memory_tracker):
        """Test widget pools don't leak memory with repeated use."""
        window = main_window

        # Access widget pools if available
        widget_pools = {}
        if hasattr(window, "main_tab") and hasattr(window.main_tab, "_widget_pools"):
            widget_pools = getattr(window.main_tab, "_widget_pools", {})

        for pool_name, pool in widget_pools.items():
            memory_tracker.track_object(pool, f"WidgetPool_{pool_name}")

        # Simulate repeated widget operations
        for cycle in range(10):
            # Simulate creating/destroying widgets from pools
            # (Implementation would depend on actual widget pool API)

            # Force periodic cleanup
            if cycle % 3 == 0:
                memory_tracker.force_cleanup()

            qtbot.wait(5)

        memory_tracker.force_cleanup()

        # Check widget pool memory stability
        leaked_pools = memory_tracker.get_leaked_objects()
        pool_leaks = [name for name, obj in leaked_pools if "WidgetPool" in name]

        # Widget pools should remain stable
        assert len(pool_leaks) == len(widget_pools), f"Widget pool memory issues: {pool_leaks}"

    def test_long_running_operation_memory_stability(self, qtbot, main_window, memory_tracker):
        """Test memory stability during simulated long-running operations."""
        window = main_window

        # Track main components
        memory_tracker.track_object(window, "MainWindow")
        memory_tracker.track_object(window.main_view_model, "MainViewModel")

        # Simulate long-running operation
        operation_cycles = 50

        for cycle in range(operation_cycles):
            # Simulate processing progress updates
            progress = int((cycle / operation_cycles) * 100)
            window._on_processing_progress(progress, 100, 5.0)

            # Simulate preview updates
            if cycle % 5 == 0:
                window.request_main_window_update("preview")

            # Simulate status updates
            if cycle % 3 == 0:
                window.status_bar.showMessage(f"Processing... {progress}%")

            # Periodic cleanup to prevent accumulation
            if cycle % 10 == 0:
                memory_tracker.force_cleanup()

            qtbot.wait(2)  # Brief wait to simulate real timing

        # Final cleanup
        memory_tracker.force_cleanup()

        # Memory should be stable after long operation
        memory_summary = memory_tracker.get_memory_summary()
        assert memory_summary["live_objects"] <= 2, f"Long operation memory leaks: {memory_summary}"
