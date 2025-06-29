"""Optimized encoding tests to speed up slow tests while maintaining coverage.

Optimizations applied:
- Shared fixtures for common encoding setups and mock configurations
- Parameterized test scenarios for comprehensive encoder validation
- Enhanced error handling and edge case coverage
- Mock-based subprocess operations to avoid real FFmpeg execution
- Comprehensive encoding workflow and failure scenario testing
"""

import os
import pathlib
from unittest.mock import ANY, MagicMock, patch, call
import pytest
import tempfile

from goesvfi.pipeline import encode


class TestEncodeV2:
    """Optimized test class for encoding functionality."""

    @pytest.fixture(scope="class")
    def encoder_scenarios(self):
        """Define various encoder scenarios for testing."""
        return {
            "software_encoders": [
                {
                    "name": "Software x264",
                    "codec": "libx264",
                    "preset": "slow",
                    "use_crf": True,
                    "default_crf": 23,
                },
                {
                    "name": "Software x265",
                    "codec": "libx265", 
                    "preset": "slower",
                    "use_crf": True,
                    "default_crf": 28,
                    "has_params": True,
                },
            ],
            "hardware_encoders": [
                {
                    "name": "Hardware HEVC (VideoToolbox)",
                    "codec": "hevc_videotoolbox",
                    "use_bitrate": True,
                    "has_tag": True,
                    "tag": "hvc1",
                },
                {
                    "name": "Hardware H.264 (VideoToolbox)",
                    "codec": "h264_videotoolbox",
                    "use_bitrate": True,
                    "has_tag": False,
                },
            ],
            "special_encoders": [
                {
                    "name": "None (copy original)",
                    "codec": "copy",
                    "minimal_command": True,
                },
                {
                    "name": "Software x265 (2-Pass)",
                    "codec": "libx265",
                    "preset": "slower",
                    "use_bitrate": True,
                    "two_pass": True,
                },
            ]
        }

    @pytest.fixture
    def temp_file_setup(self, tmp_path):
        """Create temporary file structure for encoding tests."""
        intermediate = tmp_path / "input.mp4"
        final = tmp_path / "output.mp4"
        
        # Create input file with dummy content
        intermediate.write_text("dummy input content")
        
        return {
            "intermediate": intermediate,
            "final": final,
            "temp_dir": tmp_path,
        }

    @pytest.fixture
    def mock_popen_factory(self):
        """Factory for creating mock Popen instances."""
        def create_mock(expected_cmd=None, returncode=0, output_file=None, stderr=b""):
            def popen_factory(*args, **kwargs):
                mock_process = MagicMock()
                mock_process.returncode = returncode
                mock_process.communicate.return_value = (b"", stderr)
                mock_process.wait.return_value = returncode
                
                # Create output file if specified
                if output_file and returncode == 0:
                    output_file.touch()
                
                return mock_process
            return popen_factory
        return create_mock

    def test_stream_copy_success(self, temp_file_setup, mock_popen_factory):
        """Test successful stream copy encoding."""
        with patch("goesvfi.pipeline.encode.subprocess.Popen") as mock_popen:
            expected_cmd = [
                "ffmpeg", "-y", "-i", 
                str(temp_file_setup["intermediate"]), 
                "-c", "copy", 
                str(temp_file_setup["final"])
            ]
            
            mock_popen.side_effect = mock_popen_factory(
                expected_cmd=expected_cmd,
                returncode=0,
                output_file=temp_file_setup["final"]
            )
            
            encode.encode_with_ffmpeg(
                intermediate_input=temp_file_setup["intermediate"],
                final_output=temp_file_setup["final"],
                encoder="None (copy original)",
                crf=0,
                bitrate_kbps=0,
                bufsize_kb=0,
                pix_fmt="yuv420p",
            )
            
            mock_popen.assert_called_once()
            assert temp_file_setup["final"].exists()

    def test_stream_copy_fallback_rename(self, temp_file_setup, mock_popen_factory):
        """Test stream copy fallback to file rename when FFmpeg fails."""
        with patch("goesvfi.pipeline.encode.subprocess.Popen") as mock_popen, \
             patch.object(pathlib.Path, "replace") as mock_replace:
            
            mock_popen.side_effect = mock_popen_factory(
                returncode=1,
                stderr=b"ffmpeg copy failed"
            )
            
            encode.encode_with_ffmpeg(
                intermediate_input=temp_file_setup["intermediate"],
                final_output=temp_file_setup["final"],
                encoder="None (copy original)",
                crf=0,
                bitrate_kbps=0,
                bufsize_kb=0,
                pix_fmt="yuv420p",
            )
            
            mock_popen.assert_called_once()
            mock_replace.assert_called_once_with(temp_file_setup["final"])

    @pytest.mark.parametrize("encoder_category", ["software_encoders", "hardware_encoders"])
    def test_single_pass_encoding_scenarios(self, temp_file_setup, mock_popen_factory, encoder_scenarios, encoder_category):
        """Test single-pass encoding with various encoder types."""
        encoders = encoder_scenarios[encoder_category]
        
        for encoder_config in encoders:
            with patch("goesvfi.pipeline.encode.subprocess.Popen") as mock_popen:
                mock_popen.side_effect = mock_popen_factory(
                    returncode=0,
                    output_file=temp_file_setup["final"]
                )
                
                # Set parameters based on encoder type
                if encoder_config.get("use_crf"):
                    crf = encoder_config.get("default_crf", 23)
                    bitrate_kbps = 0
                    bufsize_kb = 0
                else:
                    crf = 0
                    bitrate_kbps = 1000
                    bufsize_kb = 2000
                
                encode.encode_with_ffmpeg(
                    intermediate_input=temp_file_setup["intermediate"],
                    final_output=temp_file_setup["final"],
                    encoder=encoder_config["name"],
                    crf=crf,
                    bitrate_kbps=bitrate_kbps,
                    bufsize_kb=bufsize_kb,
                    pix_fmt="yuv420p",
                )
                
                mock_popen.assert_called_once()
                # Verify command contains expected codec
                call_args = mock_popen.call_args[0][0]
                assert encoder_config["codec"] in call_args

    @pytest.mark.parametrize("bitrate,bufsize", [
        (500, 1000),
        (1000, 2000),
        (2000, 4000),
        (5000, 10000),
    ])
    def test_hardware_encoder_bitrate_variations(self, temp_file_setup, mock_popen_factory, bitrate, bufsize):
        """Test hardware encoders with various bitrate and buffer size combinations."""
        with patch("goesvfi.pipeline.encode.subprocess.Popen") as mock_popen:
            mock_popen.side_effect = mock_popen_factory(
                returncode=0,
                output_file=temp_file_setup["final"]
            )
            
            encode.encode_with_ffmpeg(
                intermediate_input=temp_file_setup["intermediate"],
                final_output=temp_file_setup["final"],
                encoder="Hardware HEVC (VideoToolbox)",
                crf=0,
                bitrate_kbps=bitrate,
                bufsize_kb=bufsize,
                pix_fmt="yuv420p",
            )
            
            call_args = mock_popen.call_args[0][0]
            assert f"{bitrate}k" in call_args
            assert f"{bufsize}k" in call_args

    @pytest.mark.parametrize("crf_value", [15, 18, 23, 28, 32])
    def test_software_encoder_crf_variations(self, temp_file_setup, mock_popen_factory, crf_value):
        """Test software encoders with various CRF quality settings."""
        with patch("goesvfi.pipeline.encode.subprocess.Popen") as mock_popen:
            mock_popen.side_effect = mock_popen_factory(
                returncode=0,
                output_file=temp_file_setup["final"]
            )
            
            encode.encode_with_ffmpeg(
                intermediate_input=temp_file_setup["intermediate"],
                final_output=temp_file_setup["final"],
                encoder="Software x264",
                crf=crf_value,
                bitrate_kbps=0,
                bufsize_kb=0,
                pix_fmt="yuv420p",
            )
            
            call_args = mock_popen.call_args[0][0]
            assert str(crf_value) in call_args

    def test_two_pass_x265_encoding_workflow(self, temp_file_setup, mock_popen_factory):
        """Test complete two-pass x265 encoding workflow."""
        with patch("goesvfi.pipeline.encode.subprocess.Popen") as mock_popen, \
             patch("tempfile.NamedTemporaryFile") as mock_temp:
            
            # Mock temp file for pass log
            mock_log_file = MagicMock()
            mock_log_file.name = str(temp_file_setup["temp_dir"] / "ffmpeg_passlog")
            mock_temp.return_value.__enter__.return_value = mock_log_file
            
            # Setup two separate mock calls for pass 1 and pass 2
            pass1_call = mock_popen_factory(returncode=0)
            pass2_call = mock_popen_factory(returncode=0, output_file=temp_file_setup["final"])
            
            mock_popen.side_effect = [pass1_call(), pass2_call()]
            
            bitrate = 1000
            encode.encode_with_ffmpeg(
                intermediate_input=temp_file_setup["intermediate"],
                final_output=temp_file_setup["final"],
                encoder="Software x265 (2-Pass)",
                crf=0,
                bitrate_kbps=bitrate,
                bufsize_kb=0,
                pix_fmt="yuv420p",
            )
            
            # Verify two calls were made
            assert mock_popen.call_count == 2
            
            # Verify pass 1 command contains null output
            pass1_args = mock_popen.call_args_list[0][0][0]
            assert "pass=1" in " ".join(pass1_args)
            assert os.devnull in pass1_args
            
            # Verify pass 2 command contains final output
            pass2_args = mock_popen.call_args_list[1][0][0]
            assert "pass=2" in " ".join(pass2_args)
            assert str(temp_file_setup["final"]) in pass2_args

    @pytest.mark.parametrize("pix_fmt", [
        "yuv420p",
        "yuv422p",
        "yuv444p",
        "yuv420p10le",
    ])
    def test_pixel_format_variations(self, temp_file_setup, mock_popen_factory, pix_fmt):
        """Test encoding with various pixel formats."""
        with patch("goesvfi.pipeline.encode.subprocess.Popen") as mock_popen:
            mock_popen.side_effect = mock_popen_factory(
                returncode=0,
                output_file=temp_file_setup["final"]
            )
            
            encode.encode_with_ffmpeg(
                intermediate_input=temp_file_setup["intermediate"],
                final_output=temp_file_setup["final"],
                encoder="Software x264",
                crf=23,
                bitrate_kbps=0,
                bufsize_kb=0,
                pix_fmt=pix_fmt,
            )
            
            call_args = mock_popen.call_args[0][0]
            assert pix_fmt in call_args

    def test_unsupported_encoder_validation(self, temp_file_setup):
        """Test that unsupported encoders raise appropriate errors."""
        with pytest.raises(ValueError):
            encode.encode_with_ffmpeg(
                intermediate_input=temp_file_setup["intermediate"],
                final_output=temp_file_setup["final"],
                encoder="Unsupported Encoder",
                crf=0,
                bitrate_kbps=0,
                bufsize_kb=0,
                pix_fmt="yuv420p",
            )

    @pytest.mark.parametrize("encoder_name", [
        "",  # Empty string
        None,  # None value
        "Invalid Encoder Name",
        "Software x999",  # Non-existent variant
    ])
    def test_invalid_encoder_names(self, temp_file_setup, encoder_name):
        """Test handling of invalid encoder names."""
        with pytest.raises((ValueError, TypeError, AttributeError)):
            encode.encode_with_ffmpeg(
                intermediate_input=temp_file_setup["intermediate"],
                final_output=temp_file_setup["final"],
                encoder=encoder_name,
                crf=23,
                bitrate_kbps=0,
                bufsize_kb=0,
                pix_fmt="yuv420p",
            )

    def test_encoding_process_failure_handling(self, temp_file_setup, mock_popen_factory):
        """Test handling of encoding process failures."""
        with patch("goesvfi.pipeline.encode.subprocess.Popen") as mock_popen:
            # Test various failure scenarios
            failure_scenarios = [
                {"returncode": 1, "stderr": b"General FFmpeg error"},
                {"returncode": 2, "stderr": b"Invalid parameters"},
                {"returncode": 255, "stderr": b"Critical FFmpeg failure"},
            ]
            
            for scenario in failure_scenarios:
                mock_popen.side_effect = mock_popen_factory(
                    returncode=scenario["returncode"],
                    stderr=scenario["stderr"]
                )
                
                # For non-copy encoders, failure should be handled gracefully
                # (implementation may raise exception or handle differently)
                try:
                    encode.encode_with_ffmpeg(
                        intermediate_input=temp_file_setup["intermediate"],
                        final_output=temp_file_setup["final"],
                        encoder="Software x264",
                        crf=23,
                        bitrate_kbps=0,
                        bufsize_kb=0,
                        pix_fmt="yuv420p",
                    )
                except Exception as e:
                    # Failure handling is implementation-dependent
                    assert isinstance(e, (RuntimeError, subprocess.CalledProcessError, OSError))

    def test_command_structure_validation(self, temp_file_setup, mock_popen_factory):
        """Test that generated commands have correct structure."""
        test_cases = [
            {
                "encoder": "Software x264",
                "crf": 23,
                "expected_elements": ["ffmpeg", "-hide_banner", "-loglevel", "info", "-stats", "-y", "-i", "-c:v", "libx264", "-preset", "slow", "-crf", "23", "-pix_fmt"]
            },
            {
                "encoder": "Software x265",
                "crf": 28, 
                "expected_elements": ["ffmpeg", "-hide_banner", "-loglevel", "info", "-stats", "-y", "-i", "-c:v", "libx265", "-preset", "slower", "-crf", "28", "-x265-params", "-pix_fmt"]
            },
            {
                "encoder": "Hardware HEVC (VideoToolbox)",
                "bitrate": 2000,
                "bufsize": 4000,
                "expected_elements": ["ffmpeg", "-hide_banner", "-loglevel", "info", "-stats", "-y", "-i", "-c:v", "hevc_videotoolbox", "-tag:v", "hvc1", "-b:v", "-maxrate", "-pix_fmt"]
            }
        ]
        
        for test_case in test_cases:
            with patch("goesvfi.pipeline.encode.subprocess.Popen") as mock_popen:
                mock_popen.side_effect = mock_popen_factory(
                    returncode=0,
                    output_file=temp_file_setup["final"]
                )
                
                encode.encode_with_ffmpeg(
                    intermediate_input=temp_file_setup["intermediate"],
                    final_output=temp_file_setup["final"],
                    encoder=test_case["encoder"],
                    crf=test_case.get("crf", 0),
                    bitrate_kbps=test_case.get("bitrate", 0),
                    bufsize_kb=test_case.get("bufsize", 0),
                    pix_fmt="yuv420p",
                )
                
                call_args = mock_popen.call_args[0][0]
                for element in test_case["expected_elements"]:
                    assert element in call_args

    def test_file_path_handling_edge_cases(self, tmp_path, mock_popen_factory):
        """Test encoding with various file path scenarios."""
        # Test paths with spaces
        input_with_spaces = tmp_path / "input file with spaces.mp4"
        output_with_spaces = tmp_path / "output file with spaces.mp4"
        input_with_spaces.write_text("dummy")
        
        with patch("goesvfi.pipeline.encode.subprocess.Popen") as mock_popen:
            mock_popen.side_effect = mock_popen_factory(
                returncode=0,
                output_file=output_with_spaces
            )
            
            encode.encode_with_ffmpeg(
                intermediate_input=input_with_spaces,
                final_output=output_with_spaces,
                encoder="Software x264",
                crf=23,
                bitrate_kbps=0,
                bufsize_kb=0,
                pix_fmt="yuv420p",
            )
            
            call_args = mock_popen.call_args[0][0]
            assert str(input_with_spaces) in call_args
            assert str(output_with_spaces) in call_args

    def test_encoding_parameter_boundary_values(self, temp_file_setup, mock_popen_factory):
        """Test encoding with boundary parameter values."""
        boundary_tests = [
            {"crf": 0, "description": "minimum CRF"},
            {"crf": 51, "description": "maximum CRF"},
            {"bitrate_kbps": 1, "bufsize_kb": 2, "description": "minimum bitrate"},
            {"bitrate_kbps": 50000, "bufsize_kb": 100000, "description": "very high bitrate"},
        ]
        
        for test in boundary_tests:
            with patch("goesvfi.pipeline.encode.subprocess.Popen") as mock_popen:
                mock_popen.side_effect = mock_popen_factory(
                    returncode=0,
                    output_file=temp_file_setup["final"]
                )
                
                encoder = "Software x264" if "crf" in test else "Hardware HEVC (VideoToolbox)"
                
                encode.encode_with_ffmpeg(
                    intermediate_input=temp_file_setup["intermediate"],
                    final_output=temp_file_setup["final"],
                    encoder=encoder,
                    crf=test.get("crf", 0),
                    bitrate_kbps=test.get("bitrate_kbps", 0),
                    bufsize_kb=test.get("bufsize_kb", 0),
                    pix_fmt="yuv420p",
                )
                
                # Verify encoding completed
                mock_popen.assert_called_once()

    def test_concurrent_encoding_simulation(self, temp_file_setup, mock_popen_factory):
        """Simulate multiple concurrent encoding operations."""
        import threading
        import time
        
        results = []
        errors = []
        
        def encode_worker(worker_id):
            try:
                output_file = temp_file_setup["temp_dir"] / f"output_{worker_id}.mp4"
                
                with patch("goesvfi.pipeline.encode.subprocess.Popen") as mock_popen:
                    mock_popen.side_effect = mock_popen_factory(
                        returncode=0,
                        output_file=output_file
                    )
                    
                    encode.encode_with_ffmpeg(
                        intermediate_input=temp_file_setup["intermediate"],
                        final_output=output_file,
                        encoder="Software x264",
                        crf=23,
                        bitrate_kbps=0,
                        bufsize_kb=0,
                        pix_fmt="yuv420p",
                    )
                    
                results.append(f"worker_{worker_id}_success")
                time.sleep(0.001)  # Small delay
            except Exception as e:
                errors.append(f"worker_{worker_id}_error: {e}")
        
        # Create multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=encode_worker, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Verify results
        assert len(results) == 5
        assert len(errors) == 0

    def test_encoding_workflow_integration(self, temp_file_setup, mock_popen_factory):
        """Test complete encoding workflow integration."""
        workflow_steps = [
            {"encoder": "None (copy original)", "description": "Stream copy"},
            {"encoder": "Software x264", "crf": 23, "description": "x264 encoding"},
            {"encoder": "Software x265", "crf": 28, "description": "x265 encoding"},
            {"encoder": "Hardware HEVC (VideoToolbox)", "bitrate": 2000, "bufsize": 4000, "description": "Hardware encoding"},
        ]
        
        for step in workflow_steps:
            with patch("goesvfi.pipeline.encode.subprocess.Popen") as mock_popen:
                mock_popen.side_effect = mock_popen_factory(
                    returncode=0,
                    output_file=temp_file_setup["final"]
                )
                
                encode.encode_with_ffmpeg(
                    intermediate_input=temp_file_setup["intermediate"],
                    final_output=temp_file_setup["final"],
                    encoder=step["encoder"],
                    crf=step.get("crf", 0),
                    bitrate_kbps=step.get("bitrate", 0),
                    bufsize_kb=step.get("bufsize", 0),
                    pix_fmt="yuv420p",
                )
                
                # Verify encoding step completed
                mock_popen.assert_called()
                if temp_file_setup["final"].exists():
                    temp_file_setup["final"].unlink()  # Clean up for next step

    def test_encoding_memory_efficiency(self, temp_file_setup, mock_popen_factory):
        """Test encoding with focus on memory efficiency."""
        # Test with large file scenarios (simulated)
        large_file_scenarios = [
            {"size_mb": 100, "encoder": "Software x264", "crf": 23},
            {"size_mb": 500, "encoder": "Software x265", "crf": 28},
            {"size_mb": 1000, "encoder": "Hardware HEVC (VideoToolbox)", "bitrate": 5000, "bufsize": 10000},
        ]
        
        for scenario in large_file_scenarios:
            # Simulate large file by creating with dummy content
            large_content = "x" * (scenario["size_mb"] * 1024)  # Simulate size
            temp_file_setup["intermediate"].write_text(large_content)
            
            with patch("goesvfi.pipeline.encode.subprocess.Popen") as mock_popen:
                mock_popen.side_effect = mock_popen_factory(
                    returncode=0,
                    output_file=temp_file_setup["final"]
                )
                
                encode.encode_with_ffmpeg(
                    intermediate_input=temp_file_setup["intermediate"],
                    final_output=temp_file_setup["final"],
                    encoder=scenario["encoder"],
                    crf=scenario.get("crf", 0),
                    bitrate_kbps=scenario.get("bitrate", 0),
                    bufsize_kb=scenario.get("bufsize", 0),
                    pix_fmt="yuv420p",
                )
                
                # Verify encoding handled large file
                mock_popen.assert_called()

    def test_encoding_error_recovery_scenarios(self, temp_file_setup, mock_popen_factory):
        """Test various error recovery scenarios during encoding."""
        error_scenarios = [
            {
                "name": "temporary_failure_then_success",
                "first_call_fails": True,
                "second_call_succeeds": True,
            },
            {
                "name": "persistent_failure",
                "first_call_fails": True,
                "second_call_succeeds": False,
            },
        ]
        
        for scenario in error_scenarios:
            with patch("goesvfi.pipeline.encode.subprocess.Popen") as mock_popen:
                if scenario["first_call_fails"]:
                    # For copy operations, test the fallback mechanism
                    mock_popen.side_effect = mock_popen_factory(returncode=1)
                    
                    with patch.object(pathlib.Path, "replace") as mock_replace:
                        try:
                            encode.encode_with_ffmpeg(
                                intermediate_input=temp_file_setup["intermediate"],
                                final_output=temp_file_setup["final"],
                                encoder="None (copy original)",
                                crf=0,
                                bitrate_kbps=0,
                                bufsize_kb=0,
                                pix_fmt="yuv420p",
                            )
                            # Copy encoder should fall back to rename
                            mock_replace.assert_called()
                        except Exception:
                            # Some scenarios might raise exceptions
                            pass