"""Headless integration tests that don't show any GUI windows.

These tests run without displaying any windows or dialogs.
"""

import os
import pathlib
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image
from PyQt6.QtWidgets import QApplication

# Set environment for headless operation
os.environ["QT_QPA_PLATFORM"] = "offscreen"


class TestHeadlessWorkflow:
    """Test workflows without any GUI display."""

    @pytest.fixture(autouse=True)
    def _setup_headless(self):
        """Set up headless environment."""
        # Store original env
        original_platform = os.environ.get("QT_QPA_PLATFORM")
        os.environ["QT_QPA_PLATFORM"] = "offscreen"

        yield

        # Restore
        if original_platform:
            os.environ["QT_QPA_PLATFORM"] = original_platform
        elif "QT_QPA_PLATFORM" in os.environ:
            del os.environ["QT_QPA_PLATFORM"]

    @pytest.fixture
    def app(self):
        """Create headless QApplication."""
        app = QApplication.instance()
        if app is None:
            app = QApplication(["-platform", "offscreen"])
        yield app
        app.processEvents()

    @pytest.fixture
    def mock_gui_window(self, app):
        """Create fully mocked main window."""
        with patch("goesvfi.gui.MainWindow") as MockMainWindow:
            # Create mock window
            window = MagicMock()
            MockMainWindow.return_value = window

            # Mock main_tab
            main_tab = MagicMock()
            window.main_tab = main_tab

            # Mock input/output widgets
            main_tab.in_dir_edit = MagicMock()
            main_tab.in_dir_edit.text.return_value = ""
            main_tab.out_file_edit = MagicMock()
            main_tab.out_file_edit.text.return_value = ""

            # Mock buttons
            main_tab.start_button = MagicMock()
            main_tab.start_button.setEnabled = MagicMock()
            main_tab.start_button.click = MagicMock()

            # Mock other widgets
            main_tab.fps_spinbox = MagicMock()
            main_tab.fps_spinbox.value.return_value = 30
            main_tab.mid_count_spinbox = MagicMock()
            main_tab.mid_count_spinbox.value.return_value = 1
            main_tab.encoder_combo = MagicMock()
            main_tab.encoder_combo.currentText.return_value = "libx264"

            # Mock checkboxes
            main_tab.rife_tile_checkbox = MagicMock()
            main_tab.rife_tile_checkbox.isChecked.return_value = False
            main_tab.rife_uhd_checkbox = MagicMock()
            main_tab.rife_uhd_checkbox.isChecked.return_value = False
            main_tab.sanchez_false_colour_checkbox = MagicMock()
            main_tab.sanchez_false_colour_checkbox.isChecked.return_value = False

            yield window

    def test_basic_workflow_no_display(self, mock_gui_window, tmp_path):
        """Test basic workflow without any display."""
        # Create test images
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        for i in range(3):
            img = Image.new("RGB", (100, 100), color=(100, 150, 200))
            img.save(input_dir / f"img_{i:03d}.png")

        output_file = tmp_path / "output.mp4"

        # Set paths
        mock_gui_window.main_tab.in_dir_edit.setText(str(input_dir))
        mock_gui_window.main_tab.out_file_edit.setText(str(output_file))

        # Verify setText was called
        mock_gui_window.main_tab.in_dir_edit.setText.assert_called_with(str(input_dir))
        mock_gui_window.main_tab.out_file_edit.setText.assert_called_with(str(output_file))

        # Simulate start button click
        mock_gui_window.main_tab.start_button.click()

        # Verify click was called
        mock_gui_window.main_tab.start_button.click.assert_called_once()

    def test_settings_configuration_no_display(self, mock_gui_window):
        """Test settings configuration without display."""
        # Configure settings
        mock_gui_window.main_tab.fps_spinbox.setValue(60)
        mock_gui_window.main_tab.mid_count_spinbox.setValue(2)
        mock_gui_window.main_tab.rife_tile_checkbox.setChecked(True)

        # Verify methods were called
        mock_gui_window.main_tab.fps_spinbox.setValue.assert_called_with(60)
        mock_gui_window.main_tab.mid_count_spinbox.setValue.assert_called_with(2)
        mock_gui_window.main_tab.rife_tile_checkbox.setChecked.assert_called_with(True)

    @patch("goesvfi.pipeline.run_vfi.run_vfi")
    def test_vfi_processing_mocked(self, mock_run_vfi, tmp_path):
        """Test VFI processing with fully mocked pipeline."""
        # Setup
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        output_file = tmp_path / "output.mp4"

        # Create test images
        for i in range(2):
            img = Image.new("RGB", (100, 100))
            img.save(input_dir / f"img_{i}.png")

        # Mock successful processing
        mock_run_vfi.return_value = str(output_file)

        # Import and test
        from goesvfi.pipeline.run_vfi import run_vfi

        result = run_vfi(
            folder=input_dir,
            output_mp4_path=output_file,
            rife_exe_path=pathlib.Path("/mock/rife"),
            fps=30,
            num_intermediate_frames=1,
            max_workers=1,
            encoder="libx264",
        )

        # Verify
        assert mock_run_vfi.called
        assert result == str(output_file)

        # Check call arguments
        call_kwargs = mock_run_vfi.call_args.kwargs
        assert call_kwargs["in_dir"] == str(input_dir)
        assert call_kwargs["out_file_path"] == str(output_file)
        assert call_kwargs["fps"] == 30

    @patch("goesvfi.gui.VfiWorker")
    def test_worker_thread_mocked(self, MockVfiWorker):
        """Test VFI worker thread with mocking."""
        # Create mock worker
        mock_worker = MagicMock()
        MockVfiWorker.return_value = mock_worker

        # Mock signals
        mock_worker.progress = MagicMock()
        mock_worker.finished = MagicMock()
        mock_worker.error = MagicMock()

        # Mock start method
        mock_worker.start = MagicMock()

        # Import and create worker
        from goesvfi.gui import VfiWorker

        worker = VfiWorker(
            in_dir="/tmp/input",
            out_file_path="/tmp/output.mp4",
            fps=30,
            mid_count=1,
            max_workers=1,
            encoder="libx264",
        )

        # Start worker
        worker.start()

        # Verify
        MockVfiWorker.assert_called_once()
        mock_worker.start.assert_called_once()


if __name__ == "__main__":
    # Run with pytest in headless mode
    pytest.main([__file__, "-v", "--tb=short"])
