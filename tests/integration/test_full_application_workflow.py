"""Comprehensive integration tests for full application workflow.

Tests the complete user journey from application start to video generation,
covering all tabs and major functionality.
"""

import pathlib
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QMessageBox

from goesvfi.gui import MainWindow


class TestFullApplicationWorkflow:
    """Test complete application workflows from start to finish."""

    @pytest.fixture
    def app(self):
        """Use existing QApplication instance."""
        # The conftest.py already sets up headless environment
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        yield app
        app.processEvents()

    @pytest.fixture
    def mock_vfi_worker(self):
        """Comprehensive mock for VfiWorker to prevent real processing."""
        with patch("goesvfi.pipeline.run_vfi.VfiWorker") as mock_worker_class:
            mock_instance = MagicMock()

            # Mock signals with proper Signal behavior
            mock_instance.progress = MagicMock()
            mock_instance.progress.connect = MagicMock()
            mock_instance.progress.emit = MagicMock()

            mock_instance.finished = MagicMock()
            mock_instance.finished.connect = MagicMock()
            mock_instance.finished.emit = MagicMock()

            mock_instance.error = MagicMock()
            mock_instance.error.connect = MagicMock()
            mock_instance.error.emit = MagicMock()

            # Mock thread methods to prevent actual execution
            mock_instance.start = MagicMock()
            mock_instance.quit = MagicMock()
            mock_instance.wait = MagicMock()
            mock_instance.isRunning = MagicMock(return_value=False)

            # Configure the class to return our instance
            mock_worker_class.return_value = mock_instance

            yield mock_worker_class, mock_instance

    @pytest.fixture
    def main_window(self, app, tmp_path, mock_vfi_worker):
        """Create MainWindow instance for testing."""
        # mock_vfi_worker is automatically applied
        with (
            patch("goesvfi.gui.config.get_available_rife_models") as mock_models,
            patch("goesvfi.gui.config.find_rife_executable") as mock_find_rife,
            patch(
                "goesvfi.utils.rife_analyzer.analyze_rife_executable"
            ) as mock_analyze,
            patch(
                "goesvfi.pipeline.sanchez_processor.SanchezProcessor.process_image"
            ) as mock_sanchez,
            patch("os.path.getmtime") as mock_getmtime,
            patch("os.path.exists") as mock_exists,
            patch("socket.gethostbyname") as mock_gethostbyname,
        ):

            mock_models.return_value = ["rife-v4.6"]
            mock_find_rife.return_value = pathlib.Path("/mock/rife")
            mock_analyze.return_value = {
                "version": "4.6",
                "capabilities": {"supports_tiling": True, "supports_uhd": True},
                "output": "",
            }
            mock_getmtime.return_value = 1234567890.0  # Mock timestamp
            mock_exists.return_value = True
            mock_gethostbyname.return_value = "192.168.1.1"  # Mock DNS resolution

            # Create window without showing it
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
    def test_images(self, tmp_path):
        """Create test images for processing."""
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        # Create test images
        for i in range(5):
            img = Image.new("RGB", (640, 480), color=(i * 50, 100, 200 - i * 40))
            img.save(input_dir / f"image_{i:04d}.png")

        return input_dir

    def test_complete_workflow_main_tab_to_video(
        self, main_window, app, test_images, tmp_path, mock_vfi_worker
    ):
        """Test complete workflow from main tab setup to video generation."""
        mock_worker_class, mock_instance = mock_vfi_worker
        output_file = tmp_path / "output.mp4"

        # Step 1: Set input directory
        main_window.main_tab.in_dir_edit.setText(str(test_images))
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

        # Enable start button (force it for testing)
        main_window.main_tab.start_button.setEnabled(True)

        # Click start
        QTest.mouseClick(main_window.main_tab.start_button, Qt.MouseButton.LeftButton)
        app.processEvents()

        # Verify worker was created and started
        mock_worker_class.assert_called_once()
        mock_instance.start.assert_called_once()

        # Verify settings were passed correctly
        # VfiWorker is called with keyword arguments
        call_kwargs = mock_worker_class.call_args[1]  # kwargs are in args[1]
        assert call_kwargs["fps"] == 30  # We set it to 30
        assert call_kwargs["mid_count"] == 1  # multiplier(2) - 1 = 1
        assert call_kwargs["encoder"] == "RIFE"  # We set it to RIFE
        assert "in_dir" in call_kwargs
        assert "out_file_path" in call_kwargs

    def test_complete_workflow_with_crop(self, main_window, app, test_images, tmp_path):
        """Test workflow with crop selection."""
        output_file = tmp_path / "output_cropped.mp4"

        # Setup input/output
        main_window.main_tab.in_dir_edit.setText(str(test_images))
        main_window.main_tab.out_file_edit.setText(str(output_file))
        app.processEvents()

        # Mock crop dialog
        with patch("goesvfi.gui_tabs.main_tab.CropSelectionDialog") as mock_dialog:
            mock_dialog_instance = MagicMock()
            mock_dialog_instance.exec.return_value = 1  # Accepted
            mock_dialog_instance.get_crop_rect.return_value = (100, 100, 400, 300)
            mock_dialog.return_value = mock_dialog_instance

            # Mock getting preview pixmap
            from PyQt6.QtGui import QPixmap

            mock_pixmap = QPixmap(640, 480)
            with patch.object(main_window, "current_preview_pixmap", mock_pixmap):

                # Click crop button
                QTest.mouseClick(
                    main_window.main_tab.crop_button, Qt.MouseButton.LeftButton
                )
                app.processEvents()
                QTimer.singleShot(
                    100, lambda: app.processEvents()
                )  # Wait for SuperButton

                # Verify crop was set
                assert main_window.current_crop_rect == (100, 100, 400, 300)
                assert "100, 100" in main_window.main_tab.crop_label.text()

    def test_workflow_with_ffmpeg_settings(
        self, main_window, app, test_images, tmp_path
    ):
        """Test workflow including FFmpeg settings configuration."""
        # Switch to FFmpeg tab
        tab_widget = main_window.centralWidget()
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

        # Change profile if it exists
        if hasattr(ffmpeg_tab, "profile_combo"):
            ffmpeg_tab.profile_combo.setCurrentText("Optimal")
            app.processEvents()

        # Enable motion interpolation if checkbox exists
        if hasattr(ffmpeg_tab, "minterpolate_checkbox"):
            ffmpeg_tab.minterpolate_checkbox.setChecked(True)
            app.processEvents()

        # Set quality if slider exists
        if hasattr(ffmpeg_tab, "quality_slider"):
            ffmpeg_tab.quality_slider.setValue(25)
            app.processEvents()

        # Switch back to main tab
        tab_widget.setCurrentIndex(0)
        app.processEvents()

        # Verify settings are retained if they exist
        if hasattr(ffmpeg_tab, "minterpolate_checkbox"):
            assert ffmpeg_tab.minterpolate_checkbox.isChecked()
        if hasattr(ffmpeg_tab, "quality_slider"):
            assert ffmpeg_tab.quality_slider.value() == 25

    def test_workflow_with_file_sorter(self, main_window, app, tmp_path):
        """Test workflow using file sorter to organize images."""
        # Create unsorted images
        unsorted_dir = tmp_path / "unsorted"
        unsorted_dir.mkdir()

        # Create images with non-sequential names
        for i in range(5):
            img = Image.new("RGB", (320, 240), color=(100, 150, 200))
            # Random names
            names = ["sunset", "morning", "noon", "evening", "night"]
            img.save(unsorted_dir / f"{names[i]}_{i}.png")

        # Switch to File Sorter tab
        tab_widget = main_window.centralWidget()
        file_sorter_index = -1
        for i in range(tab_widget.count()):
            if tab_widget.tabText(i) == "File Sorter":
                file_sorter_index = i
                break

        if file_sorter_index >= 0:
            tab_widget.setCurrentIndex(file_sorter_index)
            app.processEvents()

            file_sorter_tab = main_window.file_sorter_tab

            # Set directories
            file_sorter_tab.in_dir_edit.setText(str(unsorted_dir))
            sorted_dir = tmp_path / "sorted"
            file_sorter_tab.out_dir_edit.setText(str(sorted_dir))
            app.processEvents()

            # Mock the sorting operation
            with patch.object(file_sorter_tab, "_run_sorter") as mock_sort:
                # Click sort button
                file_sorter_tab.sort_button.click()
                app.processEvents()

                # Verify sorter was called
                assert mock_sort.called

    def test_workflow_with_sanchez_processing(
        self, main_window, app, test_images, tmp_path
    ):
        """Test workflow with Sanchez false color processing enabled."""
        output_file = tmp_path / "output_sanchez.mp4"

        # Setup
        main_window.main_tab.in_dir_edit.setText(str(test_images))
        main_window.main_tab.out_file_edit.setText(str(output_file))
        app.processEvents()

        # Enable Sanchez processing
        main_window.main_tab.sanchez_false_colour_checkbox.setChecked(True)
        main_window.main_tab.sanchez_res_combo.setCurrentText("2")
        app.processEvents()

        # Verify Sanchez options are enabled
        assert main_window.main_tab.sanchez_res_combo.isEnabled()

        # Mock processing with Sanchez
        with patch("goesvfi.gui_tabs.main_tab.VfiWorker") as mock_worker_class:
            mock_worker = MagicMock()
            mock_worker_class.return_value = mock_worker

            mock_worker.progress.connect = MagicMock()
            mock_worker.finished.connect = MagicMock()
            mock_worker.error.connect = MagicMock()
            mock_worker.start = MagicMock()

            # Enable and click start
            main_window.main_tab.start_button.setEnabled(True)
            QTest.mouseClick(
                main_window.main_tab.start_button, Qt.MouseButton.LeftButton
            )
            app.processEvents()

            # Verify Sanchez settings were passed
            call_args = mock_worker_class.call_args[1]
            assert call_args["false_colour"] is True
            assert call_args["res_km"] == 2

    def test_all_tab_navigation(self, main_window, app):
        """Test navigation through all tabs."""
        tab_widget = main_window.centralWidget()
        tab_count = tab_widget.count()

        # Expected tabs (order may vary)
        expected_tabs = {
            "Main",
            "FFmpeg Settings",
            "Date Sorter",
            "File Sorter",
            "Batch Processing",
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

    def test_error_handling_workflow(self, main_window, app, tmp_path):
        """Test error handling across the workflow."""
        # Test 1: Invalid input directory
        main_window.main_tab.in_dir_edit.setText("/nonexistent/directory")
        main_window.main_tab.out_file_edit.setText(str(tmp_path / "output.mp4"))
        app.processEvents()

        # Start button should be disabled
        assert not main_window.main_tab.start_button.isEnabled()

        # Test 2: No output file specified
        main_window.main_tab.in_dir_edit.setText(str(tmp_path))
        main_window.main_tab.out_file_edit.setText("")
        app.processEvents()

        # Start button should be disabled
        assert not main_window.main_tab.start_button.isEnabled()

        # Test 3: Processing error
        test_dir = tmp_path / "test_input"
        test_dir.mkdir()

        main_window.main_tab.in_dir_edit.setText(str(test_dir))
        main_window.main_tab.out_file_edit.setText(str(tmp_path / "output.mp4"))
        app.processEvents()

        with patch("goesvfi.gui_tabs.main_tab.VfiWorker") as mock_worker_class:
            mock_worker = MagicMock()
            mock_worker_class.return_value = mock_worker

            error_callback = None

            def mock_error_connect(callback):
                nonlocal error_callback
                error_callback = callback

            mock_worker.progress.connect = MagicMock()
            mock_worker.finished.connect = MagicMock()
            mock_worker.error.connect = mock_error_connect

            def mock_start():
                if error_callback:
                    error_callback("Test error: Processing failed")

            mock_worker.start = mock_start

            # Mock message box to prevent actual dialog
            with patch.object(QMessageBox, "critical") as mock_msgbox:
                # Enable and click start
                main_window.main_tab.start_button.setEnabled(True)
                QTest.mouseClick(
                    main_window.main_tab.start_button, Qt.MouseButton.LeftButton
                )
                app.processEvents()

                # Verify error was handled
                assert mock_worker.start.called

    def test_settings_persistence_workflow(self, main_window, app, tmp_path):
        """Test that settings persist across tab switches."""
        # Configure settings in main tab
        main_window.main_tab.fps_spinbox.setValue(60)
        main_window.main_tab.multiplier_spinbox.setValue(4)
        main_window.main_tab.rife_tile_checkbox.setChecked(True)
        main_window.main_tab.sanchez_false_colour_checkbox.setChecked(True)
        app.processEvents()

        # Switch to FFmpeg tab
        tab_widget = main_window.centralWidget()
        tab_widget.setCurrentIndex(1)  # Assuming FFmpeg is second
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
    def test_different_encoders_workflow(
        self, main_window, app, test_images, tmp_path, encoder
    ):
        """Test workflow with different encoders."""
        output_file = tmp_path / f"output_{encoder}.mp4"

        # Setup
        main_window.main_tab.in_dir_edit.setText(str(test_images))
        main_window.main_tab.out_file_edit.setText(str(output_file))
        app.processEvents()

        # Select encoder
        encoder_index = main_window.main_tab.encoder_combo.findText(encoder)
        if encoder_index >= 0:
            main_window.main_tab.encoder_combo.setCurrentIndex(encoder_index)
            app.processEvents()

            # Verify encoder-specific options are shown/hidden appropriately
            if encoder == "RIFE":
                assert main_window.main_tab.rife_options_group.isEnabled()
            elif encoder == "FFmpeg":
                # FFmpeg specific behavior
                pass
