"""Tests specifically for the refactored run_vfi function and its helper functions."""

import pathlib
import subprocess
import tempfile
from typing import Dict, List, Optional, Tuple, Union
from unittest.mock import ANY, MagicMock, patch

import numpy as np
import pytest
from PIL import Image

from goesvfi.pipeline import run_vfi as run_vfi_mod
from goesvfi.pipeline.image_processing_interfaces import ImageData
from goesvfi.utils.rife_analyzer import RifeCapabilityDetector


def create_test_png(path: pathlib.Path, size: tuple = (10, 10)):
    """Create a minimal valid PNG file at the given path."""
    img_array = np.zeros((size[1], size[0], 3), dtype=np.uint8)
    img = Image.fromarray(img_array)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, format="PNG")
    return path


def make_dummy_images(tmp_path, n, size=(4, 4)):
    """Create n dummy PNG images in the given directory."""
    paths = []
    for i in range(n):
        img_path = tmp_path / f"img{i}.png"
        create_test_png(img_path, size=size)
        paths.append(img_path)
    return paths


@pytest.fixture
def mock_capability_detector(mocker):
    """Fixture to provide a mock RifeCapabilityDetector."""
    mock_detector = mocker.MagicMock(spec=RifeCapabilityDetector)
    mock_detector.supports_thread_spec.return_value = True
    mock_detector.supports_tiling.return_value = True
    mock_detector.supports_uhd.return_value = True
    mock_detector.supports_model_path.return_value = True
    mock_detector.supports_tta_spatial.return_value = True
    mock_detector.supports_tta_temporal.return_value = True
    
    # Patch where it's used in run_vfi
    return mocker.patch(
        "goesvfi.pipeline.run_vfi.RifeCapabilityDetector", return_value=mock_detector
    )


# Tests for parameter validation and preparation
class TestParameterValidation:
    """Tests for parameter validation and preparation functions."""
    
    def test_validate_and_prepare_run_vfi_parameters(self, tmp_path):
        """Test the parameter validation helper function."""
        # Create test images
        img_paths = make_dummy_images(tmp_path, 2)
        
        # Test with valid parameters
        result = run_vfi_mod._validate_and_prepare_run_vfi_parameters(
            folder=tmp_path,
            num_intermediate_frames=1,
            encoder_type="RIFE",
            false_colour=False,
            crop_rect_xywh=(0, 0, 2, 2),
            skip_model=False,
        )
        
        # Check the return values
        assert isinstance(result, tuple)
        assert len(result) == 3
        
        # Unpack the result
        updated_false_colour, paths, crop_for_pil = result
        
        # Verify false_colour wasn't changed for RIFE
        assert updated_false_colour is False
        
        # Verify paths were found
        assert len(paths) == 2
        assert all(isinstance(p, pathlib.Path) for p in paths)
        
        # Verify crop conversion
        assert crop_for_pil == (0, 0, 2, 2)  # Converted from (x,y,w,h) to (left,top,right,bottom)
    
    def test_sanchez_forces_true_colour(self, tmp_path):
        """Test that Sanchez encoder forces false_colour to True."""
        # Create test images
        img_paths = make_dummy_images(tmp_path, 2)
        
        # Test with Sanchez and false_colour=False
        result = run_vfi_mod._validate_and_prepare_run_vfi_parameters(
            folder=tmp_path,
            num_intermediate_frames=1,
            encoder_type="Sanchez",
            false_colour=False,
            crop_rect_xywh=None,
            skip_model=False,
        )
        
        # Check that false_colour was forced to True
        updated_false_colour, _, _ = result
        assert updated_false_colour is True
    
    def test_validation_with_invalid_crop(self, tmp_path):
        """Test validation with invalid crop rectangle."""
        # Create test images
        img_paths = make_dummy_images(tmp_path, 2)
        
        # Test with invalid crop (negative width)
        result = run_vfi_mod._validate_and_prepare_run_vfi_parameters(
            folder=tmp_path,
            num_intermediate_frames=1,
            encoder_type="RIFE",
            false_colour=False,
            crop_rect_xywh=(0, 0, -1, 2),
            skip_model=False,
        )
        
        # Check that crop was set to None
        _, _, crop_for_pil = result
        assert crop_for_pil is None
    
    def test_validation_with_no_images(self, tmp_path):
        """Test validation with no images in the folder."""
        # Try to validate with no images
        with pytest.raises(ValueError, match="No PNG images found"):
            run_vfi_mod._validate_and_prepare_run_vfi_parameters(
                folder=tmp_path,
                num_intermediate_frames=1,
                encoder_type="RIFE",
                false_colour=False,
                crop_rect_xywh=None,
                skip_model=False,
            )


# Tests for FFmpeg helper functions
class TestFfmpegHelpers:
    """Tests for FFmpeg-related helper functions."""
    
    def test_build_ffmpeg_command(self):
        """Test building FFmpeg command."""
        fps = 30
        output_path = pathlib.Path("/test/output.mp4")
        
        cmd = run_vfi_mod._build_ffmpeg_command(fps, output_path)
        
        # Check command structure
        assert isinstance(cmd, list)
        assert cmd[0] == "ffmpeg"
        assert "-framerate" in cmd
        assert str(fps) in cmd
        assert str(output_path) in cmd
    
    def test_get_unique_output_path(self):
        """Test generating unique output path."""
        original_path = pathlib.Path("/test/output.mp4")
        
        # Patch datetime.now to return a fixed timestamp
        with patch("datetime.datetime") as mock_datetime:
            mock_datetime.now.return_value.strftime.return_value = "20250101_120000"
            
            result = run_vfi_mod._get_unique_output_path(original_path)
            
            # Check that timestamp was added
            assert result.name.startswith("output_20250101_120000")
            assert result.suffix == ".mp4"


# Tests for RIFE helper functions
class TestRifeHelpers:
    """Tests for RIFE-related helper functions."""
    
    def test_create_rife_command(self, mock_capability_detector):
        """Test creating RIFE command with various settings."""
        rife_exe = pathlib.Path("/test/rife")
        img1 = pathlib.Path("/test/img1.png")
        img2 = pathlib.Path("/test/img2.png")
        output = pathlib.Path("/test/output.png")
        
        # Create a capability detector
        detector = RifeCapabilityDetector(rife_exe)
        
        # Test with all features enabled
        cmd = run_vfi_mod._create_rife_command(
            rife_exe_path=rife_exe,
            temp_p1_path=img1,
            temp_p2_path=img2,
            output_path=output,
            model_key="rife-v4.6",
            capability_detector=detector,
            rife_tile_enable=True,
            rife_tile_size=256,
            rife_uhd_mode=True,
            rife_tta_spatial=True,
            rife_tta_temporal=True,
            rife_thread_spec="2:4:4"
        )
        
        # Check command structure
        assert cmd[0] == str(rife_exe)
        assert "-0" in cmd and str(img1) in cmd
        assert "-1" in cmd and str(img2) in cmd
        assert "-o" in cmd and str(output) in cmd
        assert "-t" in cmd and "256" in cmd  # Tiling
        assert "-s" in cmd  # Spatial TTA
        assert "-T" in cmd  # Temporal TTA
        assert "-y" in cmd and "2:4:4" in cmd  # Thread spec
    
    def test_check_rife_capability_warnings(self, caplog):
        """Test warning logs for unsupported RIFE features."""
        # Create a mock capability detector
        detector = MagicMock(spec=RifeCapabilityDetector)
        detector.supports_tiling.return_value = False
        detector.supports_uhd.return_value = False
        detector.supports_tta_spatial.return_value = False
        detector.supports_tta_temporal.return_value = False
        detector.supports_thread_spec.return_value = False
        
        # Check warnings for unsupported features
        run_vfi_mod._check_rife_capability_warnings(
            capability_detector=detector,
            rife_tile_enable=True,
            rife_uhd_mode=True,
            rife_tta_spatial=True,
            rife_tta_temporal=True,
            rife_thread_spec="2:4:4"
        )
        
        # Check that warnings were logged
        assert "Tiling requested but not supported" in caplog.text
        assert "UHD mode requested but not supported" in caplog.text
        assert "Spatial TTA requested but not supported" in caplog.text
        assert "Temporal TTA requested but not supported" in caplog.text
        assert "thread specification" in caplog.text


# Tests for image processing helpers
class TestImageProcessingHelpers:
    """Tests for image processing helper functions."""
    
    @patch("goesvfi.pipeline.run_vfi.Image.open")
    def test_process_in_skip_model_mode(self, mock_image_open, tmp_path):
        """Test processing frames in skip_model mode."""
        # Create mock images
        img_paths = make_dummy_images(tmp_path, 3)
        
        # Create mock FFmpeg process
        mock_proc = MagicMock()
        mock_proc.stdin = MagicMock()
        
        # Configure mock Image.open
        mock_img = MagicMock()
        mock_img.size = (4, 4)
        mock_img.__enter__.return_value = mock_img
        mock_image_open.return_value = mock_img
        
        # Call the function
        generator = run_vfi_mod._process_in_skip_model_mode(mock_proc, img_paths)
        
        # Collect all yielded values
        progress_updates = list(generator)
        
        # Verify function behavior
        assert len(progress_updates) == 2  # Should yield for each frame after the first
        assert all(isinstance(p, tuple) and len(p) == 3 for p in progress_updates)
        assert mock_proc.stdin.write.call_count == 2
    
    @patch("goesvfi.pipeline.run_vfi.subprocess.run")
    def test_process_with_rife(self, mock_subprocess_run, mock_capability_detector, tmp_path):
        """Test processing frames with RIFE interpolation."""
        # Create mock images
        img_paths = make_dummy_images(tmp_path, 3)
        
        # Create mock FFmpeg process
        mock_proc = MagicMock()
        mock_proc.stdin = MagicMock()
        
        # Configure mock subprocess.run to succeed
        mock_subprocess_run.return_value.returncode = 0
        
        # Patch Image.open to handle interpolated frame
        with patch("goesvfi.pipeline.run_vfi.Image.open") as mock_image_open:
            mock_img = MagicMock()
            mock_img.size = (4, 4)
            mock_img.__enter__.return_value = mock_img
            mock_image_open.return_value = mock_img
            
            # Call the function
            generator = run_vfi_mod._process_with_rife(
                ffmpeg_proc=mock_proc,
                all_processed_paths=img_paths,
                rife_exe_path=pathlib.Path("/test/rife"),
                model_key="rife-v4.6",
                processed_img_dir=tmp_path,
                rife_tile_enable=True,
                rife_tile_size=256,
                rife_uhd_mode=True,
                rife_thread_spec="2:4:4",
                rife_tta_spatial=True,
                rife_tta_temporal=True
            )
            
            # Collect all yielded values
            progress_updates = list(generator)
            
            # Verify function behavior
            assert len(progress_updates) == 4  # 2 iterations x 2 yields per iteration
            assert all(isinstance(p, tuple) and len(p) == 3 for p in progress_updates)
            assert mock_subprocess_run.call_count == 2
            assert mock_proc.stdin.write.call_count == 4  # 2 interpolated + 2 second frames


# Tests for VfiWorker refactored methods
class TestVfiWorker:
    """Tests for VfiWorker class and its refactored helper methods."""
    
    def test_get_rife_executable(self, mocker):
        """Test retrieving RIFE executable path."""
        # Mock config.find_rife_executable
        mock_find_rife = mocker.patch(
            "goesvfi.utils.config.find_rife_executable",
            return_value=pathlib.Path("/test/rife")
        )
        
        # Create a VfiWorker instance with minimum required attributes
        worker = run_vfi_mod.VfiWorker(
            in_dir=pathlib.Path("/test/input"),
            out_file_path=pathlib.Path("/test/output.mp4"),
            fps=30,
            mid_count=1,
            max_workers=1,
            encoder="RIFE",
            use_preset_optimal=False,
            use_ffmpeg_interp=False,
            filter_preset="",
            mi_mode="",
            mc_mode="",
            me_mode="",
            me_algo="",
            search_param=0,
            scd_mode="",
            scd_threshold=None,
            minter_mb_size=None,
            minter_vsbmc=0,
            apply_unsharp=False,
            unsharp_lx=0,
            unsharp_ly=0,
            unsharp_la=0.0,
            unsharp_cx=0,
            unsharp_cy=0,
            unsharp_ca=0.0,
            crf=0,
            bitrate_kbps=0,
            bufsize_kb=0,
            pix_fmt="",
            skip_model=False,
            crop_rect=None,
            debug_mode=False,
            rife_tile_enable=False,
            rife_tile_size=256,
            rife_uhd_mode=False,
            rife_thread_spec="1:2:2",
            rife_tta_spatial=False,
            rife_tta_temporal=False,
            model_key="rife-v4.6",
            false_colour=False,
            res_km=0,
            sanchez_gui_temp_dir=pathlib.Path("/test/sanchez"),
        )
        
        # Call the method
        result = worker._get_rife_executable()
        
        # Verify the result
        assert result == pathlib.Path("/test/rife")
        mock_find_rife.assert_called_once_with("rife-v4.6")
    
    def test_prepare_ffmpeg_settings(self):
        """Test preparing FFmpeg settings dictionary."""
        # Create a VfiWorker instance with test FFmpeg settings
        worker = run_vfi_mod.VfiWorker(
            in_dir=pathlib.Path("/test/input"),
            out_file_path=pathlib.Path("/test/output.mp4"),
            fps=30,
            mid_count=1,
            max_workers=1,
            encoder="RIFE",
            use_preset_optimal=True,
            use_ffmpeg_interp=True,
            filter_preset="medium",
            mi_mode="bilinear",
            mc_mode="obmc",
            me_mode="bilat",
            me_algo="epzs",
            search_param=32,
            scd_mode="fdiff",
            scd_threshold=10.0,
            minter_mb_size=16,
            minter_vsbmc=1,
            apply_unsharp=True,
            unsharp_lx=5,
            unsharp_ly=5,
            unsharp_la=1.0,
            unsharp_cx=5,
            unsharp_cy=5,
            unsharp_ca=0.5,
            crf=23,
            bitrate_kbps=5000,
            bufsize_kb=10000,
            pix_fmt="yuv420p",
            skip_model=False,
            crop_rect=None,
            debug_mode=False,
            rife_tile_enable=False,
            rife_tile_size=256,
            rife_uhd_mode=False,
            rife_thread_spec="1:2:2",
            rife_tta_spatial=False,
            rife_tta_temporal=False,
            model_key="rife-v4.6",
            false_colour=False,
            res_km=0,
            sanchez_gui_temp_dir=pathlib.Path("/test/sanchez"),
        )
        
        # Call the method
        settings = worker._prepare_ffmpeg_settings()
        
        # Verify the settings
        assert isinstance(settings, dict)
        assert settings["use_ffmpeg_interp"] is True
        assert settings["filter_preset"] == "medium"
        assert settings["mi_mode"] == "bilinear"
        assert settings["search_param"] == 32
        assert settings["crf"] == 23
        assert settings["bitrate_kbps"] == 5000
    
    def test_process_run_vfi_output(self, mocker):
        """Test processing output from run_vfi generator."""
        # Create a VfiWorker instance with minimum required attributes and mock signals
        worker = run_vfi_mod.VfiWorker(
            in_dir=pathlib.Path("/test/input"),
            out_file_path=pathlib.Path("/test/output.mp4"),
            fps=30,
            mid_count=1,
            max_workers=1,
            encoder="RIFE",
            use_preset_optimal=False,
            use_ffmpeg_interp=False,
            filter_preset="",
            mi_mode="",
            mc_mode="",
            me_mode="",
            me_algo="",
            search_param=0,
            scd_mode="",
            scd_threshold=None,
            minter_mb_size=None,
            minter_vsbmc=0,
            apply_unsharp=False,
            unsharp_lx=0,
            unsharp_ly=0,
            unsharp_la=0.0,
            unsharp_cx=0,
            unsharp_cy=0,
            unsharp_ca=0.0,
            crf=0,
            bitrate_kbps=0,
            bufsize_kb=0,
            pix_fmt="",
            skip_model=False,
            crop_rect=None,
            debug_mode=False,
            rife_tile_enable=False,
            rife_tile_size=256,
            rife_uhd_mode=False,
            rife_thread_spec="1:2:2",
            rife_tta_spatial=False,
            rife_tta_temporal=False,
            model_key="rife-v4.6",
            false_colour=False,
            res_km=0,
            sanchez_gui_temp_dir=pathlib.Path("/test/sanchez"),
        )
        
        # Mock signals
        worker.progress = MagicMock()
        worker.finished = MagicMock()
        worker.error = MagicMock()
        
        # Create a mock generator with various outputs
        progress_update = (1, 10, 5.0)  # current, total, eta
        final_path = pathlib.Path("/test/output.mp4")
        error_message = "ERROR: Something went wrong"
        
        # Test progress update
        worker._process_run_vfi_output([progress_update])
        worker.progress.emit.assert_called_once_with(1, 10, 5.0)
        
        # Reset mocks
        worker.progress.reset_mock()
        
        # Test final path
        worker._process_run_vfi_output([final_path])
        worker.finished.emit.assert_called_once_with(final_path)
        
        # Test error message
        worker._process_run_vfi_output([error_message])
        worker.error.emit.assert_called_once_with("Something went wrong")


# Integration test for the refactored run_vfi
@patch("goesvfi.pipeline.run_vfi.subprocess.run")
@patch("goesvfi.pipeline.run_vfi.subprocess.Popen")
@patch("goesvfi.pipeline.run_vfi.Image.open")
@patch("goesvfi.pipeline.run_vfi.ProcessPoolExecutor")
def test_run_vfi_integration(
    mock_executor,
    mock_image_open,
    mock_popen_patch,
    mock_run_patch,
    tmp_path,
    mock_capability_detector,
):
    """Integration test for the refactored run_vfi function."""
    # Setup a mock executor that doesn't actually use multiprocessing
    mock_executor_instance = MagicMock()
    mock_executor.return_value.__enter__.return_value = mock_executor_instance
    mock_executor_instance.map.return_value = []
    
    # Create test images
    img_paths = make_dummy_images(tmp_path, 3)
    output_mp4 = tmp_path / "output.mp4"
    raw_output = output_mp4.with_suffix(".raw.mp4")
    rife_exe = tmp_path / "rife"
    
    # Mock Image.open
    mock_img = MagicMock()
    mock_img.size = (4, 4)
    mock_img.__enter__.return_value = mock_img
    mock_image_open.return_value = mock_img
    
    # Mock FFmpeg Popen
    mock_popen_instance = MagicMock()
    mock_popen_instance.stdin = MagicMock()
    mock_popen_instance.stdout = MagicMock()
    mock_popen_instance.returncode = 0
    mock_popen_patch.return_value = mock_popen_instance
    
    # Create the raw output file to simulate successful FFmpeg execution
    raw_output.parent.mkdir(parents=True, exist_ok=True)
    raw_output.touch()
    
    # Patch glob to return our test images
    with patch.object(pathlib.Path, "glob", return_value=img_paths):
        # Call run_vfi
        gen = run_vfi_mod.run_vfi(
            folder=tmp_path,
            output_mp4_path=output_mp4,
            rife_exe_path=rife_exe,
            fps=30,
            num_intermediate_frames=1,
            max_workers=1,
            skip_model=True,  # Skip model for simpler testing
        )
        
        # Collect results
        results = list(gen)
    
    # Verify behavior
    assert any(isinstance(r, pathlib.Path) for r in results)
    assert mock_popen_patch.called
    assert mock_image_open.called