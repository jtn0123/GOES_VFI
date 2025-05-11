"""Tests for the improved enhanced integrity check tab."""

import os
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QApplication, QWidget

from goesvfi.integrity_check.enhanced_gui_tab_improved import (
    ImprovedEnhancedIntegrityCheckTab,
)
from goesvfi.integrity_check.enhanced_view_model import EnhancedIntegrityCheckViewModel
from goesvfi.integrity_check.time_index import Satellite, SatellitePattern


class TestImprovedEnhancedTab:
    """Test the improved enhanced integrity check tab."""

    @pytest.fixture
    def view_model(self, tmpdir):
        """Create a view model for testing."""
        # Use temp dir for testing
        model = EnhancedIntegrityCheckViewModel(base_directory=tmpdir)

        # Set test data
        model.start_date = datetime.now() - timedelta(days=1)
        model.end_date = datetime.now()

        return model

    @pytest.fixture
    def tab(self, qtbot, view_model):
        """Create the tab widget for testing."""
        widget = ImprovedEnhancedIntegrityCheckTab(view_model)
        qtbot.addWidget(widget)
        return widget

    def test_initial_state(self, tab, view_model):
        """Test the initial state of the tab."""
        # Check that UI elements are initialized correctly
        assert tab.directory_edit.text() == str(view_model.base_directory)
        assert not tab.download_button.isEnabled()
        assert not tab.export_button.isEnabled()
        assert tab.scan_button.isEnabled()

        # Advanced options are collapsed by default
        assert not tab.advanced_options.isChecked()

    def test_date_range_display(self, tab, view_model):
        """Test the date range display functionality."""
        # Set a specific date range
        test_start = datetime(2023, 5, 1, 10, 0)
        test_end = datetime(2023, 5, 1, 16, 0)

        view_model.start_date = test_start
        view_model.end_date = test_end

        # Update the UI
        tab._update_date_range_label()

        # Same day format: "2023-05-01 (10:00 - 16:00)"
        expected_text = "2023-05-01 (10:00 - 16:00)"
        assert tab.date_range_label.text() == expected_text

        # Different days format: "2023-05-01 10:00 → 2023-05-03 16:00"
        test_end = datetime(2023, 5, 3, 16, 0)
        view_model.end_date = test_end
        tab._update_date_range_label()

        expected_text = "2023-05-01 10:00 → 2023-05-03 16:00"
        assert tab.date_range_label.text() == expected_text

    def test_browse_directory(self, qtbot, tab, view_model, monkeypatch):
        """Test browsing for a directory."""
        # Mock the QFileDialog.getExistingDirectory method
        monkeypatch.setattr(
            "PyQt6.QtWidgets.QFileDialog.getExistingDirectory",
            lambda *args, **kwargs: "/test/path",
        )

        # Click the browse button
        qtbot.mouseClick(tab.directory_browse_button, Qt.MouseButton.LeftButton)

        # Check that the view model was updated
        assert str(view_model.base_directory) == "/test/path"
        assert tab.directory_edit.text() == "/test/path"

    def test_start_scan(self, qtbot, tab, view_model, monkeypatch):
        """Test starting a scan."""
        # Mock the start_scan method
        start_scan_called = False

        def mock_start_scan():
            nonlocal start_scan_called
            start_scan_called = True

        monkeypatch.setattr(view_model, "start_scan", mock_start_scan)

        # Set some test values
        tab.interval_spinbox.setValue(15)
        tab.force_rescan_checkbox.setChecked(True)
        tab.auto_download_checkbox.setChecked(True)
        tab.satellite_combo.setCurrentIndex(1)  # Select a different satellite
        tab.source_combo.setCurrentIndex(1)  # Select S3 source

        # Click the scan button
        qtbot.mouseClick(tab.scan_button, Qt.MouseButton.LeftButton)

        # Check that the view model was updated and scan started
        assert start_scan_called
        assert view_model.interval_minutes == 15
        assert view_model.force_rescan
        assert view_model.auto_download

    def test_cancel_operation(self, qtbot, tab, view_model, monkeypatch):
        """Test canceling an operation."""
        # Mock the cancel methods
        cancel_scan_called = False
        cancel_downloads_called = False

        def mock_cancel_scan():
            nonlocal cancel_scan_called
            cancel_scan_called = True

        def mock_cancel_downloads():
            nonlocal cancel_downloads_called
            cancel_downloads_called = True

        monkeypatch.setattr(view_model, "cancel_scan", mock_cancel_scan)
        monkeypatch.setattr(view_model, "cancel_downloads", mock_cancel_downloads)

        # Test canceling a scan
        view_model._is_scanning = True
        view_model._is_downloading = False

        # Click the cancel button
        qtbot.mouseClick(tab.cancel_button, Qt.MouseButton.LeftButton)

        # Check that the view model method was called
        assert cancel_scan_called
        assert not cancel_downloads_called

        # Test canceling downloads
        cancel_scan_called = False
        view_model._is_scanning = False
        view_model._is_downloading = True

        # Click the cancel button
        qtbot.mouseClick(tab.cancel_button, Qt.MouseButton.LeftButton)

        # Check that the view model method was called
        assert not cancel_scan_called
        assert cancel_downloads_called

    def test_progress_updates(self, qtbot, tab):
        """Test progress bar updates."""
        # Emit the progress_updated signal
        tab.view_model.progress_updated.emit(50, 100, 30.5)

        # Check that the progress bar was updated
        assert tab.progress_bar.value() == 50
        assert "50%" in tab.progress_bar.format()
        assert "30" in tab.progress_bar.format()  # 30 seconds

        # Test with no ETA
        tab.view_model.progress_updated.emit(75, 100, 0)

        # Check that the progress bar was updated
        assert tab.progress_bar.value() == 75
        assert "75%" in tab.progress_bar.format()
        assert "ETA" not in tab.progress_bar.format()

    def test_scan_completion(self, qtbot, tab, monkeypatch):
        """Test handling scan completion."""
        # Mock QMessageBox.information
        info_shown = False

        def mock_info(*args, **kwargs):
            nonlocal info_shown
            info_shown = True

        monkeypatch.setattr("PyQt6.QtWidgets.QMessageBox.information", mock_info)

        # Set up test data
        tab.view_model._missing_count = 5
        tab.view_model._total_expected = 100

        # Emit the scan_completed signal
        tab.view_model.scan_completed.emit(True, "Scan completed successfully")

        # Check that the progress bar shows 100%
        assert tab.progress_bar.value() == 100
        assert tab.progress_bar.format() == "100%"

        # Check that the message box was shown
        assert info_shown

        # Test with no missing items
        info_shown = False
        tab.view_model._missing_count = 0

        # Emit the scan_completed signal
        tab.view_model.scan_completed.emit(True, "Scan completed successfully")

        # Check that the message box was shown
        assert info_shown

        # Test with an error
        error_shown = False

        def mock_error(*args, **kwargs):
            nonlocal error_shown
            error_shown = True

        monkeypatch.setattr("PyQt6.QtWidgets.QMessageBox.critical", mock_error)

        # Emit the scan_completed signal with failure
        tab.view_model.scan_completed.emit(False, "Error during scan")

        # Check that the error message box was shown
        assert error_shown
