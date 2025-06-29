"""Optimized raw encoder tests to speed up slow tests while maintaining coverage.

Optimizations applied:
- Shared fixtures for common frame setups and encoding configurations
- Parameterized test scenarios for comprehensive raw encoding validation
- Enhanced error handling and edge case coverage
- Mock-based testing to avoid actual FFmpeg execution and file I/O
- Comprehensive frame processing and lossless encoding testing
"""

import subprocess
import tempfile
import pathlib
from unittest.mock import MagicMock, patch, call
import pytest
import numpy as np
from PIL import Image

from goesvfi.pipeline import raw_encoder


class TestRawEncoderV2:
    """Optimized test class for raw encoder functionality."""

    @pytest.fixture(scope="class")
    def encoding_scenarios(self):
        """Define various encoding scenarios."""
        return {
            "minimal_frames": {
                "frame_count": 2,
                "frame_shape": (4, 4, 3),
                "fps": 24,
                "expected_success": True,
            },
            "standard_video": {
                "frame_count": 10,
                "frame_shape": (64, 64, 3),
                "fps": 30,
                "expected_success": True,
            },
            "high_resolution": {
                "frame_count": 5,
                "frame_shape": (256, 256, 3),
                "fps": 60,
                "expected_success": True,
            },
            "single_frame": {
                "frame_count": 1,
                "frame_shape": (32, 32, 3),
                "fps": 1,
                "expected_success": True,
            },
            "many_frames": {
                "frame_count": 100,
                "frame_shape": (16, 16, 3),
                "fps": 120,
                "expected_success": True,
            },
        }

    @pytest.fixture
    def frame_data_factory(self):
        """Factory for creating test frame data."""
        def create_frames(count=3, shape=(4, 4, 3), pattern="gradient"):
            frames = []
            for i in range(count):
                if pattern == "gradient":
                    # Create gradient frames with different intensities
                    frame = np.ones(shape, dtype=np.float32) * (i / max(1, count - 1))
                elif pattern == "random":
                    # Create random frames
                    frame = np.random.random(shape).astype(np.float32)
                elif pattern == "solid":
                    # Create solid color frames
                    frame = np.full(shape, i * 0.1, dtype=np.float32)
                elif pattern == "extreme":
                    # Create frames with extreme values (testing clipping)
                    frame = np.full(shape, 2.0 if i % 2 else -1.0, dtype=np.float32)
                else:
                    # Default uniform frames
                    frame = np.ones(shape, dtype=np.float32) * 0.5
                
                frames.append(frame)
            return frames
        return create_frames

    @pytest.fixture
    def mock_environment_factory(self, tmp_path):
        """Factory for creating mock environments."""
        def create_environment(scenario_config, simulate_failure=None):
            raw_path = tmp_path / "output.mp4"
            temp_dir_path = tmp_path / "tempdir"
            temp_dir_path.mkdir()
            
            mock_patches = {}
            
            # Mock temporary directory
            mock_tempdir = MagicMock()
            mock_tempdir.__enter__.return_value = str(temp_dir_path)
            mock_tempdir.__exit__.return_value = None
            mock_patches["tempdir"] = patch(
                "goesvfi.pipeline.raw_encoder.tempfile.TemporaryDirectory",
                return_value=mock_tempdir
            )
            
            # Mock PIL Image operations
            mock_img = MagicMock()
            mock_fromarray = MagicMock(return_value=mock_img)
            mock_patches["fromarray"] = patch(
                "goesvfi.pipeline.raw_encoder.Image.fromarray",
                mock_fromarray
            )
            
            # Mock subprocess run
            if simulate_failure == "ffmpeg_error":
                error = subprocess.CalledProcessError(1, ["ffmpeg"], stderr="FFmpeg failed")
                mock_patches["subprocess"] = patch(
                    "goesvfi.pipeline.raw_encoder.subprocess.run",
                    side_effect=error
                )
            elif simulate_failure == "ffmpeg_not_found":
                error = FileNotFoundError("ffmpeg not found")
                mock_patches["subprocess"] = patch(
                    "goesvfi.pipeline.raw_encoder.subprocess.run",
                    side_effect=error
                )
            else:
                # Success case
                mock_result = MagicMock()
                mock_result.returncode = 0
                mock_result.stdout = "FFmpeg encoding successful"
                mock_result.stderr = ""
                mock_patches["subprocess"] = patch(
                    "goesvfi.pipeline.raw_encoder.subprocess.run",
                    return_value=mock_result
                )
                # Simulate file creation on success
                def create_output(*args, **kwargs):
                    raw_path.touch()
                    return mock_result
                mock_patches["subprocess"].side_effect = create_output
            
            return {
                "patches": mock_patches,
                "paths": {
                    "raw_path": raw_path,
                    "temp_dir": temp_dir_path,
                },
                "mocks": {
                    "tempdir": mock_tempdir,
                    "fromarray": mock_fromarray,
                    "img": mock_img,
                }
            }
        return create_environment

    @pytest.mark.parametrize("scenario_name", [
        "minimal_frames",
        "standard_video",
        "high_resolution",
        "single_frame",
    ])
    def test_write_raw_mp4_success_scenarios(self, frame_data_factory, mock_environment_factory, 
                                           encoding_scenarios, scenario_name):
        """Test successful raw MP4 writing with various scenarios."""
        scenario = encoding_scenarios[scenario_name]
        frames = frame_data_factory(
            count=scenario["frame_count"],
            shape=scenario["frame_shape"],
            pattern="gradient"
        )
        environment = mock_environment_factory(scenario)
        
        # Apply all patches
        active_patches = []
        for patch_obj in environment["patches"].values():
            active_patches.append(patch_obj.start())
        
        try:
            result = raw_encoder.write_raw_mp4(
                frames,
                environment["paths"]["raw_path"],
                fps=scenario["fps"]
            )
            
            # Verify result
            assert result == environment["paths"]["raw_path"]
            assert environment["paths"]["raw_path"].exists()
            
            # Verify frame processing
            environment["mocks"]["fromarray"].assert_called()
            assert environment["mocks"]["fromarray"].call_count == scenario["frame_count"]
            
            # Verify FFmpeg command
            environment["patches"]["subprocess"].assert_called_once()
            
        finally:
            # Clean up patches
            for patch_obj in active_patches:
                patch_obj.stop()

    @pytest.mark.parametrize("fps", [1, 24, 30, 60, 120])
    def test_fps_parameter_variations(self, frame_data_factory, mock_environment_factory, fps):
        """Test raw MP4 writing with various FPS values."""
        scenario_config = {"frame_count": 5, "frame_shape": (32, 32, 3), "fps": fps}
        frames = frame_data_factory(count=5, shape=(32, 32, 3))
        environment = mock_environment_factory(scenario_config)
        
        active_patches = []
        for patch_obj in environment["patches"].values():
            active_patches.append(patch_obj.start())
        
        try:
            result = raw_encoder.write_raw_mp4(
                frames,
                environment["paths"]["raw_path"],
                fps=fps
            )
            
            assert result == environment["paths"]["raw_path"]
            
            # Verify FPS was passed to FFmpeg command
            call_args = environment["patches"]["subprocess"].call_args
            if call_args:
                cmd = call_args[0][0] if call_args[0] else []
                assert str(fps) in cmd
                
        finally:
            for patch_obj in active_patches:
                patch_obj.stop()

    @pytest.mark.parametrize("frame_pattern", ["gradient", "random", "solid", "extreme"])
    def test_frame_data_patterns(self, frame_data_factory, mock_environment_factory, frame_pattern):
        """Test raw MP4 writing with different frame data patterns."""
        scenario_config = {"frame_count": 3, "frame_shape": (16, 16, 3)}
        frames = frame_data_factory(count=3, shape=(16, 16, 3), pattern=frame_pattern)
        environment = mock_environment_factory(scenario_config)
        
        active_patches = []
        for patch_obj in environment["patches"].values():
            active_patches.append(patch_obj.start())
        
        try:
            result = raw_encoder.write_raw_mp4(
                frames,
                environment["paths"]["raw_path"],
                fps=30
            )
            
            assert result == environment["paths"]["raw_path"]
            
            # Verify frames were processed
            assert environment["mocks"]["fromarray"].call_count == 3
            
            # Verify frame data was properly converted
            for call in environment["mocks"]["fromarray"].call_args_list:
                frame_data = call[0][0]
                assert isinstance(frame_data, np.ndarray)
                assert frame_data.dtype == np.uint8
                assert 0 <= frame_data.min() <= frame_data.max() <= 255
                
        finally:
            for patch_obj in active_patches:
                patch_obj.stop()

    def test_ffmpeg_command_structure_validation(self, frame_data_factory, mock_environment_factory):
        """Test that FFmpeg command has correct structure."""
        frames = frame_data_factory(count=3)
        scenario_config = {"fps": 30}
        environment = mock_environment_factory(scenario_config)
        
        active_patches = []
        for patch_obj in environment["patches"].values():
            active_patches.append(patch_obj.start())
        
        try:
            raw_encoder.write_raw_mp4(
                frames,
                environment["paths"]["raw_path"],
                fps=30
            )
            
            # Verify FFmpeg command structure
            call_args = environment["patches"]["subprocess"].call_args
            cmd = call_args[0][0] if call_args and call_args[0] else []
            
            expected_elements = [
                "ffmpeg",
                "-y",
                "-framerate",
                "30",
                "-i",
                "-c:v",
                "ffv1",
                str(environment["paths"]["raw_path"])
            ]
            
            for element in expected_elements:
                assert element in cmd
                
        finally:
            for patch_obj in active_patches:
                patch_obj.stop()

    def test_ffmpeg_error_handling(self, frame_data_factory, mock_environment_factory):
        """Test handling of FFmpeg execution errors."""
        frames = frame_data_factory(count=2)
        scenario_config = {}
        environment = mock_environment_factory(scenario_config, simulate_failure="ffmpeg_error")
        
        active_patches = []
        for patch_obj in environment["patches"].values():
            active_patches.append(patch_obj.start())
        
        try:
            with pytest.raises(subprocess.CalledProcessError):
                raw_encoder.write_raw_mp4(
                    frames,
                    environment["paths"]["raw_path"],
                    fps=30
                )
            
            # Verify FFmpeg was called despite the error
            environment["patches"]["subprocess"].assert_called_once()
            
        finally:
            for patch_obj in active_patches:
                patch_obj.stop()

    def test_ffmpeg_not_found_handling(self, frame_data_factory, mock_environment_factory):
        """Test handling when FFmpeg is not found."""
        frames = frame_data_factory(count=2)
        scenario_config = {}
        environment = mock_environment_factory(scenario_config, simulate_failure="ffmpeg_not_found")
        
        active_patches = []
        for patch_obj in environment["patches"].values():
            active_patches.append(patch_obj.start())
        
        try:
            with pytest.raises(FileNotFoundError):
                raw_encoder.write_raw_mp4(
                    frames,
                    environment["paths"]["raw_path"],
                    fps=30
                )
            
            # Verify FFmpeg was attempted
            environment["patches"]["subprocess"].assert_called_once()
            
        finally:
            for patch_obj in active_patches:
                patch_obj.stop()

    def test_temporary_directory_usage(self, frame_data_factory, mock_environment_factory):
        """Test proper usage of temporary directory."""
        frames = frame_data_factory(count=3)
        scenario_config = {}
        environment = mock_environment_factory(scenario_config)
        
        active_patches = []
        for patch_obj in environment["patches"].values():
            active_patches.append(patch_obj.start())
        
        try:
            raw_encoder.write_raw_mp4(
                frames,
                environment["paths"]["raw_path"],
                fps=30
            )
            
            # Verify temporary directory context manager was used
            environment["patches"]["tempdir"].assert_called_once()
            environment["mocks"]["tempdir"].__enter__.assert_called_once()
            environment["mocks"]["tempdir"].__exit__.assert_called_once()
            
        finally:
            for patch_obj in active_patches:
                patch_obj.stop()

    def test_frame_conversion_accuracy(self, mock_environment_factory):
        """Test accuracy of frame conversion from float32 to uint8."""
        # Create test frames with known values
        test_frames = [
            np.zeros((2, 2, 3), dtype=np.float32),  # All black
            np.ones((2, 2, 3), dtype=np.float32),   # All white
            np.full((2, 2, 3), 0.5, dtype=np.float32),  # Middle gray
        ]
        
        scenario_config = {}
        environment = mock_environment_factory(scenario_config)
        
        active_patches = []
        for patch_obj in environment["patches"].values():
            active_patches.append(patch_obj.start())
        
        try:
            raw_encoder.write_raw_mp4(
                test_frames,
                environment["paths"]["raw_path"],
                fps=30
            )
            
            # Verify conversion calls
            assert environment["mocks"]["fromarray"].call_count == 3
            
            # Check conversion accuracy
            call_args_list = environment["mocks"]["fromarray"].call_args_list
            
            # First frame (all black): should be 0
            black_frame = call_args_list[0][0][0]
            assert np.all(black_frame == 0)
            
            # Second frame (all white): should be 255
            white_frame = call_args_list[1][0][0]
            assert np.all(white_frame == 255)
            
            # Third frame (middle gray): should be 127 or 128
            gray_frame = call_args_list[2][0][0]
            assert np.all((gray_frame >= 127) & (gray_frame <= 128))
            
        finally:
            for patch_obj in active_patches:
                patch_obj.stop()

    def test_frame_clipping_behavior(self, mock_environment_factory):
        """Test that frame values are properly clipped to [0, 1] range."""
        # Create frames with out-of-range values
        test_frames = [
            np.full((2, 2, 3), -0.5, dtype=np.float32),  # Below range
            np.full((2, 2, 3), 1.5, dtype=np.float32),   # Above range
            np.array([[[2.0, -1.0, 0.5]]], dtype=np.float32),  # Mixed values
        ]
        
        scenario_config = {}
        environment = mock_environment_factory(scenario_config)
        
        active_patches = []
        for patch_obj in environment["patches"].values():
            active_patches.append(patch_obj.start())
        
        try:
            raw_encoder.write_raw_mp4(
                test_frames,
                environment["paths"]["raw_path"],
                fps=30
            )
            
            # Verify clipping behavior
            call_args_list = environment["mocks"]["fromarray"].call_args_list
            
            # Check all converted frames have values in [0, 255] range
            for call_args in call_args_list:
                converted_frame = call_args[0][0]
                assert converted_frame.min() >= 0
                assert converted_frame.max() <= 255
                assert converted_frame.dtype == np.uint8
                
        finally:
            for patch_obj in active_patches:
                patch_obj.stop()

    @pytest.mark.parametrize("frame_shape", [
        (1, 1, 3),      # Minimal
        (4, 4, 3),      # Small
        (64, 64, 3),    # Medium
        (128, 128, 3),  # Large
    ])
    def test_frame_resolution_variations(self, frame_data_factory, mock_environment_factory, frame_shape):
        """Test raw MP4 writing with various frame resolutions."""
        frames = frame_data_factory(count=2, shape=frame_shape)
        scenario_config = {}
        environment = mock_environment_factory(scenario_config)
        
        active_patches = []
        for patch_obj in environment["patches"].values():
            active_patches.append(patch_obj.start())
        
        try:
            result = raw_encoder.write_raw_mp4(
                frames,
                environment["paths"]["raw_path"],
                fps=30
            )
            
            assert result == environment["paths"]["raw_path"]
            
            # Verify frames were processed with correct shape
            for call_args in environment["mocks"]["fromarray"].call_args_list:
                converted_frame = call_args[0][0]
                assert converted_frame.shape == frame_shape
                
        finally:
            for patch_obj in active_patches:
                patch_obj.stop()

    def test_empty_frame_list(self, mock_environment_factory):
        """Test behavior with empty frame list."""
        frames = []  # Empty frame list
        scenario_config = {}
        environment = mock_environment_factory(scenario_config)
        
        active_patches = []
        for patch_obj in environment["patches"].values():
            active_patches.append(patch_obj.start())
        
        try:
            result = raw_encoder.write_raw_mp4(
                frames,
                environment["paths"]["raw_path"],
                fps=30
            )
            
            # Should still return the path
            assert result == environment["paths"]["raw_path"]
            
            # No frames should be processed
            environment["mocks"]["fromarray"].assert_not_called()
            
            # FFmpeg should still be called (though it may fail with no input)
            environment["patches"]["subprocess"].assert_called_once()
            
        finally:
            for patch_obj in active_patches:
                patch_obj.stop()

    def test_logging_behavior(self, frame_data_factory, mock_environment_factory):
        """Test that appropriate logging occurs during encoding."""
        frames = frame_data_factory(count=2)
        scenario_config = {}
        environment = mock_environment_factory(scenario_config)
        
        active_patches = []
        for patch_obj in environment["patches"].values():
            active_patches.append(patch_obj.start())
        
        with patch("goesvfi.pipeline.raw_encoder.LOGGER") as mock_logger:
            try:
                raw_encoder.write_raw_mp4(
                    frames,
                    environment["paths"]["raw_path"],
                    fps=30
                )
                
                # Verify logging calls
                assert mock_logger.info.call_count >= 3  # Start, encode, complete messages
                
                # Check specific log messages
                log_calls = [call[0][0] for call in mock_logger.info.call_args_list]
                assert any("Writing frames to temporary PNGs" in msg for msg in log_calls)
                assert any("Encoding frames to lossless MP4" in msg for msg in log_calls)
                assert any("Lossless encoding successful" in msg for msg in log_calls)
                
            finally:
                for patch_obj in active_patches:
                    patch_obj.stop()

    def test_subprocess_timeout_parameter(self, frame_data_factory, mock_environment_factory):
        """Test that subprocess timeout parameter is set correctly."""
        frames = frame_data_factory(count=2)
        scenario_config = {}
        environment = mock_environment_factory(scenario_config)
        
        active_patches = []
        for patch_obj in environment["patches"].values():
            active_patches.append(patch_obj.start())
        
        try:
            raw_encoder.write_raw_mp4(
                frames,
                environment["paths"]["raw_path"],
                fps=30
            )
            
            # Verify subprocess was called with timeout
            call_kwargs = environment["patches"]["subprocess"].call_args[1]
            assert call_kwargs.get("timeout") == 120
            assert call_kwargs.get("check") is True
            assert call_kwargs.get("capture_output") is True
            assert call_kwargs.get("text") is True
            
        finally:
            for patch_obj in active_patches:
                patch_obj.stop()

    def test_png_filename_pattern(self, frame_data_factory, mock_environment_factory):
        """Test that PNG filename pattern is correct."""
        frames = frame_data_factory(count=5)
        scenario_config = {}
        environment = mock_environment_factory(scenario_config)
        
        active_patches = []
        for patch_obj in environment["patches"].values():
            active_patches.append(patch_obj.start())
        
        try:
            raw_encoder.write_raw_mp4(
                frames,
                environment["paths"]["raw_path"],
                fps=30
            )
            
            # Verify PNG save calls with correct filenames
            save_calls = environment["mocks"]["img"].save.call_args_list
            assert len(save_calls) == 5
            
            # Check filename pattern (should be 000000.png, 000001.png, etc.)
            for i, call in enumerate(save_calls):
                filename = call[0][0]
                expected_filename = environment["paths"]["temp_dir"] / f"{i:06d}.png"
                assert filename == expected_filename
                
        finally:
            for patch_obj in active_patches:
                patch_obj.stop()

    def test_concurrent_encoding_simulation(self, frame_data_factory, mock_environment_factory):
        """Simulate multiple concurrent encoding operations."""
        import threading
        import time
        
        results = []
        errors = []
        
        def encoding_worker(worker_id):
            try:
                frames = frame_data_factory(count=2, shape=(4, 4, 3))
                scenario_config = {}
                environment = mock_environment_factory(scenario_config)
                
                active_patches = []
                for patch_obj in environment["patches"].values():
                    active_patches.append(patch_obj.start())
                
                try:
                    # Use different output path for each worker
                    output_path = environment["paths"]["raw_path"].parent / f"output_{worker_id}.mp4"
                    
                    result = raw_encoder.write_raw_mp4(
                        frames,
                        output_path,
                        fps=30
                    )
                    
                    results.append(f"worker_{worker_id}_success")
                    time.sleep(0.001)  # Small delay
                    
                finally:
                    for patch_obj in active_patches:
                        patch_obj.stop()
                        
            except Exception as e:
                errors.append(f"worker_{worker_id}_error: {e}")
        
        # Create multiple threads
        threads = []
        for i in range(3):
            thread = threading.Thread(target=encoding_worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Verify results
        assert len(results) == 3
        assert len(errors) == 0

    def test_memory_efficiency_large_batch(self, mock_environment_factory):
        """Test memory efficiency with large frame batches."""
        # Test with progressively larger frame counts
        frame_counts = [10, 50, 100]
        
        for count in frame_counts:
            # Create frames generator to simulate memory efficiency
            def frame_generator():
                for i in range(count):
                    yield np.ones((8, 8, 3), dtype=np.float32) * (i / count)
            
            scenario_config = {}
            environment = mock_environment_factory(scenario_config)
            
            active_patches = []
            for patch_obj in environment["patches"].values():
                active_patches.append(patch_obj.start())
            
            try:
                result = raw_encoder.write_raw_mp4(
                    frame_generator(),
                    environment["paths"]["raw_path"],
                    fps=30
                )
                
                assert result == environment["paths"]["raw_path"]
                assert environment["mocks"]["fromarray"].call_count == count
                
            finally:
                for patch_obj in active_patches:
                    patch_obj.stop()
                
            # Reset for next iteration
            environment["mocks"]["fromarray"].reset_mock()

    def test_integration_with_different_codecs(self, frame_data_factory, tmp_path):
        """Test integration considerations for different codec scenarios."""
        frames = frame_data_factory(count=3)
        raw_path = tmp_path / "output.mp4"
        
        # Test that FFV1 codec is always used (lossless requirement)
        with patch("goesvfi.pipeline.raw_encoder.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            
            with patch("goesvfi.pipeline.raw_encoder.tempfile.TemporaryDirectory"):
                with patch("goesvfi.pipeline.raw_encoder.Image.fromarray"):
                    raw_encoder.write_raw_mp4(frames, raw_path, fps=30)
                    
                    # Verify FFV1 codec is used
                    cmd = mock_run.call_args[0][0]
                    assert "-c:v" in cmd
                    assert "ffv1" in cmd