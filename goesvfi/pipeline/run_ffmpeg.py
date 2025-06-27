"""Helper utilities to run FFmpeg based interpolation."""

from __future__ import annotations

import logging
from pathlib import Path

from .encode import _run_ffmpeg_command

LOGGER = logging.getLogger(__name__)


def run_ffmpeg_interpolation(
    input_dir: Path,
    output_mp4_path: Path,
    fps: int,
    num_intermediate_frames: int,
    _use_preset_optimal: bool,
    crop_rect: tuple[int, int, int, int] | None,
    debug_mode: bool,
    use_ffmpeg_interp: bool,
    filter_preset: str,
    mi_mode: str,
    mc_mode: str,
    me_mode: str,
    me_algo: str,
    search_param: int,
    scd_mode: str,
    scd_threshold: float | None,
    minter_mb_size: int | None,
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
    """Run FFmpeg interpolation using the minterpolate filter.

    This function builds an FFmpeg command based on the provided parameters and
    executes it using the common ``_run_ffmpeg_command`` helper.  It supports
    optional cropping, minterpolate settings and unsharp filtering.
    """
    if not input_dir.is_dir():
        msg = f"Input directory {input_dir} does not exist"
        raise ValueError(msg)

    images = sorted(input_dir.glob("*.png"))
    if not images:
        msg = f"No PNG files found in {input_dir}"
        raise ValueError(msg)

    loglevel = "debug" if debug_mode else "info"

    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        loglevel,
        "-y",
        "-framerate",
        str(fps),
        "-pattern_type",
        "glob",
        "-i",
        str(input_dir / "*.png"),
    ]

    filter_parts = []

    if crop_rect:
        x, y, w, h = crop_rect
        filter_parts.append(f"crop={w}:{h}:{x}:{y}")

    target_fps = fps * (num_intermediate_frames + 1)

    if use_ffmpeg_interp:
        interp_options = [
            f"fps={target_fps}",
            f"mi_mode={mi_mode}",
            f"mc_mode={mc_mode}",
            f"me_mode={me_mode}",
        ]
        if me_algo and me_algo != "(default)":
            interp_options.append(f"me={me_algo}")
        if search_param:
            interp_options.append(f"search_param={search_param}")
        if scd_mode:
            interp_options.append(f"scd={scd_mode}")
        if scd_threshold is not None:
            interp_options.append(f"scd_threshold={scd_threshold}")
        if minter_mb_size is not None:
            interp_options.append(f"mb_size={minter_mb_size}")
        if minter_vsbmc:
            interp_options.append("vsbmc=1")
        filter_parts.append("minterpolate=" + ":".join(interp_options))

    if apply_unsharp:
        filter_parts.append(f"unsharp={unsharp_lx}:{unsharp_ly}:{unsharp_la}:{unsharp_cx}:{unsharp_cy}:{unsharp_ca}")

    filter_parts.append("scale=trunc(iw/2)*2:trunc(ih/2)*2")

    filter_str = ",".join(filter_parts)

    cmd.extend([
        "-vf",
        filter_str,
        "-an",
        "-vcodec",
        "libx264",
        "-preset",
        filter_preset,
        "-crf",
        str(crf),
    ])

    if bitrate_kbps:
        cmd.extend(["-b:v", f"{bitrate_kbps}k"])
    if bufsize_kb:
        cmd.extend(["-bufsize", f"{bufsize_kb}k"])

    cmd.extend(["-pix_fmt", pix_fmt, str(output_mp4_path)])

    LOGGER.info("Running FFmpeg command: %s", " ".join(cmd))

    try:
        _run_ffmpeg_command(cmd, "FFmpeg interpolation", monitor_memory=False)
    except Exception as exc:  # pragma: no cover - unexpected
        LOGGER.exception("FFmpeg interpolation failed: %s", exc)
        raise

    LOGGER.info("Interpolation completed: %s", output_mp4_path)
    return output_mp4_path
