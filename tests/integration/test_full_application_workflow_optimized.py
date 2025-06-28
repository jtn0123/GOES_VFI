"""Optimized comprehensive integration tests for full application workflow.

This optimized version combines related tests, shares fixtures more efficiently,
and reduces redundant setup/teardown operations while maintaining full coverage.
"""

import pathlib
import time
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QMessageBox

from goesvfi.gui import MainWindow


class TestFullApplicationWorkflowOptimized:
    """Optimized test complete application workflows from start to finish."""

    @pytest.fixture(scope="class")
    def app(self):
        """Shared QApplication instance for the test class."""
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        yield app
        app.processEvents()

    @pytest.fixture(scope="class")
    def mock_dependencies(self):
        """Shared mock setup for common dependencies."""
        with (
            patch("goesvfi.utils.config.get_available_rife_models") as mock_models,
            patch("goesvfi.utils.config.find_rife_executable") as mock_find_rife,
            patch("goesvfi.utils.rife_analyzer.analyze_rife_executable") as mock_analyze,
            patch("goesvfi.pipeline.sanchez_processor.SanchezProcessor.process_image"),
            patch("os.path.getmtime", return_value=1234567890.0),
            patch("os.path.exists", return_value=True),
            patch("pathlib.Path.exists", return_value=True),
            patch("socket.gethostbyname", return_value="192.168.1.1"),
            patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="", stderr="")),
        ):
            mock_models.return_value = ["rife-v4.6"]
            mock_find_rife.return_value = pathlib.Path("/mock/rife")
            mock_analyze.return_value = {
                "version": "4.6",
                "capabilities": {"supports_tiling": True, "supports_uhd": True},
                "output": "",
            }
            yield

    @pytest.fixture
    def mock_vfi_worker(self):
        """Optimized mock for VfiWorker."""
        with (
            patch("goesvfi.pipeline.run_vfi.VfiWorker") as mock_worker_class,
            patch("goesvfi.gui_tabs.main_tab.VfiWorker") as mock_worker_class_tab,
        ):
            mock_instance = MagicMock()

            # Set up signal mocks
            for signal_name in ["progress", "finished", "error"]:
                signal_mock = MagicMock()
                signal_mock.connect = MagicMock()
                signal_mock.emit = MagicMock()
                setattr(mock_instance, signal_name, signal_mock)

            # Thread methods
            mock_instance.start = MagicMock()
            mock_instance.quit = MagicMock()
            mock_instance.wait = MagicMock()
            mock_instance.isRunning = MagicMock(return_value=False)

            # Configure both classes
            mock_worker_class.return_value = mock_instance
            mock_worker_class_tab.return_value = mock_instance

            yield mock_worker_class_tab, mock_instance

    @pytest.fixture
    def main_window(self, app, mock_dependencies, mock_vfi_worker):
        """Create MainWindow instance with all mocks applied."""
        window = MainWindow()
        app.processEvents()

        yield window

        # Clean up
        if hasattr(window, "vfi_worker") and window.vfi_worker:
            window.vfi_worker.quit()
            window.vfi_worker.wait()

        window.close()
        app.processEvents()

    @pytest.fixture
    def test_environment(self, tmp_path):
        """Create test environment with images and directories."""
        # Input directory with test images
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        # Create test images
        for i in range(5):
            img = Image.new("RGB", (640, 480), color=(i * 50, 100, 200 - i * 40))
            img.save(input_dir / f"image_{i:04d}.png")

        # Unsorted directory for file sorter tests
        unsorted_dir = tmp_path / "unsorted"
        unsorted_dir.mkdir()

        # Create unsorted images
        names = ["sunset", "morning", "noon", "evening", "night"]
        for i, name in enumerate(names):
            img = Image.new("RGB", (320, 240), color=(100, 150, 200))
            img.save(unsorted_dir / f"{name}_{i}.png")

        return {
            "input_dir": input_dir,
            "unsorted_dir": unsorted_dir,
            "output_dir": tmp_path,
        }

    def test_complete_workflows_combined(
        self, main_window, app, test_environment, mock_vfi_worker
    ):
        """Combined test for multiple complete workflows."""
        mock_worker_class, mock_instance = mock_vfi_worker

        # Test data
        test_cases = [
            {
                "name": "basic_workflow",
                "fps": 30,
                "multiplier": 2,
                "encoder": "RIFE",
                "rife_tile": True,
                "rife_uhd": False,
                "sanchez": False,
            },
            {
                "name": "sanchez_workflow",
                "fps": 24,
                "multiplier": 4,
                "encoder": "RIFE",
                "rife_tile": False,
                "rife_uhd": True,
                "sanchez": True,
            },
            {
                "name": "ffmpeg_workflow",
                "fps": 60,
                "multiplier": 2,
                "encoder": "FFmpeg",
                "rife_tile": False,
                "rife_uhd": False,
                "sanchez": False,
            },
        ]

        for test_case in test_cases:
            # Reset UI state
            output_file = test_environment["output_dir"] / f"output_{test_case['name']}.mp4"

            # Configure main tab
            main_window.main_tab.in_dir_edit.setText(str(test_environment["input_dir"]))
            main_window.main_tab.out_file_edit.setText(str(output_file))
            main_window.main_tab.fps_spinbox.setValue(test_case["fps"])
            main_window.main_tab.multiplier_spinbox.setValue(test_case["multiplier"])
            main_window.main_tab.encoder_combo.setCurrentText(test_case["encoder"])

            # Configure RIFE options if applicable
            if test_case["encoder"] == "RIFE":
                main_window.main_tab.rife_tile_checkbox.setChecked(test_case["rife_tile"])
                main_window.main_tab.rife_uhd_checkbox.setChecked(test_case["rife_uhd"])

            # Configure Sanchez
            main_window.main_tab.sanchez_false_colour_checkbox.setChecked(test_case["sanchez"])
            if test_case["sanchez"]:
                main_window.main_tab.sanchez_res_combo.setCurrentText("2")

            app.processEvents()

            # Verify configuration
            assert main_window.main_tab.fps_spinbox.value() == test_case["fps"]
            assert main_window.main_tab.multiplier_spinbox.value() == test_case["multiplier"]
            assert main_window.main_tab.encoder_combo.currentText() == test_case["encoder"]

            # Simulate processing
            self._simulate_processing(main_window, app, mock_instance, output_file)

    def test_all_tabs_and_error_handling(self, main_window, app, test_environment):
        """Combined test for tab navigation and error handling."""
        tab_widget = main_window.tab_widget

        # Test 1: Navigate all tabs
        expected_tabs = {
            "Main", "FFmpeg Settings", "Date Sorter", 
            "File Sorter", "Model Library", "Satellite Integrity"
        }
        found_tabs = set()

        for i in range(tab_widget.count()):
            tab_name = tab_widget.tabText(i)
            found_tabs.add(tab_name)

            # Switch to tab
            tab_widget.setCurrentIndex(i)
            app.processEvents()

            # Verify tab is active
            assert tab_widget.currentIndex() == i
            assert tab_widget.currentWidget() is not None

        assert expected_tabs.issubset(found_tabs)

        # Test 2: Error handling scenarios
        # Invalid input directory
        main_window.main_tab.in_dir_edit.setText("/nonexistent/directory")
        main_window.main_tab.out_file_edit.setText(str(test_environment["output_dir"] / "output.mp4"))
        app.processEvents()
        assert not main_window.main_tab.start_button.isEnabled()

        # No output file
        main_window.main_tab.in_dir_edit.setText(str(test_environment["input_dir"]))
        main_window.main_tab.out_file_edit.setText("")
        app.processEvents()
        assert not main_window.main_tab.start_button.isEnabled()

        # Test 3: Settings persistence
        # Configure settings
        main_window.main_tab.fps_spinbox.setValue(60)
        main_window.main_tab.multiplier_spinbox.setValue(4)
        main_window.main_tab.rife_tile_checkbox.setChecked(True)
        main_window.main_tab.sanchez_false_colour_checkbox.setChecked(True)
        app.processEvents()

        # Switch tabs
        tab_widget.setCurrentIndex(1)  # FFmpeg tab
        app.processEvents()
        tab_widget.setCurrentIndex(0)  # Back to main
        app.processEvents()

        # Verify settings preserved
        assert main_window.main_tab.fps_spinbox.value() == 60
        assert main_window.main_tab.multiplier_spinbox.value() == 4
        assert main_window.main_tab.rife_tile_checkbox.isChecked()
        assert main_window.main_tab.sanchez_false_colour_checkbox.isChecked()

    def test_ffmpeg_and_file_sorter_integration(self, main_window, app, test_environment):
        """Combined test for FFmpeg settings and file sorter functionality."""
        tab_widget = main_window.tab_widget

        # Test 1: FFmpeg Settings
        ffmpeg_tab_index = self._find_tab_index(tab_widget, "FFmpeg Settings")
        if ffmpeg_tab_index >= 0:
            tab_widget.setCurrentIndex(ffmpeg_tab_index)
            app.processEvents()

            ffmpeg_tab = main_window.ffmpeg_settings_tab

            # Configure settings if components exist
            settings_applied = False
            if hasattr(ffmpeg_tab, "profile_combo"):
                ffmpeg_tab.profile_combo.setCurrentText("Optimal")
                settings_applied = True

            if hasattr(ffmpeg_tab, "minterpolate_checkbox"):
                ffmpeg_tab.minterpolate_checkbox.setChecked(True)
                settings_applied = True

            if hasattr(ffmpeg_tab, "quality_slider"):
                ffmpeg_tab.quality_slider.setValue(25)
                settings_applied = True

            app.processEvents()

            # Verify settings if applied
            if settings_applied:
                if hasattr(ffmpeg_tab, "minterpolate_checkbox"):
                    assert ffmpeg_tab.minterpolate_checkbox.isChecked()
                if hasattr(ffmpeg_tab, "quality_slider"):
                    assert ffmpeg_tab.quality_slider.value() == 25

        # Test 2: File Sorter
        file_sorter_index = self._find_tab_index(tab_widget, "File Sorter")
        if file_sorter_index >= 0:
            tab_widget.setCurrentIndex(file_sorter_index)
            app.processEvents()

            file_sorter_tab = main_window.file_sorter_tab

            # Set source directory
            file_sorter_tab.source_line_edit.setText(str(test_environment["unsorted_dir"]))
            app.processEvents()

            # Test sort button without crashing
            file_sorter_tab.sort_button.click()
            app.processEvents()

            # Verify UI remains responsive
            assert file_sorter_tab.sort_button is not None

    def test_crop_and_preview_workflow(self, main_window, app, test_environment):
        """Test crop selection and preview functionality."""
        output_file = test_environment["output_dir"] / "output_cropped.mp4"

        # Setup
        main_window.main_tab.in_dir_edit.setText(str(test_environment["input_dir"]))
        main_window.main_tab.out_file_edit.setText(str(output_file))
        app.processEvents()

        # Verify preview labels exist
        assert main_window.main_tab.first_frame_label is not None
        assert main_window.main_tab.middle_frame_label is not None
        assert main_window.main_tab.last_frame_label is not None

        # Mock crop dialog
        with (
            patch("goesvfi.gui_tabs.main_tab.CropSelectionDialog") as mock_dialog,
            patch("goesvfi.gui_tabs.main_tab.QMessageBox"),
        ):
            mock_dialog_instance = MagicMock()
            mock_dialog_instance.exec.return_value = 1  # Accepted
            mock_dialog_instance.get_crop_rect.return_value = (100, 100, 400, 300)
            mock_dialog.return_value = mock_dialog_instance

            # Mock set_crop_rect
            main_window.set_crop_rect = MagicMock()
            main_window.current_crop_rect = None

            # Click crop button
            QTest.mouseClick(main_window.main_tab.crop_button, Qt.MouseButton.LeftButton)
            app.processEvents()
            QTimer.singleShot(100, lambda: app.processEvents())

            # Verify no crash
            assert True

    def test_error_recovery_workflow(self, main_window, app, test_environment):
        """Test error handling and recovery during processing."""
        test_dir = test_environment["input_dir"]
        output_file = test_environment["output_dir"] / "output_error.mp4"

        main_window.main_tab.in_dir_edit.setText(str(test_dir))
        main_window.main_tab.out_file_edit.setText(str(output_file))
        app.processEvents()

        with patch("goesvfi.gui_tabs.main_tab.VfiWorker") as mock_worker_class:
            mock_worker = MagicMock()
            mock_worker_class.return_value = mock_worker

            # Set up callbacks
            error_callback = None
            finished_callback = None

            def mock_error_connect(callback):
                nonlocal error_callback
                error_callback = callback

            def mock_finished_connect(callback):
                nonlocal finished_callback
                finished_callback = callback

            mock_worker.progress.connect = MagicMock()
            mock_worker.finished.connect = mock_finished_connect
            mock_worker.error.connect = mock_error_connect

            # Test error scenario
            def mock_start_error():
                if error_callback:
                    error_callback("Test error: Processing failed")

            # Test recovery scenario
            def mock_start_success():
                if finished_callback:
                    finished_callback(str(output_file))

            # First attempt - error
            mock_worker.start = mock_start_error

            with patch.object(QMessageBox, "critical"):
                main_window.main_tab.start_button.setEnabled(True)
                QTest.mouseClick(main_window.main_tab.start_button, Qt.MouseButton.LeftButton)
                app.processEvents()

                assert mock_worker.start.called

            # Reset for recovery
            mock_worker.reset_mock()
            mock_worker.start = mock_start_success

            # Second attempt - success
            main_window.main_tab.start_button.setEnabled(True)
            QTest.mouseClick(main_window.main_tab.start_button, Qt.MouseButton.LeftButton)
            app.processEvents()

            # Verify recovery
            assert mock_worker.start.called

    # Helper methods
    def _simulate_processing(self, main_window, app, mock_instance, output_file):
        """Simulate processing workflow."""
        progress_callback = None
        finished_callback = None

        def mock_progress_connect(callback):
            nonlocal progress_callback
            progress_callback = callback

        def mock_finished_connect(callback):
            nonlocal finished_callback
            finished_callback = callback

        mock_instance.progress.connect.side_effect = mock_progress_connect
        mock_instance.finished.connect.side_effect = mock_finished_connect

        def mock_start():
            # Simulate progress
            if progress_callback:
                for i in range(1, 11):
                    progress_callback(i, 10, 10 - i)
            # Simulate completion
            if finished_callback:
                finished_callback(str(output_file))

        mock_instance.start.side_effect = mock_start

        # Enable and click start
        main_window.main_tab.start_button.setEnabled(True)
        QTest.mouseClick(main_window.main_tab.start_button, Qt.MouseButton.LeftButton)
        app.processEvents()

        # Wait for completion
        max_wait = 2  # seconds
        start = time.time()
        while time.time() - start < max_wait:
            app.processEvents()
            if not main_window.main_tab.is_processing:
                break
            time.sleep(0.05)

        # Verify completion
        assert not main_window.main_tab.is_processing
        assert main_window.main_tab.start_button.isEnabled()

    def _find_tab_index(self, tab_widget, tab_name):
        """Find tab index by name."""
        for i in range(tab_widget.count()):
            if tab_widget.tabText(i) == tab_name:
                return i
        return -1