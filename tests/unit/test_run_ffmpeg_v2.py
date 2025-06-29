"""Optimized FFmpeg interpolation tests to speed up slow tests while maintaining coverage.

Optimizations applied:
- Shared fixtures for common FFmpeg setups and parameter configurations
- Parameterized test scenarios for comprehensive interpolation functionality validation
- Enhanced error handling and edge case coverage
- Mock-based testing to avoid actual FFmpeg execution and file I/O
- Comprehensive FFmpeg command building and filter chain testing
"""

import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, call
import pytest

from goesvfi.pipeline.run_ffmpeg import run_ffmpeg_interpolation


class TestRunFFmpegV2:
    """Optimized test class for FFmpeg interpolation functionality."""

    @pytest.fixture(scope="class")
    def ffmpeg_parameter_scenarios(self):
        """Define various FFmpeg parameter scenarios."""
        return {
            "basic_interpolation": {
                "fps": 30,
                "num_intermediate_frames": 1,
                "use_ffmpeg_interp": True,
                "filter_preset": "medium",
                "crf": 18,
                "expected_fps": 60,
            },
            "high_performance": {
                "fps": 60,
                "num_intermediate_frames": 3,
                "use_ffmpeg_interp": True,
                "filter_preset": "fast",
                "crf": 20,
                "expected_fps": 240,
            },
            "quality_focused": {
                "fps": 24,
                "num_intermediate_frames": 2,
                "use_ffmpeg_interp": True,
                "filter_preset": "slow",
                "crf": 15,
                "expected_fps": 72,
            },
            "no_interpolation": {
                "fps": 30,
                "num_intermediate_frames": 0,
                "use_ffmpeg_interp": False,
                "filter_preset": "medium",
                "crf": 18,
                "expected_fps": 30,
            },
            "debug_mode": {
                "fps": 30,
                "num_intermediate_frames": 1,
                "use_ffmpeg_interp": True,
                "debug_mode": True,
                "filter_preset": "medium",
                "crf": 18,
                "expected_loglevel": "debug",
            },
        }

    @pytest.fixture(scope="class")
    def filter_configurations(self):
        """Define various filter configuration scenarios."""
        return {
            "crop_only": {
                "crop_rect": (100, 50, 800, 600),
                "use_ffmpeg_interp": False,
                "apply_unsharp": False,
                "expected_filters": ["crop=800:600:100:50", "scale=trunc(iw/2)*2:trunc(ih/2)*2"],
            },
            "minterpolate_only": {
                "crop_rect": None,
                "use_ffmpeg_interp": True,
                "apply_unsharp": False,
                "mi_mode": "mci",
                "mc_mode": "obmc",
                "me_mode": "bidir",
                "expected_filters": ["minterpolate=", "scale=trunc(iw/2)*2:trunc(ih/2)*2"],
            },
            "unsharp_only": {
                "crop_rect": None,
                "use_ffmpeg_interp": False,
                "apply_unsharp": True,
                "unsharp_lx": 5,
                "unsharp_ly": 5,
                "unsharp_la": 1.2,
                "unsharp_cx": 3,
                "unsharp_cy": 3,
                "unsharp_ca": 0.5,
                "expected_filters": ["unsharp=5:5:1.2:3:3:0.5", "scale=trunc(iw/2)*2:trunc(ih/2)*2"],
            },
            "all_filters": {
                "crop_rect": (50, 25, 1920, 1080),
                "use_ffmpeg_interp": True,
                "apply_unsharp": True,
                "mi_mode": "mci",
                "mc_mode": "obmc",
                "me_mode": "bidir",
                "unsharp_lx": 3,
                "unsharp_ly": 3,
                "unsharp_la": 1.0,
                "unsharp_cx": 5,
                "unsharp_cy": 5,
                "unsharp_ca": 0.0,
                "expected_filters": ["crop=1920:1080:50:25", "minterpolate=", "unsharp=3:3:1.0:5:5:0.0", "scale=trunc(iw/2)*2:trunc(ih/2)*2"],
            },
        }

    @pytest.fixture
    def basic_parameters(self):
        """Create basic parameters for FFmpeg interpolation."""
        return {
            "fps": 30,
            "num_intermediate_frames": 1,
            "_use_preset_optimal": False,
            "crop_rect": None,
            "debug_mode": False,
            "use_ffmpeg_interp": True,
            "filter_preset": "medium",
            "mi_mode": "mci",
            "mc_mode": "obmc",
            "me_mode": "bidir",
            "me_algo": "epzs",
            "search_param": 32,
            "scd_mode": "fdi",
            "scd_threshold": 10.0,
            "minter_mb_size": 16,
            "minter_vsbmc": 0,
            "apply_unsharp": False,
            "unsharp_lx": 3,
            "unsharp_ly": 3,
            "unsharp_la": 1.0,
            "unsharp_cx": 5,
            "unsharp_cy": 5,
            "unsharp_ca": 0.0,
            "crf": 18,
            "bitrate_kbps": 5000,
            "bufsize_kb": 10000,
            "pix_fmt": "yuv420p",
        }

    @pytest.fixture
    def temp_environment_factory(self):
        """Factory for creating temporary test environments."""
        def create_environment(num_images=5, image_size=(4, 4)):
            temp_dir = Path(tempfile.mkdtemp())
            input_dir = temp_dir / "input"
            input_dir.mkdir()
            
            # Create test PNG files
            image_paths = []
            for i in range(num_images):
                png_file = input_dir / f"frame_{i:04d}.png"
                png_file.write_text("fake png content")  # Dummy content
                image_paths.append(png_file)
            
            output_path = temp_dir / "output.mp4"
            
            return {
                "input_dir": input_dir,
                "output_path": output_path,
                "image_paths": image_paths,
                "temp_dir": temp_dir,
            }
        return create_environment

    @pytest.fixture
    def mock_ffmpeg_command(self):
        """Mock the _run_ffmpeg_command function."""
        with patch("goesvfi.pipeline.run_ffmpeg._run_ffmpeg_command") as mock_cmd:
            mock_cmd.return_value = None  # Successful execution
            yield mock_cmd

    @pytest.mark.parametrize("scenario_name", [
        "basic_interpolation",
        "high_performance", 
        "quality_focused",
        "no_interpolation",
    ])
    def test_ffmpeg_interpolation_scenarios(self, temp_environment_factory, mock_ffmpeg_command, 
                                          basic_parameters, ffmpeg_parameter_scenarios, scenario_name):
        """Test FFmpeg interpolation with various parameter scenarios."""
        scenario = ffmpeg_parameter_scenarios[scenario_name]
        env = temp_environment_factory(num_images=5)
        
        # Update parameters with scenario values
        params = basic_parameters.copy()
        params.update(scenario)
        
        result = run_ffmpeg_interpolation(
            input_dir=env["input_dir"],
            output_mp4_path=env["output_path"],
            **params
        )
        
        # Verify result
        assert result == env["output_path"]
        
        # Verify FFmpeg command was called
        mock_ffmpeg_command.assert_called_once()
        
        # Get the command that was executed
        call_args = mock_ffmpeg_command.call_args
        cmd = call_args[0][0]
        description = call_args[0][1]
        
        # Verify basic command structure
        assert cmd[0] == "ffmpeg"
        assert "-hide_banner" in cmd
        assert "-loglevel" in cmd
        assert "-y" in cmd
        assert "-framerate" in cmd
        assert str(scenario["fps"]) in cmd
        assert str(env["input_dir"] / "*.png") in cmd
        assert str(env["output_path"]) in cmd
        assert description == "FFmpeg interpolation"
        
        # Verify interpolation-specific parameters
        if scenario["use_ffmpeg_interp"] and scenario["num_intermediate_frames"] > 0:
            vf_index = cmd.index("-vf")
            filter_str = cmd[vf_index + 1]
            expected_fps = scenario["fps"] * (scenario["num_intermediate_frames"] + 1)
            assert f"fps={expected_fps}" in filter_str

    def test_debug_mode_logging(self, temp_environment_factory, mock_ffmpeg_command, basic_parameters):
        """Test FFmpeg interpolation with debug mode enabled."""
        env = temp_environment_factory()
        params = basic_parameters.copy()
        params["debug_mode"] = True
        
        run_ffmpeg_interpolation(
            input_dir=env["input_dir"],
            output_mp4_path=env["output_path"],
            **params
        )
        
        cmd = mock_ffmpeg_command.call_args[0][0]
        loglevel_index = cmd.index("-loglevel")
        assert cmd[loglevel_index + 1] == "debug"

    @pytest.mark.parametrize("filter_config", [
        "crop_only",
        "minterpolate_only",
        "unsharp_only",
        "all_filters",
    ])
    def test_filter_configurations(self, temp_environment_factory, mock_ffmpeg_command, 
                                 basic_parameters, filter_configurations, filter_config):
        """Test various filter configuration combinations."""
        env = temp_environment_factory()
        config = filter_configurations[filter_config]
        
        params = basic_parameters.copy()
        params.update(config)
        
        run_ffmpeg_interpolation(
            input_dir=env["input_dir"],
            output_mp4_path=env["output_path"],
            **params
        )
        
        cmd = mock_ffmpeg_command.call_args[0][0]
        vf_index = cmd.index("-vf")
        filter_str = cmd[vf_index + 1]
        
        # Verify expected filters are present
        for expected_filter in config["expected_filters"]:
            assert expected_filter in filter_str
        
        # Verify filter order for all_filters scenario
        if filter_config == "all_filters":
            parts = filter_str.split(",")
            assert len(parts) == 4
            assert parts[0].startswith("crop=")
            assert parts[1].startswith("minterpolate=")
            assert parts[2].startswith("unsharp=")
            assert parts[3].startswith("scale=")

    @pytest.mark.parametrize("fps,num_frames,expected_output_fps", [
        (30, 0, 30),
        (30, 1, 60),
        (24, 2, 72),
        (60, 3, 240),
        (120, 7, 960),
    ])
    def test_fps_calculation_variations(self, temp_environment_factory, mock_ffmpeg_command, 
                                      basic_parameters, fps, num_frames, expected_output_fps):
        """Test FPS calculation for different intermediate frame counts."""
        env = temp_environment_factory()
        params = basic_parameters.copy()
        params.update({
            "fps": fps,
            "num_intermediate_frames": num_frames,
            "use_ffmpeg_interp": True,
        })
        
        run_ffmpeg_interpolation(
            input_dir=env["input_dir"],
            output_mp4_path=env["output_path"],
            **params
        )
        
        cmd = mock_ffmpeg_command.call_args[0][0]
        
        if num_frames > 0:
            vf_index = cmd.index("-vf")
            filter_str = cmd[vf_index + 1]
            assert f"fps={expected_output_fps}" in filter_str

    @pytest.mark.parametrize("crop_rect", [
        (0, 0, 1920, 1080),      # Top-left corner
        (100, 50, 800, 600),     # Standard crop
        (50, 25, 1920, 1080),    # Large crop with offset
        (200, 100, 640, 480),    # Small crop
    ])
    def test_crop_rectangle_variations(self, temp_environment_factory, mock_ffmpeg_command, 
                                     basic_parameters, crop_rect):
        """Test various crop rectangle configurations."""
        env = temp_environment_factory()
        params = basic_parameters.copy()
        params["crop_rect"] = crop_rect
        
        run_ffmpeg_interpolation(
            input_dir=env["input_dir"],
            output_mp4_path=env["output_path"],
            **params
        )
        
        cmd = mock_ffmpeg_command.call_args[0][0]
        vf_index = cmd.index("-vf")
        filter_str = cmd[vf_index + 1]
        
        x, y, w, h = crop_rect
        expected_crop = f"crop={w}:{h}:{x}:{y}"
        assert expected_crop in filter_str

    @pytest.mark.parametrize("minterpolate_params", [
        {"mi_mode": "mci", "mc_mode": "obmc", "me_mode": "bidir"},
        {"mi_mode": "blend", "mc_mode": "overlap", "me_mode": "bidir"},
        {"mi_mode": "mci", "mc_mode": "obmc", "me_mode": "bidir", "me_algo": "epzs", "search_param": 64},
        {"mi_mode": "mci", "mc_mode": "obmc", "me_mode": "bidir", "scd_mode": "fdi", "scd_threshold": 15.0},
    ])
    def test_minterpolate_parameter_variations(self, temp_environment_factory, mock_ffmpeg_command, 
                                             basic_parameters, minterpolate_params):
        """Test various minterpolate parameter combinations."""
        env = temp_environment_factory()
        params = basic_parameters.copy()
        params.update(minterpolate_params)
        params["use_ffmpeg_interp"] = True
        
        run_ffmpeg_interpolation(
            input_dir=env["input_dir"],
            output_mp4_path=env["output_path"],
            **params
        )
        
        cmd = mock_ffmpeg_command.call_args[0][0]
        vf_index = cmd.index("-vf")
        filter_str = cmd[vf_index + 1]
        
        # Verify minterpolate parameters are present
        assert "minterpolate=" in filter_str
        assert f"mi_mode={minterpolate_params['mi_mode']}" in filter_str
        assert f"mc_mode={minterpolate_params['mc_mode']}" in filter_str
        assert f"me_mode={minterpolate_params['me_mode']}" in filter_str
        
        # Check optional parameters
        if "me_algo" in minterpolate_params:
            assert f"me={minterpolate_params['me_algo']}" in filter_str
        if "search_param" in minterpolate_params and minterpolate_params["search_param"] > 0:
            assert f"search_param={minterpolate_params['search_param']}" in filter_str
        if "scd_mode" in minterpolate_params:
            assert f"scd={minterpolate_params['scd_mode']}" in filter_str
        if "scd_threshold" in minterpolate_params:
            assert f"scd_threshold={minterpolate_params['scd_threshold']}" in filter_str

    @pytest.mark.parametrize("unsharp_params", [
        {"unsharp_lx": 3, "unsharp_ly": 3, "unsharp_la": 1.0, "unsharp_cx": 5, "unsharp_cy": 5, "unsharp_ca": 0.0},
        {"unsharp_lx": 5, "unsharp_ly": 5, "unsharp_la": 1.2, "unsharp_cx": 3, "unsharp_cy": 3, "unsharp_ca": 0.5},
        {"unsharp_lx": 7, "unsharp_ly": 7, "unsharp_la": 0.8, "unsharp_cx": 7, "unsharp_cy": 7, "unsharp_ca": 0.3},
    ])
    def test_unsharp_filter_variations(self, temp_environment_factory, mock_ffmpeg_command, 
                                     basic_parameters, unsharp_params):
        """Test various unsharp filter parameter combinations."""
        env = temp_environment_factory()
        params = basic_parameters.copy()
        params.update(unsharp_params)
        params["apply_unsharp"] = True
        
        run_ffmpeg_interpolation(
            input_dir=env["input_dir"],
            output_mp4_path=env["output_path"],
            **params
        )
        
        cmd = mock_ffmpeg_command.call_args[0][0]
        vf_index = cmd.index("-vf")
        filter_str = cmd[vf_index + 1]
        
        expected_unsharp = f"unsharp={unsharp_params['unsharp_lx']}:{unsharp_params['unsharp_ly']}:{unsharp_params['unsharp_la']}:{unsharp_params['unsharp_cx']}:{unsharp_params['unsharp_cy']}:{unsharp_params['unsharp_ca']}"
        assert expected_unsharp in filter_str

    @pytest.mark.parametrize("encoding_params", [
        {"crf": 15, "bitrate_kbps": 0, "bufsize_kb": 0},  # CRF only
        {"crf": 23, "bitrate_kbps": 2000, "bufsize_kb": 4000},  # CRF with bitrate
        {"crf": 28, "bitrate_kbps": 1000, "bufsize_kb": 2000},  # Lower quality
        {"crf": 18, "bitrate_kbps": 8000, "bufsize_kb": 16000},  # High bitrate
    ])
    def test_encoding_parameter_variations(self, temp_environment_factory, mock_ffmpeg_command, 
                                         basic_parameters, encoding_params):
        """Test various encoding parameter combinations."""
        env = temp_environment_factory()
        params = basic_parameters.copy()
        params.update(encoding_params)
        
        run_ffmpeg_interpolation(
            input_dir=env["input_dir"],
            output_mp4_path=env["output_path"],
            **params
        )
        
        cmd = mock_ffmpeg_command.call_args[0][0]
        
        # Verify encoding parameters
        assert "-an" in cmd  # no audio
        assert "-vcodec" in cmd
        assert "libx264" in cmd
        assert "-preset" in cmd
        assert "-crf" in cmd
        assert str(encoding_params["crf"]) in cmd
        assert "-pix_fmt" in cmd
        assert params["pix_fmt"] in cmd
        
        # Check bitrate parameters
        if encoding_params["bitrate_kbps"] > 0:
            assert "-b:v" in cmd
            assert f"{encoding_params['bitrate_kbps']}k" in cmd
            assert "-bufsize" in cmd
            assert f"{encoding_params['bufsize_kb']}k" in cmd
        else:
            assert "-b:v" not in cmd
            assert "-bufsize" not in cmd

    @pytest.mark.parametrize("pix_fmt", [
        "yuv420p",
        "yuv422p", 
        "yuv444p",
        "yuv420p10le",
        "yuv422p10le",
    ])
    def test_pixel_format_variations(self, temp_environment_factory, mock_ffmpeg_command, 
                                   basic_parameters, pix_fmt):
        """Test various pixel format options."""
        env = temp_environment_factory()
        params = basic_parameters.copy()
        params["pix_fmt"] = pix_fmt
        
        run_ffmpeg_interpolation(
            input_dir=env["input_dir"],
            output_mp4_path=env["output_path"],
            **params
        )
        
        cmd = mock_ffmpeg_command.call_args[0][0]
        assert "-pix_fmt" in cmd
        assert pix_fmt in cmd

    def test_scale_filter_always_present(self, temp_environment_factory, mock_ffmpeg_command, basic_parameters):
        """Test that scale filter is always present in the filter chain."""
        env = temp_environment_factory()
        
        run_ffmpeg_interpolation(
            input_dir=env["input_dir"],
            output_mp4_path=env["output_path"],
            **basic_parameters
        )
        
        cmd = mock_ffmpeg_command.call_args[0][0]
        vf_index = cmd.index("-vf")
        filter_str = cmd[vf_index + 1]
        
        assert "scale=trunc(iw/2)*2:trunc(ih/2)*2" in filter_str

    def test_minterpolate_optional_parameters_handling(self, temp_environment_factory, mock_ffmpeg_command, basic_parameters):
        """Test handling of optional minterpolate parameters."""
        env = temp_environment_factory()
        params = basic_parameters.copy()
        params.update({
            "use_ffmpeg_interp": True,
            "me_algo": "",  # Empty should not be included
            "search_param": 0,  # Zero should not be included
            "scd_mode": None,  # None should not be included
            "scd_threshold": None,
            "minter_mb_size": None,
            "minter_vsbmc": 0,  # Zero should not be included
        })
        
        run_ffmpeg_interpolation(
            input_dir=env["input_dir"],
            output_mp4_path=env["output_path"],
            **params
        )
        
        cmd = mock_ffmpeg_command.call_args[0][0]
        vf_index = cmd.index("-vf")
        filter_str = cmd[vf_index + 1]
        
        # Check that optional parameters are not included when empty/zero/None
        assert "me=" not in filter_str
        assert "search_param=" not in filter_str
        assert "scd=" not in filter_str
        assert "scd_threshold=" not in filter_str
        assert "mb_size=" not in filter_str
        assert "vsbmc=" not in filter_str

    def test_minterpolate_default_me_algo_handling(self, temp_environment_factory, mock_ffmpeg_command, basic_parameters):
        """Test handling of default me_algo value."""
        env = temp_environment_factory()
        params = basic_parameters.copy()
        params.update({
            "use_ffmpeg_interp": True,
            "me_algo": "(default)",  # Should not be included
        })
        
        run_ffmpeg_interpolation(
            input_dir=env["input_dir"],
            output_mp4_path=env["output_path"],
            **params
        )
        
        cmd = mock_ffmpeg_command.call_args[0][0]
        vf_index = cmd.index("-vf")
        filter_str = cmd[vf_index + 1]
        
        assert "me=" not in filter_str

    def test_minterpolate_with_vsbmc_enabled(self, temp_environment_factory, mock_ffmpeg_command, basic_parameters):
        """Test minterpolate with vsbmc enabled."""
        env = temp_environment_factory()
        params = basic_parameters.copy()
        params.update({
            "use_ffmpeg_interp": True,
            "minter_vsbmc": 1,
        })
        
        run_ffmpeg_interpolation(
            input_dir=env["input_dir"],
            output_mp4_path=env["output_path"],
            **params
        )
        
        cmd = mock_ffmpeg_command.call_args[0][0]
        vf_index = cmd.index("-vf")
        filter_str = cmd[vf_index + 1]
        
        assert "vsbmc=1" in filter_str

    def test_input_directory_validation(self, basic_parameters):
        """Test validation when input directory doesn't exist."""
        non_existent_dir = Path("/non/existent/directory")
        output_path = Path("/tmp/output.mp4")
        
        with pytest.raises(ValueError, match="Input directory .* does not exist"):
            run_ffmpeg_interpolation(
                input_dir=non_existent_dir,
                output_mp4_path=output_path,
                **basic_parameters
            )

    def test_no_png_files_validation(self, basic_parameters):
        """Test validation when no PNG files found in input directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            empty_dir = Path(temp_dir)
            output_path = Path(temp_dir) / "output.mp4"
            
            with pytest.raises(ValueError, match="No PNG files found"):
                run_ffmpeg_interpolation(
                    input_dir=empty_dir,
                    output_mp4_path=output_path,
                    **basic_parameters
                )

    def test_ffmpeg_command_execution_failure(self, temp_environment_factory, basic_parameters):
        """Test handling of FFmpeg command execution failures."""
        env = temp_environment_factory()
        
        with patch("goesvfi.pipeline.run_ffmpeg._run_ffmpeg_command", side_effect=Exception("FFmpeg failed")):
            with pytest.raises(Exception, match="FFmpeg failed"):
                run_ffmpeg_interpolation(
                    input_dir=env["input_dir"],
                    output_mp4_path=env["output_path"],
                    **basic_parameters
                )

    def test_logging_behavior(self, temp_environment_factory, mock_ffmpeg_command, basic_parameters):
        """Test that appropriate logging occurs during execution."""
        env = temp_environment_factory()
        
        with patch("goesvfi.pipeline.run_ffmpeg.LOGGER") as mock_logger:
            run_ffmpeg_interpolation(
                input_dir=env["input_dir"],
                output_mp4_path=env["output_path"],
                **basic_parameters
            )
            
            # Should log the command and completion
            assert mock_logger.info.call_count >= 2
            
            # Check specific log messages
            log_calls = [call[0][0] for call in mock_logger.info.call_args_list]
            assert any("Running FFmpeg command" in msg for msg in log_calls)
            assert any("Interpolation completed" in msg for msg in log_calls)

    def test_monitor_memory_parameter_passing(self, temp_environment_factory, mock_ffmpeg_command, basic_parameters):
        """Test that monitor_memory parameter is passed correctly."""
        env = temp_environment_factory()
        
        run_ffmpeg_interpolation(
            input_dir=env["input_dir"],
            output_mp4_path=env["output_path"],
            **basic_parameters
        )
        
        # Check that monitor_memory=False was passed to _run_ffmpeg_command
        call_kwargs = mock_ffmpeg_command.call_args[1]
        assert call_kwargs["monitor_memory"] is False

    def test_path_object_conversion(self, temp_environment_factory, mock_ffmpeg_command, basic_parameters):
        """Test that Path objects are properly converted to strings in commands."""
        env = temp_environment_factory()
        
        # Ensure we're working with Path objects
        assert isinstance(env["input_dir"], Path)
        assert isinstance(env["output_path"], Path)
        
        run_ffmpeg_interpolation(
            input_dir=env["input_dir"],
            output_mp4_path=env["output_path"],
            **basic_parameters
        )
        
        cmd = mock_ffmpeg_command.call_args[0][0]
        
        # Check that paths were converted to strings in command
        assert str(env["input_dir"] / "*.png") in cmd
        assert str(env["output_path"]) in cmd

    def test_comprehensive_filter_chain_integration(self, temp_environment_factory, mock_ffmpeg_command, basic_parameters):
        """Test comprehensive filter chain integration with all options enabled."""
        env = temp_environment_factory()
        params = basic_parameters.copy()
        params.update({
            "crop_rect": (100, 50, 1920, 1080),
            "use_ffmpeg_interp": True,
            "num_intermediate_frames": 2,
            "apply_unsharp": True,
            "mi_mode": "mci",
            "mc_mode": "obmc",
            "me_mode": "bidir",
            "me_algo": "epzs",
            "search_param": 64,
            "scd_mode": "fdi",
            "scd_threshold": 12.0,
            "minter_mb_size": 32,
            "minter_vsbmc": 1,
            "unsharp_lx": 5,
            "unsharp_ly": 5,
            "unsharp_la": 1.2,
            "unsharp_cx": 3,
            "unsharp_cy": 3,
            "unsharp_ca": 0.5,
        })
        
        run_ffmpeg_interpolation(
            input_dir=env["input_dir"],
            output_mp4_path=env["output_path"],
            **params
        )
        
        cmd = mock_ffmpeg_command.call_args[0][0]
        vf_index = cmd.index("-vf")
        filter_str = cmd[vf_index + 1]
        
        # Verify all filter components are present
        assert "crop=1920:1080:100:50" in filter_str
        assert "minterpolate=" in filter_str
        assert "unsharp=5:5:1.2:3:3:0.5" in filter_str
        assert "scale=trunc(iw/2)*2:trunc(ih/2)*2" in filter_str
        
        # Verify minterpolate parameters
        assert "mi_mode=mci" in filter_str
        assert "mc_mode=obmc" in filter_str
        assert "me_mode=bidir" in filter_str
        assert "me=epzs" in filter_str
        assert "search_param=64" in filter_str
        assert "scd=fdi" in filter_str
        assert "scd_threshold=12.0" in filter_str
        assert "mb_size=32" in filter_str
        assert "vsbmc=1" in filter_str
        
        # Verify filter order
        parts = filter_str.split(",")
        assert len(parts) == 4
        assert parts[0].startswith("crop=")
        assert parts[1].startswith("minterpolate=")
        assert parts[2].startswith("unsharp=")
        assert parts[3].startswith("scale=")

    def test_edge_case_parameter_combinations(self, temp_environment_factory, mock_ffmpeg_command, basic_parameters):
        """Test edge case parameter combinations."""
        edge_cases = [
            {"fps": 1, "num_intermediate_frames": 1},  # Very low FPS
            {"fps": 120, "num_intermediate_frames": 15},  # Very high FPS
            {"crf": 0, "bitrate_kbps": 50000},  # Extreme quality settings
            {"crf": 51, "bitrate_kbps": 100},  # Low quality settings
        ]
        
        for case in edge_cases:
            env = temp_environment_factory()
            params = basic_parameters.copy()
            params.update(case)
            
            result = run_ffmpeg_interpolation(
                input_dir=env["input_dir"],
                output_mp4_path=env["output_path"],
                **params
            )
            
            assert result == env["output_path"]
            mock_ffmpeg_command.assert_called()
            mock_ffmpeg_command.reset_mock()

    def test_memory_efficiency_with_large_batches(self, mock_ffmpeg_command, basic_parameters):
        """Test memory efficiency considerations with large image batches."""
        # Test with progressively larger image batches
        batch_sizes = [10, 50, 100, 200]
        
        for batch_size in batch_sizes:
            temp_dir = Path(tempfile.mkdtemp())
            input_dir = temp_dir / "input"
            input_dir.mkdir()
            
            # Create many test images
            for i in range(batch_size):
                png_file = input_dir / f"frame_{i:04d}.png"
                png_file.write_text("fake content")
            
            output_path = temp_dir / "output.mp4"
            
            result = run_ffmpeg_interpolation(
                input_dir=input_dir,
                output_mp4_path=output_path,
                **basic_parameters
            )
            
            assert result == output_path
            mock_ffmpeg_command.assert_called()
            mock_ffmpeg_command.reset_mock()