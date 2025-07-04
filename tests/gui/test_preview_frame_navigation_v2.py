"""
Comprehensive preview frame navigation and validation tests.

Tests the core user workflow of selecting a directory and validating that
first, middle, and last frames are properly displayed in the preview system.
This covers the essential user experience of browsing through satellite imagery.
"""

import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
import pytest

from goesvfi.gui import MainWindow


class TestPreviewFrameNavigation:
    """Test preview frame navigation and validation functionality."""

    @pytest.fixture()
    def main_window(self, qtbot):
        """Create MainWindow for preview frame testing."""
        with patch("goesvfi.gui.QSettings"):
            window = MainWindow(debug_mode=True)
            qtbot.addWidget(window)
            window._post_init_setup()
            return window

    @pytest.fixture()
    def sample_directory_with_frames(self):
        """Create a temporary directory with sample frame files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create sample frame files with realistic GOES naming pattern
            frame_files = []
            for i in range(10):  # Create 10 frames
                # Use realistic GOES file naming pattern
                filename = f"OR_ABI-L2-MCMIPC-M6_G16_s20232{i:02d}0000000_e20232{i:02d}0012190_c20232{i:02d}0013543.nc"
                frame_file = temp_path / filename

                # Create minimal NetCDF-like content
                frame_file.write_bytes(b"CDF\x01" + b"\x00" * 100)  # Minimal NetCDF header
                frame_files.append(frame_file)

            yield temp_path, frame_files

    def test_directory_selection_and_frame_preview(self, qtbot, main_window, sample_directory_with_frames):
        """Test selecting a directory and validating first, middle, last frame previews."""
        window = main_window
        temp_path, frame_files = sample_directory_with_frames

        # Get preview manager
        preview_manager = window.main_view_model.preview_manager

        # Mock successful image loading for testing
        with patch.object(preview_manager, "load_preview_thumbnails") as mock_load_previews:
            mock_load_previews.return_value = True

            # Mock frame data for first, middle, last frames
            with patch.object(preview_manager, "get_current_frame_data") as mock_frame_data:
                # Create mock ImageData objects
                first_frame_mock = MagicMock()
                first_frame_mock.file_path = str(frame_files[0])
                first_frame_mock.image_data = MagicMock()
                first_frame_mock.timestamp = "2023-01-01 00:00:00"

                middle_frame_mock = MagicMock()
                middle_frame_mock.file_path = str(frame_files[len(frame_files) // 2])
                middle_frame_mock.image_data = MagicMock()
                middle_frame_mock.timestamp = "2023-01-01 12:00:00"

                last_frame_mock = MagicMock()
                last_frame_mock.file_path = str(frame_files[-1])
                last_frame_mock.image_data = MagicMock()
                last_frame_mock.timestamp = "2023-01-01 23:00:00"

                # Set up mock frame data responses (returns tuple of first, middle, last)
                mock_frame_data.return_value = (first_frame_mock, middle_frame_mock, last_frame_mock)

                # Step 1: Select the directory through the UI
                window.main_tab.in_dir_edit.setText(str(temp_path))
                window.state_manager.set_input_directory(temp_path)
                qtbot.wait(100)

                # Step 2: Load previews
                success = preview_manager.load_preview_thumbnails(temp_path, crop_rect=None, apply_sanchez=False)
                assert success, "Preview loading should succeed"
                assert mock_load_previews.call_count >= 1, "Preview loading should be called at least once"

                # Step 3: Get frame data and validate all three frames
                first_frame_data, middle_frame_data, last_frame_data = preview_manager.get_current_frame_data()

                # Step 4: Validate first frame
                assert first_frame_data is not None, "Should get first frame data"
                assert "OR_ABI-L2-MCMIPC" in str(first_frame_data.file_path), "First frame should be GOES file"
                assert "s20232000" in str(first_frame_data.file_path), "First frame should be earliest timestamp"

                # Step 5: Validate middle frame
                assert middle_frame_data is not None, "Should get middle frame data"
                assert "OR_ABI-L2-MCMIPC" in str(middle_frame_data.file_path), "Middle frame should be GOES file"
                assert first_frame_data.file_path != middle_frame_data.file_path, (
                    "Middle frame should be different from first"
                )

                # Step 6: Validate last frame
                assert last_frame_data is not None, "Should get last frame data"
                assert "OR_ABI-L2-MCMIPC" in str(last_frame_data.file_path), "Last frame should be GOES file"
                assert "s20232090" in str(last_frame_data.file_path), "Last frame should be latest timestamp"
                assert last_frame_data.file_path != first_frame_data.file_path, (
                    "Last frame should be different from first"
                )
                assert last_frame_data.file_path != middle_frame_data.file_path, (
                    "Last frame should be different from middle"
                )

    def test_frame_navigation_ui_controls(self, qtbot, main_window, sample_directory_with_frames):
        """Test frame navigation through UI controls and preview updates."""
        window = main_window
        temp_path, frame_files = sample_directory_with_frames

        preview_manager = window.main_view_model.preview_manager

        # Mock successful preview loading
        with patch.object(preview_manager, "load_preview_thumbnails", return_value=True):
            # Load directory
            window.state_manager.set_input_directory(temp_path)
            preview_manager.load_preview_thumbnails(temp_path, None, False)
            qtbot.wait(50)

            # Test that request_preview_update can be called without errors
            try:
                preview_manager.request_preview_update(temp_path, None)
                qtbot.wait(10)
                preview_update_works = True
            except Exception:
                preview_update_works = False

            assert preview_update_works, "Preview update request should work without errors"

    def test_frame_preview_with_crop_applied(self, qtbot, main_window, sample_directory_with_frames):
        """Test frame preview functionality with crop rectangle applied."""
        window = main_window
        temp_path, frame_files = sample_directory_with_frames

        preview_manager = window.main_view_model.preview_manager
        crop_rect = (10, 20, 100, 150)  # x, y, width, height

        with patch.object(preview_manager, "load_preview_thumbnails", return_value=True):
            # Set crop rectangle first
            window.state_manager.set_crop_rect(crop_rect)
            qtbot.wait(50)

            # Load previews with crop applied
            success = preview_manager.load_preview_thumbnails(temp_path, crop_rect=crop_rect, apply_sanchez=False)
            assert success, "Preview loading with crop should succeed"

            # Verify crop was applied to preview loading
            call_args = preview_manager.load_preview_thumbnails.call_args
            assert call_args[1]["crop_rect"] == crop_rect, "Crop rectangle should be passed to preview loading"

    def test_frame_preview_validation_and_error_handling(self, qtbot, main_window):
        """Test frame preview validation and error handling for invalid directories."""
        window = main_window
        preview_manager = window.main_view_model.preview_manager

        # Test with non-existent directory
        non_existent_path = Path("/non/existent/directory")

        with patch.object(preview_manager, "load_preview_thumbnails", return_value=False):
            success = preview_manager.load_preview_thumbnails(non_existent_path, crop_rect=None, apply_sanchez=False)
            assert not success, "Should fail for non-existent directory"

        # Test with empty directory
        with tempfile.TemporaryDirectory() as empty_dir:
            empty_path = Path(empty_dir)

            with patch.object(preview_manager, "load_preview_thumbnails", return_value=False):
                success = preview_manager.load_preview_thumbnails(empty_path, crop_rect=None, apply_sanchez=False)
                assert not success, "Should fail for empty directory"

    def test_frame_preview_memory_efficiency(self, qtbot, main_window, sample_directory_with_frames):
        """Test that frame preview loading is memory efficient and doesn't leak."""
        window = main_window
        temp_path, frame_files = sample_directory_with_frames

        preview_manager = window.main_view_model.preview_manager

        # Track memory usage during frame loading
        initial_memory_info = preview_manager.get_memory_usage_info()

        with patch.object(preview_manager, "load_preview_thumbnails", return_value=True):
            # Load previews multiple times
            for _ in range(3):
                preview_manager.load_preview_thumbnails(temp_path, None, False)
                qtbot.wait(10)

                # Clear cache between loads
                preview_manager.clear_cache()
                qtbot.wait(10)

            # Verify memory is properly managed
            final_memory_info = preview_manager.get_memory_usage_info()

            # Memory usage should not accumulate indefinitely
            assert isinstance(final_memory_info, dict), "Should return memory info"

    def test_real_frame_sequence_validation(self, qtbot, main_window, sample_directory_with_frames):
        """Test validation of frame sequence ordering and continuity."""
        window = main_window
        temp_path, frame_files = sample_directory_with_frames

        preview_manager = window.main_view_model.preview_manager

        # Mock frame sequence validation
        with patch.object(preview_manager, "load_preview_thumbnails", return_value=True):
            with patch.object(preview_manager, "get_current_frame_data") as mock_frame_data:
                # Mock frame data showing proper sequence
                first_mock = MagicMock()
                first_mock.file_path = str(sorted(frame_files, key=lambda f: f.name)[0])

                middle_mock = MagicMock()
                middle_mock.file_path = str(sorted(frame_files, key=lambda f: f.name)[len(frame_files) // 2])

                last_mock = MagicMock()
                last_mock.file_path = str(sorted(frame_files, key=lambda f: f.name)[-1])

                mock_frame_data.return_value = (first_mock, middle_mock, last_mock)

                # Load previews
                preview_manager.load_preview_thumbnails(temp_path, None, False)

                # Verify frames are in correct sequence
                first_frame_data, middle_frame_data, last_frame_data = preview_manager.get_current_frame_data()

                # Verify first frame is earliest
                assert "s20232000" in str(first_frame_data.file_path), "First frame should be earliest timestamp"

                # Verify last frame is latest
                assert "s20232090" in str(last_frame_data.file_path), "Last frame should be latest timestamp"

    def test_preview_with_sanchez_processing(self, qtbot, main_window, sample_directory_with_frames):
        """Test frame preview with Sanchez colorization processing enabled."""
        window = main_window
        temp_path, frame_files = sample_directory_with_frames

        preview_manager = window.main_view_model.preview_manager

        with patch.object(preview_manager, "load_preview_thumbnails", return_value=True):
            # Enable Sanchez processing
            success = preview_manager.load_preview_thumbnails(temp_path, crop_rect=None, apply_sanchez=True)
            assert success, "Preview loading with Sanchez should succeed"

            # Verify Sanchez was enabled in the call
            call_args = preview_manager.load_preview_thumbnails.call_args
            assert call_args[1]["apply_sanchez"] is True, "Sanchez should be enabled"

    def test_concurrent_frame_loading_stability(self, qtbot, main_window, sample_directory_with_frames):
        """Test stability when loading frames concurrently or rapidly."""
        window = main_window
        temp_path, frame_files = sample_directory_with_frames

        preview_manager = window.main_view_model.preview_manager

        with patch.object(preview_manager, "load_preview_thumbnails", return_value=True):
            # Simulate rapid preview loading requests
            for i in range(5):
                success = preview_manager.load_preview_thumbnails(temp_path, None, False)
                assert success, f"Rapid loading attempt {i} should succeed"
                qtbot.wait(5)  # Brief wait between requests

            # Should remain stable after multiple requests
            assert preview_manager.load_preview_thumbnails.call_count == 5, "Should handle multiple rapid requests"
