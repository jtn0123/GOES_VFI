"""Comprehensive tests for GUI button states and interactions."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from PyQt6.QtCore import Qt
import pytest

from goesvfi.gui import MainWindow


class TestGUIButtonValidation:
    """Test suite for validating GUI buttons and their interactions."""

    @pytest.fixture()
    def window(self, qtbot, mocker):
        """Create a MainWindow instance for testing."""
        # Mock heavy components
        mocker.patch("goesvfi.integrity_check.combined_tab.CombinedIntegrityAndImageryTab")
        mocker.patch("goesvfi.integrity_check.enhanced_imagery_tab.EnhancedGOESImageryTab")

        # Create window
        window = MainWindow(debug_mode=True)
        qtbot.addWidget(window)
        window._post_init_setup()

        return window

    def test_input_directory_button_states(self, qtbot, window, mocker) -> None:
        """Test input directory button and related UI state changes."""
        # Initial state - no input directory
        assert window.main_tab.in_dir_button.isEnabled()
        assert window.main_tab.in_dir_edit.text() == ""
        assert not window.main_tab.crop_button.isEnabled()
        assert not window.main_tab.clear_crop_button.isEnabled()

        # Mock directory selection
        mock_dialog = mocker.patch("goesvfi.gui_tabs.main_tab.QFileDialog.getExistingDirectory")
        mock_dialog.return_value = "/test/input/dir"

        # Click the input directory button
        qtbot.mouseClick(window.main_tab.in_dir_button, Qt.MouseButton.LeftButton)

        # Verify state after selection
        assert window.main_tab.in_dir_edit.text() == "/test/input/dir"
        assert window.in_dir == Path("/test/input/dir")
        assert window.main_tab.crop_button.isEnabled()  # Should be enabled now
        assert not window.main_tab.clear_crop_button.isEnabled()  # Still disabled (no crop)

    def test_output_file_button_interaction(self, qtbot, window, mocker) -> None:
        """Test output file selection button."""
        # Initial state
        assert window.main_tab.out_file_button.isEnabled()
        assert window.main_tab.out_file_edit.text() == ""

        # Mock file dialog
        mock_dialog = mocker.patch("goesvfi.gui_tabs.main_tab.QFileDialog.getSaveFileName")
        mock_dialog.return_value = ("/test/output.mp4", "Video Files (*.mp4)")

        # Click the output file button
        qtbot.mouseClick(window.main_tab.out_file_button, Qt.MouseButton.LeftButton)

        # Verify state
        assert window.main_tab.out_file_edit.text() == "/test/output.mp4"
        assert window.out_file_path == Path("/test/output.mp4")

    def test_start_button_state_management(self, qtbot, window) -> None:
        """Test start button enable/disable logic based on inputs."""
        # Initial state - button disabled (no inputs)
        assert not window.main_tab.start_button.isEnabled()

        # Set only input directory - still disabled
        window.set_in_dir(Path("/test/input"))
        window._update_start_button_state()
        assert not window.main_tab.start_button.isEnabled()

        # Set output file - now enabled
        window.out_file_path = Path("/test/output.mp4")
        window._update_start_button_state()
        assert window.main_tab.start_button.isEnabled()

        # Simulate processing state - button text changes
        window._set_processing_state(True)
        assert window.main_tab.start_button.text() == "Stop Processing"
        assert window.main_tab.start_button.isEnabled()

        # Back to normal state
        window._set_processing_state(False)
        assert window.main_tab.start_button.text() == "Start Processing"

    def test_crop_button_workflow(self, qtbot, window, mocker) -> None:
        """Test complete crop button workflow."""
        # Mock components
        mock_crop_dialog = mocker.patch("goesvfi.gui_tabs.main_tab.CropSelectionDialog")
        mock_dialog_instance = MagicMock()
        mock_dialog_instance.exec.return_value = 1  # Accepted
        mock_dialog_instance.get_selected_rect.return_value = MagicMock(
            x=MagicMock(return_value=10),
            y=MagicMock(return_value=20),
            width=MagicMock(return_value=100),
            height=MagicMock(return_value=50),
        )
        mock_crop_dialog.return_value = mock_dialog_instance

        # Set input directory to enable crop button
        window.set_in_dir(Path("/test/input"))
        assert window.main_tab.crop_button.isEnabled()

        # Click crop button
        with patch.object(window, "_get_sorted_image_files") as mock_files:
            mock_files.return_value = [
                Path("/test/image1.png"),
                Path("/test/image2.png"),
            ]

            # Mock image loading
            with patch.object(window, "_prepare_image_for_crop_dialog") as mock_prepare:
                mock_pixmap = MagicMock()
                mock_pixmap.isNull.return_value = False
                mock_prepare.return_value = mock_pixmap

                # Click the crop button
                qtbot.mouseClick(window.main_tab.crop_button, Qt.MouseButton.LeftButton)

        # Verify crop was set
        assert window.current_crop_rect == (10, 20, 100, 50)
        assert window.main_tab.clear_crop_button.isEnabled()

        # Test clear crop button
        qtbot.mouseClick(window.main_tab.clear_crop_button, Qt.MouseButton.LeftButton)
        assert window.current_crop_rect is None
        assert not window.main_tab.clear_crop_button.isEnabled()

    def test_encoder_combo_triggers_ui_updates(self, qtbot, window) -> None:
        """Test encoder selection updates UI appropriately."""
        # Initial state - RIFE selected
        assert window.main_tab.encoder_combo.currentText() == "RIFE"
        assert window.main_tab.rife_options_group.isEnabled()

        # Switch to FFmpeg
        window.main_tab.encoder_combo.setCurrentText("FFmpeg")
        qtbot.wait(50)  # Allow signals to process

        # RIFE options should be disabled
        assert not window.main_tab.rife_options_group.isEnabled()
        assert not window.main_tab.model_combo.isEnabled()

        # Switch back to RIFE
        window.main_tab.encoder_combo.setCurrentText("RIFE")
        qtbot.wait(50)

        # RIFE options should be enabled again
        assert window.main_tab.rife_options_group.isEnabled()
        assert window.main_tab.model_combo.isEnabled()

    def test_sanchez_checkbox_controls(self, qtbot, window) -> None:
        """Test Sanchez preprocessing checkbox and resolution combo."""
        # Initial state
        assert not window.main_tab.sanchez_checkbox.isChecked()
        assert not window.main_tab.sanchez_res_combo.isEnabled()

        # Check the checkbox
        window.main_tab.sanchez_checkbox.setChecked(True)
        window._toggle_sanchez_res_enabled(Qt.CheckState.Checked)

        # Resolution combo should be enabled
        assert window.main_tab.sanchez_res_combo.isEnabled()

        # Uncheck
        window.main_tab.sanchez_checkbox.setChecked(False)
        window._toggle_sanchez_res_enabled(Qt.CheckState.Unchecked)

        # Resolution combo should be disabled
        assert not window.main_tab.sanchez_res_combo.isEnabled()

    def test_tab_switching_preserves_state(self, qtbot, window) -> None:
        """Test that switching tabs preserves state."""
        # Set some state in main tab
        window.set_in_dir(Path("/test/input"))
        window.out_file_path = Path("/test/output.mp4")
        window.current_crop_rect = (10, 20, 100, 50)

        # Switch to FFmpeg settings tab
        window.tab_widget.setCurrentIndex(1)
        qtbot.wait(50)

        # Switch to another tab
        window.tab_widget.setCurrentIndex(2)
        qtbot.wait(50)

        # Switch back to main tab
        window.tab_widget.setCurrentIndex(0)
        qtbot.wait(50)

        # Verify state is preserved
        assert window.in_dir == Path("/test/input")
        assert window.out_file_path == Path("/test/output.mp4")
        assert window.current_crop_rect == (10, 20, 100, 50)
        assert window.main_tab.crop_button.isEnabled()
        assert window.main_tab.clear_crop_button.isEnabled()

    def test_preview_label_click_interaction(self, qtbot, window, mocker) -> None:
        """Test clicking on preview labels."""
        # Mock the zoom dialog
        mock_zoom = mocker.patch.object(window, "_show_zoom")

        # Set up preview label with image
        window.main_tab.first_frame_label.file_path = "/test/image.png"
        mock_pixmap = MagicMock()
        mock_pixmap.isNull.return_value = False
        window.main_tab.first_frame_label.setPixmap(mock_pixmap)

        # Simulate click on preview label
        window.main_tab.first_frame_label.clicked.emit()

        # Verify zoom was called
        mock_zoom.assert_called_once_with(window.main_tab.first_frame_label)

    def test_processing_disables_ui_elements(self, qtbot, window) -> None:
        """Test that processing state disables appropriate UI elements."""
        # Set up valid inputs
        window.set_in_dir(Path("/test/input"))
        window.out_file_path = Path("/test/output.mp4")

        # Verify UI is enabled before processing
        assert window.main_tab.in_dir_button.isEnabled()
        assert window.main_tab.out_file_button.isEnabled()
        assert window.main_tab.encoder_combo.isEnabled()
        assert window.tab_widget.isTabEnabled(1)  # Other tabs enabled

        # Start processing
        window._set_processing_state(True)

        # Verify UI is disabled during processing
        assert not window.main_tab.in_dir_button.isEnabled()
        assert not window.main_tab.out_file_button.isEnabled()
        assert not window.main_tab.encoder_combo.isEnabled()
        assert not window.tab_widget.isTabEnabled(1)  # Other tabs disabled
        assert window.tab_widget.isTabEnabled(0)  # Main tab still enabled

        # Stop processing
        window._set_processing_state(False)

        # Verify UI is re-enabled
        assert window.main_tab.in_dir_button.isEnabled()
        assert window.main_tab.out_file_button.isEnabled()
        assert window.main_tab.encoder_combo.isEnabled()
        assert window.tab_widget.isTabEnabled(1)

    def test_rife_model_selection_updates(self, qtbot, window) -> None:
        """Test RIFE model selection updates UI elements."""
        # Ensure RIFE is selected
        window.main_tab.encoder_combo.setCurrentText("RIFE")

        # Initial model
        initial_model = window.main_tab.rife_model_combo.currentData()

        # Change model selection
        if window.main_tab.rife_model_combo.count() > 1:
            window.main_tab.rife_model_combo.setCurrentIndex(1)
            qtbot.wait(50)

            # Verify model changed
            new_model = window.main_tab.rife_model_combo.currentData()
            assert new_model != initial_model
            assert window.current_model_key == new_model

            # Verify RIFE UI elements updated
            window._update_rife_ui_elements()

    def test_settings_buttons_functionality(self, qtbot, window, mocker) -> None:
        """Test settings save/load button functionality."""
        # Mock settings methods
        mock_save = mocker.patch.object(window, "saveSettings")
        mocker.patch.object(window, "loadSettings")

        # If there are explicit save/load buttons, test them
        # For now, test that settings are saved on certain actions

        # Change some settings
        window.set_in_dir(Path("/test/new/input"))
        window.main_tab.fps_spinbox.setValue(60)

        # Settings should be saved when window closes
        window.close()

        # Verify save was called
        mock_save.assert_called()

    def test_error_message_displays(self, qtbot, window, mocker) -> None:
        """Test that error messages are properly displayed to user."""
        # Mock QMessageBox
        mock_msgbox = mocker.patch("goesvfi.gui.QMessageBox.critical")

        # Trigger an error
        error_msg = "Test error message"
        window._on_processing_error(error_msg)

        # Verify error dialog was shown
        mock_msgbox.assert_called_once()
        args = mock_msgbox.call_args[0]
        assert error_msg in args[2]  # Error message in dialog text

        # Verify status bar shows error
        assert "Processing failed!" in window.status_bar.currentMessage()

    def test_keyboard_shortcuts(self, qtbot, window) -> None:
        """Test keyboard shortcuts if implemented."""
        # Test Ctrl+O for open directory (if implemented)
        # Test Ctrl+S for start processing (if implemented)
        # Test ESC for stop processing (if implemented)
        # Add tests based on actual shortcuts

    def test_drag_drop_functionality(self, qtbot, window) -> None:
        """Test drag and drop of files/directories if implemented."""
        # Test dragging a directory to input field
        # Test dragging an image file
        # Test invalid drops are rejected
        # Add tests if drag-drop is implemented
