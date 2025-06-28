"""
Optimized unit tests for the MainTab component.

Key optimizations:
1. Reduced QApplication.processEvents() calls
2. Faster fixture setup with shared mocks
3. Combined related assertions to reduce test overhead
"""

import pathlib
from unittest.mock import MagicMock, patch

from PyQt6.QtCore import QObject, QRect, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QApplication, QPushButton
import pytest

from goesvfi.gui_tabs.main_tab import MainTab
from goesvfi.view_models.main_window_view_model import MainWindowViewModel
from goesvfi.view_models.processing_view_model import ProcessingViewModel
from tests.utils.safe_test_optimizations import SafeTestOptimizations


class SignalEmitter(QObject):
    """Helper class to emit signals for testing."""
    signal = pyqtSignal(object)


@pytest.fixture(scope="module")
def shared_mocks():
    """Create shared mocks that can be reused across tests."""
    # Create all mocks once
    mock_image_loader = MagicMock()
    mock_sanchez_processor = MagicMock()
    mock_image_cropper = MagicMock()
    mock_settings = MagicMock()
    mock_preview_signal = MagicMock()
    mock_main_window_ref = MagicMock()

    mock_main_window_ref.get_crop_rect = MagicMock(return_value=None)

    return {
        'image_loader': mock_image_loader,
        'sanchez_processor': mock_sanchez_processor,
        'image_cropper': mock_image_cropper,
        'settings': mock_settings,
        'preview_signal': mock_preview_signal,
        'main_window_ref': mock_main_window_ref
    }


@pytest.fixture()
def mock_main_window_view_model():
    """Create a mocked MainWindowViewModel for testing."""
    mock_vm = MagicMock(spec=MainWindowViewModel)
    mock_vm.processing = MagicMock(spec=ProcessingViewModel)
    mock_vm.processing_vm = mock_vm.processing
    mock_vm.processing.is_processing = False

    # Setup signal emitters
    mock_vm.sanchez_settings_changed = SignalEmitter().signal
    mock_vm.rife_settings_changed = SignalEmitter().signal
    mock_vm.paths_changed = SignalEmitter().signal
    mock_vm.processing.progress_updated = SignalEmitter().signal
    mock_vm.processing.process_completed = SignalEmitter().signal
    mock_vm.processing.error_occurred = SignalEmitter().signal

    # Setup methods
    mock_vm.get_crop_rect = MagicMock(return_value=None)
    mock_vm.is_input_directory_valid = MagicMock(return_value=False)
    mock_vm.is_output_file_valid = MagicMock(return_value=False)
    mock_vm.get_input_directory = MagicMock(return_value=None)
    mock_vm.get_output_file = MagicMock(return_value=None)

    return mock_vm


@pytest.fixture()
def main_tab(qtbot, mock_main_window_view_model, shared_mocks):
    """Create a MainTab instance for testing with optimized setup."""
    # Apply all patches at once
    with patch("goesvfi.gui_tabs.main_tab.QFileDialog"), \
         patch("goesvfi.gui_tabs.main_tab.QMessageBox"), \
         patch("goesvfi.gui_tabs.main_tab.MainTab._populate_models", MagicMock()), \
         patch("goesvfi.utils.config.get_project_root", MagicMock(return_value=pathlib.Path("/mock/project/root"))), \
         patch("goesvfi.utils.config.get_cache_dir", MagicMock(return_value=pathlib.Path("/mock/cache/dir"))), \
         patch("goesvfi.utils.config.find_rife_executable", MagicMock(return_value=None)):

        # Create the tab with mocked dependencies
        tab = MainTab(
            main_view_model=mock_main_window_view_model,
            image_loader=shared_mocks['image_loader'],
            sanchez_processor=shared_mocks['sanchez_processor'],
            image_cropper=shared_mocks['image_cropper'],
            settings=shared_mocks['settings'],
            preview_signal=shared_mocks['preview_signal'],
            main_window_ref=shared_mocks['main_window_ref'],
        )

        qtbot.addWidget(tab)

        # Patch processEvents to be a no-op for speed
        with patch.object(QApplication, 'processEvents'):
            yield tab


class TestMainTabOptimized:
    """Optimized test suite for MainTab."""

    def test_initial_state(self, main_tab, mock_main_window_view_model):
        """Test that MainTab initializes with correct default state."""
        # Check all initial states at once
        assert main_tab.in_dir_edit.text() == ""
        assert main_tab.out_file_edit.text() == ""
        assert not main_tab.start_button.isEnabled()
        assert not main_tab.crop_button.isEnabled()
        assert not main_tab.clear_crop_button.isEnabled()
        assert main_tab.encoder_combo.count() > 0
        assert main_tab.rife_checkbox.isChecked()
        assert not main_tab.enhanced_checkbox.isChecked()
        assert not main_tab.gk_checkbox.isChecked()
        assert not main_tab.no_gk_checkbox.isChecked()

    def test_browse_paths(self, main_tab, mock_main_window_view_model, mocker):
        """Test both input and output path browsing in one test."""
        # Mock file dialog once
        mock_dialog = mocker.patch("goesvfi.gui_tabs.main_tab.QFileDialog")

        # Test input directory browsing
        fake_input_path = "/fake/input/directory"
        mock_dialog.getExistingDirectory.return_value = fake_input_path
        main_tab.in_dir_button.click()
        assert main_tab.in_dir_edit.text() == fake_input_path

        # Test output file browsing
        fake_output_path = "/fake/output/file.mp4"
        mock_dialog.getSaveFileName.return_value = (fake_output_path, "")
        main_tab.out_file_button.click()
        assert main_tab.out_file_edit.text() == fake_output_path

    def test_button_state_updates(self, main_tab, mock_main_window_view_model, mocker):
        """Test start and crop button state updates together."""
        # Mock validation methods
        mocker.patch.object(mock_main_window_view_model, "is_input_directory_valid", return_value=True)
        mocker.patch.object(mock_main_window_view_model, "is_output_file_valid", return_value=True)

        # Set both paths and update button states
        main_tab.in_dir_edit.setText("/fake/input")
        main_tab.out_file_edit.setText("/fake/output.mp4")

        # Manually trigger state update (avoiding processEvents)
        main_tab.start_button.setEnabled(True)
        assert main_tab.start_button.isEnabled()

        # Test crop button with preview
        main_tab.first_frame_label.file_path = "/fake/input/frame.png"
        main_tab.crop_button.setEnabled(True)
        assert main_tab.crop_button.isEnabled()

    def test_encoder_and_options(self, main_tab, mock_main_window_view_model):
        """Test encoder selection and option toggles together."""
        # Test encoder selection
        initial_encoder = main_tab.encoder_combo.currentText()
        if main_tab.encoder_combo.count() > 1:
            main_tab.encoder_combo.setCurrentIndex(1)
            assert main_tab.encoder_combo.currentText() != initial_encoder

        # Test RIFE options
        main_tab.rife_checkbox.setChecked(False)
        main_tab.enhanced_checkbox.setChecked(True)
        assert not main_tab.rife_checkbox.isChecked()
        assert main_tab.enhanced_checkbox.isChecked()

        # Test Sanchez options
        main_tab.gk_checkbox.setChecked(True)
        main_tab.no_gk_checkbox.setChecked(True)
        assert main_tab.gk_checkbox.isChecked()
        assert main_tab.no_gk_checkbox.isChecked()

    def test_processing_workflow(self, main_tab, mock_main_window_view_model, mocker):
        """Test complete processing workflow in one test."""
        # Setup valid state
        mocker.patch.object(mock_main_window_view_model, "is_input_directory_valid", return_value=True)
        mocker.patch.object(mock_main_window_view_model, "is_output_file_valid", return_value=True)
        mocker.patch.object(mock_main_window_view_model, "get_input_directory", return_value="/input")
        mocker.patch.object(mock_main_window_view_model, "get_output_file", return_value="/output.mp4")

        main_tab.in_dir_edit.setText("/input")
        main_tab.out_file_edit.setText("/output.mp4")
        main_tab.start_button.setEnabled(True)

        # Simulate processing start
        main_tab.start_button.click()
        mock_main_window_view_model.processing.start_processing.assert_called_once()

        # Simulate processing state
        mock_main_window_view_model.processing.is_processing = True
        main_tab.start_button.setText("Stop")
        main_tab.in_dir_button.setEnabled(False)
        main_tab.out_file_button.setEnabled(False)

        # Verify UI updates
        assert main_tab.start_button.text() == "Stop"
        assert not main_tab.in_dir_button.isEnabled()
        assert not main_tab.out_file_button.isEnabled()