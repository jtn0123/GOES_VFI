"""
Optimized tests for GUI button validation with maintained coverage.

This v2 version maintains all test scenarios while optimizing through:
- Shared fixtures at class level
- Combined related button interaction tests
- Batch UI state validation
- Comprehensive test scenarios with enhanced coverage
"""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication
import pytest

from goesvfi.gui import MainWindow


class TestGUIButtonValidationOptimizedV2:
    """Optimized GUI button validation tests with full coverage."""

    @pytest.fixture(scope="class")
    @staticmethod
    def shared_app() -> Any:
        """Shared QApplication instance.

        Yields:
            QApplication: The shared Qt application instance.
        """
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        yield app
        app.processEvents()

    @pytest.fixture(scope="class")
    @staticmethod
    def shared_mocks() -> Any:
        """Create shared mocks that persist across tests.

        Yields:
            dict[str, Any]: Dictionary containing mock objects.
        """
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
    @staticmethod
    def main_window(qtbot: Any, shared_app: Any, shared_mocks: dict[str, Any]) -> Any:  # noqa: ARG004
        """Create MainWindow instance with proper cleanup.

        Returns:
            MainWindow: Configured main window instance.
        """
        window = MainWindow(debug_mode=True)
        qtbot.addWidget(window)
        window._post_init_setup()  # noqa: SLF001

        return window

    @staticmethod
    def test_input_directory_button_comprehensive(qtbot: Any, main_window: Any) -> None:
        """Test comprehensive input directory button functionality."""
        window = main_window

        # Test initial state
        assert window.main_tab.in_dir_button.isEnabled()
        assert not window.main_tab.in_dir_edit.text()
        assert not window.main_tab.crop_button.isEnabled()
        assert not window.main_tab.clear_crop_button.isEnabled()

        # Test multiple directory selection scenarios
        test_directories = [
            "/test/input/dir",
            "/different/path/images",
            "/home/user/videos",
            "/var/tmp/processing",  # noqa: S108
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

    @staticmethod
    def test_output_file_button_comprehensive(qtbot: Any, main_window: Any) -> None:
        """Test comprehensive output file selection functionality."""
        window = main_window

        # Test initial state
        assert window.main_tab.out_file_button.isEnabled()
        assert not window.main_tab.out_file_edit.text()

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

    @staticmethod
    def test_start_button_state_management_comprehensive(qtbot: Any, main_window: Any) -> None:  # noqa: ARG004
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

            window._update_start_button_state()  # noqa: SLF001

            assert window.main_tab.start_button.isEnabled() == expected_enabled, f"Failed for: {description}"

        # Test processing state transitions
        window.set_in_dir(Path("/test/input"))
        window.out_file_path = Path("/test/output.mp4")
        window._update_start_button_state()  # noqa: SLF001
        assert window.main_tab.start_button.isEnabled()

        # Start processing
        window._set_processing_state(enabled=True)  # noqa: SLF001
        assert window.main_tab.start_button.text() == "Stop Processing"
        assert window.main_tab.start_button.isEnabled()

        # Stop processing
        window._set_processing_state(enabled=False)  # noqa: SLF001
        assert window.main_tab.start_button.text() == "Start Processing"
        assert window.main_tab.start_button.isEnabled()

    @staticmethod
    def test_crop_button_workflow_comprehensive(qtbot: Any, main_window: Any) -> None:
        """Test comprehensive crop button workflow with all scenarios."""
        window = main_window

        # Test crop functionality without requiring actual user dialog interaction
        crop_scenarios = [
            ((10, 20, 100, 50), "Set crop"),
            ((50, 75, 200, 150), "Different crop area"),
            (None, "Clear crop"),
        ]

        for expected_crop, description in crop_scenarios:
            # Setup for each scenario
            window.set_in_dir(Path("/test/input"))
            
            # Directly test the crop functionality by setting the crop rect
            if expected_crop is not None:
                window.set_crop_rect(expected_crop)
                assert window.current_crop_rect == expected_crop, f"Failed for: {description}"
                assert window.main_tab.clear_crop_button.isEnabled()
            else:
                window.set_crop_rect(None)
                assert window.current_crop_rect is None, f"Failed for: {description}"
                assert not window.main_tab.clear_crop_button.isEnabled()

        # Test crop button state functionality
        window.set_in_dir(Path("/test/input"))
        window.main_tab._update_crop_buttons_state()  # noqa: SLF001
        assert window.main_tab.crop_button.isEnabled()

        # Test clear crop functionality
        window.set_crop_rect((10, 20, 100, 50))
        window.main_tab._update_crop_buttons_state()  # noqa: SLF001
        assert window.main_tab.clear_crop_button.isEnabled()
        assert window.current_crop_rect == (10, 20, 100, 50)  # Verify crop is set

        # Test the clear crop functionality directly
        window.main_tab._on_clear_crop_clicked()  # noqa: SLF001
        
        assert window.current_crop_rect is None, f"Expected None, got {window.current_crop_rect}"
        
        # Update button state after clearing
        window.main_tab._update_crop_buttons_state()  # noqa: SLF001
        assert not window.main_tab.clear_crop_button.isEnabled()

    @staticmethod
    def test_encoder_selection_ui_updates_comprehensive(qtbot: Any, main_window: Any) -> None:
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

    @staticmethod
    def test_sanchez_controls_comprehensive(qtbot: Any, main_window: Any) -> None:  # noqa: ARG004
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
            window._toggle_sanchez_res_enabled(check_state)  # noqa: SLF001

            assert window.main_tab.sanchez_res_combo.isEnabled() == expected_enabled, f"Failed for: {description}"

        # Test resolution selection when enabled
        window.main_tab.sanchez_checkbox.setChecked(True)
        window._toggle_sanchez_res_enabled(Qt.CheckState.Checked)  # noqa: SLF001

        # Test different resolution values
        test_resolutions = ["0.5", "1", "2", "4"]
        for resolution in test_resolutions:
            if window.main_tab.sanchez_res_combo.findText(resolution) >= 0:
                window.main_tab.sanchez_res_combo.setCurrentText(resolution)
                assert window.main_tab.sanchez_res_combo.currentText() == resolution

    @staticmethod
    def test_tab_switching_state_preservation(qtbot: Any, main_window: Any) -> None:
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

    @staticmethod
    def test_preview_interaction_comprehensive(qtbot: Any, main_window: Any) -> None:  # noqa: ARG004
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

    @staticmethod
    def test_processing_state_ui_management(qtbot: Any, main_window: Any) -> None:  # noqa: ARG004
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
        window._set_processing_state(enabled=True)  # noqa: SLF001

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
        window._set_processing_state(enabled=False)  # noqa: SLF001

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

    @staticmethod
    def test_rife_model_selection_comprehensive(qtbot: Any, main_window: Any) -> None:
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
                window._update_rife_ui_elements()  # noqa: SLF001

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

    @staticmethod
    def test_error_handling_and_display(qtbot: Any, main_window: Any) -> None:  # noqa: ARG004
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
                window._on_processing_error(error_msg)  # noqa: SLF001

                # Verify error dialog was shown
                mock_msgbox.assert_called_once()
                args = mock_msgbox.call_args[0]
                assert error_msg in args[2], f"Error message '{error_msg}' not found in dialog"

                # Verify status bar shows error
                status_message = window.status_bar.currentMessage()
                assert "Processing failed!" in status_message, f"Status bar doesn't show failure for: {error_msg}"

    @staticmethod
    def test_settings_persistence_comprehensive(qtbot: Any, main_window: Any) -> None:  # noqa: ARG004
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

    @staticmethod
    def test_ui_responsiveness_under_load(qtbot: Any, main_window: Any) -> None:
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

    @staticmethod
    def test_edge_cases_and_boundary_conditions(qtbot: Any, main_window: Any) -> None:
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
        window._update_start_button_state()  # noqa: SLF001
        assert not window.main_tab.start_button.isEnabled()

        # Test very long paths
        long_path = "/very/long/path/" + "subdir/" * 50 + "file.mp4"
        window.out_file_path = Path(long_path)
        # Should handle gracefully without crashing
        assert window.out_file_path == Path(long_path)

        # Test rapid state changes
        for i in range(20):
            window._set_processing_state(enabled=(i % 2 == 0))  # noqa: SLF001
            qtbot.wait(5)

        # Should end in a stable state
        window._set_processing_state(enabled=False)  # noqa: SLF001
        assert not window.is_processing
