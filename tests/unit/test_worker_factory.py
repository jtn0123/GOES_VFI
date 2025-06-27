"""Tests for WorkerFactory functionality."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from goesvfi.gui_components.worker_factory import WorkerFactory


class TestWorkerFactory:
    """Test WorkerFactory functionality."""

    @pytest.fixture()
    def minimal_args(self):
        """Minimal required arguments for worker creation."""
        return {
            "in_dir": "/test/input",
            "out_file": "/test/output.mp4",
            "fps": 30.0,
            "multiplier": 2,
            "encoder": "libx264",
        }

    @pytest.fixture()
    def complete_args(self):
        """Complete arguments with all optional parameters."""
        return {
            "in_dir": "/test/input",
            "out_file": "/test/output.mp4",
            "fps": 30.0,
            "multiplier": 4,
            "encoder": "libx264",
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
        }

    @patch("goesvfi.gui_components.worker_factory.VfiWorker")
    @patch("goesvfi.gui_components.worker_factory.tempfile.mkdtemp")
    def test_create_worker_minimal_args(self, mock_mkdtemp, mock_vfi_worker, minimal_args) -> None:
        """Test creating worker with minimal arguments."""
        mock_mkdtemp.return_value = "/tmp/sanchez_test"
        mock_worker_instance = Mock()
        mock_vfi_worker.return_value = mock_worker_instance

        worker = WorkerFactory.create_worker(minimal_args)

        # Check that VfiWorker was called
        mock_vfi_worker.assert_called_once()
        call_kwargs = mock_vfi_worker.call_args[1]

        # Check required parameter mapping
        assert call_kwargs["in_dir"] == "/test/input"
        assert call_kwargs["out_file_path"] == "/test/output.mp4"
        assert call_kwargs["fps"] == 30.0
        assert call_kwargs["mid_count"] == 1  # multiplier - 1
        assert call_kwargs["encoder"] == "libx264"

        # Check defaults for optional parameters
        assert call_kwargs["max_workers"] == 4  # default
        assert call_kwargs["use_ffmpeg_interp"] is False
        assert call_kwargs["rife_tile_enable"] is True  # default
        assert call_kwargs["false_colour"] is False  # default
        assert call_kwargs["debug_mode"] is False  # default

        assert worker is mock_worker_instance

    @patch("goesvfi.gui_components.worker_factory.VfiWorker")
    @patch("goesvfi.gui_components.worker_factory.tempfile.mkdtemp")
    def test_create_worker_complete_args(self, mock_mkdtemp, mock_vfi_worker, complete_args) -> None:
        """Test creating worker with complete arguments."""
        mock_mkdtemp.return_value = "/tmp/sanchez_test"
        mock_worker_instance = Mock()
        mock_vfi_worker.return_value = mock_worker_instance

        WorkerFactory.create_worker(complete_args, debug_mode=True)

        mock_vfi_worker.assert_called_once()
        call_kwargs = mock_vfi_worker.call_args[1]

        # Check basic parameters
        assert call_kwargs["in_dir"] == "/test/input"
        assert call_kwargs["out_file_path"] == "/test/output.mp4"
        assert call_kwargs["fps"] == 30.0
        assert call_kwargs["mid_count"] == 3  # multiplier - 1
        assert call_kwargs["encoder"] == "libx264"
        assert call_kwargs["max_workers"] == 8
        assert call_kwargs["debug_mode"] is True

        # Check FFmpeg settings
        assert call_kwargs["use_ffmpeg_interp"] is True
        assert call_kwargs["filter_preset"] == "fast"
        assert call_kwargs["mi_mode"] == "blend"
        assert call_kwargs["mc_mode"] == "aobmc"
        assert call_kwargs["me_mode"] == "epic"
        assert call_kwargs["me_algo"] == "hexbs"
        assert call_kwargs["search_param"] == 128
        assert call_kwargs["scd_mode"] == "fdiff"
        assert call_kwargs["scd_threshold"] == 15.0

        # Check unsharp settings
        assert call_kwargs["apply_unsharp"] is True
        assert call_kwargs["unsharp_lx"] == 5
        assert call_kwargs["unsharp_ly"] == 5
        assert call_kwargs["unsharp_la"] == 1.5
        assert call_kwargs["unsharp_cx"] == 0.7
        assert call_kwargs["unsharp_cy"] == 0.7
        assert call_kwargs["unsharp_ca"] == 0.2

        # Check quality settings
        assert call_kwargs["crf"] == 22
        assert call_kwargs["bitrate_kbps"] == 10000
        assert call_kwargs["bufsize_kb"] == 20000
        assert call_kwargs["pix_fmt"] == "yuv444p"

        # Check RIFE settings
        assert call_kwargs["rife_tile_enable"] is True
        assert call_kwargs["rife_tile_size"] == 512
        assert call_kwargs["rife_uhd_mode"] is True
        assert call_kwargs["rife_thread_spec"] == "2:4:6:8"
        assert call_kwargs["rife_tta_spatial"] is True
        assert call_kwargs["rife_tta_temporal"] is True
        assert call_kwargs["model_key"] == "rife-v4.7"

        # Check Sanchez settings
        assert call_kwargs["false_colour"] is True
        assert call_kwargs["res_km"] == 2

        # Check crop rect
        assert call_kwargs["crop_rect"] == (10, 20, 800, 600)

    def test_create_worker_missing_required_args(self) -> None:
        """Test worker creation with missing required arguments."""
        incomplete_args = {
            "in_dir": "/test/input",
            # Missing other required args
        }

        with pytest.raises(ValueError, match="Missing required argument"):
            WorkerFactory.create_worker(incomplete_args)

    @pytest.mark.parametrize("missing_arg", ["in_dir", "out_file", "fps", "multiplier", "encoder"])
    def test_create_worker_missing_each_required_arg(self, minimal_args, missing_arg) -> None:
        """Test worker creation fails when each required argument is missing."""
        del minimal_args[missing_arg]

        with pytest.raises(ValueError, match=f"Missing required argument: {missing_arg}"):
            WorkerFactory.create_worker(minimal_args)

    @patch("goesvfi.gui_components.worker_factory.VfiWorker")
    @patch("goesvfi.gui_components.worker_factory.tempfile.mkdtemp")
    def test_create_worker_ffmpeg_args_none(self, mock_mkdtemp, mock_vfi_worker, minimal_args) -> None:
        """Test worker creation when ffmpeg_args is None."""
        mock_mkdtemp.return_value = "/tmp/sanchez_test"
        mock_worker_instance = Mock()
        mock_vfi_worker.return_value = mock_worker_instance

        minimal_args["ffmpeg_args"] = None

        WorkerFactory.create_worker(minimal_args)

        mock_vfi_worker.assert_called_once()
        call_kwargs = mock_vfi_worker.call_args[1]

        # Should use defaults when ffmpeg_args is None
        assert call_kwargs["use_ffmpeg_interp"] is False
        assert call_kwargs["filter_preset"] == "slow"
        assert call_kwargs["mi_mode"] == "mci"

    @patch("goesvfi.gui_components.worker_factory.VfiWorker")
    @patch("goesvfi.gui_components.worker_factory.tempfile.mkdtemp")
    def test_create_worker_mb_size_conversion(self, mock_mkdtemp, mock_vfi_worker, minimal_args) -> None:
        """Test mb_size string to int conversion."""
        mock_mkdtemp.return_value = "/tmp/sanchez_test"
        mock_worker_instance = Mock()
        mock_vfi_worker.return_value = mock_worker_instance

        minimal_args["ffmpeg_args"] = {"mb_size": "64"}

        WorkerFactory.create_worker(minimal_args)

        call_kwargs = mock_vfi_worker.call_args[1]
        assert call_kwargs["minter_mb_size"] == 64

    @patch("goesvfi.gui_components.worker_factory.VfiWorker")
    @patch("goesvfi.gui_components.worker_factory.tempfile.mkdtemp")
    def test_create_worker_mb_size_invalid(self, mock_mkdtemp, mock_vfi_worker, minimal_args) -> None:
        """Test mb_size with invalid string."""
        mock_mkdtemp.return_value = "/tmp/sanchez_test"
        mock_worker_instance = Mock()
        mock_vfi_worker.return_value = mock_worker_instance

        minimal_args["ffmpeg_args"] = {"mb_size": "invalid"}

        WorkerFactory.create_worker(minimal_args)

        call_kwargs = mock_vfi_worker.call_args[1]
        assert call_kwargs["minter_mb_size"] == 16  # default

    @patch("goesvfi.gui_components.worker_factory.VfiWorker")
    @patch("goesvfi.gui_components.worker_factory.tempfile.mkdtemp")
    def test_create_worker_vsbmc_conversion(self, mock_mkdtemp, mock_vfi_worker, minimal_args) -> None:
        """Test vsbmc boolean to int conversion."""
        mock_mkdtemp.return_value = "/tmp/sanchez_test"
        mock_worker_instance = Mock()
        mock_vfi_worker.return_value = mock_worker_instance

        minimal_args["ffmpeg_args"] = {"vsbmc": True}

        WorkerFactory.create_worker(minimal_args)

        call_kwargs = mock_vfi_worker.call_args[1]
        assert call_kwargs["minter_vsbmc"] == 1

        # Test false case
        minimal_args["ffmpeg_args"] = {"vsbmc": False}
        WorkerFactory.create_worker(minimal_args)
        call_kwargs = mock_vfi_worker.call_args[1]
        assert call_kwargs["minter_vsbmc"] == 0

    @patch("goesvfi.gui_components.worker_factory.VfiWorker")
    @patch("goesvfi.gui_components.worker_factory.tempfile.mkdtemp")
    def test_create_worker_scd_threshold_handling(self, mock_mkdtemp, mock_vfi_worker, minimal_args) -> None:
        """Test scd_threshold handling based on scd_mode."""
        mock_mkdtemp.return_value = "/tmp/sanchez_test"
        mock_worker_instance = Mock()
        mock_vfi_worker.return_value = mock_worker_instance

        # Test with scd_mode = "none" - should use default threshold
        minimal_args["ffmpeg_args"] = {"scd": "none", "scd_threshold": 25.0}
        WorkerFactory.create_worker(minimal_args)
        call_kwargs = mock_vfi_worker.call_args[1]
        assert call_kwargs["scd_threshold"] == 10.0  # default, not the provided value

        # Test with scd_mode != "none" - should use provided threshold
        minimal_args["ffmpeg_args"] = {"scd": "fdi", "scd_threshold": 25.0}
        WorkerFactory.create_worker(minimal_args)
        call_kwargs = mock_vfi_worker.call_args[1]
        assert call_kwargs["scd_threshold"] == 25.0

    @patch("goesvfi.gui_components.worker_factory.VfiWorker")
    @patch("goesvfi.gui_components.worker_factory.tempfile.mkdtemp")
    def test_create_worker_sanchez_resolution_conversion(self, mock_mkdtemp, mock_vfi_worker, minimal_args) -> None:
        """Test sanchez resolution string to int conversion."""
        mock_mkdtemp.return_value = "/tmp/sanchez_test"
        mock_worker_instance = Mock()
        mock_vfi_worker.return_value = mock_worker_instance

        minimal_args["sanchez_resolution_km"] = "2.5"

        WorkerFactory.create_worker(minimal_args)

        call_kwargs = mock_vfi_worker.call_args[1]
        assert call_kwargs["res_km"] == 2  # int(float("2.5"))

    @patch("goesvfi.gui_components.worker_factory.VfiWorker")
    def test_create_worker_temp_dir_creation(self, mock_vfi_worker, minimal_args) -> None:
        """Test that temporary directory is created for Sanchez."""
        mock_worker_instance = Mock()
        mock_vfi_worker.return_value = mock_worker_instance

        with patch("goesvfi.gui_components.worker_factory.tempfile.mkdtemp") as mock_mkdtemp:
            mock_mkdtemp.return_value = "/tmp/sanchez_gui_12345"

            WorkerFactory.create_worker(minimal_args)

            # Check that mkdtemp was called with correct prefix
            mock_mkdtemp.assert_called_once_with(prefix="sanchez_gui_")

            # Check that the temp dir was passed to worker
            call_kwargs = mock_vfi_worker.call_args[1]
            assert call_kwargs["sanchez_gui_temp_dir"] == "/tmp/sanchez_gui_12345"

    @patch("goesvfi.gui_components.worker_factory.VfiWorker")
    @patch("goesvfi.gui_components.worker_factory.tempfile.mkdtemp")
    def test_create_worker_default_values(self, mock_mkdtemp, mock_vfi_worker, minimal_args) -> None:
        """Test that proper default values are used for optional parameters."""
        mock_mkdtemp.return_value = "/tmp/sanchez_test"
        mock_worker_instance = Mock()
        mock_vfi_worker.return_value = mock_worker_instance

        WorkerFactory.create_worker(minimal_args)

        call_kwargs = mock_vfi_worker.call_args[1]

        # Check FFmpeg defaults
        assert call_kwargs["filter_preset"] == "slow"
        assert call_kwargs["mi_mode"] == "mci"
        assert call_kwargs["mc_mode"] == "obmc"
        assert call_kwargs["me_mode"] == "bidir"
        assert call_kwargs["me_algo"] == ""
        assert call_kwargs["search_param"] == 96
        assert call_kwargs["scd_mode"] == "fdi"

        # Check unsharp defaults
        assert call_kwargs["apply_unsharp"] is False
        assert call_kwargs["unsharp_lx"] == 3
        assert call_kwargs["unsharp_ly"] == 3
        assert call_kwargs["unsharp_la"] == 1.0
        assert call_kwargs["unsharp_cx"] == 0.5
        assert call_kwargs["unsharp_cy"] == 0.5
        assert call_kwargs["unsharp_ca"] == 0.0

        # Check quality defaults
        assert call_kwargs["crf"] == 18
        assert call_kwargs["bitrate_kbps"] == 7000
        assert call_kwargs["bufsize_kb"] == 14000
        assert call_kwargs["pix_fmt"] == "yuv420p"

        # Check RIFE defaults
        assert call_kwargs["rife_tile_size"] == 384
        assert call_kwargs["rife_uhd_mode"] is False
        assert call_kwargs["rife_thread_spec"] == "0:0:0:0"
        assert call_kwargs["rife_tta_spatial"] is False
        assert call_kwargs["rife_tta_temporal"] is False
        assert call_kwargs["model_key"] == "rife-v4.6"

        # Check other defaults
        assert call_kwargs["use_preset_optimal"] is False
        assert call_kwargs["skip_model"] is False
        assert call_kwargs["crop_rect"] is None

    @patch("goesvfi.gui_components.worker_factory.VfiWorker")
    @patch("goesvfi.gui_components.worker_factory.tempfile.mkdtemp")
    def test_create_worker_exception_handling(self, mock_mkdtemp, mock_vfi_worker, minimal_args) -> None:
        """Test exception handling during worker creation."""
        mock_mkdtemp.return_value = "/tmp/sanchez_test"
        mock_vfi_worker.side_effect = Exception("Worker creation failed")

        with pytest.raises(Exception, match="Worker creation failed"):
            WorkerFactory.create_worker(minimal_args)

    @patch("goesvfi.gui_components.worker_factory.VfiWorker")
    @patch("goesvfi.gui_components.worker_factory.tempfile.mkdtemp")
    def test_create_worker_logging(self, mock_mkdtemp, mock_vfi_worker, minimal_args) -> None:
        """Test that appropriate logging occurs during worker creation."""
        mock_mkdtemp.return_value = "/tmp/sanchez_test"
        mock_worker_instance = Mock()
        mock_vfi_worker.return_value = mock_worker_instance

        with patch("goesvfi.gui_components.worker_factory.LOGGER") as mock_logger:
            WorkerFactory.create_worker(minimal_args)

            # Should log successful creation
            mock_logger.info.assert_called_once_with("Created VfiWorker with parameters from MainTab")

    def test_worker_factory_is_static(self) -> None:
        """Test that WorkerFactory methods are static and don't require instantiation."""
        # Should be able to call without creating instance
        minimal_args = {
            "in_dir": "/test/input",
            "out_file": "/test/output.mp4",
            "fps": 30.0,
            "multiplier": 2,
            "encoder": "libx264",
        }

        with patch("goesvfi.gui_components.worker_factory.VfiWorker") as mock_vfi_worker:
            with patch("goesvfi.gui_components.worker_factory.tempfile.mkdtemp"):
                mock_vfi_worker.return_value = Mock()

                # Should work without instantiating WorkerFactory
                worker = WorkerFactory.create_worker(minimal_args)
                assert worker is not None

    @patch("goesvfi.gui_components.worker_factory.VfiWorker")
    @patch("goesvfi.gui_components.worker_factory.tempfile.mkdtemp")
    def test_parameter_type_conversions(self, mock_mkdtemp, mock_vfi_worker, minimal_args) -> None:
        """Test various parameter type conversions."""
        mock_mkdtemp.return_value = "/tmp/sanchez_test"
        mock_worker_instance = Mock()
        mock_vfi_worker.return_value = mock_worker_instance

        # Test Path objects are converted to strings
        minimal_args["in_dir"] = Path("/test/input")
        minimal_args["out_file"] = Path("/test/output.mp4")

        WorkerFactory.create_worker(minimal_args)

        call_kwargs = mock_vfi_worker.call_args[1]
        assert call_kwargs["in_dir"] == "/test/input"
        assert call_kwargs["out_file_path"] == "/test/output.mp4"

    @patch("goesvfi.gui_components.worker_factory.VfiWorker")
    @patch("goesvfi.gui_components.worker_factory.tempfile.mkdtemp")
    def test_edge_case_multiplier_values(self, mock_mkdtemp, mock_vfi_worker, minimal_args) -> None:
        """Test edge case multiplier values."""
        mock_mkdtemp.return_value = "/tmp/sanchez_test"
        mock_worker_instance = Mock()
        mock_vfi_worker.return_value = mock_worker_instance

        # Test multiplier = 1 (minimum)
        minimal_args["multiplier"] = 1
        WorkerFactory.create_worker(minimal_args)
        call_kwargs = mock_vfi_worker.call_args[1]
        assert call_kwargs["mid_count"] == 0

        # Test high multiplier
        minimal_args["multiplier"] = 10
        WorkerFactory.create_worker(minimal_args)
        call_kwargs = mock_vfi_worker.call_args[1]
        assert call_kwargs["mid_count"] == 9
