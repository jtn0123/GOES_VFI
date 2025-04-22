# TODO: PyQt6 main window implementation
from __future__ import annotations
"""
GOES‑VFI PyQt6 GUI – v0.1
Run with:  python -m goesvfi.gui
"""

import sys
import pathlib
import argparse # <-- Import argparse
import importlib.resources as pkgres
from typing import Optional, Any, cast, Union, Tuple, Iterator
from datetime import datetime
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QSize, QPoint, QRect, QSettings, QByteArray
from PyQt6.QtWidgets import (
    QApplication, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QProgressBar, QSpinBox, QVBoxLayout, QWidget,
    QMessageBox, QComboBox, QCheckBox, QTabWidget, QTableWidget, QTableWidgetItem, QStatusBar,
    QDialog, QDialogButtonBox, QRubberBand, QGridLayout, QDoubleSpinBox
)
from PyQt6.QtGui import QPixmap, QMouseEvent, QCloseEvent # <-- Add QCloseEvent
import json # Import needed for pretty printing the dict

from goesvfi.utils import config, log

LOGGER = log.get_logger(__name__)

# ─── Custom clickable label ────────────────────────────────────────────────
class ClickableLabel(QLabel):
    clicked = pyqtSignal()

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.file_path: str | None = None # Add file_path attribute
        # enable mouse tracking / events
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mouseReleaseEvent(self, ev: QMouseEvent | None) -> None:
        # Check if ev is not None before accessing attributes
        if ev is not None and ev.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        # Pass ev to super method (it handles None correctly)
        super().mouseReleaseEvent(ev)

# ─── ZoomDialog closes on any click ──────────────────────────────────────
class ZoomDialog(QDialog):
    def __init__(self, pixmap: QPixmap, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        lbl = QLabel(self)
        lbl.setPixmap(pixmap)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout = QVBoxLayout(self)
        layout.addWidget(lbl)
        self.resize(pixmap.size())

    # Add type hint for event
    def mousePressEvent(self, ev: QMouseEvent | None) -> None:
        self.close()

# ─── CropDialog class ─────────────────────────────────────────────
class CropDialog(QDialog):
    def __init__(self, pixmap: QPixmap, init: tuple[int,int,int,int]|None, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Select Crop Region")

        self.original_pixmap = pixmap
        self.scale_factor = 1.0

        # --- Scale pixmap for display ---
        screen = QApplication.primaryScreen()
        if not screen:
            LOGGER.warning("Could not get screen geometry, crop dialog might be too large.")
            max_size = QSize(1024, 768) # Fallback size
        else:
            # Use 90% of available screen size
            max_size = screen.availableGeometry().size() * 0.9

        scaled_pix = pixmap.scaled(
            max_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.scale_factor = pixmap.width() / scaled_pix.width()
        # --- End scaling ---

        self.lbl = QLabel()
        self.lbl.setPixmap(scaled_pix) # Display scaled pixmap
        self.lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.rubber = QRubberBand(QRubberBand.Shape.Rectangle, self.lbl)
        self.origin = QPoint()
        self.crop_rect_scaled = QRect() # Store the rect drawn on the scaled pixmap

        if init:
            # Scale the initial rect DOWN for display
            init_rect_orig = QRect(*init)
            scaled_x = int(init_rect_orig.x() / self.scale_factor)
            scaled_y = int(init_rect_orig.y() / self.scale_factor)
            scaled_w = int(init_rect_orig.width() / self.scale_factor)
            scaled_h = int(init_rect_orig.height() / self.scale_factor)
            scaled_init_rect = QRect(scaled_x, scaled_y, scaled_w, scaled_h)
            self.rubber.setGeometry(scaled_init_rect)
            self.crop_rect_scaled = scaled_init_rect
            self.rubber.show()
        else:
            # Ensure crop_rect_scaled is initialized if no init rect
            self.crop_rect_scaled = QRect()

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel,
            parent=self
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.addWidget(self.lbl)
        lay.addWidget(btns)

        # Adjust dialog size hint based on scaled content
        self.resize(lay.sizeHint())

    def mousePressEvent(self, ev: QMouseEvent | None) -> None:
        if ev is not None and ev.button() == Qt.MouseButton.LeftButton and self.lbl.geometry().contains(ev.pos()):
            self.origin = self.lbl.mapFromParent(ev.pos())
            # Ensure origin is within scaled pixmap boundaries
            if not self.lbl.pixmap().rect().contains(self.origin):
                 self.origin = QPoint()
                 return
            self.rubber.setGeometry(QRect(self.origin, QSize()))
            self.rubber.show()

    def mouseMoveEvent(self, ev: QMouseEvent | None) -> None:
        if ev is not None and not self.origin.isNull():
            cur = self.lbl.mapFromParent(ev.pos())
            # Clamp the current position to be within the scaled pixmap bounds
            scaled_pix_rect = self.lbl.pixmap().rect()
            cur.setX(max(0, min(cur.x(), scaled_pix_rect.width())))
            cur.setY(max(0, min(cur.y(), scaled_pix_rect.height())))
            self.rubber.setGeometry(QRect(self.origin, cur).normalized())

    def mouseReleaseEvent(self, ev: QMouseEvent | None) -> None:
        if ev is not None and ev.button() == Qt.MouseButton.LeftButton and not self.origin.isNull():
            # Store the geometry relative to the scaled pixmap
            self.crop_rect_scaled = self.rubber.geometry()
            self.origin = QPoint()

    # Return the rectangle coordinates scaled UP to the original pixmap size
    def getRect(self) -> QRect:
        orig_x = int(self.crop_rect_scaled.x() * self.scale_factor)
        orig_y = int(self.crop_rect_scaled.y() * self.scale_factor)
        orig_w = int(self.crop_rect_scaled.width() * self.scale_factor)
        orig_h = int(self.crop_rect_scaled.height() * self.scale_factor)

        # Clamp to original image boundaries
        orig_w = max(0, min(orig_w, self.original_pixmap.width() - orig_x))
        orig_h = max(0, min(orig_h, self.original_pixmap.height() - orig_y))
        orig_x = max(0, min(orig_x, self.original_pixmap.width()))
        orig_y = max(0, min(orig_y, self.original_pixmap.height()))

        return QRect(orig_x, orig_y, orig_w, orig_h)

# ────────────────────────────── Worker thread ──────────────────────────────
class VfiWorker(QThread):
    progress = pyqtSignal(int, int, float)
    finished = pyqtSignal(pathlib.Path)
    error    = pyqtSignal(str)

    def __init__(
        self,
        in_dir: pathlib.Path,
        out_file_path: pathlib.Path,
        fps: int,
        mid_count: int,
        model_key: str,
        tile_enable: bool,
        max_workers: int,
        encoder: str,
        use_ffmpeg_interp: bool,
        skip_model: bool,
        crf: int,
        bitrate_kbps: int,
        bufsize_kb: int,
        pix_fmt: str,
        crop_rect: tuple[int, int, int, int] | None,
        debug_mode: bool,
        filter_preset: str,
        mi_mode: str,
        mc_mode: str,
        me_mode: str,
        me_algo: str,
        search_param: int,
        scd_mode: str,
        scd_threshold: Optional[float],
        apply_unsharp: bool,
        unsharp_lx: int,
        unsharp_ly: int,
        unsharp_la: float,
        unsharp_cx: int,
        unsharp_cy: int,
        unsharp_ca: float,
        minter_mb_size: int | None,
        minter_vsbmc: int
    ) -> None:
        super().__init__()
        self.in_dir        = in_dir
        self.out_file_path = out_file_path
        self.fps           = fps
        self.mid_count     = mid_count
        self.model_key     = model_key
        self.tile_enable   = tile_enable
        self.max_workers   = max_workers
        self.encoder       = encoder
        self.use_ffmpeg_interp = use_ffmpeg_interp
        self.skip_model = skip_model
        self.crf = crf
        self.bitrate_kbps = bitrate_kbps
        self.bufsize_kb = bufsize_kb
        self.pix_fmt = pix_fmt
        self.crop_rect     = crop_rect
        self.debug_mode = debug_mode
        self.filter_preset = filter_preset
        self.apply_unsharp = apply_unsharp

        # Store new filter params
        self.mi_mode = mi_mode
        self.mc_mode = mc_mode
        self.me_mode = me_mode
        self.me_algo = me_algo
        self.search_param = search_param
        self.scd_mode = scd_mode
        self.scd_threshold = scd_threshold
        self.unsharp_lx = unsharp_lx
        self.unsharp_ly = unsharp_ly
        self.unsharp_la = unsharp_la
        self.unsharp_cx = unsharp_cx
        self.unsharp_cy = unsharp_cy
        self.unsharp_ca = unsharp_ca
        self.minter_mb_size = minter_mb_size
        self.minter_vsbmc = minter_vsbmc

        # placeholder for middle-frame preview
        self.mid_frame_path: str | None = None
        # Find the RIFE executable within the package data (e.g., in a 'bin' folder)
        # IMPORTANT: Place your RIFE executable (e.g., 'rife-cli') in goesvfi/bin/
        #            and ensure it's executable.
        try:
            # pkgres.files returns a Traversable, convert to Path
            # In Python 3.9+, can use pkgres.files('goesvfi').joinpath('bin', 'rife-cli')
            # For broader compatibility, resolve first.
            rife_exe_resource = pkgres.files('goesvfi').joinpath('bin', 'rife-cli')
            # Need to resolve the Traversable to an actual file system path
            with pkgres.as_file(rife_exe_resource) as exe_path:
                 self.rife_exe_path = exe_path
        except FileNotFoundError:
             # Provide a more informative error if the exe isn't found
             raise FileNotFoundError("RIFE executable not found in package data (expected goesvfi/bin/rife-cli)")

        # Store interpolation preference locally for clarity in this method
        self._do_ffmpeg_interp = use_ffmpeg_interp

    def run(self) -> None:
        from goesvfi.pipeline.run_vfi import run_vfi
        from goesvfi.pipeline.encode import encode_with_ffmpeg, _run_ffmpeg_command # Import helper

        raw_intermediate_path: Optional[pathlib.Path] = None
        filtered_intermediate_path: Optional[pathlib.Path] = None
        input_for_final_encode: Optional[pathlib.Path] = None

        try:
            LOGGER.info("Starting VFI worker for %s -> %s", self.in_dir, self.out_file_path)
            # record the original middle input PNG for post‑processing preview
            all_pngs = sorted(self.in_dir.glob("*.png"))
            if all_pngs:
                mid_idx = len(all_pngs) // 2 # Use floor division
                # Ensure index is valid even for list with 1 element
                mid_idx = min(mid_idx, len(all_pngs) - 1)
                mid = all_pngs[mid_idx]
                self.mid_frame_path = str(mid)
                LOGGER.info(f"Recorded middle frame path for preview: {self.mid_frame_path}")
            else:
                LOGGER.warning("No PNGs found in input dir, cannot set mid_frame_path.")

            # --- Step A: Generating raw intermediate video --- #
            LOGGER.info("Step 1: Generating raw intermediate video (no FFmpeg interp here)...")
            # Ensure use_ffmpeg_interp is FALSE for this step
            run_vfi_kwargs = {
                'crop_rect': self.crop_rect,
                'model_key': self.model_key,
                'skip_model': self.skip_model,
                # Force use_ffmpeg_interp to False here, it's handled later
                'use_ffmpeg_interp': False
            }
            # Run the VFI pipeline to get the raw intermediate
            run_vfi_iterator: Iterator[Union[Tuple[int, int, float], pathlib.Path]] = run_vfi(
                folder=self.in_dir,
                output_mp4_path=self.out_file_path, # Base path for intermediates
                rife_exe_path=self.rife_exe_path,
                fps=self.fps,
                num_intermediate_frames=self.mid_count,
                tile_enable=self.tile_enable,
                max_workers=self.max_workers,
                **run_vfi_kwargs
            )
            for update in run_vfi_iterator:
                if isinstance(update, pathlib.Path):
                    raw_intermediate_path = update
                    LOGGER.info(f"Raw intermediate video created: {raw_intermediate_path}")
                elif isinstance(update, tuple):
                    idx, total, eta = update
                    self.progress.emit(idx, total, eta)
                else:
                    LOGGER.warning(f"Received unexpected update type from run_vfi: {type(update)}")

            if not raw_intermediate_path or not raw_intermediate_path.exists():
                raise RuntimeError(f"Raw intermediate video path not received or file not found: {raw_intermediate_path}")

            # --- Step B: Optional FFmpeg Filtering Pass --- #
            if self._do_ffmpeg_interp:
                LOGGER.info("Step 1.5: Applying FFmpeg motion interpolation filter (Safe HQ Settings)...")
                filtered_intermediate_path = raw_intermediate_path.with_name(
                    f"{raw_intermediate_path.stem}.filtered{raw_intermediate_path.suffix}"
                )

                # --- Build dynamic filter strings --- #
                # Base minterpolate options from GUI
                hq_filter_options = {
                    "mi_mode": self.mi_mode,
                    "mc_mode": self.mc_mode,
                    "me_mode": self.me_mode,
                    "search_param": str(self.search_param),
                    "fps": str(self.fps * 2),
                }
                # Add Motion Estimation algorithm if not default
                if self.me_algo != "(default)":
                    hq_filter_options["me"] = self.me_algo
                # Add Scene Change Detection options
                hq_filter_options["scd"] = self.scd_mode
                if self.scd_mode == "fdiff" and self.scd_threshold is not None:
                    hq_filter_options["scd_threshold"] = f"{self.scd_threshold:.1f}"
                # Add mb_size if specified
                if self.minter_mb_size is not None:
                    hq_filter_options["mb_size"] = str(self.minter_mb_size)
                # Add vsbmc
                hq_filter_options["vsbmc"] = str(self.minter_vsbmc)

                minterpolate_str = "minterpolate=" + ":".join([f"{k}={v}" for k, v in hq_filter_options.items()])

                # Unsharp options from GUI
                unsharp_str = (
                    f"unsharp="
                    f"luma_msize_x={self.unsharp_lx}:luma_msize_y={self.unsharp_ly}:luma_amount={self.unsharp_la:.1f}:"
                    f"chroma_msize_x={self.unsharp_cx}:chroma_msize_y={self.unsharp_cy}:chroma_amount={self.unsharp_ca:.1f}"
                )

                # Combine conditionally
                safe_hq_filter_str = minterpolate_str
                if self.apply_unsharp:
                    safe_hq_filter_str += f",{unsharp_str}"
                # --- End dynamic filter strings --- #

                # --- Attempt 1: Try the dynamically built HQ settings --- # (Renamed section)
                try:
                    filter_desc = "Filtering Pass (Safe HQ - Custom)" # Updated description
                    # Build the filtering command (using selected preset)
                    cmd_filter = [
                        "ffmpeg", # Base command starts here
                        # Add -report and -loglevel debug for detailed error logging
                        "-report",
                        "-hide_banner", "-loglevel", "debug", "-stats", "-y",
                        "-i", str(raw_intermediate_path),
                        "-vf", safe_hq_filter_str,
                        "-c:v", "libx264", "-preset", self.filter_preset, # <-- Use selected preset
                        "-an",
                        "-pix_fmt", self.pix_fmt,
                        str(filtered_intermediate_path)
                    ]
                    # Run the filtering command using the helper
                    _run_ffmpeg_command(cmd_filter, filter_desc)
                    input_for_final_encode = filtered_intermediate_path
                    LOGGER.info(f"{filter_desc} created: {input_for_final_encode}")

                # --- Fallback: If HQ fails, revert to Simple settings --- #
                except RuntimeError as e:
                    LOGGER.warning(f"{filter_desc} failed ({e})—falling back to basic motion-interp.")

                    # --- Build Simple filter + Optional Unsharp --- #
                    simple_minterpolate_str = (
                        "minterpolate="
                        f"mi_mode=mci:"
                        f"mc_mode=aobmc:"
                        f"me_mode=bidir:"
                        f"search_param=60:"
                        f"scd=none:"
                        f"fps={self.fps * 2}"
                    )
                    # Combine simple minterpolate and unsharp conditionally
                    simple_filter_str = simple_minterpolate_str
                    if self.apply_unsharp:
                         # Use the same unsharp settings as configured in the GUI for fallback too
                         unsharp_str = (
                            f"unsharp="
                            f"luma_msize_x={self.unsharp_lx}:luma_msize_y={self.unsharp_ly}:luma_amount={self.unsharp_la:.1f}:"
                            f"chroma_msize_x={self.unsharp_cx}:chroma_msize_y={self.unsharp_cy}:chroma_amount={self.unsharp_ca:.1f}"
                         )
                         simple_filter_str += f",{unsharp_str}"
                    # Rebuild the command with the simple filter + optional unsharp
                    cmd_filter_fallback = [
                        "ffmpeg", # Base command starts here
                        # Keep -report and -loglevel debug for the fallback too
                        "-report",
                        "-hide_banner", "-loglevel", "debug", "-stats", "-y",
                        "-i", str(raw_intermediate_path),
                        "-vf", simple_filter_str, # Use the simple filter string
                        "-c:v", "libx264", "-preset", self.filter_preset, # <-- Use selected preset
                        "-an",
                        "-pix_fmt", self.pix_fmt,
                        str(filtered_intermediate_path)
                    ]
                    # Re-run the command with the simple filter
                    _run_ffmpeg_command(cmd_filter_fallback, "Filtering Pass (Fallback Simple)")
                    input_for_final_encode = filtered_intermediate_path
                    LOGGER.info(f"Filtered intermediate video created (Fallback Simple): {input_for_final_encode}")

            else:
                # If not filtering, use the raw intermediate directly for the final encode
                input_for_final_encode = raw_intermediate_path
                LOGGER.info("Skipping FFmpeg motion interpolation filter pass.")

            # Check if the input for the next step exists
            if not input_for_final_encode or not input_for_final_encode.exists():
                raise RuntimeError(f"Input file for final encoding not found: {input_for_final_encode}")

            # --- Step C: Final Encoding Pass --- #
            LOGGER.info(f"Step 2: Final encoding from {input_for_final_encode} -> {self.out_file_path} using encoder '{self.encoder}'")

            encode_with_ffmpeg(
                intermediate_input=input_for_final_encode,
                final_output=self.out_file_path,
                encoder=self.encoder,
                # fps and use_interp are no longer passed
                crf=self.crf,
                bitrate_kbps=self.bitrate_kbps,
                bufsize_kb=self.bufsize_kb,
                pix_fmt=self.pix_fmt
            )

            LOGGER.info(f"Final output created: {self.out_file_path}")
            self.finished.emit(self.out_file_path)

        except Exception as exc:
            LOGGER.exception("Worker failed")
            self.error.emit(str(exc))

        finally:
            # --- Log debug status before cleanup --- #
            LOGGER.info(f"Worker finished. Debug mode is set to: {self.debug_mode}") # <-- Added log
            # --- Cleanup Intermediates --- #
            if not self.debug_mode: # <-- Check debug flag
                files_to_delete = [raw_intermediate_path, filtered_intermediate_path]
                for file_path in files_to_delete:
                    if file_path and file_path.exists() and file_path != self.out_file_path:
                        try:  # <-- Indent this block
                            LOGGER.info(f"Cleaning up intermediate file: {file_path}")
                            file_path.unlink()
                        except OSError as e:
                            LOGGER.error(f"Failed to delete intermediate file {file_path}: {e}")

# ──────────────────────────────── Main window ─────────────────────────────
class MainWindow(QWidget):
    def __init__(self, debug_mode: bool = False) -> None:
        super().__init__()
        self.setWindowTitle("GOES‑VFI")
        self.debug_mode = debug_mode

        self._base_output_path: pathlib.Path | None = None
        self.settings = QSettings("YourOrg", "GOESVFI")
        saved_crop = self.settings.value("main/cropRect", None)
        self.crop_rect = tuple(map(int, saved_crop.split(","))) if isinstance(saved_crop, str) else None

        self.tabs = QTabWidget()
        self.tabs.addTab(self._makeMainTab(), "Interpolate")
        self.tabs.addTab(self._makeFilterTab(), "Interpolation Filters") # <-- Add new tab
        self.tabs.addTab(self._makeModelLibraryTab(), "Models")
        self.ffmpeg_tab = QWidget()
        self.tabs.addTab(self.ffmpeg_tab, "FFmpeg Quality")
        self._build_ffmpeg_tab()

        self.status_bar = QStatusBar()
        self.status_bar.showMessage("Ready")

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(self.tabs)
        main_layout.addWidget(self.status_bar)
        self.setLayout(main_layout)

        self.worker: VfiWorker | None = None
        self._connect_filter_tab_signals() # Connect signals after controls are created

        self.loadSettings() # <-- Load settings after UI is built

    def _pick_in_dir(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Input Folder")
        if not folder:
            return
        self.in_edit.setText(folder)
        self._update_previews()

    def _pick_out_file(self) -> None:
        suggested_dir = self._base_output_path.parent if self._base_output_path else config.get_output_dir()
        suggested_name = self._base_output_path.name if self._base_output_path else "goes_animated.mp4"
        suggested = str(suggested_dir / suggested_name)
        path_str, _ = QFileDialog.getSaveFileName(self, "Save MP4", suggested, "MP4 files (*.mp4)")
        if path_str:
            path = pathlib.Path(path_str)
            self.out_edit.setText(str(path))
            self._base_output_path = path

    def _makeMainTab(self) -> QWidget:
        """Builds the main 'Interpolate' tab UI."""
        # Create a container widget for this tab's layout
        main_tab_widget = QWidget()
        layout = QVBoxLayout(main_tab_widget) # Layout for the main tab

        # Widgets (moved from __init__)
        self.in_edit   = QLineEdit()
        self.in_browse = QPushButton("Browse…")
        self.out_edit   = QLineEdit()
        self.out_browse = QPushButton("Save As…")
        self.fps_spin   = QSpinBox(); self.fps_spin.setRange(1, 240); self.fps_spin.setValue(10)
        self.mid_spin   = QSpinBox()
        self.mid_spin.setRange(1, 3)
        self.mid_spin.setSingleStep(2)
        self.mid_spin.setValue(1)
        self.mid_spin.setToolTip(
            "Number of in-between frames per original pair:\n"
            "• 1 = single midpoint (fastest)\n"
            "• 3 = recursive three-step (smoother)"
        )
        self.model_combo = QComboBox()
        self.model_combo.addItems([
            "RIFE v4.6 (default)",
        ])
        self.model_combo.setToolTip(
            "Choose your interpolation model.\n"
            "Currently only the built-in RIFE model is used."
        )
        self.start_btn  = QPushButton("Start")
        self.progress   = QProgressBar(); self.progress.setRange(0, 1)

        # ─── Encoder Selection ────────────────────────────────────────────
        self.encode_combo = QComboBox()
        self.encode_combo.addItems([
            "None (copy original)",
            "Software x265",
            "Software x265 (2-Pass)",
            "Hardware HEVC (VideoToolbox)",
            "Hardware H.264 (VideoToolbox)",
            # TODO: Add Windows/Linux hardware options if desired
        ])
        self.encode_combo.setToolTip(
            "Pick your output codec, or None to skip re-encoding."
        )
        # Update default setting logic: prioritize HEVC
        available_encoders = [self.encode_combo.itemText(i) for i in range(self.encode_combo.count())]
        if "Hardware HEVC (VideoToolbox)" in available_encoders:
            self.encode_combo.setCurrentText("Hardware HEVC (VideoToolbox)")
        elif "Hardware H.264 (VideoToolbox)" in available_encoders:
            self.encode_combo.setCurrentText("Hardware H.264 (VideoToolbox)")
        else:
            self.encode_combo.setCurrentText("Software x265") # Fallback

        # ─── FFmpeg motion interpolation toggle ───────────────────────────
        self.ffmpeg_interp_cb = QCheckBox("Use FFmpeg motion interpolation")
        self.ffmpeg_interp_cb.setChecked(True)
        self.ffmpeg_interp_cb.setToolTip(
            "Apply FFmpeg's 'minterpolate' filter before encoding."
        )
        # ─── Skip model interpolation toggle ─────────────────────
        self.skip_model_cb = QCheckBox("Skip AI interpolation (use originals only)")
        self.skip_model_cb.setChecked(False)
        self.skip_model_cb.setToolTip(
            "If checked, do not run the AI model; video will be assembled from\n"
            "original frames (optionally with FFmpeg interpolation)."
        )

        # ─── Max parallel workers ─────────────────────────────────────────
        self.workers_spin = QSpinBox()
        # Get cpu_count safely for default value
        import os
        cpu_cores = os.cpu_count() or 1 # Default to 1 if None
        default_workers = max(1, cpu_cores - 1) # Leave one free if possible
        self.workers_spin.setRange(1, max(8, cpu_cores)) # Allow up to cpu_count or 8
        self.workers_spin.setValue(min(default_workers, 8)) # Default, capped at 8
        self.workers_spin.setToolTip(
            "Max number of parallel interpolation processes (CPU has " + str(cpu_cores) + ").\n"
            "Reduce if you experience memory issues."
        )

        # ─── Tiling toggle ────────────────────────────────────────────────
        self.tile_checkbox = QCheckBox("Enable tiling for large frames (>2k)")
        self.tile_checkbox.setChecked(True) # Default to ON
        self.tile_checkbox.setToolTip(
            "Split large frames into tiles before interpolating.\n"
            "Faster & uses less RAM, but may have edge artifacts.\n"
            "Disable if RAM allows or edges look bad."
        )

        # ─── Preview thumbnails ───────────────────────────────────────────
        self.preview_first = ClickableLabel("First frame")
        self.preview_mid   = ClickableLabel("Mid frame")
        self.preview_last  = ClickableLabel("Last frame")
        for lbl in (self.preview_first, self.preview_mid, self.preview_last):
            lbl.setFixedSize(128,128)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("border: 1px solid gray; background-color: #eee;")
            # Connect click -> open dialog
            lbl.clicked.connect(lambda lb=lbl: self._show_zoom(lb))

        pv_row = QHBoxLayout()
        pv_row.addWidget(self.preview_first)
        pv_row.addWidget(self.preview_mid)
        pv_row.addWidget(self.preview_last)

        # Layout (Specific to this tab)
        in_row  = QHBoxLayout();  in_row.addWidget(QLabel("Input folder:"));  in_row.addWidget(self.in_edit);  in_row.addWidget(self.in_browse)
        out_row = QHBoxLayout(); out_row.addWidget(QLabel("Output MP4:"));  out_row.addWidget(self.out_edit); out_row.addWidget(self.out_browse)
        fps_row = QHBoxLayout(); fps_row.addWidget(QLabel("Target FPS:")); fps_row.addWidget(self.fps_spin); fps_row.addStretch()
        mid_row = QHBoxLayout(); mid_row.addWidget(QLabel("Intermediate frames:")); mid_row.addWidget(self.mid_spin); mid_row.addStretch()

        # Add new layout rows
        tile_row = QHBoxLayout()
        tile_row.addWidget(self.tile_checkbox)
        tile_row.addStretch()

        workers_row = QHBoxLayout()
        workers_row.addWidget(QLabel("Max workers:"))
        workers_row.addWidget(self.workers_spin)
        workers_row.addStretch()

        model_row = QHBoxLayout(); model_row.addWidget(QLabel("Model:")); model_row.addWidget(self.model_combo); model_row.addStretch()
        # Add layout row for encoder
        encode_row = QHBoxLayout(); encode_row.addWidget(QLabel("Encoder:")); encode_row.addWidget(self.encode_combo); encode_row.addStretch()

        # Add FFmpeg interpolation checkbox row
        interp_row = QHBoxLayout()
        interp_row.addWidget(self.ffmpeg_interp_cb)
        interp_row.addStretch()
        # Ensure this row is added
        layout.addLayout(interp_row)

        # Add skip_model checkbox row
        skip_row = QHBoxLayout()
        skip_row.addWidget(self.skip_model_cb)
        skip_row.addStretch()
        layout.addLayout(skip_row)

        # ─── Crop button ────────────────────────────────────────────────
        self.crop_btn = QPushButton("Crop…")
        self.crop_btn.setToolTip("Draw a rectangle on the first frame to crop all images")
        in_row.addWidget(self.crop_btn)
        self.crop_btn.clicked.connect(self._on_crop_clicked)

        # Add Clear Crop button (New)
        self.clear_crop_btn = QPushButton("Clear Crop")
        self.clear_crop_btn.setToolTip("Remove the current crop selection")
        in_row.addWidget(self.clear_crop_btn)
        self.clear_crop_btn.clicked.connect(self._on_clear_crop_clicked) # Connect new signal

        layout.addLayout(in_row); layout.addLayout(out_row);
        # Update layout adding order
        layout.addLayout(fps_row)
        layout.addLayout(mid_row)
        layout.addLayout(tile_row)      # Add tile row
        layout.addLayout(workers_row)   # Add workers row
        layout.addLayout(model_row)
        layout.addLayout(encode_row)    # Add encode row
        layout.addLayout(pv_row) # Add preview row
        layout.addWidget(self.start_btn); layout.addWidget(self.progress)

        # ─── Open in VLC button ───────────────────────────────────────────
        self.open_btn = QPushButton("Open in VLC")
        self.open_btn.setEnabled(False)
        self.open_btn.setToolTip("Launch the finished MP4 in VLC")
        layout.addWidget(self.open_btn) # Add button to layout

        # Signals (Connect signals specific to this tab's widgets here)
        self.in_browse.clicked.connect(self._pick_in_dir)
        self.out_browse.clicked.connect(self._pick_out_file)
        self.start_btn.clicked.connect(self._start)
        self.open_btn.clicked.connect(self._open_in_vlc) # Connect new button

        return main_tab_widget # Return the widget containing the tab's layout

    def _makeFilterTab(self) -> QWidget:
        """Builds the Interpolation Filters tab UI."""
        filter_tab_widget = QWidget()
        layout = QVBoxLayout(filter_tab_widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # --- motion interpolation settings --- #
        layout.addWidget(QLabel("<b>Motion Interpolation Filter Settings (minterpolate):</b>"))
        grid = QGridLayout()

        # Interpolation Mode
        mi_lbl = QLabel("Interpolation Mode (mi_mode):")
        self.mi_combo = QComboBox()
        self.mi_combo.addItems(["dup", "blend", "mci", "mc"])
        self.mi_combo.setCurrentText("mci") # Default
        self.mi_combo.setToolTip(
            "Method for creating intermediate frames.\n"
            "- dup: Duplicate frames (Fastest, no interpolation). Use for testing.\n"
            "- blend: Simple frame averaging (Fast, blurry).\n"
            "- mci: Motion Compensated Interpolation (Requires good motion vectors). Uses 'mc_mode', 'me_mode', 'me_algo', 'search_param'.\n"
            "- mc: Motion Compensation (No interpolation, just uses vectors). Often combined with 'mci'.\n"
            "Recommended: 'mci' for smooth results, requires tuning other MC params."
        )
        grid.addWidget(mi_lbl, 0, 0)
        grid.addWidget(self.mi_combo, 0, 1)

        # Motion Compensation Mode
        mc_lbl = QLabel("Motion Comp. Mode (mc_mode):")
        self.mc_combo = QComboBox()
        self.mc_combo.addItems(["obmc", "aobmc"])
        self.mc_combo.setCurrentText("obmc") # Default
        self.mc_combo.setToolTip(
            "Algorithm for applying motion vectors.\n"
            "- obmc: Overlapped Block Motion Compensation (Standard, good balance).\n"
            "- aobmc: Adaptive Overlapped Block MC (Potentially higher quality, slightly slower).\n"
            "Recommended: 'obmc' is usually sufficient."
        )
        grid.addWidget(mc_lbl, 1, 0)
        grid.addWidget(self.mc_combo, 1, 1)

        # Motion Estimation Mode
        me_lbl = QLabel("Motion Estimation Mode (me_mode):")
        self.me_combo = QComboBox()
        self.me_combo.addItems(["bidir", "bilat"]) # Removed 'direct' as it's less common/useful here
        self.me_combo.setCurrentText("bidir") # Default
        self.me_combo.setToolTip(
            "Direction for motion vector search.\n"
            "- bidir: Bidirectional (Uses past and future frames, generally best quality).\n"
            "- bilat: Bilateral (Alternative bidirectional, might differ slightly).\n"
            "Recommended: 'bidir' is the standard choice."
        )
        grid.addWidget(me_lbl, 2, 0)
        grid.addWidget(self.me_combo, 2, 1)

        # Motion Estimation Algorithm
        me_algo_lbl = QLabel("ME Algorithm (me_algo):")
        self.me_algo_combo = QComboBox()
        # Common/useful algorithms. Removed very old/esoteric ones.
        self.me_algo_combo.addItems(["(default)", "esa", "epzs", "hexbs", "umh"])
        self.me_algo_combo.setCurrentText("(default)") # Default
        self.me_algo_combo.setToolTip(
            "Algorithm for finding motion vectors. Affects speed and quality.\n"
            "- (default): FFmpeg's internal choice, often a good balance (usually EPZS or HexBS).\n"
            "- esa: Exhaustive Search (Slowest, highest quality, can be unstable).\n"
            "- epzs: Enhanced Predictive Zonal Search (Good balance, often recommended if not default).\n"
            "- hexbs: Hexagon-based Search (Faster than EPZS, good quality).\n"
            "- umh: Uneven Multi-Hexagon Search (Similar to hexbs, sometimes faster/better).\n"
            "Recommended: Start with '(default)'. Try 'epzs' or 'hexbs'/'umh' if needed."
        )
        grid.addWidget(me_algo_lbl, 3, 0) # Changed label var name
        grid.addWidget(self.me_algo_combo, 3, 1) # Changed combo var name

        # Search parameter
        search_param_lbl = QLabel("ME Search Parameter (search_param):")
        self.search_param_spin = QSpinBox()
        self.search_param_spin.setRange(4, 256) # Practical range
        self.search_param_spin.setValue(96) # Increased default, often better for complex motion
        self.search_param_spin.setToolTip(
            "Maximum pixel distance to search for motion vectors.\n"
            "Larger values = Slower, potentially better for fast motion.\n"
            "Smaller values = Faster, may miss distant motion.\n"
            "Recommended: 64-128 is often a good trade-off. High motion might need more."
        )
        grid.addWidget(search_param_lbl, 4, 0)
        grid.addWidget(self.search_param_spin, 4, 1)

        # Scene change detection algorithm
        scd_lbl = QLabel("Scene Change Detection (scd):")
        self.scd_combo = QComboBox()
        self.scd_combo.addItems(["none", "fdiff"])
        self.scd_combo.setCurrentText("fdiff") # Default to fdiff
        self.scd_combo.setToolTip(
            "Method to detect scene cuts to prevent interpolating across them.\n"
            "- fdiff: Frame Difference (Recommended). Prevents unnatural morphing between scenes.\n"
            "- none: No detection (Faster, but causes artifacts at scene changes)."
        )
        grid.addWidget(scd_lbl, 5, 0)
        grid.addWidget(self.scd_combo, 5, 1)

        # Scene change threshold
        scd_thresh_lbl = QLabel("Scene Change Threshold (%):") # Added unit
        self.scd_thresh_spin = QDoubleSpinBox()
        self.scd_thresh_spin.setRange(0.0, 100.0)
        self.scd_thresh_spin.setSingleStep(0.1)
        self.scd_thresh_spin.setValue(10.0) # Common default
        self.scd_thresh_spin.setDecimals(1) # Show one decimal
        self.scd_thresh_spin.setToolTip(
            "Sensitivity for 'fdiff' scene change detection (0-100%).\n"
            "Lower value = More sensitive (detects smaller changes as cuts).\n"
            "Higher value = Less sensitive (needs bigger changes).\n"
            "Recommended: Start with 8-12. Increase if it falsely detects cuts during fades/motion."
        )
        grid.addWidget(scd_thresh_lbl, 6, 0)
        grid.addWidget(self.scd_thresh_spin, 6, 1)

        # Filter Encoding Preset (NEW)
        filter_preset_lbl = QLabel("Filter Encoding Preset:")
        self.filter_preset_combo = QComboBox()
        self.filter_preset_combo.addItems([
            "ultrafast", "superfast", "veryfast", "faster", "fast",
            "medium", "slow", "slower", "veryslow"
        ])
        self.filter_preset_combo.setCurrentText("slow") # Changed default to slow for potentially better intermediate quality
        self.filter_preset_combo.setToolTip(
            "x264 encoding preset for the *intermediate* filtered video.\n"
            "Affects the encoding speed and compression efficiency of the temporary\n"
            "video file generated by the minterpolate filter BEFORE RIFE processing.\n"
            "Slower presets take longer but create a slightly smaller/higher quality\n"
            "intermediate file, which *might* minimally impact RIFE's input.\n"
            "This does NOT directly affect the final output encoding settings.\n"
            "Recommended: 'medium' or 'slow'. 'fast'/'faster' if speed is critical."
        )
        grid.addWidget(filter_preset_lbl, 7, 0) # Added at row 7
        grid.addWidget(self.filter_preset_combo, 7, 1)

        # Macroblock size
        mbsize_lbl = QLabel("Macroblock Size (mb_size):")
        self.mbsize_combo = QComboBox()
        self.mbsize_combo.addItems(["(default)", "16", "8", "4"])
        self.mbsize_combo.setCurrentText("(default)") # Default
        self.mbsize_combo.setToolTip(
            "Size of blocks (pixels) used for motion estimation.\n"
            "- (default)/16: Standard size, good balance of speed and detail.\n"
            "- 8/4: Smaller blocks capture finer motion detail but are *significantly* slower\n"
            "  and may increase processing time dramatically. Can sometimes cause artifacts.\n"
            "Compatibility: Sizes < 16 may be incompatible with some hardware decoders if used\n"
            "  directly in output, but less relevant for intermediate filter step.\n"
            "Recommended: Stick with '(default)' or '16' unless fine motion is poorly captured."
        )
        grid.addWidget(mbsize_lbl, 8, 0) # Moved to row 8
        grid.addWidget(self.mbsize_combo, 8, 1)

        # Variable-size block motion comp
        vsbmc_lbl = QLabel("Variable Size Blocks (vsbmc):")
        self.vsbmc_cb = QCheckBox()
        self.vsbmc_cb.setChecked(False) # Default off
        self.vsbmc_cb.setToolTip(
            "Allow using smaller block sizes within the main macroblock (mb_size).\n"
            "Potentially improves detail capture on complex motion, especially with smaller mb_size,\n"
            "but increases processing time significantly.\n"
            "Compatibility: May also impact hardware decoder compatibility if used directly.\n"
            "Recommended: Keep off unless necessary and prepared for longer processing."
        )
        grid.addWidget(vsbmc_lbl, 9, 0) # Moved to row 9
        grid.addWidget(self.vsbmc_cb, 9, 1)

        layout.addLayout(grid)
        layout.addSpacing(15)

        # --- unsharp settings --- #
        layout.addWidget(QLabel("<b>Sharpening Filter Settings (unsharp):</b>")) # Clarified filter name
        unsharp_grid = QGridLayout()

        self.unsharp_cb = QCheckBox("Apply 'unsharp' filter after interpolation") # Clarified text
        self.unsharp_cb.setChecked(True) # Default on
        self.unsharp_cb.setToolTip(
            "Apply the 'unsharp' filter to enhance detail after motion interpolation.\n"
            "Useful for slightly softening caused by interpolation or source material.\n"
            "Can significantly increase fine detail/noise. Disable if over-sharpening occurs."
        )
        unsharp_grid.addWidget(self.unsharp_cb, 0, 0, 1, 2) # Span 2 columns

        self.luma_x_label = QLabel("Luma Matrix X Size (lx):")
        unsharp_grid.addWidget(self.luma_x_label, 1, 0)
        self.luma_x_spin = QSpinBox(); self.luma_x_spin.setRange(3, 23); self.luma_x_spin.setSingleStep(2); self.luma_x_spin.setValue(7) # Increased default slightly
        self.luma_x_spin.setToolTip(
            "Horizontal size of the luma (brightness) sharpening mask (odd number, 3-23).\n"
            "Larger values consider a wider area for sharpening = smoother but less localized effect.\n"
            "Smaller values = sharper, more localized effect, can enhance noise.\n"
            "Recommended: 5 or 7 is common."
        )
        unsharp_grid.addWidget(self.luma_x_spin, 1, 1)

        self.luma_y_label = QLabel("Luma Matrix Y Size (ly):")
        unsharp_grid.addWidget(self.luma_y_label, 2, 0)
        self.luma_y_spin = QSpinBox(); self.luma_y_spin.setRange(3, 23); self.luma_y_spin.setSingleStep(2); self.luma_y_spin.setValue(7) # Increased default slightly
        self.luma_y_spin.setToolTip(
            "Vertical size of the luma (brightness) sharpening mask (odd number, 3-23).\n"
            "Similar effect to X size, but vertically.\n"
            "Recommended: 5 or 7 is common. Often same as X size."
        )
        unsharp_grid.addWidget(self.luma_y_spin, 2, 1)

        self.luma_amount_label = QLabel("Luma Amount (la):")
        unsharp_grid.addWidget(self.luma_amount_label, 3, 0)
        self.luma_amount_spin = QDoubleSpinBox(); self.luma_amount_spin.setRange(-1.5, 5.0); self.luma_amount_spin.setDecimals(1); self.luma_amount_spin.setSingleStep(0.1); self.luma_amount_spin.setValue(1.0) # Reduced default slightly
        self.luma_amount_spin.setToolTip(
            "Strength of luma (brightness) sharpening (-1.5 to 5.0).\n"
            "> 0 sharpens (higher = stronger, risk of halos/noise).\n"
            "< 0 blurs (rarely used here).\n"
            "0 = no luma sharpening.\n"
            "Recommended: Start around 0.5-1.0. Adjust carefully."
        )
        unsharp_grid.addWidget(self.luma_amount_spin, 3, 1)

        self.chroma_x_label = QLabel("Chroma Matrix X Size (cx):")
        unsharp_grid.addWidget(self.chroma_x_label, 4, 0)
        self.chroma_x_spin = QSpinBox(); self.chroma_x_spin.setRange(3, 23); self.chroma_x_spin.setSingleStep(2); self.chroma_x_spin.setValue(5)
        self.chroma_x_spin.setToolTip(
            "Horizontal size of the chroma (color) sharpening mask (odd number, 3-23).\n"
            "Similar to luma, but affects color detail. Sharpening chroma is often less\n"
            "desirable or noticeable and can introduce color artifacts.\n"
            "Recommended: Usually same or smaller than luma size (e.g., 3 or 5)."
        )
        unsharp_grid.addWidget(self.chroma_x_spin, 4, 1)

        self.chroma_y_label = QLabel("Chroma Matrix Y Size (cy):")
        unsharp_grid.addWidget(self.chroma_y_label, 5, 0)
        self.chroma_y_spin = QSpinBox(); self.chroma_y_spin.setRange(3, 23); self.chroma_y_spin.setSingleStep(2); self.chroma_y_spin.setValue(5)
        self.chroma_y_spin.setToolTip(
            "Vertical size of the chroma (color) sharpening mask (odd number, 3-23).\n"
            "Similar to chroma X size.\n"
            "Recommended: Usually same or smaller than luma size (e.g., 3 or 5). Often same as Chroma X."
        )
        unsharp_grid.addWidget(self.chroma_y_spin, 5, 1)

        self.chroma_amount_label = QLabel("Chroma Amount (ca):")
        unsharp_grid.addWidget(self.chroma_amount_label, 6, 0)
        self.chroma_amount_spin = QDoubleSpinBox(); self.chroma_amount_spin.setRange(-1.5, 5.0); self.chroma_amount_spin.setDecimals(1); self.chroma_amount_spin.setSingleStep(0.1); self.chroma_amount_spin.setValue(0.0) # Default to 0
        self.chroma_amount_spin.setToolTip(
             "Strength of chroma (color) sharpening (-1.5 to 5.0).\n"
             "> 0 sharpens color (can cause ringing/artifacts easily).\n"
             "< 0 blurs color.\n"
             "0 = no chroma sharpening (Often recommended).\n"
             "Recommended: Start at 0.0. Increase very slightly (e.g., 0.1-0.3) only if needed."
        )
        unsharp_grid.addWidget(self.chroma_amount_spin, 6, 1)

        layout.addLayout(unsharp_grid)

        return filter_tab_widget

    def _connect_filter_tab_signals(self) -> None:
        """Connect signals for enabling/disabling controls on the filter tab."""
        # Enable/disable scd_threshold based on scd mode
        self.scd_combo.currentTextChanged.connect(self._update_scd_thresh_state)
        # Enable/disable all unsharp controls based on master checkbox
        self.unsharp_cb.toggled.connect(self._update_unsharp_controls_state)
        # Initial state update
        self._update_scd_thresh_state(self.scd_combo.currentText())
        self._update_unsharp_controls_state(self.unsharp_cb.isChecked())

    def _update_scd_thresh_state(self, scd_mode: str) -> None:
        enable = (scd_mode == "fdiff")
        self.scd_thresh_spin.setEnabled(enable)

    def _update_unsharp_controls_state(self, checked: bool) -> None:
        widgets_to_toggle = [
            self.luma_x_label, self.luma_x_spin,
            self.luma_y_label, self.luma_y_spin,
            self.luma_amount_label, self.luma_amount_spin,
            self.chroma_x_label, self.chroma_x_spin,
            self.chroma_y_label, self.chroma_y_spin,
            self.chroma_amount_label, self.chroma_amount_spin,
            # Do not disable mb_size or vsbmc based on unsharp
        ]
        for widget in widgets_to_toggle:
            widget.setEnabled(checked)

    def _start(self) -> None:
        in_dir  = pathlib.Path(self.in_edit.text()).expanduser()

        # --- Generate timestamped output path based on the BASE path ---
        if self._base_output_path:
            base_out_path = self._base_output_path
        else:
            # Fallback if base path isn't set (shouldn't happen after init)
            LOGGER.warning("_base_output_path not set, falling back to current text.")
            base_out_path = pathlib.Path(self.out_edit.text()).expanduser()

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        stem, suf = base_out_path.stem, base_out_path.suffix or ".mp4" # Ensure .mp4
        # Ensure suffix starts with a dot if it exists but doesn't have one (pathlib quirk)
        if suf and not suf.startswith('.'):
            suf = '.' + suf
        # Use the parent from the base path
        final_out_mp4 = base_out_path.with_name(f"{stem}_{ts}{suf}")

        # Reflect the ACTUAL timestamped path back into the UI
        self.out_edit.setText(str(final_out_mp4))
        # --- End timestamp logic ---

        # Use the generated final_out_mp4 path from now on
        fps     = self.fps_spin.value()
        mid_count = self.mid_spin.value()
        model_key = self.model_combo.currentText()
        # Get values from new widgets
        tile_enable = self.tile_checkbox.isChecked()
        max_workers = self.workers_spin.value()
        encoder     = self.encode_combo.currentText()
        use_ffmpeg_interp = self.ffmpeg_interp_cb.isChecked()
        skip_model = self.skip_model_cb.isChecked()

        # --- Get Filter Tab Settings --- #
        mi_mode = self.mi_combo.currentText()
        mc_mode = self.mc_combo.currentText()
        me_mode = self.me_combo.currentText()
        me_algo = self.me_algo_combo.currentText()
        search_param = self.search_param_spin.value()
        scd_mode = self.scd_combo.currentText()
        scd_threshold = self.scd_thresh_spin.value() if scd_mode == "fdiff" else None # Pass None if not used

        apply_unsharp = self.unsharp_cb.isChecked()
        unsharp_lx = self.luma_x_spin.value()
        unsharp_ly = self.luma_y_spin.value()
        unsharp_la = self.luma_amount_spin.value()
        unsharp_cx = self.chroma_x_spin.value()
        unsharp_cy = self.chroma_y_spin.value()
        unsharp_ca = self.chroma_amount_spin.value()

        # Get mb_size, handle default
        mb_size_str = self.mbsize_combo.currentText()
        minter_mb_size = int(mb_size_str) if mb_size_str != "(default)" else None

        # Get vsbmc
        minter_vsbmc = 1 if self.vsbmc_cb.isChecked() else 0
        # --- End Filter Tab Settings --- #

        # Calculate CRF from preset text
        preset_text = self.preset_combo.currentText()
        try:
            # Extract number after "CRF "
            crf_value = int(preset_text.split("CRF ")[-1].rstrip(")"))
        except (IndexError, ValueError):
            LOGGER.warning(f"Could not parse CRF from preset '{preset_text}', defaulting to 20.")
            crf_value = 20 # Default fallback

        # --- Log all settings before starting worker ---
        settings_to_log = {
            "Input Directory": str(in_dir),
            "Output File": str(final_out_mp4),
            "FPS": fps,
            "Intermediate Frames": mid_count,
            "Model": model_key,
            "Tiling Enabled": tile_enable,
            "Max Workers": max_workers,
            "Encoder": encoder,
            "Use FFmpeg Interp": use_ffmpeg_interp,
            "Skip AI Model": skip_model,
            "Crop Rectangle": self.crop_rect,
            "Debug Mode": self.debug_mode,
            "Filters": {
                "Intermediate Preset": self.filter_preset_combo.currentText(),
                "MI Mode": mi_mode,
                "MC Mode": mc_mode,
                "ME Mode": me_mode,
                "ME Algorithm": me_algo,
                "Search Param": search_param,
                "SCD Mode": scd_mode,
                "SCD Threshold": scd_threshold,
                "MB Size": minter_mb_size,
                "VSBMC": minter_vsbmc,
                "Apply Unsharp": apply_unsharp,
                "Unsharp Luma X": unsharp_lx,
                "Unsharp Luma Y": unsharp_ly,
                "Unsharp Luma Amount": unsharp_la,
                "Unsharp Chroma X": unsharp_cx,
                "Unsharp Chroma Y": unsharp_cy,
                "Unsharp Chroma Amount": unsharp_ca,
            },
            "Quality": {
                "Software Preset (CRF)": f"{self.preset_combo.currentText()} ({crf_value})", # <-- Use preset_combo and LOCAL crf_value
                "Hardware Bitrate (kbps)": self.bitrate_spin.value(),
                "Hardware Buffer (kb)": self.bufsize_spin.value(),
                "Pixel Format": self.pixfmt_combo.currentText(),
            },
        }
        LOGGER.info(f"Starting VFI process with settings:\n{json.dumps(settings_to_log, indent=2)}")
        # --- End Logging ---

        # disable the Open button until we finish
        self.open_btn.setEnabled(False)

        if not in_dir.is_dir():
            self._show_error("Input folder does not exist."); return
        # Ensure output directory exists, but use the full path for the worker
        final_out_mp4.parent.mkdir(parents=True, exist_ok=True)

        # Disable UI & launch worker
        self.start_btn.setEnabled(False); self.progress.setRange(0, 0)
        self.progress.setValue(0) # Explicitly reset progress value
        self.status_bar.showMessage("Starting interpolation...") # Update status bar

        bitrate_kbps = self.bitrate_spin.value()
        bufsize_kb = self.bufsize_spin.value()
        pix_fmt = self.pixfmt_combo.currentText()

        # Ensure crop_rect type matches worker's expectation using cast
        current_crop_rect = cast(Optional[Tuple[int, int, int, int]], self.crop_rect)

        # Start worker
        self.worker = VfiWorker(
            # Standard args
            in_dir,
            final_out_mp4,
            fps,
            mid_count,
            model_key,
            tile_enable=tile_enable,
            max_workers=max_workers,
            encoder=encoder,
            use_ffmpeg_interp=use_ffmpeg_interp,
            skip_model=skip_model,
            # Quality args
            crf=crf_value,
            bitrate_kbps=bitrate_kbps,
            bufsize_kb=bufsize_kb,
            pix_fmt=pix_fmt,
            # Crop args
            crop_rect=current_crop_rect,
            # Debugging args
            debug_mode=self.debug_mode,
            # Filter args
            filter_preset=self.filter_preset_combo.currentText(),
            mi_mode=mi_mode,
            mc_mode=mc_mode,
            me_mode=me_mode,
            me_algo=me_algo,
            search_param=search_param,
            scd_mode=scd_mode,
            scd_threshold=scd_threshold,
            apply_unsharp=apply_unsharp,
            unsharp_lx=unsharp_lx,
            unsharp_ly=unsharp_ly,
            unsharp_la=unsharp_la,
            unsharp_cx=unsharp_cx,
            unsharp_cy=unsharp_cy,
            unsharp_ca=unsharp_ca,
            # Add mb_size and vsbmc
            minter_mb_size=minter_mb_size,
            minter_vsbmc=minter_vsbmc
        )
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._show_error)
        self.worker.start()

    # ------------- callbacks --------------
    def _on_progress(self, current: int, total: int, eta: float) -> None:
        """Update progress bar and status bar with ETA."""
        if total > 0:
            self.progress.setRange(0, total)
            self.progress.setValue(current)
            # Format ETA nicely
            if eta > 0:
                eta_seconds = int(eta)
                eta_str = f"{eta_seconds // 60}m {eta_seconds % 60}s" if eta_seconds > 60 else f"{eta_seconds}s"
                self.status_bar.showMessage(f"Processing {current}/{total}... ETA: {eta_str}")
            else:
                self.status_bar.showMessage(f"Processing {current}/{total}...")
        else: # Handle indeterminate case (shouldn't happen with new logic but safe)
            self.progress.setRange(0, 0)
            self.status_bar.showMessage("Processing...")

    def _on_finished(self, mp4: pathlib.Path) -> None:
        # mark progress done
        self.progress.setRange(0, 1); self.progress.setValue(1)
        self.start_btn.setEnabled(True)
        self.open_btn.setEnabled(True) # Enable Open button on success
        self.status_bar.showMessage(f"Finished: {mp4.name}") # Update status bar

        # Store the path for the Open button
        self._last_out = mp4

        # --- Load mid-frame preview --- #
        # NOTE: This assumes self.worker exists and has a populated 'mid_frame_path'
        #       which needs to be implemented in the worker/run_vfi logic separately.
        if self.worker and hasattr(self.worker, 'mid_frame_path'):
            mid_png_path_str = getattr(self.worker, 'mid_frame_path', None)
            if mid_png_path_str:
                mid_png = pathlib.Path(mid_png_path_str)
                if mid_png.exists():
                    try:
                        pixm = QPixmap(str(mid_png)).scaled(128, 128, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                        self.preview_mid.setPixmap(pixm)
                        self.preview_mid.file_path = str(mid_png)
                        if not pixm.isNull(): self.preview_mid.setText("") # Clear text
                    except Exception as e:
                        LOGGER.error(f"Error loading mid-frame preview '{mid_png}': {e}")
                        self.preview_mid.setText("Mid frame\n(Error)")
                else:
                     LOGGER.warning(f"Mid-frame path provided but file not found: {mid_png}")
                     self.preview_mid.setText("Mid frame\n(Not found)")
            else:
                 LOGGER.info("No mid-frame path available after run.")
                 self.preview_mid.setText("Mid frame") # Reset text if no path
        else:
            LOGGER.warning("Worker or mid_frame_path attribute not available in _on_finished")
        # --- End mid-frame preview logic ---

        self._show_info(f"Video saved to:\n{mp4}")

    def _show_error(self, msg: str) -> None:
        LOGGER.error(msg)
        self.start_btn.setEnabled(True) # Re-enable start on error
        self.progress.setRange(0, 1); self.progress.setValue(0) # Reset progress visually
        self.status_bar.showMessage("Error occurred") # Update status bar
        QMessageBox.critical(self, "Error", msg)

    def _show_info(self, msg: str) -> None:
        QMessageBox.information(self, "Info", msg)

    # ------------- Add VLC opener method -----------
    def _open_in_vlc(self) -> None:
        """Launch the last output MP4 in VLC (cross-platform)."""
        import sys, subprocess, pathlib # Keep imports local if preferred
        if not hasattr(self, "_last_out") or not self._last_out.exists():
             self._show_error("No valid output file found to open.")
             return
        path = str(self._last_out)
        try:
            if sys.platform == "darwin":
                subprocess.Popen(["open", "-a", "VLC", path])
            elif sys.platform.startswith("win"):
                # Use 'start' command which should find VLC if in PATH
                # Providing full path to vlc.exe might be more robust if needed
                subprocess.Popen(["cmd", "/c", "start", "vlc", path], shell=True) # Use shell=True cautiously on Windows
            else:
                # Assume Linux/other Unix-like
                subprocess.Popen(["vlc", path])
        except FileNotFoundError:
             # Handle case where 'open', 'cmd', or 'vlc' command isn't found
            self._show_error(f"Could not find command to launch VLC. Is it installed and in your PATH?")
        except Exception as e:
             self._show_error(f"Failed to open file in VLC: {e}")

    # --- Zoom Dialog Method ---
    def _show_zoom(self, label: ClickableLabel) -> None:
        """Pop up a frameless dialog showing the image from file_path, scaled to fit screen."""
        if not label.file_path or not pathlib.Path(label.file_path).exists():
            LOGGER.warning(f"Zoom requested but file_path is invalid: {label.file_path}")
            return # Do nothing if no valid file path

        try:
            pix = QPixmap(label.file_path)
            if pix.isNull():
                LOGGER.error(f"Failed to load pixmap for zoom: {label.file_path}")
                self._show_error(f"Could not load image:\n{label.file_path}")
                return

            # --- Apply crop if it exists --- #
            if self.crop_rect:
                try:
                    x, y, w, h = cast(Tuple[int, int, int, int], self.crop_rect)
                    pix = pix.copy(x, y, w, h)
                    if pix.isNull(): # Check if copy resulted in an empty pixmap
                        LOGGER.error(f"Cropping resulted in null pixmap. Rect: {self.crop_rect}, Orig Size: {pix.size()}")
                        self._show_error("Error applying crop to image.")
                        return
                except Exception as crop_err:
                    LOGGER.exception(f"Error applying crop rect {self.crop_rect} during zoom")
                    self._show_error(f"Error applying crop:\n{crop_err}")
                    return
            # --- End Apply crop --- #

            # scale to fit screen (80% of available geometry)
            target_size: QSize
            screen = self.screen()
            if screen:
                screen_geo = screen.availableGeometry()
                target_size = screen_geo.size() * 0.8 # Scale QSize directly
            else:
                LOGGER.warning("Could not get screen geometry, using default size for zoom.")
                target_size = QSize(1000, 1000) # Default fallback size

            scaled_pix = pix.scaled(
                target_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )

            dlg = ZoomDialog(scaled_pix, self)
            dlg.exec()

        except Exception as e:
            LOGGER.exception(f"Error showing zoom dialog for {label.file_path}")
            self._show_error(f"Error displaying image:\n{e}")

    # +++ ADD NEW METHOD FOR MODELS TAB +++
    def _makeModelLibraryTab(self) -> QWidget:
        """Builds the Models tab with a simple table of available checkpoints."""
        w = QWidget()
        tbl = QTableWidget(1, 4, parent=w)
        tbl.setHorizontalHeaderLabels(["Name", "Size", "Speed (FPS)", "ΔPSNR"])
        # Row 0: RIFE v4.6
        tbl.setItem(0, 0, QTableWidgetItem("RIFE v4.6"))
        tbl.setItem(0, 1, QTableWidgetItem("≈416 MB ZIP"))
        tbl.setItem(0, 2, QTableWidgetItem("~2 FPS@5 k")) # Assuming 5k resolution context
        tbl.setItem(0, 3, QTableWidgetItem("–")) # Placeholder for PSNR
        tbl.resizeColumnsToContents()

        lay = QVBoxLayout(w)
        lay.addWidget(tbl)
        return w

    def _on_crop_clicked(self) -> None:
        from pathlib import Path
        folder = Path(self.in_edit.text()).expanduser()
        imgs = sorted(folder.glob("*.png"))
        if not imgs:
            QMessageBox.warning(self, "No Images", "Select a folder with PNGs first")
            return

        pix = QPixmap(str(imgs[0]))
        crop_init = cast(Optional[Tuple[int, int, int, int]], self.crop_rect)
        dlg = CropDialog(pix, crop_init, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            rect = dlg.getRect()
            self.crop_rect = (rect.x(), rect.y(), rect.width(), rect.height())
            self.settings.setValue("main/cropRect", ",".join(map(str, self.crop_rect)))
            self._update_previews()

    def _update_previews(self) -> None:
        LOGGER.info("Starting preview update...")
        start_time = datetime.now()
        from pathlib import Path
        folder = Path(self.in_edit.text()).expanduser()
        try:
            files = sorted(folder.glob("*.png"))
        except Exception as e:
            LOGGER.error(f"Error listing files in {folder}: {e}")
            files = [] # Ensure files is a list

        if not files:
            LOGGER.info("No PNG files found, clearing previews.")
            self.preview_first.clear(); self.preview_first.file_path = None
            self.preview_mid.clear(); self.preview_mid.file_path = None
            self.preview_last.clear(); self.preview_last.file_path = None
            return

        LOGGER.info(f"Found {len(files)} PNG files.")

        def crop_and_scale(path: Path) -> QPixmap:
            try:
                pix = QPixmap(str(path))
                if pix.isNull():
                    LOGGER.warning(f"Loaded null pixmap for {path.name}")
                    return QPixmap() # Return empty pixmap
                orig_size = pix.size()
                if self.crop_rect:
                    x,y,w,h = cast(Tuple[int, int, int, int], self.crop_rect)
                    pix = pix.copy(x,y,w,h)
                    if pix.isNull():
                        LOGGER.warning(f"Cropping {path.name} resulted in null pixmap. Rect: {(x,y,w,h)}, Orig: {orig_size}")
                        return QPixmap() # Return empty pixmap
                return pix.scaled(128,128, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            except Exception as e:
                LOGGER.exception(f"Error cropping/scaling {path.name}")
                return QPixmap() # Return empty pixmap on error

        previews = [self.preview_first, self.preview_mid, self.preview_last]
        preview_names = ["First", "Mid", "Last"] # For logging
        indices = [0, len(files)//2, -1]

        if len(files) == 1:
            indices = [0, 0, 0]
        elif len(files) == 2:
            indices = [0, 0, 1]

        for i, (idx, lbl) in enumerate(zip(indices, previews)):
            p = files[idx]
            preview_name = preview_names[i]
            LOGGER.info(f"Updating preview '{preview_name}' with image index {idx}: {p.name}")
            pixmap = crop_and_scale(p)
            if not pixmap.isNull():
                lbl.setPixmap(pixmap)
                lbl.file_path = str(p)
            else:
                lbl.clear()
                lbl.setText(f"{preview_name}\n(Error)") # Indicate error on label
                lbl.file_path = None

        end_time = datetime.now()
        LOGGER.info(f"Preview update finished in {(end_time - start_time).total_seconds():.3f} seconds.")

    def _on_clear_crop_clicked(self) -> None:
        """Clears the stored crop rectangle and updates previews."""
        if self.crop_rect is None:
            self.status_bar.showMessage("No crop is currently set.", 3000)
            return

        LOGGER.info("Clearing crop rectangle.")
        self.crop_rect = None
        self.settings.remove("main/cropRect") # Remove from persistent settings
        self._update_previews() # Refresh previews with full images
        self.status_bar.showMessage("Crop cleared.", 3000)

    # Add the new _build_ffmpeg_tab method
    def _build_ffmpeg_tab(self) -> None:
        """Builds the FFmpeg settings tab content."""
        lay = QVBoxLayout(self.ffmpeg_tab) # Use the tab widget instance

        # Preset selector (influences CRF for software codecs)
        lay.addWidget(QLabel("Software Encoder Preset:"))
        self.preset_combo = QComboBox()
        self.preset_combo.addItems(["Very High (CRF 16)", "High (CRF 18)", "Medium (CRF 20)"])
        self.preset_combo.setCurrentText("Very High (CRF 16)") # Default changed to Very High (16)
        self.preset_combo.setToolTip("Selects the CRF value used for software encoders (libx264, libx265). Lower value = higher quality.")
        lay.addWidget(self.preset_combo)

        # Bitrate control (for hardware codecs)
        lay.addWidget(QLabel("Hardware Encoder Target Bitrate (kbps):"))
        self.bitrate_spin = QSpinBox()
        self.bitrate_spin.setRange(1000, 20000) # 1-20 Mbps
        self.bitrate_spin.setSuffix(" kbps")
        self.bitrate_spin.setValue(15000) # Default 15 Mbps (Increased from 8000)
        self.bitrate_spin.setToolTip("Target average bitrate for hardware encoders (VideoToolbox, NVENC, etc.). Ignored by software encoders.")
        lay.addWidget(self.bitrate_spin)

        # Buffer size control (for hardware codecs)
        lay.addWidget(QLabel("Hardware Encoder VBV Buffer Size (kb):"))
        self.bufsize_spin = QSpinBox()
        self.bufsize_spin.setRange(1000, 40000) # 1-40 Mbits
        self.bufsize_spin.setSuffix(" kb")
        default_buf = int(self.bitrate_spin.value() * 1.5) # Set based on default bitrate
        self.bufsize_spin.setValue(default_buf)
        self.bufsize_spin.setToolTip("Video Buffer Verifier size (controls max bitrate). ~1.5x bitrate is a good start. Ignored by software encoders.")
        # Connect bitrate changes to update default buffer size
        self.bitrate_spin.valueChanged.connect(
            lambda val: self.bufsize_spin.setValue(min(self.bufsize_spin.maximum(), max(self.bufsize_spin.minimum(), int(val * 1.5))))
        )
        lay.addWidget(self.bufsize_spin)

        # Pixel format selector
        lay.addWidget(QLabel("Output Pixel Format:"))
        self.pixfmt_combo = QComboBox()
        self.pixfmt_combo.addItems(["yuv420p", "yuv444p"])
        self.pixfmt_combo.setCurrentText("yuv444p") # Default changed to yuv444p
        self.pixfmt_combo.setToolTip("Video pixel format. yuv420p is standard, yuv444p retains more color (larger file).")
        lay.addWidget(self.pixfmt_combo)

        lay.addStretch()

    # +++ Add Settings Persistence Methods +++
    def loadSettings(self) -> None:
        """Load settings from QSettings and apply them to the UI."""
        LOGGER.info("Loading settings...")
        settings = self.settings # Use the instance member

        # --- Window Geometry ---
        geom = settings.value("window/geometry")
        if isinstance(geom, QByteArray): # QSettings might return QByteArray
             self.restoreGeometry(geom)
        else:
             self.resize(560, 500) # Default size if no geometry saved

        # --- Main Tab ---
        self.in_edit.setText(settings.value("main/inputDir", "", type=str))
        # Handle output path carefully - use default if saved is empty
        saved_out_path = settings.value("main/outputFile", "", type=str)
        if saved_out_path:
             self.out_edit.setText(saved_out_path)
             # Update internal base path used for suggestions
             try: # Add try-except for invalid paths
                self._base_output_path = pathlib.Path(saved_out_path)
             except Exception as e:
                 LOGGER.warning(f"Could not create Path from saved output '{saved_out_path}': {e}. Using default.")
                 out_dir = config.get_output_dir()
                 out_dir.mkdir(parents=True, exist_ok=True)
                 default_path = out_dir / "goes_timelapse.mp4"
                 self.out_edit.setText(str(default_path))
                 self._base_output_path = default_path
        else:
             # Calculate default if nothing saved
             out_dir = config.get_output_dir()
             out_dir.mkdir(parents=True, exist_ok=True)
             default_path = out_dir / "goes_timelapse.mp4"
             self.out_edit.setText(str(default_path))
             self._base_output_path = default_path

        self.fps_spin.setValue(settings.value("main/fps", 10, type=int))
        self.mid_spin.setValue(settings.value("main/midFrames", 1, type=int))
        self.model_combo.setCurrentText(settings.value("main/model", "RIFE v4.6 (default)", type=str))
        # Ensure default encoder logic matches _makeMainTab if setting is missing/invalid
        default_encoder = "Software x265"
        available_encoders = [self.encode_combo.itemText(i) for i in range(self.encode_combo.count())]
        if "Hardware HEVC (VideoToolbox)" in available_encoders:
            default_encoder = "Hardware HEVC (VideoToolbox)"
        elif "Hardware H.264 (VideoToolbox)" in available_encoders:
            default_encoder = "Hardware H.264 (VideoToolbox)"
        self.encode_combo.setCurrentText(settings.value("main/encoder", default_encoder, type=str))
        self.ffmpeg_interp_cb.setChecked(settings.value("main/useFFmpegInterp", True, type=bool))
        self.skip_model_cb.setChecked(settings.value("main/skipModel", False, type=bool))
        # Ensure default worker logic matches _makeMainTab if setting is missing
        import os
        cpu_cores = os.cpu_count() or 1
        default_workers = min(max(1, cpu_cores - 1), 8) # Default calc from _makeMainTab
        self.workers_spin.setValue(settings.value("main/maxWorkers", default_workers, type=int))
        self.tile_checkbox.setChecked(settings.value("main/tilingEnabled", True, type=bool))

        # --- Filter Tab ---
        self.mi_combo.setCurrentText(settings.value("filter/miMode", "mci", type=str))
        self.mc_combo.setCurrentText(settings.value("filter/mcMode", "obmc", type=str))
        self.me_combo.setCurrentText(settings.value("filter/meMode", "bidir", type=str))
        self.me_algo_combo.setCurrentText(settings.value("filter/meAlgo", "(default)", type=str))
        self.search_param_spin.setValue(settings.value("filter/searchParam", 96, type=int))
        self.scd_combo.setCurrentText(settings.value("filter/scdMode", "fdiff", type=str))
        self.scd_thresh_spin.setValue(settings.value("filter/scdThreshold", 10.0, type=float))
        self.filter_preset_combo.setCurrentText(settings.value("filter/preset", "slow", type=str))
        self.mbsize_combo.setCurrentText(settings.value("filter/mbSize", "(default)", type=str))
        self.vsbmc_cb.setChecked(settings.value("filter/vsbmc", False, type=bool))
        # Unsharp
        self.unsharp_cb.setChecked(settings.value("filter/unsharpEnabled", True, type=bool))
        self.luma_x_spin.setValue(settings.value("filter/unsharpLx", 7, type=int))
        self.luma_y_spin.setValue(settings.value("filter/unsharpLy", 7, type=int))
        self.luma_amount_spin.setValue(settings.value("filter/unsharpLa", 1.0, type=float))
        self.chroma_x_spin.setValue(settings.value("filter/unsharpCx", 5, type=int))
        self.chroma_y_spin.setValue(settings.value("filter/unsharpCy", 5, type=int))
        self.chroma_amount_spin.setValue(settings.value("filter/unsharpCa", 0.0, type=float))

        # --- FFmpeg Quality Tab ---
        self.preset_combo.setCurrentText(settings.value("quality/presetCRF", "Very High (CRF 16)", type=str))
        # Handle bitrate/bufsize defaults carefully
        default_bitrate = 15000
        saved_bitrate = settings.value("quality/bitrate", default_bitrate, type=int)
        self.bitrate_spin.setValue(saved_bitrate)
        default_bufsize = int(saved_bitrate * 1.5) # Calculate default based on loaded/default bitrate
        self.bufsize_spin.setValue(settings.value("quality/bufsize", default_bufsize, type=int))
        self.pixfmt_combo.setCurrentText(settings.value("quality/pixFmt", "yuv444p", type=str))

        # --- Update UI state after loading ---
        # Call the signal connectors *after* setting values to ensure dependent controls update
        self._connect_filter_tab_signals()
        # Trigger the state update manually for controls dependent on others
        self._update_scd_thresh_state(self.scd_combo.currentText())
        self._update_unsharp_controls_state(self.unsharp_cb.isChecked())

        self._update_previews() # Load previews based on loaded input dir
        LOGGER.info("Settings loaded.")

    def saveSettings(self) -> None:
        """Save current UI settings to QSettings."""
        LOGGER.info("Saving settings...")
        settings = self.settings # Use the instance member

        # --- Window Geometry ---
        settings.setValue("window/geometry", self.saveGeometry())

        # --- Main Tab ---
        settings.setValue("main/inputDir", self.in_edit.text())
        settings.setValue("main/outputFile", self.out_edit.text())
        settings.setValue("main/fps", self.fps_spin.value())
        settings.setValue("main/midFrames", self.mid_spin.value())
        settings.setValue("main/model", self.model_combo.currentText())
        settings.setValue("main/encoder", self.encode_combo.currentText())
        settings.setValue("main/useFFmpegInterp", self.ffmpeg_interp_cb.isChecked())
        settings.setValue("main/skipModel", self.skip_model_cb.isChecked())
        settings.setValue("main/maxWorkers", self.workers_spin.value())
        settings.setValue("main/tilingEnabled", self.tile_checkbox.isChecked())
        # Save crop rect
        if self.crop_rect:
             settings.setValue("main/cropRect", ",".join(map(str, self.crop_rect)))
        else:
             settings.remove("main/cropRect") # Remove if None


        # --- Filter Tab ---
        settings.setValue("filter/miMode", self.mi_combo.currentText())
        settings.setValue("filter/mcMode", self.mc_combo.currentText())
        settings.setValue("filter/meMode", self.me_combo.currentText())
        settings.setValue("filter/meAlgo", self.me_algo_combo.currentText())
        settings.setValue("filter/searchParam", self.search_param_spin.value())
        settings.setValue("filter/scdMode", self.scd_combo.currentText())
        settings.setValue("filter/scdThreshold", self.scd_thresh_spin.value())
        settings.setValue("filter/preset", self.filter_preset_combo.currentText())
        settings.setValue("filter/mbSize", self.mbsize_combo.currentText())
        settings.setValue("filter/vsbmc", self.vsbmc_cb.isChecked())
        # Unsharp
        settings.setValue("filter/unsharpEnabled", self.unsharp_cb.isChecked())
        settings.setValue("filter/unsharpLx", self.luma_x_spin.value())
        settings.setValue("filter/unsharpLy", self.luma_y_spin.value())
        settings.setValue("filter/unsharpLa", self.luma_amount_spin.value())
        settings.setValue("filter/unsharpCx", self.chroma_x_spin.value())
        settings.setValue("filter/unsharpCy", self.chroma_y_spin.value())
        settings.setValue("filter/unsharpCa", self.chroma_amount_spin.value())

        # --- FFmpeg Quality Tab ---
        settings.setValue("quality/presetCRF", self.preset_combo.currentText())
        settings.setValue("quality/bitrate", self.bitrate_spin.value())
        settings.setValue("quality/bufsize", self.bufsize_spin.value())
        settings.setValue("quality/pixFmt", self.pixfmt_combo.currentText())

        LOGGER.info("Settings saved.")

    # Override closeEvent
    def closeEvent(self, event: QCloseEvent | None) -> None:
        """Save settings when the window is closed."""
        self.saveSettings()
        # Ensure we call the superclass method correctly, checking if event is None
        if event:
            super().closeEvent(event)
        else:
            # If event is None for some reason, just proceed with closing if possible
            # Or handle as an error, though typically closeEvent receives a valid event
            LOGGER.warning("closeEvent received None, proceeding with default close.")
            pass # Ensure this is correctly indented
    # --- End Settings Persistence Methods ---

# ────────────────────────── top‑level launcher ────────────────────────────
def main() -> None:
    # --- Add Argument Parsing --- #
    parser = argparse.ArgumentParser(description="GOES-VFI GUI")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()

    app = QApplication(sys.argv)
    # Pass the parsed debug flag to the MainWindow
    win = MainWindow(debug_mode=args.debug)
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
