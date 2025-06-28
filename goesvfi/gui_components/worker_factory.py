"""Factory for creating VfiWorker instances with proper parameter mapping."""

import tempfile
from pathlib import Path
from typing import Any, Dict

from goesvfi.pipeline.run_vfi import VfiWorker
from goesvfi.utils import log

LOGGER = log.get_logger(__name__)


class WorkerFactory:
    """Factory class for creating VfiWorker instances."""

    @staticmethod
    def create_worker(args: dict[str, Any], debug_mode: bool = False) -> VfiWorker:
        """Create a VfiWorker instance from MainTab arguments.

        This method handles the complex parameter mapping between MainTab's
        processing_started signal arguments and VfiWorker's constructor parameters.

        Args:
            args: Dictionary of processing arguments from MainTab
            debug_mode: Whether to enable debug mode

        Returns:
            Configured VfiWorker instance

        Raises:
            ValueError: If required arguments are missing
            Exception: If worker creation fails
        """
        # Validate required arguments
        required_args = ["in_dir", "out_file", "fps", "multiplier", "encoder"]
        for arg in required_args:
            if arg not in args:
                raise ValueError(f"Missing required argument: {arg}")

        # Extract FFmpeg settings
        ffmpeg_settings = args.get("ffmpeg_args", {}) or {}

        # Extract FFmpeg interpolation settings
        use_ffmpeg_interp = ffmpeg_settings.get("use_ffmpeg_interp", False)
        filter_preset = ffmpeg_settings.get("filter_preset", "slow")
        mi_mode = ffmpeg_settings.get("mi_mode", "mci")
        mc_mode = ffmpeg_settings.get("mc_mode", "obmc")
        me_mode = ffmpeg_settings.get("me_mode", "bidir")
        me_algo = ffmpeg_settings.get("me_algo", "")
        search_param = ffmpeg_settings.get("search_param", 96)
        scd_mode = ffmpeg_settings.get("scd", "fdi")
        scd_threshold = ffmpeg_settings.get("scd_threshold") if scd_mode != "none" else None

        # Handle mb_size conversion
        mb_size_text = ffmpeg_settings.get("mb_size", "")
        minter_mb_size = int(mb_size_text) if isinstance(mb_size_text, str) and mb_size_text.isdigit() else None
        minter_vsbmc = 1 if ffmpeg_settings.get("vsbmc", False) else 0

        # Extract unsharp settings
        apply_unsharp = ffmpeg_settings.get("apply_unsharp", False)
        unsharp_lx = ffmpeg_settings.get("unsharp_lx", 3)
        unsharp_ly = ffmpeg_settings.get("unsharp_ly", 3)
        unsharp_la = ffmpeg_settings.get("unsharp_la", 1.0)
        unsharp_cx = ffmpeg_settings.get("unsharp_cx", 0.5)
        unsharp_cy = ffmpeg_settings.get("unsharp_cy", 0.5)
        unsharp_ca = ffmpeg_settings.get("unsharp_ca", 0.0)

        # Get a temporary directory for Sanchez processing
        sanchez_gui_temp_dir = Path(tempfile.mkdtemp(prefix="sanchez_gui_"))

        # Create worker with mapped parameters
        worker = VfiWorker(
            in_dir=str(args["in_dir"]),
            out_file_path=str(args["out_file"]),  # VfiWorker expects out_file_path
            fps=args["fps"],
            mid_count=args["multiplier"] - 1,  # VfiWorker expects mid_count
            max_workers=args.get("max_workers", 4),
            encoder=args["encoder"],
            # FFmpeg settings
            use_preset_optimal=False,
            use_ffmpeg_interp=use_ffmpeg_interp,
            filter_preset=filter_preset,
            mi_mode=mi_mode,
            mc_mode=mc_mode,
            me_mode=me_mode,
            me_algo=me_algo,
            search_param=search_param,
            scd_mode=scd_mode,
            scd_threshold=scd_threshold if scd_threshold is not None else 10.0,
            minter_mb_size=minter_mb_size if minter_mb_size is not None else 16,
            minter_vsbmc=minter_vsbmc,
            # Unsharp settings
            apply_unsharp=apply_unsharp,
            unsharp_lx=unsharp_lx,
            unsharp_ly=unsharp_ly,
            unsharp_la=unsharp_la,
            unsharp_cx=unsharp_cx,
            unsharp_cy=unsharp_cy,
            unsharp_ca=unsharp_ca,
            # Quality settings
            crf=ffmpeg_settings.get("cr", 18),
            bitrate_kbps=ffmpeg_settings.get("bitrate_kbps", 7000),
            bufsize_kb=ffmpeg_settings.get("bufsize_kb", 14000),
            pix_fmt=ffmpeg_settings.get("pix_fmt", "yuv420p"),
            # Model settings
            skip_model=False,
            # Crop settings
            crop_rect=args.get("crop_rect", None),
            # Debug mode
            debug_mode=debug_mode,
            # RIFE settings
            rife_tile_enable=args.get("rife_tiling_enabled", True),
            rife_tile_size=args.get("rife_tile_size", 384),
            rife_uhd_mode=args.get("rife_uhd", False),
            rife_thread_spec=args.get("rife_thread_spec", "0:0:0:0"),
            rife_tta_spatial=args.get("rife_tta_spatial", False),
            rife_tta_temporal=args.get("rife_tta_temporal", False),
            model_key=args.get("rife_model_key", "rife-v4.6"),
            # Sanchez settings
            false_colour=bool(args.get("sanchez_enabled", False)),
            res_km=int(float(args.get("sanchez_resolution_km", 4.0))),
            # Sanchez GUI temp dir
            sanchez_gui_temp_dir=(str(sanchez_gui_temp_dir) if sanchez_gui_temp_dir else None),
        )

        LOGGER.info("Created VfiWorker with parameters from MainTab")
        return worker
