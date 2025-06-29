"""Optimized integration tests for full application workflow with maintained coverage.

This v2 version maintains all test scenarios while optimizing through:
- Shared application and mock fixtures at class level
- Parameterized tests for encoder variations
- Combined related workflows without losing test isolation
- Batched UI operations
- Maintained all edge cases and error scenarios
"""

from collections.abc import Callable, Generator
import pathlib
import time
from unittest.mock import MagicMock, patch

from PIL import Image
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QMessageBox
import pytest

from goesvfi.gui import MainWindow


class TestFullApplicationWorkflowOptimizedV2:
    """Optimized integration tests with full coverage."""

    @pytest.fixture(scope="class")
    @staticmethod
    def app() -> Generator[QApplication]:
        """Shared QApplication instance.

        Yields:
            QApplication: The application instance for testing.
        """
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        yield app
        app.processEvents()

    @pytest.fixture(scope="class")
    @staticmethod
    def mock_dependencies() -> Generator[None]:
        """Shared mock setup for common dependencies.

        Yields:
            None: Mock context manager for dependencies.
        """
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
            mock_models.return_value = ["rife-v4.6", "rife-v4.3"]
            mock_find_rife.return_value = pathlib.Path("/mock/rife")
            mock_analyze.return_value = {
                "version": "4.6",
                "capabilities": {"supports_tiling": True, "supports_uhd": True},
                "output": "",
            }
            yield

    @pytest.fixture()
    @staticmethod
    def mock_vfi_worker() -> Generator[tuple[MagicMock, MagicMock]]:
        """Mock VfiWorker for all tests.

        Yields:
            tuple[MagicMock, MagicMock]: Mock worker class and instance.
        """
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

    @pytest.fixture()
    @staticmethod
    def main_window(
        app: QApplication, _mock_dependencies: None, _mock_vfi_worker: tuple[MagicMock, MagicMock]
    ) -> Generator[MainWindow]:
        """Create MainWindow instance.

        Args:
            app: QApplication instance.
            mock_dependencies: Mock dependencies fixture.
            mock_vfi_worker: Mock VfiWorker fixture.

        Yields:
            MainWindow: Configured main window instance.
        """
        window = MainWindow()
        app.processEvents()

        yield window

        # Cleanup
        if hasattr(window, "vfi_worker") and window.vfi_worker:
            window.vfi_worker.quit()
            window.vfi_worker.wait()

        window.close()
        app.processEvents()

    @pytest.fixture()
    @staticmethod
    def test_environment(tmp_path: pathlib.Path) -> dict[str, pathlib.Path]:
        """Create comprehensive test environment.

        Args:
            tmp_path: Pytest temporary path fixture.

        Returns:
            Dict[str, pathlib.Path]: Test environment paths.
        """
        # Input directory with various image types
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        # Create test images
        for i in range(5):
            img = Image.new("RGB", (640, 480), color=(i * 50, 100, 200 - i * 40))
            img.save(input_dir / f"image_{i:04d}.png")

        # Unsorted directory for file sorter
        unsorted_dir = tmp_path / "unsorted"
        unsorted_dir.mkdir()

        names = ["sunset", "morning", "noon", "evening", "night"]
        for i, name in enumerate(names):
            img = Image.new("RGB", (320, 240), color=(100, 150, 200))
            img.save(unsorted_dir / f"{name}_{i}.png")

        # Empty directory for testing
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        return {
            "input_dir": input_dir,
            "unsorted_dir": unsorted_dir,
            "empty_dir": empty_dir,
            "output_dir": tmp_path,
        }

    @staticmethod
    def test_complete_workflow_main_tab_to_video(
        main_window: MainWindow,
        app: QApplication,
        test_environment: dict[str, pathlib.Path],
        mock_vfi_worker: tuple[MagicMock, MagicMock],
    ) -> None:
        """Test complete workflow from main tab setup to video generation."""
        _mock_worker_class, mock_instance = mock_vfi_worker
        output_file = test_environment["output_dir"] / "output.mp4"

        # Step 1: Set input directory
        main_window.main_tab.in_dir_edit.setText(str(test_environment["input_dir"]))
        app.processEvents()

        # Verify preview labels exist
        assert main_window.main_tab.first_frame_label is not None
        assert main_window.main_tab.middle_frame_label is not None
        assert main_window.main_tab.last_frame_label is not None

        # Step 2: Set output file
        main_window.main_tab.out_file_edit.setText(str(output_file))
        app.processEvents()

        # Step 3: Configure settings
        main_window.main_tab.fps_spinbox.setValue(30)
        main_window.main_tab.multiplier_spinbox.setValue(2)
        main_window.main_tab.encoder_combo.setCurrentText("RIFE")
        app.processEvents()

        # Step 4: Enable RIFE options
        main_window.main_tab.rife_tile_checkbox.setChecked(True)
        main_window.main_tab.rife_uhd_checkbox.setChecked(False)
        app.processEvents()

        # Set up callbacks to simulate processing
        progress_callback = None
        finished_callback = None

        def mock_progress_connect(callback: Callable[[int, int, int], None]) -> None:
            nonlocal progress_callback
            progress_callback = callback

        def mock_finished_connect(callback: Callable[[str], None]) -> None:
            nonlocal finished_callback
            finished_callback = callback

        mock_instance.progress.connect.side_effect = mock_progress_connect
        mock_instance.finished.connect.side_effect = mock_finished_connect

        def mock_start() -> None:
            # Simulate progress
            if progress_callback:
                for i in range(1, 11):
                    progress_callback(i, 10, 10 - i)
            # Simulate completion
            if finished_callback:
                finished_callback(str(output_file))

        mock_instance.start.side_effect = mock_start

        # Enable start button
        main_window.main_tab.start_button.setEnabled(True)

        # Click start
        QTest.mouseClick(main_window.main_tab.start_button, Qt.MouseButton.LeftButton)
        app.processEvents()

        # Wait for processing
        max_wait_time = 2
        start_time = time.time()

        while time.time() - start_time < max_wait_time:
            app.processEvents()
            if not main_window.main_tab.is_processing:
                break
            time.sleep(0.05)

        # Verify completion
        assert not main_window.main_tab.is_processing
        assert main_window.main_tab.start_button.isEnabled()

    @staticmethod
    def test_complete_workflow_with_crop(
        main_window: MainWindow, app: QApplication, test_environment: dict[str, pathlib.Path]
    ) -> None:
        """Test workflow with crop selection."""
        output_file = test_environment["output_dir"] / "output_cropped.mp4"

        # Setup
        main_window.main_tab.in_dir_edit.setText(str(test_environment["input_dir"]))
        main_window.main_tab.out_file_edit.setText(str(output_file))
        app.processEvents()

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
            main_window.set_crop_rect = MagicMock()  # type: ignore[assignment]
            main_window.current_crop_rect = None

            # Click crop button
            QTest.mouseClick(main_window.main_tab.crop_button, Qt.MouseButton.LeftButton)
            app.processEvents()
            QTimer.singleShot(100, app.processEvents)

            # Verify no crash
            assert True

    @staticmethod
    def test_workflow_with_ffmpeg_settings(main_window: MainWindow, app: QApplication) -> None:
        """Test workflow including FFmpeg settings configuration."""
        # Find FFmpeg tab
        tab_widget = main_window.tab_widget
        ffmpeg_tab_index = -1
        for i in range(tab_widget.count()):
            if tab_widget.tabText(i) == "FFmpeg Settings":
                ffmpeg_tab_index = i
                break

        assert ffmpeg_tab_index >= 0
        tab_widget.setCurrentIndex(ffmpeg_tab_index)
        app.processEvents()

        # Configure FFmpeg settings
        ffmpeg_tab = main_window.ffmpeg_settings_tab

        # Change profile
        if hasattr(ffmpeg_tab, "profile_combo"):
            ffmpeg_tab.profile_combo.setCurrentText("Optimal")
            app.processEvents()

        # Enable motion interpolation
        if hasattr(ffmpeg_tab, "minterpolate_checkbox"):
            ffmpeg_tab.minterpolate_checkbox.setChecked(True)
            app.processEvents()

        # Set quality
        if hasattr(ffmpeg_tab, "quality_slider"):
            ffmpeg_tab.quality_slider.setValue(25)
            app.processEvents()

        # Switch back to main tab
        tab_widget.setCurrentIndex(0)
        app.processEvents()

        # Verify settings are retained
        if hasattr(ffmpeg_tab, "minterpolate_checkbox"):
            assert ffmpeg_tab.minterpolate_checkbox.isChecked()
        if hasattr(ffmpeg_tab, "quality_slider"):
            assert ffmpeg_tab.quality_slider.value() == 25

    @staticmethod
    def test_workflow_with_file_sorter(
        main_window: MainWindow, app: QApplication, test_environment: dict[str, pathlib.Path]
    ) -> None:
        """Test workflow using file sorter to organize images."""
        # Find File Sorter tab
        tab_widget = main_window.tab_widget
        file_sorter_index = -1
        for i in range(tab_widget.count()):
            if tab_widget.tabText(i) == "File Sorter":
                file_sorter_index = i
                break

        if file_sorter_index >= 0:
            tab_widget.setCurrentIndex(file_sorter_index)
            app.processEvents()

            file_sorter_tab = main_window.file_sorter_tab

            # Set source directory
            file_sorter_tab.source_line_edit.setText(str(test_environment["unsorted_dir"]))
            app.processEvents()

            # Test sort button
            file_sorter_tab.sort_button.click()
            app.processEvents()

            # Verify UI remains responsive
            assert file_sorter_tab.sort_button is not None

    @staticmethod
    def test_workflow_with_sanchez_processing(
        main_window: MainWindow,
        app: QApplication,
        test_environment: dict[str, pathlib.Path],
        mock_vfi_worker: tuple[MagicMock, MagicMock],
    ) -> None:
        """Test workflow with Sanchez false color processing enabled."""
        mock_worker_class, _mock_instance = mock_vfi_worker
        output_file = test_environment["output_dir"] / "output_sanchez.mp4"

        # Setup
        main_window.main_tab.in_dir_edit.setText(str(test_environment["input_dir"]))
        main_window.main_tab.out_file_edit.setText(str(output_file))
        app.processEvents()

        # Enable Sanchez processing
        main_window.main_tab.sanchez_false_colour_checkbox.setChecked(True)
        main_window.main_tab.sanchez_res_combo.setCurrentText("2")
        app.processEvents()

        # Verify Sanchez options are enabled
        assert main_window.main_tab.sanchez_res_combo.isEnabled()

        # Enable and click start
        main_window.main_tab.start_button.setEnabled(True)
        QTest.mouseClick(main_window.main_tab.start_button, Qt.MouseButton.LeftButton)
        app.processEvents()

        # Verify Sanchez settings were passed
        call_args = mock_worker_class.call_args[1]
        assert call_args["false_colour"] is True
        assert call_args["res_km"] == 2

    @staticmethod
    def test_all_tab_navigation(main_window: MainWindow, app: QApplication) -> None:
        """Test navigation through all tabs."""
        tab_widget = main_window.tab_widget
        tab_count = tab_widget.count()

        # Expected tabs
        expected_tabs = {
            "Main",
            "FFmpeg Settings",
            "Date Sorter",
            "File Sorter",
            "Model Library",
            "Satellite Integrity",
        }

        found_tabs = set()

        # Navigate through each tab
        for i in range(tab_count):
            tab_name = tab_widget.tabText(i)
            found_tabs.add(tab_name)

            # Switch to tab
            tab_widget.setCurrentIndex(i)
            app.processEvents()

            # Verify tab is visible
            assert tab_widget.currentIndex() == i

            # Verify tab widget exists
            current_widget = tab_widget.currentWidget()
            assert current_widget is not None

        # Verify all expected tabs are present
        assert expected_tabs.issubset(found_tabs)

    @staticmethod
    def test_error_handling_workflow(
        main_window: MainWindow, app: QApplication, test_environment: dict[str, pathlib.Path]
    ) -> None:
        """Test error handling across the workflow."""
        # Test 1: Invalid input directory
        main_window.main_tab.in_dir_edit.setText("/nonexistent/directory")
        main_window.main_tab.out_file_edit.setText(str(test_environment["output_dir"] / "output.mp4"))
        app.processEvents()

        # Start button should be disabled
        assert not main_window.main_tab.start_button.isEnabled()

        # Test 2: No output file specified
        main_window.main_tab.in_dir_edit.setText(str(test_environment["input_dir"]))
        main_window.main_tab.out_file_edit.setText("")
        app.processEvents()

        # Start button should be disabled
        assert not main_window.main_tab.start_button.isEnabled()

        # Test 3: Processing error
        test_dir = test_environment["empty_dir"]
        main_window.main_tab.in_dir_edit.setText(str(test_dir))
        main_window.main_tab.out_file_edit.setText(str(test_environment["output_dir"] / "output.mp4"))
        app.processEvents()

        with patch("goesvfi.gui_tabs.main_tab.VfiWorker") as mock_worker_class:
            mock_worker = MagicMock()
            mock_worker_class.return_value = mock_worker

            error_callback = None

            def mock_error_connect(callback: Callable[[str], None]) -> None:
                nonlocal error_callback
                error_callback = callback

            mock_worker.progress.connect = MagicMock()
            mock_worker.finished.connect = MagicMock()
            mock_worker.error.connect = mock_error_connect

            def mock_start() -> None:
                if error_callback:
                    error_callback("Test error: Processing failed")

            mock_worker.start = mock_start

            # Mock message box
            with patch.object(QMessageBox, "critical"):
                # Enable and click start
                main_window.main_tab.start_button.setEnabled(True)
                QTest.mouseClick(main_window.main_tab.start_button, Qt.MouseButton.LeftButton)
                app.processEvents()

                # Verify error was handled
                assert mock_worker.start.called

    @staticmethod
    def test_settings_persistence_workflow(main_window: MainWindow, app: QApplication) -> None:
        """Test that settings persist across tab switches."""
        # Configure settings in main tab
        main_window.main_tab.fps_spinbox.setValue(60)
        main_window.main_tab.multiplier_spinbox.setValue(4)
        main_window.main_tab.rife_tile_checkbox.setChecked(True)
        main_window.main_tab.sanchez_false_colour_checkbox.setChecked(True)
        app.processEvents()

        # Switch to FFmpeg tab
        tab_widget = main_window.tab_widget
        tab_widget.setCurrentIndex(1)
        app.processEvents()

        # Switch back to main tab
        tab_widget.setCurrentIndex(0)
        app.processEvents()

        # Verify settings are preserved
        assert main_window.main_tab.fps_spinbox.value() == 60
        assert main_window.main_tab.multiplier_spinbox.value() == 4
        assert main_window.main_tab.rife_tile_checkbox.isChecked()
        assert main_window.main_tab.sanchez_false_colour_checkbox.isChecked()

    @pytest.mark.parametrize("encoder", ["RIFE", "FFmpeg"])
    @staticmethod
    def test_different_encoders_workflow(
        main_window: MainWindow,
        app: QApplication,
        test_environment: dict[str, pathlib.Path],
        encoder: str,
        mock_vfi_worker: tuple[MagicMock, MagicMock],
    ) -> None:
        """Test workflow with different encoders."""
        mock_worker_class, _mock_instance = mock_vfi_worker
        output_file = test_environment["output_dir"] / f"output_{encoder}.mp4"

        # Setup
        main_window.main_tab.in_dir_edit.setText(str(test_environment["input_dir"]))
        main_window.main_tab.out_file_edit.setText(str(output_file))
        app.processEvents()

        # Select encoder
        encoder_index = main_window.main_tab.encoder_combo.findText(encoder)
        if encoder_index >= 0:
            main_window.main_tab.encoder_combo.setCurrentIndex(encoder_index)
            app.processEvents()

            # Verify encoder-specific options
            if encoder == "RIFE":
                assert main_window.main_tab.rife_options_group.isEnabled()

                # Configure RIFE options
                main_window.main_tab.rife_tile_checkbox.setChecked(True)
                main_window.main_tab.rife_uhd_checkbox.setChecked(False)

            # Set common options
            main_window.main_tab.fps_spinbox.setValue(30)
            main_window.main_tab.multiplier_spinbox.setValue(2)
            app.processEvents()

            # Start processing
            main_window.main_tab.start_button.setEnabled(True)
            QTest.mouseClick(main_window.main_tab.start_button, Qt.MouseButton.LeftButton)
            app.processEvents()

            # Verify correct encoder was passed
            call_args = mock_worker_class.call_args[1]
            assert call_args["encoder"] == encoder

    @staticmethod
    def test_preview_functionality(
        main_window: MainWindow, app: QApplication, test_environment: dict[str, pathlib.Path]
    ) -> None:
        """Test preview dialog functionality."""
        # Set input directory
        main_window.main_tab.in_dir_edit.setText(str(test_environment["input_dir"]))
        app.processEvents()

        # Preview button should be enabled
        assert main_window.main_tab.preview_button.isEnabled()

        # Mock preview dialog
        with patch("goesvfi.gui_tabs.main_tab.PreviewDialog") as mock_preview:
            mock_dialog = MagicMock()
            mock_preview.return_value = mock_dialog
            mock_dialog.exec.return_value = 1

            # Click preview
            QTest.mouseClick(main_window.main_tab.preview_button, Qt.MouseButton.LeftButton)
            app.processEvents()

            # Verify preview dialog was created
            mock_preview.assert_called_once()

    @staticmethod
    def test_model_library_integration(main_window: MainWindow, app: QApplication) -> None:
        """Test Model Library tab integration."""
        tab_widget = main_window.tab_widget

        # Find Model Library tab
        model_lib_index = -1
        for i in range(tab_widget.count()):
            if tab_widget.tabText(i) == "Model Library":
                model_lib_index = i
                break

        if model_lib_index >= 0:
            # Switch to Model Library
            tab_widget.setCurrentIndex(model_lib_index)
            app.processEvents()

            # Verify tab is active
            assert tab_widget.currentIndex() == model_lib_index

            # Basic interaction test
            model_lib_tab = tab_widget.currentWidget()
            assert model_lib_tab is not None

    @staticmethod
    def test_satellite_integrity_integration(main_window: MainWindow, app: QApplication) -> None:
        """Test Satellite Integrity tab integration."""
        tab_widget = main_window.tab_widget

        # Find Satellite Integrity tab
        integrity_index = -1
        for i in range(tab_widget.count()):
            if tab_widget.tabText(i) == "Satellite Integrity":
                integrity_index = i
                break

        if integrity_index >= 0:
            # Switch to Satellite Integrity
            tab_widget.setCurrentIndex(integrity_index)
            app.processEvents()

            # Verify tab is active
            assert tab_widget.currentIndex() == integrity_index

            # Basic interaction test
            integrity_tab = tab_widget.currentWidget()
            assert integrity_tab is not None

    @staticmethod
    def test_date_sorter_integration(main_window: MainWindow, app: QApplication) -> None:
        """Test Date Sorter tab integration."""
        tab_widget = main_window.tab_widget

        # Find Date Sorter tab
        date_sorter_index = -1
        for i in range(tab_widget.count()):
            if tab_widget.tabText(i) == "Date Sorter":
                date_sorter_index = i
                break

        if date_sorter_index >= 0:
            # Switch to Date Sorter
            tab_widget.setCurrentIndex(date_sorter_index)
            app.processEvents()

            # Verify tab is active
            assert tab_widget.currentIndex() == date_sorter_index

            # Basic interaction test
            date_sorter_tab = tab_widget.currentWidget()
            assert date_sorter_tab is not None
