"""Tests for WorkerFactory functionality (Optimized v2).

Optimizations:
- Shared fixture for common test arguments
- Parameterized tests for repeated patterns
- Mocked all file system operations
- Consolidated similar test cases
- Reduced test method count while maintaining coverage
"""

from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import pytest

from goesvfi.gui_components.worker_factory import WorkerFactory


@pytest.fixture()
def base_worker_args() -> dict[str, Any]:
    """Base required arguments for worker creation."""
    return {
        "in_dir": "/test/input",
        "out_file": "/test/output.mp4",
        "fps": 30.0,
        "multiplier": 2,
        "encoder": "libx264",
    }


@pytest.fixture()
def extended_worker_args(base_worker_args) -> dict[str, Any]:
    """Extended arguments with all optional parameters."""
    extended = base_worker_args.copy()
    extended.update({
        "max_workers": 8,
        "crop_rect": (10, 20, 800, 600),
        "rife_tiling_enabled": True,
        "rife_tile_size": 512,
        "rife_uhd": True,
        "rife_thread_spec": "2:4:6:8",
        "rife_tta_spatial": True,
        "rife_tta_temporal": True,
        "rife_model_key": "rife-v4.7",
        "sanchez_enabled": True,
        "sanchez_resolution_km": 2.0,
        "ffmpeg_args": {
            "use_ffmpeg_interp": True,
            "filter_preset": "fast",
            "mi_mode": "blend",
            "mc_mode": "aobmc",
            "me_mode": "epic",
            "me_algo": "hexbs",
            "search_param": 128,
            "scd": "fdiff",
            "scd_threshold": 15.0,
            "mb_size": "32",
            "vsbmc": True,
            "apply_unsharp": True,
            "unsharp_lx": 5,
            "unsharp_ly": 5,
            "unsharp_la": 1.5,
            "unsharp_cx": 0.7,
            "unsharp_cy": 0.7,
            "unsharp_ca": 0.2,
            "cr": 22,
            "bitrate_kbps": 10000,
            "bufsize_kb": 20000,
            "pix_fmt": "yuv444p",
        },
    })
    return extended


@pytest.fixture()
def mocked_worker_creation():
    """Fixture to mock VfiWorker creation and tempfile operations."""
    with patch("goesvfi.gui_components.worker_factory.VfiWorker") as mock_vfi_worker:
        with patch("goesvfi.gui_components.worker_factory.tempfile.mkdtemp") as mock_mkdtemp:
            mock_mkdtemp.return_value = "/tmp/sanchez_test"
            mock_worker_instance = Mock()
            mock_vfi_worker.return_value = mock_worker_instance
            yield mock_vfi_worker, mock_worker_instance


class TestWorkerFactory:
    """Test WorkerFactory functionality with optimized test methods."""

    def test_worker_creation_with_minimal_args(self, base_worker_args, mocked_worker_creation) -> None:
        """Test creating worker with minimal arguments."""
        mock_vfi_worker, mock_worker_instance = mocked_worker_creation

        worker = WorkerFactory.create_worker(base_worker_args)

        # Verify worker creation
        mock_vfi_worker.assert_called_once()
        call_kwargs = mock_vfi_worker.call_args[1]

        # Check required parameter mapping
        assert call_kwargs["in_dir"] == "/test/input"
        assert call_kwargs["out_file_path"] == "/test/output.mp4"
        assert call_kwargs["fps"] == 30.0
        assert call_kwargs["mid_count"] == 1  # multiplier - 1
        assert call_kwargs["encoder"] == "libx264"

        # Check defaults for optional parameters
        assert call_kwargs["max_workers"] == 4
        assert call_kwargs["use_ffmpeg_interp"] is False
        assert call_kwargs["rife_tile_enable"] is True
        assert call_kwargs["false_colour"] is False
        assert call_kwargs["debug_mode"] is False

        assert worker is mock_worker_instance

    def test_worker_creation_with_extended_args(self, extended_worker_args, mocked_worker_creation) -> None:
        """Test creating worker with complete arguments."""
        mock_vfi_worker, _ = mocked_worker_creation

        WorkerFactory.create_worker(extended_worker_args, debug_mode=True)

        call_kwargs = mock_vfi_worker.call_args[1]

        # Verify all parameters are set correctly
        expected_mappings = {
            "in_dir": "/test/input",
            "out_file_path": "/test/output.mp4",
            "fps": 30.0,
            "mid_count": 1,  # multiplier - 1
            "encoder": "libx264",
            "max_workers": 8,
            "debug_mode": True,
            "use_ffmpeg_interp": True,
            "filter_preset": "fast",
            "mi_mode": "blend",
            "mc_mode": "aobmc",
            "me_mode": "epic",
            "me_algo": "hexbs",
            "search_param": 128,
            "scd_mode": "fdiff",
            "scd_threshold": 15.0,
            "rife_tile_enable": True,
            "rife_tile_size": 512,
            "rife_uhd_mode": True,
            "rife_thread_spec": "2:4:6:8",
            "rife_tta_spatial": True,
            "rife_tta_temporal": True,
            "model_key": "rife-v4.7",
            "false_colour": True,
            "res_km": 2,
            "crop_rect": (10, 20, 800, 600),
        }

        for key, expected_value in expected_mappings.items():
            assert call_kwargs[key] == expected_value

    @pytest.mark.parametrize("missing_arg", ["in_dir", "out_file", "fps", "multiplier", "encoder"])
    def test_worker_creation_missing_required_args(self, base_worker_args, missing_arg) -> None:
        """Test worker creation with missing required arguments."""
        incomplete_args = base_worker_args.copy()
        del incomplete_args[missing_arg]

        with pytest.raises(ValueError, match=f"Missing required argument: {missing_arg}"):
            WorkerFactory.create_worker(incomplete_args)

    @pytest.mark.parametrize(
        "mb_size_input,expected_output",
        [
            ("64", 64),
            ("32", 32),
            ("invalid", 16),  # default
        ],
    )
    def test_mb_size_conversion(self, base_worker_args, mocked_worker_creation, mb_size_input, expected_output) -> None:
        """Test mb_size string to int conversion."""
        mock_vfi_worker, _ = mocked_worker_creation

        args_with_mb_size = base_worker_args.copy()
        args_with_mb_size["ffmpeg_args"] = {"mb_size": mb_size_input}

        WorkerFactory.create_worker(args_with_mb_size)

        call_kwargs = mock_vfi_worker.call_args[1]
        assert call_kwargs["minter_mb_size"] == expected_output

    @pytest.mark.parametrize(
        "vsbmc_input,expected_output",
        [
            (True, 1),
            (False, 0),
        ],
    )
    def test_vsbmc_conversion(self, base_worker_args, mocked_worker_creation, vsbmc_input, expected_output) -> None:
        """Test vsbmc boolean to int conversion."""
        mock_vfi_worker, _ = mocked_worker_creation

        args_with_vsbmc = base_worker_args.copy()
        args_with_vsbmc["ffmpeg_args"] = {"vsbmc": vsbmc_input}

        WorkerFactory.create_worker(args_with_vsbmc)

        call_kwargs = mock_vfi_worker.call_args[1]
        assert call_kwargs["minter_vsbmc"] == expected_output

    @pytest.mark.parametrize(
        "scd_mode,threshold_input,expected_threshold",
        [
            ("none", 25.0, 10.0),  # Should use default
            ("fdi", 25.0, 25.0),  # Should use provided
            ("fdiff", 30.0, 30.0),  # Should use provided
        ],
    )
    def test_scd_threshold_handling(
        self, base_worker_args, mocked_worker_creation, scd_mode, threshold_input, expected_threshold
    ) -> None:
        """Test scd_threshold handling based on scd_mode."""
        mock_vfi_worker, _ = mocked_worker_creation

        args_with_scd = base_worker_args.copy()
        args_with_scd["ffmpeg_args"] = {"scd": scd_mode, "scd_threshold": threshold_input}

        WorkerFactory.create_worker(args_with_scd)

        call_kwargs = mock_vfi_worker.call_args[1]
        assert call_kwargs["scd_threshold"] == expected_threshold

    def test_ffmpeg_args_none_handling(self, base_worker_args, mocked_worker_creation) -> None:
        """Test worker creation when ffmpeg_args is None."""
        mock_vfi_worker, _ = mocked_worker_creation

        args_with_none = base_worker_args.copy()
        args_with_none["ffmpeg_args"] = None

        WorkerFactory.create_worker(args_with_none)

        call_kwargs = mock_vfi_worker.call_args[1]

        # Should use defaults when ffmpeg_args is None
        assert call_kwargs["use_ffmpeg_interp"] is False
        assert call_kwargs["filter_preset"] == "slow"
        assert call_kwargs["mi_mode"] == "mci"

    def test_path_object_conversion(self, base_worker_args, mocked_worker_creation) -> None:
        """Test Path objects are converted to strings."""
        mock_vfi_worker, _ = mocked_worker_creation

        # Test Path objects are converted to strings
        path_args = base_worker_args.copy()
        path_args["in_dir"] = Path("/test/input")
        path_args["out_file"] = Path("/test/output.mp4")

        WorkerFactory.create_worker(path_args)

        call_kwargs = mock_vfi_worker.call_args[1]
        assert call_kwargs["in_dir"] == "/test/input"
        assert call_kwargs["out_file_path"] == "/test/output.mp4"

    @pytest.mark.parametrize(
        "multiplier,expected_mid_count",
        [
            (1, 0),
            (2, 1),
            (4, 3),
            (10, 9),
        ],
    )
    def test_multiplier_to_mid_count_conversion(
        self, base_worker_args, mocked_worker_creation, multiplier, expected_mid_count
    ) -> None:
        """Test edge case multiplier values."""
        mock_vfi_worker, _ = mocked_worker_creation

        args_with_multiplier = base_worker_args.copy()
        args_with_multiplier["multiplier"] = multiplier

        WorkerFactory.create_worker(args_with_multiplier)

        call_kwargs = mock_vfi_worker.call_args[1]
        assert call_kwargs["mid_count"] == expected_mid_count

    def test_temp_directory_creation(self, base_worker_args, mocked_worker_creation) -> None:
        """Test that temporary directory is created for Sanchez."""
        mock_vfi_worker, _ = mocked_worker_creation

        with patch("goesvfi.gui_components.worker_factory.tempfile.mkdtemp") as mock_mkdtemp:
            mock_mkdtemp.return_value = "/tmp/sanchez_gui_12345"

            WorkerFactory.create_worker(base_worker_args)

            # Check that mkdtemp was called with correct prefix
            mock_mkdtemp.assert_called_once_with(prefix="sanchez_gui_")

            # Check that the temp dir was passed to worker
            call_kwargs = mock_vfi_worker.call_args[1]
            assert call_kwargs["sanchez_gui_temp_dir"] == "/tmp/sanchez_gui_12345"

    def test_sanchez_resolution_conversion(self, base_worker_args, mocked_worker_creation) -> None:
        """Test sanchez resolution string to int conversion."""
        mock_vfi_worker, _ = mocked_worker_creation

        args_with_resolution = base_worker_args.copy()
        args_with_resolution["sanchez_resolution_km"] = "2.5"

        WorkerFactory.create_worker(args_with_resolution)

        call_kwargs = mock_vfi_worker.call_args[1]
        assert call_kwargs["res_km"] == 2  # int(float("2.5"))

    def test_worker_creation_exception_handling(self, base_worker_args, mocked_worker_creation) -> None:
        """Test exception handling during worker creation."""
        mock_vfi_worker, _ = mocked_worker_creation
        mock_vfi_worker.side_effect = Exception("Worker creation failed")

        with pytest.raises(Exception, match="Worker creation failed"):
            WorkerFactory.create_worker(base_worker_args)

    def test_logging_during_creation(self, base_worker_args, mocked_worker_creation) -> None:
        """Test that appropriate logging occurs during worker creation."""
        _mock_vfi_worker, _ = mocked_worker_creation

        with patch("goesvfi.gui_components.worker_factory.LOGGER") as mock_logger:
            WorkerFactory.create_worker(base_worker_args)

            # Should log successful creation
            mock_logger.info.assert_called_once_with("Created VfiWorker with parameters from MainTab")

    def test_static_method_accessibility(self, base_worker_args) -> None:
        """Test that WorkerFactory methods are static and don't require instantiation."""
        # Should be able to call without creating instance
        with patch("goesvfi.gui_components.worker_factory.VfiWorker") as mock_vfi_worker:
            with patch("goesvfi.gui_components.worker_factory.tempfile.mkdtemp"):
                mock_vfi_worker.return_value = Mock()

                # Should work without instantiating WorkerFactory
                worker = WorkerFactory.create_worker(base_worker_args)
                assert worker is not None

    def test_default_values_comprehensive(self, base_worker_args, mocked_worker_creation) -> None:
        """Test that proper default values are used for all optional parameters."""
        mock_vfi_worker, _ = mocked_worker_creation

        WorkerFactory.create_worker(base_worker_args)

        call_kwargs = mock_vfi_worker.call_args[1]

        # Comprehensive check of all defaults
        expected_defaults = {
            "filter_preset": "slow",
            "mi_mode": "mci",
            "mc_mode": "obmc",
            "me_mode": "bidir",
            "me_algo": "",
            "search_param": 96,
            "scd_mode": "fdi",
            "apply_unsharp": False,
            "unsharp_lx": 3,
            "unsharp_ly": 3,
            "unsharp_la": 1.0,
            "unsharp_cx": 0.5,
            "unsharp_cy": 0.5,
            "unsharp_ca": 0.0,
            "crf": 18,
            "bitrate_kbps": 7000,
            "bufsize_kb": 14000,
            "pix_fmt": "yuv420p",
            "rife_tile_size": 384,
            "rife_uhd_mode": False,
            "rife_thread_spec": "0:0:0:0",
            "rife_tta_spatial": False,
            "rife_tta_temporal": False,
            "model_key": "rife-v4.6",
            "use_preset_optimal": False,
            "skip_model": False,
            "crop_rect": None,
        }

        for key, expected_value in expected_defaults.items():
            assert call_kwargs[key] == expected_value
