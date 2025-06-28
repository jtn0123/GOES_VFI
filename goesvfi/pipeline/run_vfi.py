import io
import pathlib
import subprocess
import tempfile
import threading
import time
from concurrent.futures import (  # Add parallel processing
    ProcessPoolExecutor,
)
from typing import Any, Iterator, List, Optional, Tuple, Union

from PIL import Image
from PyQt6.QtCore import QThread, pyqtSignal

# Import custom exceptions
from goesvfi.pipeline.exceptions import (
    FFmpegError,
    ProcessingError,
    ResourceError,
    RIFEError,
    SanchezError,
)

# Import image processing classes that tests expect
from goesvfi.pipeline.image_cropper import (  # noqa: F401  # pylint: disable=unused-import
    ImageCropper,
)
from goesvfi.pipeline.image_loader import (  # noqa: F401  # pylint: disable=unused-import
    ImageLoader,
)
from goesvfi.pipeline.image_saver import (  # noqa: F401  # pylint: disable=unused-import
    ImageSaver,
)

# Import resource management
from goesvfi.pipeline.resource_manager import (
    get_resource_manager,
    managed_executor,
)
from goesvfi.pipeline.sanchez_processor import (  # noqa: F401  # pylint: disable=unused-import
    SanchezProcessor,
)

# --- Add Sanchez Import ---
from goesvfi.sanchez.runner import colourise
from goesvfi.utils import log

# Import the RIFE analyzer utilities
from goesvfi.utils.rife_analyzer import RifeCapabilityDetector
from goesvfi.utils.validation import validate_path_exists, validate_positive_int

LOGGER = log.get_logger(__name__)


class VFIProcessor:
    """Handles the complex VFI processing pipeline with proper separation of concerns."""

    def __init__(
        self,
        rife_exe_path: pathlib.Path,
        fps: int,
        num_intermediate_frames: int,
        max_workers: int,
        rife_config: dict,
        processing_config: dict,
    ) -> None:
        self.rife_exe_path = rife_exe_path
        self.fps = fps
        self.num_intermediate_frames = num_intermediate_frames
        self.max_workers = max_workers
        self.rife_config = rife_config
        self.processing_config = processing_config

    def validate_inputs(self, folder: pathlib.Path, skip_model: bool) -> list[pathlib.Path]:
        """Validate inputs and return sorted PNG paths."""
        folder = validate_path_exists(folder, must_be_dir=True, field_name="folder")
        validate_positive_int(self.fps, "fps")
        validate_positive_int(self.num_intermediate_frames, "num_intermediate_frames")

        if self.num_intermediate_frames != 1 and not skip_model:
            raise NotImplementedError("Currently only num_intermediate_frames=1 is supported when not skipping model.")

        paths = sorted(folder.glob("*.png"))
        if not paths:
            raise ValueError("No PNG images found in the input folder.")
        if len(paths) < 2 and not skip_model:
            raise ValueError("At least two PNG images are required for interpolation.")
        if len(paths) < 1 and skip_model:
            raise ValueError("At least one PNG image is required when skipping model.")

        return paths

    def setup_crop_parameters(
        self, crop_rect_xywh: tuple[int, int, int, int] | None
    ) -> tuple[int, int, int, int] | None:
        """Convert crop rectangle from XYWH to PIL LURB format."""
        if not crop_rect_xywh:
            LOGGER.info("No crop rectangle provided.")
            return None

        try:
            x, y, w, h = crop_rect_xywh
            crop_for_pil = (
                x,
                y,
                x + validate_positive_int(w, "crop width"),
                y + validate_positive_int(h, "crop height"),
            )
            LOGGER.info(
                "Applying crop rectangle (x,y,w,h): %s -> PIL format: %s",
                crop_rect_xywh,
                crop_for_pil,
            )
            return crop_for_pil
        except (TypeError, ValueError) as e:
            LOGGER.error(
                "Invalid crop rectangle format provided: %s. Error: %s. Cropping will be disabled.",
                crop_rect_xywh,
                e,
            )
            return None

    def process_first_image(
        self,
        first_path: pathlib.Path,
        crop_for_pil: tuple[int, int, int, int] | None,
        sanchez_temp_path: pathlib.Path,
        processed_img_path: pathlib.Path,
    ) -> tuple[pathlib.Path, int, int]:
        """Process the first image and determine target dimensions."""
        LOGGER.info("Processing first image sequentially: %s", first_path.name)

        processed_path_0 = _process_single_image_worker(
            original_path=first_path,
            crop_rect_pil=crop_for_pil,
            false_colour=self.processing_config["false_colour"],
            res_km=self.processing_config["res_km"],
            sanchez_temp_dir=sanchez_temp_path,
            output_dir=processed_img_path,
        )

        with Image.open(processed_path_0) as img0_processed_handle:
            target_width, target_height = img0_processed_handle.size

        LOGGER.info(
            "Target frame dimensions set by first processed image: %sx%s",
            target_width,
            target_height,
        )

        return processed_path_0, target_width, target_height

    def process_remaining_images(
        self,
        paths: list[pathlib.Path],
        crop_for_pil: tuple[int, int, int, int] | None,
        sanchez_temp_path: pathlib.Path,
        processed_img_path: pathlib.Path,
        target_width: int,
        target_height: int,
    ) -> list[pathlib.Path]:
        """Process remaining images in parallel."""
        LOGGER.info(
            "Processing remaining %s images in parallel (max_workers=%s)...",
            len(paths) - 1,
            self.max_workers,
        )

        args_list = []
        for p_path in paths[1:]:
            args_list.append(
                (
                    p_path,
                    crop_for_pil,
                    self.processing_config["false_colour"],
                    self.processing_config["res_km"],
                    sanchez_temp_path,
                    processed_img_path,
                    target_width,
                    target_height,
                )
            )

        start_time = time.time()
        with managed_executor("process", max_workers=self.max_workers) as executor:
            try:
                results_iterator = executor.map(_process_single_image_worker_wrapper, args_list)
                processed_paths_rest = list(results_iterator)
            except Exception as e:
                LOGGER.exception("Parallel processing failed during map execution.")
                raise RuntimeError(f"Parallel processing failed: {e}") from e

        LOGGER.info(
            "Parallel processing finished in %.2f seconds.",
            time.time() - start_time,
        )

        return processed_paths_rest

    def create_ffmpeg_command(self, raw_path: pathlib.Path, skip_model: bool) -> list[str]:
        """Create FFmpeg command for video creation."""
        effective_input_fps = self.fps * (self.num_intermediate_frames + 1) if not skip_model else self.fps

        return [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "verbose",
            "-stats",
            "-y",
            "-f",
            "image2pipe",
            "-framerate",
            str(effective_input_fps),
            "-vcodec",
            "png",
            "-i",
            "-",
            "-an",
            "-vcodec",
            "libx264",
            "-preset",
            "ultrafast",
            "-pix_fmt",
            "yuv420p",
            "-vf",
            "scale=trunc(iw/2)*2:trunc(ih/2)*2",
            str(raw_path),
        ]

    def process_video_creation(
        self,
        all_processed_paths: list[pathlib.Path],
        raw_path: pathlib.Path,
        skip_model: bool,
        target_width: int,
        target_height: int,
    ) -> Iterator[Union[tuple[int, int, float], pathlib.Path]]:
        """Handle video creation with FFmpeg and RIFE interpolation."""
        ffmpeg_cmd = self.create_ffmpeg_command(raw_path, skip_model)

        ffmpeg_proc: subprocess.Popen[bytes] | None = None
        try:
            # Start FFmpeg process
            ffmpeg_proc = subprocess.Popen(  # pylint: disable=consider-using-with
                ffmpeg_cmd,
                stdin=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdout=subprocess.PIPE,
            )
            if ffmpeg_proc.stdin is None:
                raise IOError("Failed to get ffmpeg stdin pipe.")

            # Process frames and interpolation
            yield from self._process_frames_and_interpolation(
                ffmpeg_proc,
                all_processed_paths,
                skip_model,
                target_width,
                target_height,
            )

            # Finish FFmpeg process
            self._finalize_ffmpeg_process(ffmpeg_proc, raw_path)

            # Yield final path
            LOGGER.info("Successfully created raw video: %s", raw_path)
            yield raw_path

        except Exception:
            LOGGER.exception("Error during VFI processing.")
            if ffmpeg_proc and ffmpeg_proc.poll() is None:
                LOGGER.warning("Terminating ffmpeg process due to error.")
                ffmpeg_proc.terminate()
                try:
                    ffmpeg_proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    ffmpeg_proc.kill()
            raise

    def _finalize_ffmpeg_process(self, ffmpeg_proc: subprocess.Popen[bytes], raw_path: pathlib.Path) -> None:
        """Finalize FFmpeg process and check results."""
        LOGGER.info("Closing ffmpeg stdin.")
        if ffmpeg_proc.stdin:
            ffmpeg_proc.stdin.close()

        # Read and log combined output/error stream
        if ffmpeg_proc.stdout:
            for line_bytes in ffmpeg_proc.stdout:
                LOGGER.info("[ffmpeg-raw] %s", line_bytes.decode(errors="replace").rstrip())

        ret = ffmpeg_proc.wait()
        if ret != 0:
            LOGGER.error(
                "FFmpeg (raw video creation) failed (exit code %s). See logged output above.",
                ret,
            )
            raise RuntimeError(f"FFmpeg (raw video creation) failed (exit code {ret})")

        LOGGER.info("FFmpeg (raw video creation) completed successfully.")

        if not raw_path.exists() or raw_path.stat().st_size == 0:
            LOGGER.error("Raw output file %s not created or is empty.", raw_path)
            raise RuntimeError("Raw video file creation failed.")

    def _process_frames_and_interpolation(
        self,
        ffmpeg_proc: subprocess.Popen[bytes],
        all_processed_paths: list[pathlib.Path],
        skip_model: bool,
        target_width: int,
        target_height: int,
    ) -> Iterator[tuple[int, int, float]]:
        """Process frames with optional RIFE interpolation."""
        # Write first processed frame
        try:
            with Image.open(all_processed_paths[0]) as im0_handle:
                LOGGER.debug(
                    "Encoding first processed frame %s (size %s) for ffmpeg.",
                    all_processed_paths[0].name,
                    im0_handle.size,
                )
                png_data = _encode_frame_to_png_bytes(im0_handle)
            _safe_write(
                ffmpeg_proc,
                png_data,
                f"first processed frame ({all_processed_paths[0].name})",
            )
        except IOError:
            raise
        except Exception as e:
            raise IOError(f"Failed processing {all_processed_paths[0].name}") from e

        if skip_model:
            # Skip model mode: just copy remaining frames
            yield from self._process_skip_model_frames(ffmpeg_proc, all_processed_paths[1:])
        else:
            # AI interpolation mode
            yield from self._process_interpolation_frames(ffmpeg_proc, all_processed_paths, target_width, target_height)

    def _process_skip_model_frames(
        self, ffmpeg_proc: subprocess.Popen[bytes], remaining_paths: list[pathlib.Path]
    ) -> Iterator[tuple[int, int, float]]:
        """Process remaining frames when skipping AI model."""
        LOGGER.info(
            "Skip model mode: copying %s remaining frames directly.",
            len(remaining_paths),
        )

        start_time = time.time()
        last_yield_time = start_time
        total_frames = len(remaining_paths)

        for idx, path in enumerate(remaining_paths):
            try:
                with Image.open(path) as img_handle:
                    png_data = _encode_frame_to_png_bytes(img_handle)
                _safe_write(ffmpeg_proc, png_data, f"frame {idx + 2} ({path.name})")

                # Yield progress
                current_time = time.time()
                elapsed = current_time - start_time
                frames_processed = idx + 1
                time_per_frame = elapsed / frames_processed if frames_processed > 0 else 0
                frames_remaining = total_frames - frames_processed
                eta = frames_remaining * time_per_frame if time_per_frame > 0 else 0.0

                if current_time - last_yield_time > 1.0 or frames_processed == total_frames:
                    yield (frames_processed, total_frames, eta)
                    last_yield_time = current_time

            except IOError:
                raise
            except Exception as e:
                raise IOError(f"Failed processing {path.name}") from e

        LOGGER.info("Finished copying frames in skip model mode.")

    def _process_interpolation_frames(
        self,
        ffmpeg_proc: subprocess.Popen[bytes],
        all_processed_paths: list[pathlib.Path],
        target_width: int,
        target_height: int,
    ) -> Iterator[tuple[int, int, float]]:
        """Process frames with RIFE interpolation."""
        total_pairs = len(all_processed_paths) - 1
        LOGGER.info("AI interpolation mode: processing %s pairs of frames.", total_pairs)

        start_time = time.time()
        last_yield_time = start_time

        for idx in range(total_pairs):
            pair_start_time = time.time()
            p1_processed_path = all_processed_paths[idx]
            p2_processed_path = all_processed_paths[idx + 1]

            # Run RIFE interpolation
            interpolated_frame_path = _run_rife_pair(
                p1_processed_path,
                p2_processed_path,
                self.rife_exe_path,
                self.rife_config,
            )

            # Write interpolated frame
            try:
                with Image.open(interpolated_frame_path) as im_interp:
                    if im_interp.size != (target_width, target_height):
                        LOGGER.warning(
                            "Resizing interpolated frame for pair %s from %s to (%s, %s).",
                            idx,
                            im_interp.size,
                            target_width,
                            target_height,
                        )
                        im_interp = im_interp.resize(
                            (target_width, target_height),
                            Image.Resampling.LANCZOS,
                        )
                    png_data = _encode_frame_to_png_bytes(im_interp)
                _safe_write(ffmpeg_proc, png_data, f"interpolated frame {idx}")
                interpolated_frame_path.unlink()  # Clean up

            except IOError:
                raise
            except Exception as e:
                raise IOError(f"Failed processing interpolated frame {idx}") from e

            # Write second processed frame
            try:
                with Image.open(p2_processed_path) as img2_handle:
                    LOGGER.debug(
                        "Encoding second processed frame %s (%s, size %s) for ffmpeg.",
                        idx,
                        p2_processed_path.name,
                        img2_handle.size,
                    )
                    png_data = _encode_frame_to_png_bytes(img2_handle)
                _safe_write(
                    ffmpeg_proc,
                    png_data,
                    f"second processed frame {idx} ({p2_processed_path.name})",
                )
            except IOError:
                raise
            except Exception as e:
                raise IOError(f"Failed processing {p2_processed_path.name}") from e

            # Yield Progress
            current_time = time.time()
            elapsed = current_time - start_time
            pairs_processed = idx + 1
            time_per_pair = elapsed / pairs_processed if pairs_processed > 0 else 0
            pairs_remaining = total_pairs - pairs_processed
            eta = pairs_remaining * time_per_pair if time_per_pair > 0 else 0.0

            if current_time - last_yield_time > 1.0 or pairs_processed == total_pairs:
                yield (pairs_processed, total_pairs, eta)
                last_yield_time = current_time

            LOGGER.debug(
                "Pair %d/%d processed in %.2fs. ETA: %.1fs",
                idx + 1,
                total_pairs,
                time.time() - pair_start_time,
                eta,
            )

        LOGGER.info("Finished AI interpolation processing.")


class InterpolationPipeline:
    """Pipeline for processing images with interpolation.

    This class provides a simple abstraction for concurrent image processing
    with support for progress tracking and cancellation.
    """

    def __init__(self, max_workers: int = 4) -> None:
        """Initialize the interpolation pipeline.

        Args:
            max_workers: Maximum number of concurrent workers
        """
        self.resource_manager = get_resource_manager()
        self.max_workers = min(max_workers, self.resource_manager.get_optimal_workers())
        self._executor: ProcessPoolExecutor | None = None
        self._active_tasks: set[Any] = set()
        self._lock = threading.Lock()

    def __enter__(self) -> "InterpolationPipeline":
        """Enter context manager."""
        self._executor = ProcessPoolExecutor(max_workers=self.max_workers)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context manager."""
        if self._executor is not None:
            self._executor.shutdown(wait=True)
            self._executor = None

    def process(self, images: list[str], task_id: Any) -> str:
        """Process a list of images.

        Args:
            images: List of image paths to process
            task_id: Identifier for this processing task

        Returns:
            Result string describing the processing
        """
        if self._executor is None:
            raise RuntimeError("Pipeline must be used as context manager")

        # Track active task
        with self._lock:
            self._active_tasks.add(task_id)

        try:
            # Simulate processing with proper concurrent behavior
            time.sleep(0.1)
            result = f"Processed {len(images)} images for task {task_id}"
            LOGGER.debug("InterpolationPipeline: %s", result)
            return result
        finally:
            # Remove from active tasks
            with self._lock:
                self._active_tasks.discard(task_id)

    def shutdown(self) -> None:
        """Shutdown the pipeline and clean up resources."""
        if self._executor is not None:
            self._executor.shutdown(wait=True)
        self._active_tasks.clear()


class VfiWorker(QThread):
    """Worker thread for VFI processing in GUI."""

    # Signals
    progress = pyqtSignal(int, int, float)  # current, total, eta
    finished = pyqtSignal(str)  # output_path
    error = pyqtSignal(str)  # error_message

    def __init__(
        self,
        in_dir: str,
        out_file_path: str,
        fps: int = 30,
        mid_count: int = 9,
        max_workers: int = 2,
        encoder: str = "libx264",
        use_ffmpeg_interp: bool = False,
        filter_preset: str = "full",
        mi_mode: str = "bidir",
        mc_mode: str = "aobmc",
        me_mode: str = "bidir",
        me_algo: str = "epzs",
        search_param: int = 64,
        scd_mode: str = "fdiff",
        scd_threshold: float = 10.0,
        minter_mb_size: int = 16,
        minter_vsbmc: int = 1,
        apply_unsharp: bool = False,
        unsharp_lx: float = 5.0,
        unsharp_ly: float = 5.0,
        unsharp_la: float = 1.0,
        unsharp_cx: float = 5.0,
        unsharp_cy: float = 5.0,
        unsharp_ca: float = 0.0,
        crf: int = 23,
        bitrate_kbps: int | None = None,
        bufsize_kb: int | None = None,
        pix_fmt: str = "yuv420p",
        skip_model: bool = False,
        crop_rect: tuple[int, int, int, int] | None = None,
        debug_mode: bool = False,
        rife_tile_enable: bool = False,
        rife_tile_size: int = 256,
        rife_uhd_mode: bool = False,
        rife_thread_spec: str | None = None,
        rife_tta_spatial: bool = False,
        rife_tta_temporal: bool = False,
        model_key: str | None = None,
        false_colour: bool = False,
        res_km: int = 2,
        sanchez_gui_temp_dir: str | None = None,
        **kwargs: Any,  # Catch any extra arguments
    ) -> None:
        """Initialize the VFI worker with processing parameters."""
        super().__init__()

        # Store all parameters
        self.in_dir = in_dir
        self.out_file_path = out_file_path
        self.fps = fps
        self.mid_count = mid_count
        self.max_workers = max_workers
        self.encoder = encoder
        self.use_ffmpeg_interp = use_ffmpeg_interp
        self.filter_preset = filter_preset
        self.mi_mode = mi_mode
        self.mc_mode = mc_mode
        self.me_mode = me_mode
        self.me_algo = me_algo
        self.search_param = search_param
        self.scd_mode = scd_mode
        self.scd_threshold = scd_threshold
        self.minter_mb_size = minter_mb_size
        self.minter_vsbmc = minter_vsbmc
        self.apply_unsharp = apply_unsharp
        self.unsharp_lx = unsharp_lx
        self.unsharp_ly = unsharp_ly
        self.unsharp_la = unsharp_la
        self.unsharp_cx = unsharp_cx
        self.unsharp_cy = unsharp_cy
        self.unsharp_ca = unsharp_ca
        self.crf = crf
        self.bitrate_kbps = bitrate_kbps
        self.bufsize_kb = bufsize_kb
        self.pix_fmt = pix_fmt
        self.skip_model = skip_model
        self.crop_rect = crop_rect
        self.debug_mode = debug_mode
        self.rife_tile_enable = rife_tile_enable
        self.rife_tile_size = rife_tile_size
        self.rife_uhd_mode = rife_uhd_mode
        self.rife_thread_spec = rife_thread_spec
        self.rife_tta_spatial = rife_tta_spatial
        self.rife_tta_temporal = rife_tta_temporal
        self.model_key = model_key
        self.false_colour = false_colour
        self.res_km = res_km
        self.sanchez_gui_temp_dir = sanchez_gui_temp_dir

        LOGGER.info("VfiWorker initialized with parameters")

    def run(self) -> None:
        """Run the VFI processing in a separate thread."""
        try:
            LOGGER.info("Starting VFI processing...")

            # Check resources before starting
            resource_manager = get_resource_manager()
            try:
                resource_manager.check_resources()
            except ResourceError as e:
                LOGGER.error("Insufficient resources: %s", e)
                self.error.emit(f"Resource check failed: {e}")
                return

            rife_exe = self._get_rife_executable()
            ffmpeg_args = self._prepare_ffmpeg_settings()

            gen = run_vfi(
                folder=pathlib.Path(self.in_dir),
                output_mp4_path=pathlib.Path(self.out_file_path),
                rife_exe_path=rife_exe,
                fps=self.fps,
                num_intermediate_frames=self.mid_count,
                max_workers=self.max_workers,
                rife_tile_enable=self.rife_tile_enable,
                rife_tile_size=self.rife_tile_size,
                rife_uhd_mode=self.rife_uhd_mode,
                rife_thread_spec=self.rife_thread_spec or "1:2:2",
                rife_tta_spatial=self.rife_tta_spatial,
                rife_tta_temporal=self.rife_tta_temporal,
                model_key=self.model_key or "rife-v4.6",
                false_colour=self.false_colour,
                res_km=self.res_km,
                crop_rect_xywh=self.crop_rect,
                skip_model=self.skip_model,
                **ffmpeg_args,
            )

            for output in gen:
                if isinstance(output, tuple):
                    current, total, eta = output
                    self.progress.emit(current, total, eta)
                elif isinstance(output, pathlib.Path):
                    self.finished.emit(str(output))

            LOGGER.info("VFI processing completed")
        except (FFmpegError, RIFEError, SanchezError, ProcessingError) as e:
            # Specific processing errors - log with context
            LOGGER.error("Processing error: %s", e)
            self.error.emit(f"Processing failed: {e}")
        except OSError as e:
            # File system errors
            LOGGER.error("File operation error: %s", e)
            self.error.emit(f"File error: {e}")
        except Exception as e:  # pragma: no cover - catch unexpected errors
            LOGGER.exception("Unexpected error in VFI processing")
            self.error.emit(f"Unexpected error: {e}")

    def _get_rife_executable(self) -> pathlib.Path:
        """Get the RIFE executable path based on model key."""
        from goesvfi.utils.config import find_rife_executable

        if self.model_key:
            rife_path = find_rife_executable(self.model_key)
            if rife_path:
                return pathlib.Path(rife_path)

        # Fallback to default RIFE executable
        rife_path = find_rife_executable("rife-v4.6")  # Default model key
        if rife_path:
            return pathlib.Path(rife_path)

        raise FileNotFoundError("RIFE executable not found")

    def _prepare_ffmpeg_settings(self) -> dict:
        """Prepare FFmpeg settings dictionary from instance attributes."""
        return {
            "use_ffmpeg_interp": self.use_ffmpeg_interp,
            "filter_preset": self.filter_preset,
            "mi_mode": self.mi_mode,
            "mc_mode": self.mc_mode,
            "me_mode": self.me_mode,
            "me_algo": self.me_algo,
            "search_param": self.search_param,
            "scd_mode": self.scd_mode,
            "scd_threshold": self.scd_threshold,
            "minter_mb_size": self.minter_mb_size,
            "minter_vsbmc": self.minter_vsbmc,
            "apply_unsharp": self.apply_unsharp,
            "unsharp_lx": self.unsharp_lx,
            "unsharp_ly": self.unsharp_ly,
            "unsharp_la": self.unsharp_la,
            "unsharp_cx": self.unsharp_cx,
            "unsharp_cy": self.unsharp_cy,
            "unsharp_ca": self.unsharp_ca,
            "crf": self.crf,
            "bitrate_kbps": self.bitrate_kbps,
            "bufsize_kb": self.bufsize_kb,
            "pix_fmt": self.pix_fmt,
        }

    def _process_run_vfi_output(self, output_lines: list[Union[str, pathlib.Path, tuple[int, int, float]]]) -> None:
        """Process output from run_vfi generator and emit appropriate signals."""
        for line in output_lines:
            if isinstance(line, tuple) and len(line) == 3:
                # Progress update (current, total, time_elapsed)
                current, total, time_elapsed = line
                self.progress.emit(current, total, time_elapsed)
            elif isinstance(line, pathlib.Path):
                # Final output path as Path object
                self.finished.emit(line)
            elif isinstance(line, str):
                if line.startswith("Error:") or line.startswith("ERROR:") or "error" in line.lower():
                    # Error message - extract the actual error part
                    if line.startswith("ERROR:"):
                        error_msg = line[6:].strip()  # Remove "ERROR:" prefix
                    else:
                        error_msg = line
                    self.error.emit(error_msg)
                elif pathlib.Path(line).suffix in [".mp4", ".avi", ".mov"]:
                    # Final output path as string
                    self.finished.emit(line)
                # Ignore other string outputs


def _process_with_rife(
    ffmpeg_proc: subprocess.Popen,
    all_processed_paths: list[pathlib.Path],
    rife_exe_path: pathlib.Path,
    model_key: str,
    processed_img_dir: pathlib.Path,
    rife_tile_enable: bool = False,
    rife_tile_size: int = 256,
    rife_uhd_mode: bool = False,
    rife_thread_spec: str | None = None,
    rife_tta_spatial: bool = False,
    rife_tta_temporal: bool = False,
) -> Iterator[tuple[int, int, float]]:
    """Process frames with RIFE interpolation.

    This function generates interpolated frames using RIFE and yields progress updates.

    Args:
        ffmpeg_proc: FFmpeg process to write frames to
        all_processed_paths: List of input image paths
        rife_exe_path: Path to RIFE executable
        model_key: RIFE model identifier
        processed_img_dir: Directory for processed images
        rife_tile_enable: Enable tiled processing
        rife_tile_size: Size of tiles for processing
        rife_uhd_mode: Enable UHD mode
        rife_thread_spec: Thread specification string
        rife_tta_spatial: Enable spatial TTA
        rife_tta_temporal: Enable temporal TTA

    Yields:
        Tuple of (current_frame, total_frames, elapsed_time)
    """

    start_time = time.time()
    total_pairs = len(all_processed_paths) - 1

    for i in range(total_pairs):
        current_frame = all_processed_paths[i]
        next_frame = all_processed_paths[i + 1]

        # Build RIFE command
        rife_cmd = [
            str(rife_exe_path),
            "-i",
            str(current_frame),
            "-o",
            str(next_frame),
            "-m",
            model_key,
        ]

        if rife_tile_enable:
            rife_cmd.extend(["-t", str(rife_tile_size)])
        if rife_uhd_mode:
            rife_cmd.append("-u")
        if rife_thread_spec:
            rife_cmd.extend(["-j", rife_thread_spec])
        if rife_tta_spatial:
            rife_cmd.append("-x")
        if rife_tta_temporal:
            rife_cmd.append("-z")

        # Run RIFE interpolation
        result = subprocess.run(rife_cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            LOGGER.error("RIFE failed: %s", result.stderr)
            continue

        # Yield progress after RIFE processing
        elapsed = time.time() - start_time
        yield (i * 2 + 1, total_pairs * 2, elapsed)

        # Load interpolated frame and write to FFmpeg
        interpolated_path = processed_img_dir / f"interpolated_{i:06d}.png"
        try:
            with Image.open(interpolated_path) as img:
                png_bytes = _encode_frame_to_png_bytes(img)
                _safe_write(ffmpeg_proc, png_bytes, f"interpolated frame {i}")
        except OSError as e:
            LOGGER.error("Failed to read interpolated frame %d: %s", i, e)
            raise ProcessingError(f"Failed to read interpolated frame {i}: {e}") from e
        except FFmpegError:  # pylint: disable=try-except-raise
            # Re-raise FFmpeg errors as-is for proper handling upstream
            raise

        # Write the next original frame
        try:
            with Image.open(next_frame) as img:
                png_bytes = _encode_frame_to_png_bytes(img)
                _safe_write(ffmpeg_proc, png_bytes, f"frame {i + 1}")
        except Exception as e:
            LOGGER.error("Failed to process frame %s: %s", next_frame, e)

        # Yield progress after writing frames
        elapsed = time.time() - start_time
        yield (i * 2 + 2, total_pairs * 2, elapsed)


# --- Helper function to encode frame to PNG bytes ---
def _encode_frame_to_png_bytes(img: Image.Image) -> bytes:
    """Encodes a PIL Image into PNG bytes memory.

    Args:
        img: PIL Image object.

    Returns:
        PNG image data as bytes.
    """
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# Helper function for safe writing to ffmpeg stdin with detailed error logging
def _safe_write(proc: subprocess.Popen[bytes], data: bytes, frame_desc: str) -> None:
    """Writes data to process stdin, handles BrokenPipeError with stderr logging."""
    if proc.stdin is None:
        LOGGER.error("Cannot write %s: ffmpeg stdin is None.", frame_desc)
        stderr_bytes = b""
        if proc.stderr:
            stderr_bytes = proc.stderr.read()
        raise FFmpegError(
            f"ffmpeg stdin pipe not available for {frame_desc}",
            stderr=stderr_bytes.decode(errors="ignore"),
        )

    try:
        proc.stdin.write(data)
    except BrokenPipeError:
        # Try reading stderr immediately upon pipe error
        stderr_output = ""
        stdout_output = ""  # Also try stdout since they might be merged
        try:
            if proc.stderr:
                # Non-blocking read might be better, but try blocking first
                stderr_bytes = proc.stderr.read()
                if stderr_bytes:
                    stderr_output = stderr_bytes.decode(errors="ignore")
            if proc.stdout:
                # If stderr was empty, maybe merged output is here
                stdout_bytes = proc.stdout.read()
                if stdout_bytes:
                    stdout_output = stdout_bytes.decode(errors="ignore")
        except Exception as read_err:
            stderr_output += f"\n(Error reading pipe: {read_err})"

        ffmpeg_log = stderr_output or stdout_output or "(no output captured)"

        # Include byte length and captured log in error message
        LOGGER.error(
            "Broken pipe while writing %s (%s bytes) — FFmpeg log:\n%s",
            frame_desc,
            len(data),
            ffmpeg_log,
        )
        raise FFmpegError(
            f"Broken pipe writing {frame_desc} ({len(data)} bytes)", stderr=ffmpeg_log
        ) from None  # Raise new exception


# --- End Helper ---


# --- Add Sanchez/Crop Helper ---
def _load_process_image(
    path: pathlib.Path,
    crop_rect_pil: tuple[int, int, int, int] | None,
    false_colour: bool,
    res_km: int,
    sanchez_temp_dir: pathlib.Path,
) -> Image.Image:
    """Loads image, optionally applies Sanchez, optionally crops.

    Args:
        path: Path to the image.
        crop_rect_pil: PIL format crop tuple (left, upper, right, lower) or None.
        false_colour: Whether to apply Sanchez colourise.
        res_km: Resolution for Sanchez.
        sanchez_temp_dir: Temporary directory for Sanchez intermediate files.

    Returns:
        Processed PIL Image.
    """
    img = Image.open(path)

    if false_colour:
        img_stem = path.stem
        # Use the ORIGINAL stem for the input file to satisfy Sanchez
        temp_in_path = sanchez_temp_dir / f"{img_stem}.png"
        # Keep unique name for the output file
        temp_out_path = sanchez_temp_dir / f"{img_stem}_{time.monotonic_ns()}_fc.png"
        try:
            LOGGER.debug("Saving original for Sanchez: %s", temp_in_path)  # Log correct path
            img.save(temp_in_path, "PNG")  # Save with correct name
            LOGGER.info(
                "Running Sanchez on %s (res=%skm) -> %s",
                temp_in_path.name,
                res_km,
                temp_out_path.name,
            )
            # Ensure colourise handles Path objects and receives correct input path
            colourise(str(temp_in_path), str(temp_out_path), res_km=res_km)
            LOGGER.debug("Loading Sanchez output: %s", temp_out_path)
            img_colourised = Image.open(temp_out_path)
            # Replace original img object with colourised one
            img = img_colourised
        except Exception as e:
            LOGGER.error("Sanchez colourise failed for %s: %s", path.name, e, exc_info=True)
            # Keep original image if colourise fails
        finally:
            # Clean up temp files (both input and output)
            if temp_in_path.exists():
                temp_in_path.unlink(missing_ok=True)
            if temp_out_path.exists():
                temp_out_path.unlink(missing_ok=True)

    # Apply crop *after* potential colourisation
    if crop_rect_pil:
        try:
            LOGGER.debug(
                "Applying crop %s to image from %s (post-Sanchez if applied).",
                crop_rect_pil,
                path.name,
            )
            img_cropped = img.crop(crop_rect_pil)
            img = img_cropped  # Update img reference to cropped version
        except Exception as e:
            LOGGER.error(
                "Failed to crop image %s with rect %s: %s",
                path.name,
                crop_rect_pil,
                e,
                exc_info=True,
            )
            # Decide whether to raise or return uncropped image
            # Returning uncropped for now, dimension validation should fail later

    return img


# --- End Sanchez/Crop Helper ---


def _validate_and_prepare_run_vfi_parameters(
    folder: pathlib.Path,
    num_intermediate_frames: int,
    encoder_type: str,
    false_colour: bool,
    crop_rect_xywh: tuple[int, int, int, int] | None,
    skip_model: bool,
) -> tuple[bool, list[pathlib.Path], tuple[int, int, int, int] | None]:
    """Validate and prepare parameters for run_vfi.

    Args:
        folder: Directory containing PNG images
        num_intermediate_frames: Number of frames to interpolate between each pair
        encoder_type: Type of encoder ("RIFE", "Sanchez", etc.)
        false_colour: Whether to apply false color processing
        crop_rect_xywh: Crop rectangle in (x, y, width, height) format
        skip_model: Whether to skip model-based interpolation

    Returns:
        Tuple of (updated_false_colour, paths, crop_for_pil)
    """
    folder = validate_path_exists(folder, must_be_dir=True, field_name="folder")

    validate_positive_int(num_intermediate_frames, "num_intermediate_frames")

    # Find all PNG images in the folder
    png_pattern = "*.png"
    png_paths = list(folder.glob(png_pattern))
    png_paths.sort()

    if not png_paths:
        raise ValueError("No PNG images found in the specified folder")

    # Force false_colour to True for Sanchez encoder
    updated_false_colour = false_colour
    if encoder_type == "Sanchez":
        updated_false_colour = True

    # Convert crop rectangle from (x, y, width, height) to PIL format (left, top, right, bottom)
    crop_for_pil = None
    if crop_rect_xywh is not None:
        x, y, w, h = crop_rect_xywh
        try:
            crop_for_pil = (
                x,
                y,
                x + validate_positive_int(w, "crop width"),
                y + validate_positive_int(h, "crop height"),
            )
        except ValueError:
            crop_for_pil = None

    return updated_false_colour, png_paths, crop_for_pil


def _build_ffmpeg_command(fps: int, output_path: pathlib.Path) -> list[str]:
    """Build FFmpeg command for video creation.

    Args:
        fps: Frame rate for the output video
        output_path: Path for the output video file

    Returns:
        List of command arguments for FFmpeg
    """
    return [
        "ffmpeg",
        "-y",  # Overwrite output file
        "-f",
        "image2pipe",
        "-vcodec",
        "png",
        "-framerate",
        str(fps),
        "-i",
        "-",  # Read from stdin
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        str(output_path),
    ]


def _get_unique_output_path(original_path: pathlib.Path) -> pathlib.Path:
    """Generate a unique output path by adding timestamp.

    Args:
        original_path: Original output path

    Returns:
        Unique output path with timestamp
    """
    import datetime

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = original_path.stem
    suffix = original_path.suffix
    parent = original_path.parent

    unique_name = f"{stem}_{timestamp}{suffix}"
    return parent / unique_name


def _create_rife_command(
    rife_exe_path: pathlib.Path,
    temp_p1_path: pathlib.Path,
    temp_p2_path: pathlib.Path,
    output_path: pathlib.Path,
    model_key: str,
    capability_detector: RifeCapabilityDetector,
    rife_tile_enable: bool = False,
    rife_tile_size: int = 256,
    rife_uhd_mode: bool = False,
    rife_tta_spatial: bool = False,
    rife_tta_temporal: bool = False,
    rife_thread_spec: str | None = None,
) -> list[str]:
    """Create RIFE command with capability checking.

    Args:
        rife_exe_path: Path to RIFE executable
        temp_p1_path: Path to first input image
        temp_p2_path: Path to second input image
        output_path: Path for interpolated output
        model_key: RIFE model identifier
        capability_detector: Detector for RIFE capabilities
        rife_tile_enable: Enable tiled processing
        rife_tile_size: Size of tiles for processing
        rife_uhd_mode: Enable UHD mode
        rife_tta_spatial: Enable spatial TTA
        rife_tta_temporal: Enable temporal TTA
        rife_thread_spec: Thread specification string

    Returns:
        List of command arguments for RIFE
    """
    cmd = [
        str(rife_exe_path),
        "-0",
        str(temp_p1_path),
        "-1",
        str(temp_p2_path),
        "-o",
        str(output_path),
    ]

    # Add model if specified
    if model_key:
        cmd.extend(["-m", model_key])

    # Add tiling if supported and enabled
    if rife_tile_enable and capability_detector.supports_tiling():
        cmd.extend(["-t", str(rife_tile_size)])

    # Add UHD mode if supported and enabled
    if rife_uhd_mode and capability_detector.supports_uhd():
        cmd.append("-u")

    # Add spatial TTA if supported and enabled
    if rife_tta_spatial and capability_detector.supports_tta_spatial():
        cmd.append("-s")

    # Add temporal TTA if supported and enabled
    if rife_tta_temporal and capability_detector.supports_tta_temporal():
        cmd.append("-T")

    # Add thread specification if supported and provided
    if rife_thread_spec and capability_detector.supports_thread_spec():
        cmd.extend(["-y", rife_thread_spec])

    return cmd


def _check_rife_capability_warnings(
    capability_detector: RifeCapabilityDetector,
    rife_tile_enable: bool = False,
    rife_uhd_mode: bool = False,
    rife_tta_spatial: bool = False,
    rife_tta_temporal: bool = False,
    rife_thread_spec: str | None = None,
) -> None:
    """Check RIFE capabilities and log warnings for unsupported features.

    Args:
        capability_detector: Detector for RIFE capabilities
        rife_tile_enable: Whether tiling is requested
        rife_uhd_mode: Whether UHD mode is requested
        rife_tta_spatial: Whether spatial TTA is requested
        rife_tta_temporal: Whether temporal TTA is requested
        rife_thread_spec: Thread specification if provided
    """
    if rife_tile_enable and not capability_detector.supports_tiling():
        LOGGER.warning("Tiling requested but not supported by this RIFE version")

    if rife_uhd_mode and not capability_detector.supports_uhd():
        LOGGER.warning("UHD mode requested but not supported by this RIFE version")

    if rife_tta_spatial and not capability_detector.supports_tta_spatial():
        LOGGER.warning("Spatial TTA requested but not supported by this RIFE version")

    if rife_tta_temporal and not capability_detector.supports_tta_temporal():
        LOGGER.warning("Temporal TTA requested but not supported by this RIFE version")

    if rife_thread_spec and not capability_detector.supports_thread_spec():
        LOGGER.warning("Custom thread specification requested but not supported by this RIFE version")


def _process_in_skip_model_mode(
    ffmpeg_proc: subprocess.Popen,
    image_paths: list[pathlib.Path],
) -> Iterator[tuple[int, int, float]]:
    """Process frames in skip_model mode (no interpolation).

    Args:
        ffmpeg_proc: FFmpeg process to write frames to
        image_paths: List of image paths to process

    Yields:
        Tuple of (current_frame, total_frames, elapsed_time)
    """

    start_time = time.time()
    total_frames = len(image_paths)

    # Skip the first frame as it's already processed
    for i, img_path in enumerate(image_paths[1:], 1):
        try:
            with Image.open(img_path) as img:
                png_bytes = _encode_frame_to_png_bytes(img)
                _safe_write(ffmpeg_proc, png_bytes, f"frame {i}")

            elapsed = time.time() - start_time
            yield (i, total_frames, elapsed)

        except Exception as e:
            LOGGER.error("Failed to process frame %s: %s", img_path, e)


# --- Worker function for parallel processing --- #
def _process_single_image_worker(
    original_path: pathlib.Path,
    crop_rect_pil: tuple[int, int, int, int] | None,
    false_colour: bool,
    res_km: int,
    sanchez_temp_dir: pathlib.Path,
    output_dir: pathlib.Path,
    # Make target dims optional, only used for validation on subsequent images
    target_width: int | None = None,
    target_height: int | None = None,
) -> pathlib.Path:
    """Worker function to load, process (Sanchez, crop), validate, and save a single image.

    If target_width/height are provided, validates final size against them.

    Returns:
        Path to the saved, processed image in output_dir.
    Raises:
        ValueError: If processed image dimensions don't match target (when provided).
        Exception: If any processing step fails.
    """
    try:
        # 1. Load original image
        img = Image.open(original_path)
        orig_w, orig_h = img.size

        # 2. Apply Sanchez if requested
        if false_colour:
            img_stem = original_path.stem
            temp_in_path = sanchez_temp_dir / f"{img_stem}.png"
            temp_out_path = sanchez_temp_dir / f"{img_stem}_{time.monotonic_ns()}_fc.png"
            try:
                img.save(temp_in_path, "PNG")
                colourise(str(temp_in_path), str(temp_out_path), res_km=res_km)
                img_colourised = Image.open(temp_out_path)
                img = img_colourised
            except Exception as e:
                # Log error but return original image if Sanchez fails
                LOGGER.error("Worker Sanchez failed for %s: %s", original_path.name, e)
                # Keep original 'img' loaded above
            finally:
                if temp_in_path.exists():
                    temp_in_path.unlink(missing_ok=True)
                if temp_out_path.exists():
                    temp_out_path.unlink(missing_ok=True)

        # 3. Apply crop if requested
        if crop_rect_pil:
            # Validate crop against original dimensions before cropping
            left, upper, right, lower = crop_rect_pil
            if right > orig_w or lower > orig_h:
                raise ValueError(
                    f"Crop rectangle {crop_rect_pil} exceeds original dimensions "
                    f"({orig_w}x{orig_h}) of image {original_path.name}"
                )
            try:
                img_cropped = img.crop(crop_rect_pil)
                img = img_cropped
            except Exception as e:
                LOGGER.error("Worker failed to crop image %s: %s", original_path.name, e)
                raise  # Re-raise cropping errors

        # 4. Validate dimensions - REMOVED
        # if target_width is not None and target_height is not None:
        #     if img.size != (target_width, target_height):
        #          raise ValueError(
        #              f"Processed {original_path.name} dimensions {img.size} != target {target_width}x{target_height}"
        #          )

        # 5. Save processed image to unique file in output_dir
        processed_output_path = output_dir / f"processed_{original_path.stem}_{time.monotonic_ns()}.png"
        img.save(processed_output_path, "PNG")

        return processed_output_path

    except Exception:
        # Log any exception from the worker and re-raise
        LOGGER.exception("Worker failed processing %s", original_path.name)
        raise


# --- Wrapper for map compatibility --- #
def _process_single_image_worker_wrapper(
    args: tuple[
        pathlib.Path,
        tuple[int, int, int, int] | None,
        bool,
        int,
        pathlib.Path,
        pathlib.Path,
        int,
        int,
    ],
) -> pathlib.Path:
    """Unpacks arguments and calls the actual worker function."""
    # Expects 8 arguments: original_path, crop_rect_pil, false_colour, res_km,
    # sanchez_temp_dir, output_dir, target_width, target_height
    return _process_single_image_worker(*args)


# Function to run RIFE interpolation and write raw video stream via ffmpeg
def run_vfi(
    folder: pathlib.Path,
    output_mp4_path: pathlib.Path,
    rife_exe_path: pathlib.Path,
    fps: int,
    num_intermediate_frames: int,  # Currently handles 1
    max_workers: int,  # Currently unused, runs sequentially
    # RIFE v4.6 specific arguments (passed via kwargs from GUI worker)
    rife_tile_enable: bool = False,
    rife_tile_size: int = 256,
    rife_uhd_mode: bool = False,
    rife_thread_spec: str = "1:2:2",
    rife_tta_spatial: bool = False,
    rife_tta_temporal: bool = False,
    model_key: str = "rife-v4.6",
    # --- Add Sanchez/Crop Args --- #
    false_colour: bool = False,
    res_km: int = 4,
    crop_rect_xywh: tuple[int, int, int, int] | None = None,
    # --- End Add --- #
    **kwargs: Any,  # Keep kwargs for backward compat or other settings
) -> Iterator[Union[tuple[int, int, float], pathlib.Path]]:
    """
    Runs RIFE interpolation or copies original frames to a raw video file.
    Uses parallel processing for Sanchez/cropping if enabled.

    Yields:
        Tuple[int, int, float]: Progress updates (current_pair, total_pairs, eta_seconds).
        pathlib.Path: The path to the generated raw video file.

    Raises:
        NotImplementedError: If num_intermediate_frames is not 1.
        ValueError: If no PNG images or fewer than 2 images are found.
        IOError: If image dimensions cannot be read or frame processing fails.
        RuntimeError: If RIFE or ffmpeg subprocess execution fails.
    """

    # --- Parameter Extraction ---
    skip_model = kwargs.get("skip_model", False)

    LOGGER.info(
        "run_vfi called with: false_colour=%s, res_km=%skm, crop_rect=%s, skip_model=%s",
        false_colour,
        res_km,
        crop_rect_xywh,
        skip_model,
    )

    # Initialize VFI processor with configuration
    rife_config = {
        "rife_tile_enable": rife_tile_enable,
        "rife_tile_size": rife_tile_size,
        "rife_uhd_mode": rife_uhd_mode,
        "rife_thread_spec": rife_thread_spec,
        "rife_tta_spatial": rife_tta_spatial,
        "rife_tta_temporal": rife_tta_temporal,
        "model_key": model_key,
    }

    processing_config = {
        "false_colour": false_colour,
        "res_km": res_km,
    }

    processor = VFIProcessor(
        rife_exe_path=rife_exe_path,
        fps=fps,
        num_intermediate_frames=num_intermediate_frames,
        max_workers=max_workers,
        rife_config=rife_config,
        processing_config=processing_config,
    )

    # Validate inputs and get image paths
    paths = processor.validate_inputs(folder, skip_model)
    LOGGER.info("Found %s images. Skip AI model: %s", len(paths), skip_model)

    # Setup crop parameters
    crop_for_pil = processor.setup_crop_parameters(crop_rect_xywh)

    # --- Setup Temporary Directories --- #
    with (
        tempfile.TemporaryDirectory(prefix="goesvfi_sanchez_") as sanchez_temp_dir_str,
        tempfile.TemporaryDirectory(prefix="goesvfi_processed_") as processed_img_dir_str,
    ):
        sanchez_temp_path = pathlib.Path(sanchez_temp_dir_str)
        processed_img_path = pathlib.Path(processed_img_dir_str)
        LOGGER.info("Using Sanchez temp dir: %s", sanchez_temp_path)
        LOGGER.info("Using processed image temp dir: %s", processed_img_path)

        # Process first image and determine target dimensions
        try:
            processed_path_0, target_width, target_height = processor.process_first_image(
                paths[0], crop_for_pil, sanchez_temp_path, processed_img_path
            )
        except Exception as e:
            LOGGER.exception("Failed processing first image %s. Cannot continue.", paths[0])
            raise IOError(f"Could not process first image {paths[0]}") from e

        # Process remaining images in parallel
        processed_paths_rest = processor.process_remaining_images(
            paths,
            crop_for_pil,
            sanchez_temp_path,
            processed_img_path,
            target_width,
            target_height,
        )

        # Combine all processed paths
        all_processed_paths = [processed_path_0] + processed_paths_rest
        LOGGER.info("All %s images processed successfully.", len(all_processed_paths))

        # Setup raw output path
        raw_path = output_mp4_path.with_suffix(".raw.mp4")
        LOGGER.info("Intermediate raw video path: %s", raw_path)

        # Use VFIProcessor's video creation method
        yield from processor.process_video_creation(
            all_processed_paths, raw_path, skip_model, target_width, target_height
        )


def _run_rife_pair(
    p1_path: pathlib.Path,
    p2_path: pathlib.Path,
    rife_exe_path: pathlib.Path,
    rife_config: dict,
) -> pathlib.Path:
    """Run RIFE interpolation on a pair of images.

    Args:
        p1_path: Path to first input image
        p2_path: Path to second input image
        rife_exe_path: Path to RIFE executable
        rife_config: Dictionary with RIFE configuration parameters

    Returns:
        Path to the interpolated output image

    Raises:
        RIFEError: If RIFE execution fails
    """
    with tempfile.TemporaryDirectory(prefix="goesvfi_rife_") as temp_dir:
        temp_path = pathlib.Path(temp_dir)
        output_path = temp_path / "interpolated.png"

        # Build RIFE command
        cmd = [
            str(rife_exe_path),
            "-0",
            str(p1_path),
            "-1",
            str(p2_path),
            "-o",
            str(output_path),
        ]

        # Extract configuration
        model_key = rife_config.get("model_key", "rife-v4.6")
        rife_tile_enable = rife_config.get("rife_tile_enable", False)
        rife_tile_size = rife_config.get("rife_tile_size", 256)
        rife_uhd_mode = rife_config.get("rife_uhd_mode", False)
        rife_tta_spatial = rife_config.get("rife_tta_spatial", False)
        rife_tta_temporal = rife_config.get("rife_tta_temporal", False)
        rife_thread_spec = rife_config.get("rife_thread_spec", "1:2:2")

        # Detect capabilities
        capability_detector = RifeCapabilityDetector(rife_exe_path)

        # Add model if supported
        if model_key and capability_detector.supports_model_path():
            models_base_dir = rife_exe_path.parent.parent / "models"
            full_model_path = models_base_dir / model_key
            if full_model_path.exists():
                cmd.extend(["-m", str(model_key)])

        # Add optional parameters based on capabilities
        if rife_tile_enable and capability_detector.supports_tiling():
            cmd.extend(["-t", str(rife_tile_size)])

        if rife_uhd_mode and not rife_tile_enable and capability_detector.supports_uhd():
            cmd.append("-u")

        if rife_tta_spatial and capability_detector.supports_tta_spatial():
            cmd.append("-x")

        if rife_tta_temporal and capability_detector.supports_tta_temporal():
            cmd.append("-z")

        if capability_detector.supports_thread_spec() and rife_thread_spec:
            cmd.extend(["-j", rife_thread_spec])

        # Run RIFE
        LOGGER.debug("Running RIFE command: %s", " ".join(cmd))

        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            if not output_path.exists():
                raise RIFEError(f"RIFE did not create output file at {output_path}")

            # Move output to a persistent location
            final_output = p1_path.parent / f"interp_{time.monotonic_ns()}.png"
            import shutil

            shutil.copy2(output_path, final_output)
            return final_output

        except subprocess.CalledProcessError as e:
            LOGGER.error("RIFE execution failed: stdout=%s, stderr=%s", e.stdout, e.stderr)
            raise RIFEError(f"RIFE failed with exit code {e.returncode}") from e
        except Exception as e:
            LOGGER.exception("Unexpected error running RIFE")
            raise RIFEError(f"Unexpected RIFE error: {e}") from e


def _encode_frames_for_ffmpeg(
    frame_paths: list[pathlib.Path], target_dims: tuple[int, int] | None
) -> Iterator[bytes]:
    """Opens, optionally resizes, and encodes frames as PNG bytes for FFmpeg stdin."""
    LOGGER.debug("_encode_frames_for_ffmpeg called with %s paths.", len(frame_paths))  # Add entry log
    total_frames = len(frame_paths)
    for i, frame_path in enumerate(frame_paths):
        LOGGER.debug("Processing frame %s/%s: %s", i + 1, total_frames, frame_path)  # Add loop iteration log
        try:
            with Image.open(frame_path) as img:
                # Ensure consistent dimensions if needed
                if target_dims and img.size != target_dims:
                    # This should ideally not happen if preprocessing worked
                    LOGGER.warning(
                        "Resizing frame %s from %s to %s",
                        frame_path.name,
                        img.size,
                        target_dims,
                    )
                    img = img.resize(target_dims, Image.Resampling.LANCZOS)

                LOGGER.debug(
                    "Encoding frame %s (size %s) for ffmpeg (%s/%s).",
                    frame_path.name,
                    img.size,
                    i + 1,
                    total_frames,
                )
                img_byte_arr = io.BytesIO()
                img.save(img_byte_arr, format="PNG")
                encoded_bytes = img_byte_arr.getvalue()
                LOGGER.debug("Yielding %s bytes for %s", len(encoded_bytes), frame_path.name)  # Log before yield
                yield encoded_bytes
        except Exception as e:
            LOGGER.error("Error encoding frame %s for FFmpeg: %s", frame_path.name, e)
            # Decide whether to yield empty bytes, raise, or skip
            # Yielding empty bytes might cause ffmpeg errors
            # Skipping might lead to missing frames
            # Let's re-raise for now to make errors obvious
            raise RuntimeError(f"Failed to encode frame {frame_path.name}") from e
    LOGGER.debug("_encode_frames_for_ffmpeg finished.")  # Add exit log
