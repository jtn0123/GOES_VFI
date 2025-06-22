"""Tests for utility functions in the MainTab class."""

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, Mock, patch

import pytest
from PyQt6.QtCore import QRect, QSettings
from PyQt6.QtWidgets import QApplication, QLineEdit, QMessageBox

from goesvfi.gui_tabs.main_tab import MainTab


@pytest.fixture
def app():
    """Create a QApplication for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app
    app.quit()


@pytest.fixture
def main_tab(app):
    """Create a MainTab instance for testing."""
    # Create mock dependencies
    mock_main_view_model = Mock()
    mock_main_view_model.processing_vm = Mock()

    mock_image_loader = Mock()
    mock_sanchez_processor = Mock()
    mock_image_cropper = Mock()
    mock_settings = Mock(spec=QSettings)
    mock_settings.sync = Mock()
    mock_preview_signal = Mock()

    # Create a mock main window with necessary attributes
    mock_main_window = Mock()
    mock_main_window.in_dir = None
    mock_main_window.current_crop_rect = None

    # Create MainTab instance with all required arguments
    tab = MainTab(
        main_view_model=mock_main_view_model,
        image_loader=mock_image_loader,
        sanchez_processor=mock_sanchez_processor,
        image_cropper=mock_image_cropper,
        settings=mock_settings,
        request_previews_update_signal=mock_preview_signal,
        main_window_ref=mock_main_window,
        parent=None,
    )

    # Set up minimal UI elements needed for tests
    tab.rife_thread_spec_edit = QLineEdit()
    tab.out_file_path = None

    yield tab


class TestValidateThreadSpec:
    """Tests for the _validate_thread_spec utility function."""

    def test_empty_thread_spec_allowed(self, main_tab):
        """Test that empty thread spec is allowed."""
        main_tab._validate_thread_spec("")
        assert main_tab.rife_thread_spec_edit.styleSheet() == ""

    def test_valid_thread_spec_single_digits(self, main_tab):
        """Test valid thread spec with single digits."""
        main_tab._validate_thread_spec("1:2:3")
        assert main_tab.rife_thread_spec_edit.styleSheet() == ""

    def test_valid_thread_spec_multiple_digits(self, main_tab):
        """Test valid thread spec with multiple digits."""
        main_tab._validate_thread_spec("10:20:30")
        assert main_tab.rife_thread_spec_edit.styleSheet() == ""

    def test_invalid_thread_spec_missing_colons(self, main_tab):
        """Test invalid thread spec with missing colons."""
        main_tab._validate_thread_spec("1:2")
        assert "background-color: #401010;" in main_tab.rife_thread_spec_edit.styleSheet()

    def test_invalid_thread_spec_extra_colons(self, main_tab):
        """Test invalid thread spec with extra colons."""
        main_tab._validate_thread_spec("1:2:3:4")
        assert "background-color: #401010;" in main_tab.rife_thread_spec_edit.styleSheet()

    def test_invalid_thread_spec_non_digits(self, main_tab):
        """Test invalid thread spec with non-digit characters."""
        main_tab._validate_thread_spec("a:b:c")
        assert "background-color: #401010;" in main_tab.rife_thread_spec_edit.styleSheet()

    def test_invalid_thread_spec_mixed_content(self, main_tab):
        """Test invalid thread spec with mixed valid/invalid content."""
        main_tab._validate_thread_spec("1:2a:3")
        assert "background-color: #401010;" in main_tab.rife_thread_spec_edit.styleSheet()


class TestGenerateTimestampedOutputPath:
    """Tests for the _generate_timestamped_output_path utility function."""

    @patch("datetime.datetime")
    def test_generate_with_base_params(self, mock_datetime, main_tab):
        """Test generating path with provided base directory and name."""
        mock_datetime.now.return_value.strftime.return_value = "20231225_120000"

        base_dir = Path("/test/output")
        base_name = "test_video"

        result = main_tab._generate_timestamped_output_path(base_dir, base_name)

        assert result == Path("/test/output/test_video_output_20231225_120000.mp4")
        mock_datetime.now.return_value.strftime.assert_called_once_with("%Y%m%d_%H%M%S")

    @patch("datetime.datetime")
    def test_generate_from_input_dir(self, mock_datetime, main_tab):
        """Test generating path using input directory as base."""
        mock_datetime.now.return_value.strftime.return_value = "20231225_120000"

        # Set up main window with input directory
        mock_path = MagicMock(spec=Path)
        mock_path.is_dir.return_value = True
        mock_path.parent = Path("/test/input")
        mock_path.name = "my_images"
        main_tab.main_window_ref.in_dir = mock_path

        result = main_tab._generate_timestamped_output_path()

        assert result == Path("/test/input/my_images_output_20231225_120000.mp4")

    @patch("datetime.datetime")
    @patch("os.getcwd")
    def test_generate_fallback_to_cwd(self, mock_getcwd, mock_datetime, main_tab):
        """Test fallback to current working directory when no input dir."""
        mock_datetime.now.return_value.strftime.return_value = "20231225_120000"
        mock_getcwd.return_value = "/current/working/dir"

        # No input directory set
        main_tab.main_window_ref.in_dir = None

        result = main_tab._generate_timestamped_output_path()

        assert result == Path("/current/working/dir/output_output_20231225_120000.mp4")

    def test_timestamp_format(self, main_tab):
        """Test that timestamp format is correct."""
        # Create a real timestamp to verify format
        base_dir = Path("/test")
        base_name = "test"

        result = main_tab._generate_timestamped_output_path(base_dir, base_name)

        # Extract timestamp from filename
        filename = result.name
        timestamp_match = re.search(r"(\d{8}_\d{6})\.mp4$", filename)
        assert timestamp_match is not None

        # Verify timestamp format
        timestamp = timestamp_match.group(1)
        assert len(timestamp) == 15  # YYYYMMDD_HHMMSS
        assert timestamp[8] == "_"


class TestCheckInputDirectoryContents:
    """Tests for the _check_input_directory_contents utility function."""

    @patch("PIL.Image")
    def test_check_empty_directory(self, mock_image_class, main_tab, tmp_path):
        """Test checking an empty directory."""
        with patch("goesvfi.gui_tabs.main_tab.LOGGER") as mock_logger:
            main_tab._check_input_directory_contents(tmp_path)

            # Should log warning about no images
            mock_logger.warning.assert_called_once_with("No image files found in input directory")

    @patch("goesvfi.gui_tabs.main_tab.np")
    @patch("PIL.Image")
    def test_check_directory_with_images(self, mock_image_class, mock_np, main_tab, tmp_path):
        """Test checking directory with valid image files."""
        # Create test image files
        image_files = []
        for i in range(5):
            img_file = tmp_path / f"image_{i}.png"
            img_file.touch()
            image_files.append(img_file)

        # Mock PIL Image
        mock_img = Mock()
        mock_img.size = (1920, 1080)
        mock_image_class.open.return_value = mock_img

        # Mock numpy array
        mock_array = Mock()
        mock_array.shape = (1080, 1920, 3)
        mock_array.dtype = "uint8"
        mock_np.array.return_value = mock_array

        with patch("goesvfi.gui_tabs.main_tab.LOGGER") as mock_logger:
            main_tab._check_input_directory_contents(tmp_path)

            # Should have logged debug info
            mock_logger.debug.assert_any_call(f"Found 5 image files in {tmp_path}")

            # Should have opened sample images (first, middle, last)
            assert mock_image_class.open.call_count == 3

    @patch("PIL.Image")
    def test_check_directory_with_mixed_files(self, mock_image_class, main_tab, tmp_path):
        """Test checking directory with mixed file types."""
        # Create various file types
        (tmp_path / "image1.png").touch()
        (tmp_path / "image2.jpg").touch()
        (tmp_path / "document.txt").touch()
        (tmp_path / "data.csv").touch()
        (tmp_path / "image3.JPEG").touch()  # Test case insensitive

        # Mock PIL Image
        mock_img = Mock()
        mock_img.size = (1920, 1080)
        mock_image_class.open.return_value = mock_img

        # Mock numpy
        with patch("goesvfi.gui_tabs.main_tab.np.array") as mock_array:
            mock_array.return_value.shape = (1080, 1920, 3)
            mock_array.return_value.dtype = "uint8"

            with patch("goesvfi.gui_tabs.main_tab.LOGGER") as mock_logger:
                main_tab._check_input_directory_contents(tmp_path)

                # Should only count image files
                mock_logger.debug.assert_any_call(f"Found 3 image files in {tmp_path}")

    @patch("PIL.Image")
    def test_check_directory_with_corrupt_image(self, mock_image_class, main_tab, tmp_path):
        """Test handling of corrupt/unreadable images."""
        # Create test image files
        for i in range(3):
            (tmp_path / f"image_{i}.png").touch()

        # Mock Image.open to fail on middle image
        def side_effect(path):
            if "image_1" in str(path):
                raise Exception("Corrupt image")
            mock_img = Mock()
            mock_img.size = (1920, 1080)
            return mock_img

        mock_image_class.open.side_effect = side_effect

        with patch("goesvfi.gui_tabs.main_tab.np.array") as mock_array:
            mock_array.return_value.shape = (1080, 1920, 3)
            mock_array.return_value.dtype = "uint8"

            with patch("goesvfi.gui_tabs.main_tab.LOGGER") as mock_logger:
                main_tab._check_input_directory_contents(tmp_path)

                # Should log error for corrupt image
                error_calls = [
                    call for call in mock_logger.error.call_args_list if "Error analyzing image" in str(call)
                ]
                assert len(error_calls) == 1


class TestGetProcessingArgs:
    """Tests for the get_processing_args utility function."""

    def setup_main_tab_ui(self, main_tab):
        """Set up necessary UI elements for get_processing_args."""
        # Create mock UI elements
        main_tab.encoder_combo = Mock()
        main_tab.encoder_combo.currentText.return_value = "RIFE"

        main_tab.rife_model_combo = Mock()
        main_tab.rife_model_combo.currentData.return_value = "rife-ncnn-vulkan"

        main_tab.fps_spinbox = Mock()
        main_tab.fps_spinbox.value.return_value = 30

        main_tab.multiplier_spinbox = Mock()
        main_tab.multiplier_spinbox.value.return_value = 2

        main_tab.max_workers_spinbox = Mock()
        main_tab.max_workers_spinbox.value.return_value = 4

        main_tab.rife_tta_spatial_checkbox = Mock()
        main_tab.rife_tta_spatial_checkbox.isChecked.return_value = False

        main_tab.rife_tta_temporal_checkbox = Mock()
        main_tab.rife_tta_temporal_checkbox.isChecked.return_value = False

        main_tab.rife_uhd_checkbox = Mock()
        main_tab.rife_uhd_checkbox.isChecked.return_value = True

        main_tab.rife_tile_checkbox = Mock()
        main_tab.rife_tile_checkbox.isChecked.return_value = False

        main_tab.rife_tile_size_spinbox = Mock()
        main_tab.rife_tile_size_spinbox.value.return_value = 256

        main_tab.rife_thread_spec_edit = Mock()
        main_tab.rife_thread_spec_edit.text.return_value = "1:2:1"

        main_tab.sanchez_false_colour_checkbox = Mock()
        main_tab.sanchez_false_colour_checkbox.isChecked.return_value = False

        main_tab.sanchez_res_combo = Mock()
        main_tab.sanchez_res_combo.currentText.return_value = "2.0"

    def test_get_args_no_input_directory(self, main_tab):
        """Test error when no input directory is selected."""
        self.setup_main_tab_ui(main_tab)
        main_tab.out_file_path = Path("/test/output.mp4")

        with patch.object(QMessageBox, "critical"):
            result = main_tab.get_processing_args()
            assert result is None

    def test_get_args_no_output_file(self, main_tab):
        """Test error when no output file is selected."""
        self.setup_main_tab_ui(main_tab)
        main_tab.main_window_ref.in_dir = Path("/test/input")
        main_tab.out_file_path = None

        with patch.object(QMessageBox, "critical"):
            result = main_tab.get_processing_args()
            assert result is None

    def test_get_args_input_dir_not_exists(self, main_tab):
        """Test error when input directory doesn't exist."""
        self.setup_main_tab_ui(main_tab)
        main_tab.main_window_ref.in_dir = Path("/nonexistent/directory")
        main_tab.out_file_path = Path("/test/output.mp4")

        with patch.object(QMessageBox, "critical"):
            result = main_tab.get_processing_args()
            assert result is None

    @patch("goesvfi.gui_tabs.main_tab.config")
    def test_get_args_rife_encoder(self, mock_config, main_tab, tmp_path):
        """Test getting args with RIFE encoder."""
        self.setup_main_tab_ui(main_tab)

        # Set up paths
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        output_file = tmp_path / "output.mp4"

        main_tab.main_window_ref.in_dir = input_dir
        main_tab.out_file_path = output_file
        main_tab.main_window_ref.current_crop_rect = (0, 0, 100, 100)

        # Mock config module
        mock_config.get_project_root.return_value = Path("/project/root")
        mock_config.find_rife_executable.return_value = Path("/path/to/rife")

        result = main_tab.get_processing_args()

        assert result is not None
        assert result["in_dir"] == input_dir
        assert result["out_file"] == output_file
        assert result["fps"] == 30
        assert result["multiplier"] == 2
        assert result["max_workers"] == 4
        assert result["encoder"] == "RIFE"
        assert result["rife_model_key"] == "rife-ncnn-vulkan"
        assert result["rife_model_path"] == Path("/project/root/models/rife-ncnn-vulkan")
        assert result["rife_exe_path"] == Path("/path/to/rife")
        assert result["rife_uhd"] is True
        assert result["rife_thread_spec"] == "1:2:1"
        assert result["crop_rect"] == (0, 0, 100, 100)

    def test_get_args_ffmpeg_encoder(self, main_tab, tmp_path):
        """Test getting args with FFmpeg encoder."""
        self.setup_main_tab_ui(main_tab)
        main_tab.encoder_combo.currentText.return_value = "FFmpeg"

        # Set up paths
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        output_file = tmp_path / "output.mp4"

        main_tab.main_window_ref.in_dir = input_dir
        main_tab.out_file_path = output_file

        # Mock FFmpeg tab
        mock_ffmpeg_tab = Mock()
        mock_ffmpeg_tab.get_ffmpeg_args.return_value = {"preset": "fast", "crf": 23}
        main_tab.main_window_ref.ffmpeg_tab = mock_ffmpeg_tab

        result = main_tab.get_processing_args()

        assert result is not None
        assert result["encoder"] == "FFmpeg"
        assert result["rife_model_key"] is None
        assert result["ffmpeg_args"] == {"preset": "fast", "crf": 23}

    def test_get_args_creates_output_directory(self, main_tab, tmp_path):
        """Test that output directory is created if it doesn't exist."""
        self.setup_main_tab_ui(main_tab)

        # Set up paths
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        output_file = tmp_path / "new_dir" / "output.mp4"

        main_tab.main_window_ref.in_dir = input_dir
        main_tab.out_file_path = output_file

        result = main_tab.get_processing_args()

        assert result is not None
        assert output_file.parent.exists()

    def test_get_args_no_rife_model_selected(self, main_tab, tmp_path):
        """Test error when RIFE encoder selected but no model."""
        self.setup_main_tab_ui(main_tab)
        main_tab.rife_model_combo.currentData.return_value = None

        # Set up paths
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        main_tab.main_window_ref.in_dir = input_dir
        main_tab.out_file_path = tmp_path / "output.mp4"

        with patch.object(QMessageBox, "critical"):
            result = main_tab.get_processing_args()
            assert result is None


class TestVerifyCropAgainstImages:
    """Tests for the _verify_crop_against_images utility function."""

    @patch("PIL.Image")
    def test_verify_valid_crop(self, mock_image_class, main_tab, tmp_path):
        """Test verifying a valid crop rectangle."""
        # Create test images
        for i in range(3):
            (tmp_path / f"image_{i}.png").touch()

        # Mock PIL Image
        mock_img = Mock()
        mock_img.size = (1920, 1080)
        mock_image_class.open.return_value = mock_img

        with patch("goesvfi.gui_tabs.main_tab.LOGGER") as mock_logger:
            # Valid crop within image bounds
            main_tab._verify_crop_against_images(tmp_path, (100, 100, 500, 400))

            # Should log debug info
            assert any(
                "Crop rectangle:" in str(call) or "Crop within bounds:" in str(call)
                for call in mock_logger.debug.call_args_list
            )

    @patch("PIL.Image")
    def test_verify_invalid_crop_exceeds_bounds(self, mock_image_class, main_tab, tmp_path):
        """Test verifying a crop rectangle that exceeds image bounds."""
        # Create test image
        (tmp_path / "image.png").touch()

        # Mock PIL Image
        mock_img = Mock()
        mock_img.size = (800, 600)
        mock_image_class.open.return_value = mock_img

        with patch("goesvfi.gui_tabs.main_tab.LOGGER") as mock_logger:
            # Crop exceeds image dimensions
            main_tab._verify_crop_against_images(tmp_path, (100, 100, 900, 700))

            # Should log warning about crop exceeding bounds
            warning_calls = [
                call for call in mock_logger.warning.call_args_list if "exceeds image dimensions" in str(call)
            ]
            assert len(warning_calls) > 0

    def test_verify_crop_no_images(self, main_tab, tmp_path):
        """Test verifying crop with no images in directory."""
        with patch("goesvfi.gui_tabs.main_tab.LOGGER") as mock_logger:
            main_tab._verify_crop_against_images(tmp_path, (0, 0, 100, 100))

            # Should handle gracefully
            mock_logger.warning.assert_called_once()


class TestSetInputDirectory:
    """Tests for the set_input_directory utility function."""

    def test_set_input_directory_string(self, main_tab):
        """Test setting input directory with string path."""
        main_tab.in_dir_edit = Mock()

        main_tab.set_input_directory("/test/path")

        main_tab.in_dir_edit.setText.assert_called_once_with("/test/path")

    def test_set_input_directory_path_object(self, main_tab):
        """Test setting input directory with Path object."""
        main_tab.in_dir_edit = Mock()

        main_tab.set_input_directory(Path("/test/path"))

        main_tab.in_dir_edit.setText.assert_called_once_with("/test/path")


class TestVerifyStartButtonState:
    """Tests for the _verify_start_button_state utility function."""

    def test_verify_button_should_be_enabled(self, main_tab):
        """Test verification when button should be enabled."""
        # Set up conditions for enabled state
        mock_path = MagicMock(spec=Path)
        mock_path.is_dir.return_value = True
        main_tab.main_window_ref.in_dir = mock_path
        main_tab.out_file_path = Path("/test/output.mp4")

        # Mock UI elements
        main_tab.encoder_combo = Mock()
        main_tab.encoder_combo.currentText.return_value = "RIFE"
        main_tab.rife_model_combo = Mock()
        main_tab.rife_model_combo.currentData.return_value = "rife-model"

        # Mock processing state and button
        main_tab.is_processing = False
        main_tab.start_button = Mock()
        main_tab.start_button.isEnabled.return_value = True

        with patch("goesvfi.gui_tabs.main_tab.LOGGER") as mock_logger:
            result = main_tab._verify_start_button_state()

            assert result is True
            mock_logger.debug.assert_any_call("Start button should be enabled: True")

    def test_verify_button_should_be_disabled_no_input(self, main_tab):
        """Test verification when button should be disabled due to no input."""
        # No input directory
        main_tab.main_window_ref.in_dir = None
        main_tab.out_file_path = Path("/test/output.mp4")

        # Mock UI elements
        main_tab.encoder_combo = Mock()
        main_tab.encoder_combo.currentText.return_value = "RIFE"
        main_tab.rife_model_combo = Mock()
        main_tab.rife_model_combo.currentData.return_value = "rife-model"

        # Mock processing state and button
        main_tab.is_processing = False
        main_tab.start_button = Mock()
        main_tab.start_button.isEnabled.return_value = False

        with patch("goesvfi.gui_tabs.main_tab.LOGGER") as mock_logger:
            result = main_tab._verify_start_button_state()

            assert result is False
            assert any("Has valid input directory: False" in str(call) for call in mock_logger.debug.call_args_list)

    def test_verify_button_should_be_disabled_no_output(self, main_tab):
        """Test verification when button should be disabled due to no output."""
        # No output file
        mock_path = MagicMock(spec=Path)
        mock_path.is_dir.return_value = True
        main_tab.main_window_ref.in_dir = mock_path
        main_tab.out_file_path = None

        # Mock UI elements
        main_tab.encoder_combo = Mock()
        main_tab.encoder_combo.currentText.return_value = "RIFE"
        main_tab.rife_model_combo = Mock()
        main_tab.rife_model_combo.currentData.return_value = "rife-model"

        # Mock processing state and button
        main_tab.is_processing = False
        main_tab.start_button = Mock()
        main_tab.start_button.isEnabled.return_value = False

        with patch("goesvfi.gui_tabs.main_tab.LOGGER") as mock_logger:
            result = main_tab._verify_start_button_state()

            assert result is False
            assert any("Has output file path: False" in str(call) for call in mock_logger.debug.call_args_list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
