from pathlib import Path
from typing import Optional, Tuple
import logging

LOGGER = logging.getLogger(__name__)


def run_ffmpeg_interpolation(
    input_dir: Path,
    output_mp4_path: Path,
    fps: int,
    num_intermediate_frames: int,
    use_preset_optimal: bool,
    crop_rect: Optional[Tuple[int, int, int, int]],
    debug_mode: bool,
    use_ffmpeg_interp: bool,
    filter_preset: str,
    mi_mode: str,
    mc_mode: str,
    me_mode: str,
    me_algo: str,
    search_param: int,
    scd_mode: str,
    scd_threshold: Optional[float],
    minter_mb_size: Optional[int],
    minter_vsbmc: int,
    apply_unsharp: bool,
    unsharp_lx: int,
    unsharp_ly: int,
    unsharp_la: float,
    unsharp_cx: int,
    unsharp_cy: int,
    unsharp_ca: float,
    crf: int,
    bitrate_kbps: int,
    bufsize_kb: int,
    pix_fmt: str,
) -> Path:
    """
    Stub for FFmpeg interpolation pipeline.
    Currently not implemented.
    """
    LOGGER.error("run_ffmpeg_interpolation is not implemented for FFmpeg pipeline.")
    raise NotImplementedError("FFmpeg interpolation pipeline not implemented yet")
