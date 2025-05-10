"""
Performance tests for the integrity check tabs.

These tests focus on measuring and analyzing performance characteristics of
the integrity check tabs, including:
1. Load times for large datasets
2. Response times for UI interactions
3. Memory usage patterns

Note: These tests should be used for diagnostics and relative comparison,
not for absolute performance benchmarks, as times will vary based on the
test machine's capabilities.
"""

import unittest
import tempfile
import os
import time
import gc
import psutil
import tracemalloc
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtTest import QTest

# Import our test utilities
from tests.utils.pyqt_async_test import PyQtAsyncTestCase, AsyncSignalWaiter, async_test

# Import the components to test
from goesvfi.integrity_check.time_index import SatellitePattern
from goesvfi.integrity_check.view_model import ScanStatus, MissingTimestamp
from goesvfi.integrity_check.enhanced_view_model import (
    EnhancedIntegrityCheckViewModel, EnhancedMissingTimestamp, FetchSource
)
from goesvfi.integrity_check.enhanced_gui_tab import EnhancedIntegrityCheckTab
from goesvfi.integrity_check.optimized_timeline_tab import OptimizedTimelineTab
from goesvfi.integrity_check.satellite_integrity_tab_group import OptimizedResultsTab
from goesvfi.integrity_check.combined_tab import CombinedIntegrityTab


class PerformanceMetrics:
    """Class to track performance metrics."""
    
    def __init__(self):
        """Initialize performance metrics tracking."""
        self.start_time = 0
        self.end_time = 0
        self.start_memory = 0
        self.end_memory = 0
        self.peak_memory = 0
    
    def start(self):
        """Start performance measurement."""
        # Collect garbage first to reduce noise
        gc.collect()
        
        # Get current process
        process = psutil.Process(os.getpid())
        
        # Record starting time and memory
        self.start_time = time.time()
        self.start_memory = process.memory_info().rss / (1024 * 1024)  # MB
        self.peak_memory = self.start_memory
        
        # Start memory tracing
        tracemalloc.start()
    
    def update_peak(self):
        """Update peak memory usage."""
        process = psutil.Process(os.getpid())
        current_memory = process.memory_info().rss / (1024 * 1024)  # MB
        self.peak_memory = max(self.peak_memory, current_memory)
    
    def stop(self):
        """Stop performance measurement and return results."""
        # Record end time
        self.end_time = time.time()
        
        # Get current process
        process = psutil.Process(os.getpid())
        
        # Record end memory
        self.end_memory = process.memory_info().rss / (1024 * 1024)  # MB
        self.peak_memory = max(self.peak_memory, self.end_memory)
        
        # Get memory allocation from tracemalloc
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        # Collect garbage
        gc.collect()
        
        # Return metrics
        return {
            "elapsed_time": self.end_time - self.start_time,
            "memory_diff": self.end_memory - self.start_memory,
            "peak_memory": self.peak_memory,
            "traced_current": current / (1024 * 1024),  # MB
            "traced_peak": peak / (1024 * 1024)  # MB
        }


class TestIntegrityTabPerformance(PyQtAsyncTestCase):
    """Performance tests for integrity check tabs."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Call parent setUp for proper PyQt/asyncio setup
        super().setUp()
        
        # Ensure we have a QApplication
        self.app = QApplication.instance() or QApplication([])
        
        # Create a temporary directory
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temp_dir.name)
        
        # Mock the view model
        self.mock_view_model = MagicMock(spec=EnhancedIntegrityCheckViewModel)
        self.mock_view_model.base_directory = self.base_dir
        self.mock_view_model.satellite = SatellitePattern.GOES_18
        self.mock_view_model.fetch_source = FetchSource.AUTO
        self.mock_view_model.status = ScanStatus.READY
        self.mock_view_model.status_message = "Ready"
        
        # Setup dates
        self.start_date = datetime(2023, 1, 1)
        self.end_date = datetime(2023, 1, 3, 23, 59, 59)
        self.mock_view_model.start_date = self.start_date
        self.mock_view_model.end_date = self.end_date
        
        # Setup for disk space
        self.mock_view_model.get_disk_space_info = MagicMock(return_value=(10.0, 100.0))
        
        # Set up metrics collection
        self.metrics = PerformanceMetrics()
    
    def tearDown(self):
        """Tear down test fixtures."""
        # Clean up temporary directory
        self.temp_dir.cleanup()
        
        # Call parent tearDown for proper event loop cleanup
        super().tearDown()
    
    def _generate_test_data(self, count=100):
        """Generate a large dataset for performance testing."""
        items = []
        
        # Create a mix of different item types
        # 40% Missing, 30% Downloaded, 20% Error, 10% Downloading
        missing_count = int(count * 0.4)
        downloaded_count = int(count * 0.3)
        error_count = int(count * 0.2)
        downloading_count = count - missing_count - downloaded_count - error_count
        
        # Create timestamp base
        base_date = datetime(2023, 1, 1)
        
        # Generate missing items
        for i in range(missing_count):
            ts = base_date + timedelta(minutes=i*10)
            item = EnhancedMissingTimestamp(ts, f"missing_file_{i}.nc")
            items.append(item)
        
        # Generate downloaded items
        for i in range(downloaded_count):
            ts = base_date + timedelta(minutes=(i + missing_count)*10)
            item = EnhancedMissingTimestamp(ts, f"downloaded_file_{i}.nc")
            item.is_downloaded = True
            item.local_path = f"/test/path/downloaded_file_{i}.nc"
            items.append(item)
        
        # Generate error items
        for i in range(error_count):
            ts = base_date + timedelta(minutes=(i + missing_count + downloaded_count)*10)
            item = EnhancedMissingTimestamp(ts, f"error_file_{i}.nc")
            item.download_error = f"Error downloading file: Connection timeout {i}"
            items.append(item)
        
        # Generate downloading items
        for i in range(downloading_count):
            ts = base_date + timedelta(minutes=(i + missing_count + downloaded_count + error_count)*10)
            item = EnhancedMissingTimestamp(ts, f"downloading_file_{i}.nc")
            item.is_downloading = True
            item.progress = i % 100  # Random progress
            items.append(item)
        
        return items
    
    def test_timeline_tab_data_loading_performance(self):
        """Test performance of loading data in the timeline tab."""
        # Create the timeline tab
        timeline_tab = OptimizedTimelineTab()
        
        # Generate test data with various dataset sizes
        dataset_sizes = [100, 500, 1000]
        
        print("\nTimeline Tab Data Loading Performance:")
        print("=====================================")
        print(f"{'Dataset Size':<15} {'Time (s)':<10} {'Memory Diff (MB)':<20} {'Peak Memory (MB)':<20}")
        
        for size in dataset_sizes:
            # Generate data
            items = self._generate_test_data(size)
            
            # Start measurement
            self.metrics.start()
            
            # Load data
            timeline_tab.set_data(
                items,
                self.start_date,
                self.end_date,
                interval_minutes=15
            )
            
            # Process events to ensure UI updates
            QApplication.processEvents()
            
            # Stop measurement and get results
            metrics = self.metrics.stop()
            
            # Print results
            print(f"{size:<15} {metrics['elapsed_time']:<10.6f} {metrics['memory_diff']:<20.2f} {metrics['peak_memory']:<20.2f}")
            
            # Add a small delay to ensure we're starting the next test clean
            time.sleep(0.1)
        
        # Clean up the tab
        timeline_tab.close()
        timeline_tab.deleteLater()
    
    def test_results_tab_data_loading_performance(self):
        """Test performance of loading data in the results tab."""
        # Create the results tab
        results_tab = OptimizedResultsTab()
        
        # Generate test data with various dataset sizes
        dataset_sizes = [100, 500, 1000]
        
        print("\nResults Tab Data Loading Performance:")
        print("===================================")
        print(f"{'Dataset Size':<15} {'Time (s)':<10} {'Memory Diff (MB)':<20} {'Peak Memory (MB)':<20}")
        
        for size in dataset_sizes:
            # Generate data
            items = self._generate_test_data(size)
            
            # Start measurement
            self.metrics.start()
            
            # Load data
            results_tab.set_items(items, size + 20)  # Add some buffer for total_expected
            
            # Process events to ensure UI updates
            QApplication.processEvents()
            
            # Stop measurement and get results
            metrics = self.metrics.stop()
            
            # Print results
            print(f"{size:<15} {metrics['elapsed_time']:<10.6f} {metrics['memory_diff']:<20.2f} {metrics['peak_memory']:<20.2f}")
            
            # Add a small delay to ensure we're starting the next test clean
            time.sleep(0.1)
        
        # Clean up the tab
        results_tab.close()
        results_tab.deleteLater()
    
    def test_results_tab_grouping_performance(self):
        """Test performance of grouping data in the results tab."""
        # Create the results tab
        results_tab = OptimizedResultsTab()
        
        # Generate a large dataset
        items = self._generate_test_data(1000)
        
        # Load data first
        results_tab.set_items(items, 1020)
        QApplication.processEvents()
        
        # Test performance of different grouping methods
        grouping_methods = ["Day", "Hour", "Satellite", "Status", "Source"]
        
        print("\nResults Tab Grouping Performance:")
        print("===============================")
        print(f"{'Grouping Method':<20} {'Time (s)':<10} {'Memory Diff (MB)':<20} {'Peak Memory (MB)':<20}")
        
        for method in grouping_methods:
            # Start measurement
            self.metrics.start()
            
            # Change grouping
            results_tab._handle_group_changed(method)
            
            # Process events to ensure UI updates
            QApplication.processEvents()
            
            # Stop measurement and get results
            metrics = self.metrics.stop()
            
            # Print results
            print(f"{method:<20} {metrics['elapsed_time']:<10.6f} {metrics['memory_diff']:<20.2f} {metrics['peak_memory']:<20.2f}")
            
            # Add a small delay to ensure we're starting the next test clean
            time.sleep(0.1)
        
        # Clean up the tab
        results_tab.close()
        results_tab.deleteLater()
    
    def test_tab_switch_performance(self):
        """Test performance of switching between tabs."""
        # Create a main window with tab widget
        main_window = QMainWindow()
        tab_widget = QTabWidget()
        main_window.setCentralWidget(tab_widget)
        
        # Create tabs
        integrity_tab = EnhancedIntegrityCheckTab(self.mock_view_model)
        timeline_tab = OptimizedTimelineTab()
        results_tab = OptimizedResultsTab()
        
        # Add tabs to widget
        tab_widget.addTab(integrity_tab, "File Integrity")
        tab_widget.addTab(timeline_tab, "Timeline")
        tab_widget.addTab(results_tab, "Results")
        
        # Generate data and load it
        items = self._generate_test_data(500)
        timeline_tab.set_data(items, self.start_date, self.end_date, 15)
        results_tab.set_items(items, 520)
        
        # Show the window
        main_window.show()
        QApplication.processEvents()
        
        print("\nTab Switching Performance:")
        print("========================")
        print(f"{'Transition':<25} {'Time (s)':<10} {'Memory Diff (MB)':<20} {'Peak Memory (MB)':<20}")
        
        # Test switching from Integrity to Timeline
        self.metrics.start()
        tab_widget.setCurrentIndex(0)  # Integrity tab
        QApplication.processEvents()
        tab_widget.setCurrentIndex(1)  # Timeline tab
        QApplication.processEvents()
        metrics = self.metrics.stop()
        print(f"{'Integrity -> Timeline':<25} {metrics['elapsed_time']:<10.6f} {metrics['memory_diff']:<20.2f} {metrics['peak_memory']:<20.2f}")
        
        # Test switching from Timeline to Results
        self.metrics.start()
        tab_widget.setCurrentIndex(1)  # Timeline tab
        QApplication.processEvents()
        tab_widget.setCurrentIndex(2)  # Results tab
        QApplication.processEvents()
        metrics = self.metrics.stop()
        print(f"{'Timeline -> Results':<25} {metrics['elapsed_time']:<10.6f} {metrics['memory_diff']:<20.2f} {metrics['peak_memory']:<20.2f}")
        
        # Test switching from Results to Integrity
        self.metrics.start()
        tab_widget.setCurrentIndex(2)  # Results tab
        QApplication.processEvents()
        tab_widget.setCurrentIndex(0)  # Integrity tab
        QApplication.processEvents()
        metrics = self.metrics.stop()
        print(f"{'Results -> Integrity':<25} {metrics['elapsed_time']:<10.6f} {metrics['memory_diff']:<20.2f} {metrics['peak_memory']:<20.2f}")
        
        # Test cycling through all tabs
        self.metrics.start()
        tab_widget.setCurrentIndex(0)  # Integrity
        QApplication.processEvents()
        tab_widget.setCurrentIndex(1)  # Timeline
        QApplication.processEvents()
        tab_widget.setCurrentIndex(2)  # Results
        QApplication.processEvents()
        tab_widget.setCurrentIndex(0)  # Back to Integrity
        QApplication.processEvents()
        metrics = self.metrics.stop()
        print(f"{'Full Cycle':<25} {metrics['elapsed_time']:<10.6f} {metrics['memory_diff']:<20.2f} {metrics['peak_memory']:<20.2f}")
        
        # Clean up
        main_window.close()
        main_window.deleteLater()
    
    def test_ui_responsiveness(self):
        """Test UI responsiveness during data loading."""
        # Create a main window with tab widget
        main_window = QMainWindow()
        tab_widget = QTabWidget()
        main_window.setCentralWidget(tab_widget)
        
        # Create tabs
        integrity_tab = EnhancedIntegrityCheckTab(self.mock_view_model)
        timeline_tab = OptimizedTimelineTab()
        results_tab = OptimizedResultsTab()
        
        # Add tabs to widget
        tab_widget.addTab(integrity_tab, "File Integrity")
        tab_widget.addTab(timeline_tab, "Timeline")
        tab_widget.addTab(results_tab, "Results")
        
        # Show the window
        main_window.show()
        QApplication.processEvents()
        
        print("\nUI Responsiveness During Data Loading:")
        print("===================================")
        
        # Generate large dataset
        large_dataset = self._generate_test_data(2000)
        
        # Create a timer to simulate UI interactions during loading
        timer_count = 0
        max_timer_count = 10
        event_times = []
        
        def ui_interaction():
            nonlocal timer_count
            # Record the time taken for the event to be processed
            event_start = time.time()
            # Simulate UI interaction
            QTest.mouseMove(tab_widget)
            QApplication.processEvents()
            event_end = time.time()
            event_times.append(event_end - event_start)
            
            timer_count += 1
            if timer_count < max_timer_count:
                QTimer.singleShot(100, ui_interaction)
        
        # Start measuring
        self.metrics.start()
        
        # Start the UI interaction timer
        QTimer.singleShot(0, ui_interaction)
        
        # Set the timeline tab data (this should be a heavy operation)
        tab_widget.setCurrentIndex(1)  # Timeline tab
        timeline_tab.set_data(large_dataset, self.start_date, self.end_date, 15)
        
        # Process events to ensure UI updates
        QApplication.processEvents()
        
        # Set the results tab data
        tab_widget.setCurrentIndex(2)  # Results tab
        results_tab.set_items(large_dataset, 2020)
        
        # Process more events
        QApplication.processEvents()
        
        # Allow some time for the UI interactions to complete
        time.sleep(1.5)
        
        # Stop measuring
        metrics = self.metrics.stop()
        
        # Print overall metrics
        print(f"Total time for loading: {metrics['elapsed_time']:.6f} seconds")
        print(f"Memory usage: {metrics['memory_diff']:.2f} MB (diff), {metrics['peak_memory']:.2f} MB (peak)")
        
        # Print UI responsiveness metrics
        if event_times:
            avg_event_time = sum(event_times) / len(event_times)
            max_event_time = max(event_times)
            print(f"UI interaction times:")
            print(f"  Average: {avg_event_time:.6f} seconds")
            print(f"  Maximum: {max_event_time:.6f} seconds")
            print(f"  Events recorded: {len(event_times)}")
        else:
            print("No UI events were recorded.")
        
        # Clean up
        main_window.close()
        main_window.deleteLater()


if __name__ == '__main__':
    unittest.main()