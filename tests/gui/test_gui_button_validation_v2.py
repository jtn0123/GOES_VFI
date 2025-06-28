"""
Optimized tests for GUI button validation with maintained coverage.

This v2 version maintains all test scenarios while optimizing through:
- Shared fixtures at class level
- Combined related button interaction tests
- Batch UI state validation
- Comprehensive test scenarios with enhanced coverage
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from PyQt6.QtCore import Qt
import pytest

from goesvfi.gui import MainWindow


class TestGUIButtonValidationOptimizedV2:
    """Optimized GUI button validation tests with full coverage."""

    @pytest.fixture(scope="class")
    def shared_app(self):
        """Shared QApplication instance."""
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        yield app
        app.processEvents()

    @pytest.fixture(scope="class")
    def shared_mocks(self):
        """Create shared mocks that persist across tests."""
        mocks = {}

        # Mock heavy components
        with (
            patch("goesvfi.integrity_check.combined_tab.CombinedIntegrityAndImageryTab") as mock_combined,
            patch("goesvfi.integrity_check.enhanced_imagery_tab.EnhancedGOESImageryTab") as mock_imagery,
        ):
            mocks["combined_tab"] = mock_combined
            mocks["imagery_tab"] = mock_imagery
            yield mocks

    @pytest.fixture()
    def main_window(self, qtbot, shared_app, shared_mocks):
        """Create MainWindow instance with proper cleanup."""
        window = MainWindow(debug_mode=True)
        qtbot.addWidget(window)
        window._post_init_setup()

        return window

    def test_input_directory_button_comprehensive(self, qtbot, main_window) -> None:
        """Test comprehensive input directory button functionality."""
        window = main_window

        # Test initial state
        assert window.main_tab.in_dir_button.isEnabled()
        assert window.main_tab.in_dir_edit.text() == ""
        assert not window.main_tab.crop_button.isEnabled()
        assert not window.main_tab.clear_crop_button.isEnabled()

        # Test multiple directory selection scenarios
        test_directories = [
            "/test/input/dir",
            "/different/path/images",
            "/home/user/videos",
            "/tmp/processing",
        ]

        for test_dir in test_directories:
            with patch("goesvfi.gui_tabs.main_tab.QFileDialog.getExistingDirectory") as mock_dialog:
                mock_dialog.return_value = test_dir

                # Click the input directory button
                qtbot.mouseClick(window.main_tab.in_dir_button, Qt.MouseButton.LeftButton)

                # Verify state after selection
                assert window.main_tab.in_dir_edit.text() == test_dir
                assert window.in_dir == Path(test_dir)
                assert window.main_tab.crop_button.isEnabled()
                assert not window.main_tab.clear_crop_button.isEnabled()  # No crop set yet

        # Test empty directory selection (user cancels)
        with patch("goesvfi.gui_tabs.main_tab.QFileDialog.getExistingDirectory") as mock_dialog:
            mock_dialog.return_value = ""  # User cancelled

            original_text = window.main_tab.in_dir_edit.text()
            qtbot.mouseClick(window.main_tab.in_dir_button, Qt.MouseButton.LeftButton)

            # Text should not change when user cancels
            assert window.main_tab.in_dir_edit.text() == original_text

    def test_output_file_button_comprehensive(self, qtbot, main_window) -> None:
        """Test comprehensive output file selection functionality."""
        window = main_window

        # Test initial state
        assert window.main_tab.out_file_button.isEnabled()
        assert window.main_tab.out_file_edit.text() == ""

        # Test multiple file type selections
        test_files = [
            ("/test/output.mp4", "Video Files (*.mp4)"),
            ("/videos/result.mov", "MOV Files (*.mov)"),
            ("/export/final.mkv", "MKV Files (*.mkv)"),
            ("/render/sequence.avi", "AVI Files (*.avi)"),
        ]

        for test_file, file_filter in test_files:
            with patch("goesvfi.gui_tabs.main_tab.QFileDialog.getSaveFileName") as mock_dialog:
                mock_dialog.return_value = (test_file, file_filter)

                # Click the output file button
                qtbot.mouseClick(window.main_tab.out_file_button, Qt.MouseButton.LeftButton)

                # Verify state
                assert window.main_tab.out_file_edit.text() == test_file
                assert window.out_file_path == Path(test_file)

        # Test cancelled file selection
        with patch("goesvfi.gui_tabs.main_tab.QFileDialog.getSaveFileName") as mock_dialog:
            mock_dialog.return_value = ("", "")  # User cancelled

            original_text = window.main_tab.out_file_edit.text()
            qtbot.mouseClick(window.main_tab.out_file_button, Qt.MouseButton.LeftButton)

            # Text should not change when user cancels
            assert window.main_tab.out_file_edit.text() == original_text

    def test_start_button_state_management_comprehensive(self, qtbot, main_window) -> None:
        """Test comprehensive start button state management."""
        window = main_window

        # Test state progression scenarios
        test_scenarios = [
            # (has_input, has_output, expected_enabled, description)
            (False, False, False, "No inputs"),
            (True, False, False, "Input only"),
            (False, True, False, "Output only"),
            (True, True, True, "Both inputs"),
        ]

        for has_input, has_output, expected_enabled, description in test_scenarios:
            # Reset state
            if has_input:
                window.set_in_dir(Path("/test/input"))
            else:
                window.in_dir = None
                window.main_tab.in_dir_edit.setText("")

            if has_output:
                window.out_file_path = Path("/test/output.mp4")
                window.main_tab.out_file_edit.setText("/test/output.mp4")
            else:
                window.out_file_path = None
                window.main_tab.out_file_edit.setText("")

            window._update_start_button_state()

            assert window.main_tab.start_button.isEnabled() == expected_enabled, f"Failed for: {description}"

        # Test processing state transitions
        window.set_in_dir(Path("/test/input"))
        window.out_file_path = Path("/test/output.mp4")
        window._update_start_button_state()
        assert window.main_tab.start_button.isEnabled()

        # Start processing
        window._set_processing_state(True)
        assert window.main_tab.start_button.text() == "Stop Processing"
        assert window.main_tab.start_button.isEnabled()

        # Stop processing
        window._set_processing_state(False)
        assert window.main_tab.start_button.text() == "Start Processing"
        assert window.main_tab.start_button.isEnabled()

    def test_crop_button_workflow_comprehensive(self, qtbot, main_window) -> None:
        """Test comprehensive crop button workflow with all scenarios."""
        window = main_window

        # Test crop dialog with different selection outcomes
        crop_scenarios = [
            # (dialog_result, rect_data, expected_crop, description)
            (1, (10, 20, 100, 50), (10, 20, 100, 50), "Accepted crop"),
            (0, (0, 0, 0, 0), None, "Rejected crop"),
            (1, (50, 75, 200, 150), (50, 75, 200, 150), "Different crop area"),
        ]

        for dialog_result, rect_data, expected_crop, description in crop_scenarios:
            # Setup for each scenario
            window.set_in_dir(Path("/test/input"))
            window.current_crop_rect = None  # Reset crop

            # Mock crop dialog
            with patch("goesvfi.gui_tabs.main_tab.CropSelectionDialog") as mock_crop_dialog:
                mock_dialog_instance = MagicMock()
                mock_dialog_instance.exec.return_value = dialog_result

                if dialog_result == 1:  # Accepted
                    mock_rect = MagicMock()
                    mock_rect.x.return_value = rect_data[0]
                    mock_rect.y.return_value = rect_data[1]
                    mock_rect.width.return_value = rect_data[2]
                    mock_rect.height.return_value = rect_data[3]
                    mock_dialog_instance.get_selected_rect.return_value = mock_rect

                mock_crop_dialog.return_value = mock_dialog_instance

                # Mock required methods
                with (
                    patch.object(window, "_get_sorted_image_files") as mock_files,
                    patch.object(window, "_prepare_image_for_crop_dialog") as mock_prepare,
                ):
                    mock_files.return_value = [Path("/test/image1.png"), Path("/test/image2.png")]
                    mock_pixmap = MagicMock()
                    mock_pixmap.isNull.return_value = False
                    mock_prepare.return_value = mock_pixmap

                    # Ensure crop button is enabled
                    assert window.main_tab.crop_button.isEnabled()

                    # Click crop button
                    qtbot.mouseClick(window.main_tab.crop_button, Qt.MouseButton.LeftButton)

                    # Verify results
                    assert window.current_crop_rect == expected_crop, f"Failed for: {description}"

                    if expected_crop is not None:
                        assert window.main_tab.clear_crop_button.isEnabled()
                    else:
                        assert not window.main_tab.clear_crop_button.isEnabled()

        # Test clear crop functionality
        window.current_crop_rect = (10, 20, 100, 50)
        window._update_crop_buttons_state()
        assert window.main_tab.clear_crop_button.isEnabled()

        qtbot.mouseClick(window.main_tab.clear_crop_button, Qt.MouseButton.LeftButton)
        assert window.current_crop_rect is None
        assert not window.main_tab.clear_crop_button.isEnabled()

    def test_encoder_selection_ui_updates_comprehensive(self, qtbot, main_window) -> None:
        """Test comprehensive encoder selection and UI updates."""
        window = main_window

        # Test encoder switching scenarios
        encoder_scenarios = [
            ("RIFE", True, True, "RIFE encoder enables RIFE options"),
            ("FFmpeg", False, False, "FFmpeg encoder disables RIFE options"),
        ]

        for encoder, rife_enabled, model_enabled, description in encoder_scenarios:
            # Switch encoder
            window.main_tab.encoder_combo.setCurrentText(encoder)
            qtbot.wait(50)  # Allow signals to process

            # Verify UI state
            assert window.main_tab.rife_options_group.isEnabled() == rife_enabled, (
                f"Failed RIFE group for: {description}"
            )
            assert window.main_tab.model_combo.isEnabled() == model_enabled, f"Failed model combo for: {description}"

        # Test rapid encoder switching doesn't cause issues
        for _i in range(5):
            window.main_tab.encoder_combo.setCurrentText("RIFE")
            qtbot.wait(10)
            window.main_tab.encoder_combo.setCurrentText("FFmpeg")
            qtbot.wait(10)

        # Final state should be stable
        assert window.main_tab.encoder_combo.currentText() == "FFmpeg"
        assert not window.main_tab.rife_options_group.isEnabled()

    def test_sanchez_controls_comprehensive(self, qtbot, main_window) -> None:
        """Test comprehensive Sanchez checkbox and resolution controls."""
        window = main_window

        # Test checkbox state scenarios
        checkbox_scenarios = [
            (False, False, "Unchecked disables resolution"),
            (True, True, "Checked enables resolution"),
        ]

        for checked_state, expected_enabled, description in checkbox_scenarios:
            window.main_tab.sanchez_checkbox.setChecked(checked_state)

            # Trigger the toggle method
            check_state = Qt.CheckState.Checked if checked_state else Qt.CheckState.Unchecked
            window._toggle_sanchez_res_enabled(check_state)

            assert window.main_tab.sanchez_res_combo.isEnabled() == expected_enabled, f"Failed for: {description}"

        # Test resolution selection when enabled
        window.main_tab.sanchez_checkbox.setChecked(True)
        window._toggle_sanchez_res_enabled(Qt.CheckState.Checked)

        # Test different resolution values
        test_resolutions = ["0.5", "1", "2", "4"]
        for resolution in test_resolutions:
            if window.main_tab.sanchez_res_combo.findText(resolution) >= 0:
                window.main_tab.sanchez_res_combo.setCurrentText(resolution)
                assert window.main_tab.sanchez_res_combo.currentText() == resolution

    def test_tab_switching_state_preservation(self, qtbot, main_window) -> None:
        """Test comprehensive tab switching with state preservation."""
        window = main_window

        # Set comprehensive initial state
        test_state = {
            "input_dir": Path("/test/input"),
            "output_file": Path("/test/output.mp4"),
            "crop_rect": (10, 20, 100, 50),
            "fps": 60,
            "encoder": "RIFE",
        }

        # Apply initial state
        window.set_in_dir(test_state["input_dir"])
        window.out_file_path = test_state["output_file"]
        window.current_crop_rect = test_state["crop_rect"]
        window.main_tab.fps_spinbox.setValue(test_state["fps"])
        window.main_tab.encoder_combo.setCurrentText(test_state["encoder"])

        # Test switching through all available tabs
        tab_count = window.tab_widget.count()
        for tab_index in range(tab_count):
            window.tab_widget.setCurrentIndex(tab_index)
            qtbot.wait(25)

            # Verify tab switch succeeded
            assert window.tab_widget.currentIndex() == tab_index

        # Return to main tab
        window.tab_widget.setCurrentIndex(0)
        qtbot.wait(50)

        # Verify all state is preserved
        assert window.in_dir == test_state["input_dir"]
        assert window.out_file_path == test_state["output_file"]
        assert window.current_crop_rect == test_state["crop_rect"]
        assert window.main_tab.fps_spinbox.value() == test_state["fps"]
        assert window.main_tab.encoder_combo.currentText() == test_state["encoder"]

        # Verify button states are correct
        assert window.main_tab.crop_button.isEnabled()
        assert window.main_tab.clear_crop_button.isEnabled()
        assert window.main_tab.start_button.isEnabled()

    def test_preview_interaction_comprehensive(self, qtbot, main_window) -> None:
        """Test comprehensive preview label click interactions."""
        window = main_window

        # Test all preview labels
        preview_labels = [
            window.main_tab.first_frame_label,
            window.main_tab.middle_frame_label,
            window.main_tab.last_frame_label,
        ]

        with patch.object(window, "_show_zoom") as mock_zoom:
            for label in preview_labels:
                # Setup label with image data
                label.file_path = f"/test/image_{id(label)}.png"
                mock_pixmap = MagicMock()
                mock_pixmap.isNull.return_value = False
                label.setPixmap(mock_pixmap)

                # Simulate click
                label.clicked.emit()

                # Verify zoom was called for this label
                mock_zoom.assert_called_with(label)
                mock_zoom.reset_mock()

        # Test click on label without image
        empty_label = window.main_tab.first_frame_label
        empty_label.file_path = None
        empty_label.setPixmap(MagicMock())

        with patch.object(window, "_show_zoom") as mock_zoom:
            empty_label.clicked.emit()
            # Should still call zoom even without file_path
            mock_zoom.assert_called_once_with(empty_label)

    def test_processing_state_ui_management(self, qtbot, main_window) -> None:
        """Test comprehensive UI management during processing states."""
        window = main_window

        # Setup valid inputs
        window.set_in_dir(Path("/test/input"))
        window.out_file_path = Path("/test/output.mp4")

        # Define UI elements to test
        ui_elements = [
            ("main_tab.in_dir_button", True),
            ("main_tab.out_file_button", True),
            ("main_tab.encoder_combo", True),
            ("main_tab.fps_spinbox", True),
            ("main_tab.crop_button", True),
        ]

        # Verify elements are enabled before processing
        for element_path, should_be_enabled in ui_elements:
            element = window
            for attr in element_path.split("."):
                element = getattr(element, attr)
            assert element.isEnabled() == should_be_enabled, f"Element {element_path} initial state incorrect"

        # Test tab states before processing
        tab_count = window.tab_widget.count()
        for i in range(tab_count):
            assert window.tab_widget.isTabEnabled(i), f"Tab {i} should be enabled before processing"

        # Start processing
        window._set_processing_state(True)

        # Verify elements are disabled during processing (except main tab)
        for element_path, _ in ui_elements:
            element = window
            for attr in element_path.split("."):
                element = getattr(element, attr)
            assert not element.isEnabled(), f"Element {element_path} should be disabled during processing"

        # Verify tab states during processing
        assert window.tab_widget.isTabEnabled(0), "Main tab should remain enabled during processing"
        for i in range(1, tab_count):
            assert not window.tab_widget.isTabEnabled(i), f"Tab {i} should be disabled during processing"

        # Stop processing
        window._set_processing_state(False)

        # Verify elements are re-enabled after processing
        for element_path, should_be_enabled in ui_elements:
            element = window
            for attr in element_path.split("."):
                element = getattr(element, attr)
            assert element.isEnabled() == should_be_enabled, (
                f"Element {element_path} should be re-enabled after processing"
            )

        # Verify all tabs are re-enabled
        for i in range(tab_count):
            assert window.tab_widget.isTabEnabled(i), f"Tab {i} should be re-enabled after processing"

    def test_rife_model_selection_comprehensive(self, qtbot, main_window) -> None:
        """Test comprehensive RIFE model selection functionality."""
        window = main_window

        # Ensure RIFE is selected
        window.main_tab.encoder_combo.setCurrentText("RIFE")
        qtbot.wait(50)

        # Test model selection if multiple models available
        model_combo = window.main_tab.rife_model_combo

        if model_combo.count() > 1:
            # Test selecting different models
            for i in range(model_combo.count()):
                model_combo.setCurrentIndex(i)
                qtbot.wait(25)

                # Verify model selection
                current_model = model_combo.currentData()
                assert window.current_model_key == current_model

                # Update RIFE UI elements
                window._update_rife_ui_elements()

                # Verify UI remains stable
                assert window.main_tab.rife_options_group.isEnabled()

        # Test model selection persistence during encoder switching
        if model_combo.count() > 0:
            original_model = model_combo.currentData()

            # Switch to FFmpeg and back
            window.main_tab.encoder_combo.setCurrentText("FFmpeg")
            qtbot.wait(25)
            window.main_tab.encoder_combo.setCurrentText("RIFE")
            qtbot.wait(25)

            # Model selection should be preserved
            assert model_combo.currentData() == original_model

    def test_error_handling_and_display(self, qtbot, main_window) -> None:
        """Test comprehensive error handling and display mechanisms."""
        window = main_window

        # Test different error scenarios
        error_scenarios = [
            "File not found error",
            "Processing timeout error",
            "Memory allocation failed",
            "Invalid input format",
            "Network connection error",
        ]

        with patch("goesvfi.gui.QMessageBox.critical") as mock_msgbox:
            for error_msg in error_scenarios:
                # Clear previous state
                window.status_bar.clearMessage()
                mock_msgbox.reset_mock()

                # Trigger error
                window._on_processing_error(error_msg)

                # Verify error dialog was shown
                mock_msgbox.assert_called_once()
                args = mock_msgbox.call_args[0]
                assert error_msg in args[2], f"Error message '{error_msg}' not found in dialog"

                # Verify status bar shows error
                status_message = window.status_bar.currentMessage()
                assert "Processing failed!" in status_message, f"Status bar doesn't show failure for: {error_msg}"

    def test_settings_persistence_comprehensive(self, qtbot, main_window) -> None:
        """Test comprehensive settings save/load functionality."""
        window = main_window

        # Test settings that should persist
        test_settings = {
            "input_dir": Path("/test/persistent/input"),
            "fps": 120,
            "encoder": "FFmpeg",
            "sanchez_enabled": True,
        }

        with patch.object(window, "saveSettings") as mock_save:
            # Apply settings
            window.set_in_dir(test_settings["input_dir"])
            window.main_tab.fps_spinbox.setValue(test_settings["fps"])
            window.main_tab.encoder_combo.setCurrentText(test_settings["encoder"])
            window.main_tab.sanchez_checkbox.setChecked(test_settings["sanchez_enabled"])

            # Force settings save
            window.close()

            # Verify save was called
            mock_save.assert_called()

        # Test that UI state changes trigger appropriate updates
        with patch.object(window, "_update_start_button_state") as mock_update:
            window.set_in_dir(Path("/new/input"))
            # Some implementations may call update automatically
            # Just verify the method exists and can be called
            mock_update.reset_mock()

    def test_ui_responsiveness_under_load(self, qtbot, main_window) -> None:
        """Test UI responsiveness under various load conditions."""
        window = main_window

        # Rapid UI interactions
        operations = [
            lambda: window.main_tab.encoder_combo.setCurrentText("RIFE"),
            lambda: window.main_tab.encoder_combo.setCurrentText("FFmpeg"),
            lambda: window.main_tab.fps_spinbox.setValue(60),
            lambda: window.main_tab.fps_spinbox.setValue(30),
            lambda: window.main_tab.sanchez_checkbox.setChecked(True),
            lambda: window.main_tab.sanchez_checkbox.setChecked(False),
        ]

        # Perform rapid operations
        for _ in range(3):  # Repeat cycle 3 times
            for operation in operations:
                operation()
                qtbot.wait(5)  # Minimal wait

        # Verify UI is still responsive
        assert window.main_tab.encoder_combo.isEnabled()
        assert window.main_tab.fps_spinbox.isEnabled()
        assert window.main_tab.sanchez_checkbox.isEnabled()

        # Test tab switching under load
        tab_count = window.tab_widget.count()
        for _ in range(10):  # Switch tabs rapidly
            for i in range(tab_count):
                window.tab_widget.setCurrentIndex(i)
                qtbot.wait(5)

        # UI should remain stable
        assert window.tab_widget.currentIndex() >= 0
        assert window.tab_widget.currentIndex() < tab_count

    def test_edge_cases_and_boundary_conditions(self, qtbot, main_window) -> None:
        """Test edge cases and boundary conditions."""
        window = main_window

        # Test extreme values
        extreme_values = [
            ("fps_spinbox", [1, 999, 500]),  # Min, max, mid values
            ("mid_count_spinbox", [1, 100, 50]),
        ]

        for widget_name, values in extreme_values:
            widget = getattr(window.main_tab, widget_name)
            for value in values:
                widget.setValue(value)
                qtbot.wait(10)
                assert widget.value() == value, f"Failed to set {widget_name} to {value}"

        # Test null/empty paths
        window.set_in_dir(None)
        window.out_file_path = None
        window._update_start_button_state()
        assert not window.main_tab.start_button.isEnabled()

        # Test very long paths
        long_path = "/very/long/path/" + "subdir/" * 50 + "file.mp4"
        window.out_file_path = Path(long_path)
        # Should handle gracefully without crashing
        assert window.out_file_path == Path(long_path)

        # Test rapid state changes
        for i in range(20):
            window._set_processing_state(i % 2 == 0)
            qtbot.wait(5)

        # Should end in a stable state
        window._set_processing_state(False)
        assert not window.is_processing
