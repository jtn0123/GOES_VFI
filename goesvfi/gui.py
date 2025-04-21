# TODO: PyQt6 main window implementation
from __future__ import annotations
"""
GOES‑VFI PyQt6 GUI – v0.1
Run with:  python -m goesvfi.gui
"""

import sys
import pathlib
import importlib.resources as pkgres
from typing import Optional, Any, cast, Union, Tuple, Iterator
from datetime import datetime
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QSize, QPoint, QRect, QSettings
from PyQt6.QtWidgets import (
    QApplication, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QProgressBar, QSpinBox, QVBoxLayout, QWidget,
    QMessageBox, QComboBox, QCheckBox, QTabWidget, QTableWidget, QTableWidgetItem, QStatusBar,
    QDialog, QDialogButtonBox, QRubberBand
)
from PyQt6.QtGui import QPixmap, QMouseEvent

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
        crop_rect: tuple[int, int, int, int] | None
    ) -> None:
        super().__init__()
        self.in_dir        = in_dir
        self.out_file_path = out_file_path
        self.fps           = fps
        self.mid_count     = mid_count
        self.model_key     = model_key # Storing it but not passing directly to run_vfi
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

    def run(self) -> None:
        # Import here to avoid potential top-level circular imports
        from goesvfi.pipeline.run_vfi import run_vfi
        from goesvfi.pipeline.encode import encode_with_ffmpeg

        raw_mp4_path: Optional[pathlib.Path] = None
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

            LOGGER.info("Step 1: Generating raw intermediate video...")

            run_vfi_kwargs = {
                'crop_rect': self.crop_rect,
                'encoder': self.encoder,
                'use_ffmpeg_interp': self.use_ffmpeg_interp,
                'model_key': self.model_key, # Pass model_key via kwargs now
                'skip_model': self.skip_model, # Pass skip_model via kwargs
            }

            # Use the full Union directly in the type hint
            run_vfi_iterator: Iterator[Union[Tuple[int, int, float], pathlib.Path]] = run_vfi(
                folder=self.in_dir,
                output_mp4_path=self.out_file_path,
                rife_exe_path=self.rife_exe_path,
                fps=self.fps,
                num_intermediate_frames=self.mid_count,
                tile_enable=self.tile_enable,
                max_workers=self.max_workers,
                **run_vfi_kwargs
            )

            for update in run_vfi_iterator:
                if isinstance(update, pathlib.Path):
                    raw_mp4_path = update # Store the raw path when yielded
                    LOGGER.info(f"Raw intermediate video created: {raw_mp4_path}")
                    # Don't break here, let iterator finish (though it should be the last item)
                elif isinstance(update, tuple) and len(update) == 3:
                    # This is a progress update (idx, total, eta)
                    idx, total, eta = update
                    # Emit progress relative to raw creation step (consider adjusting total?)
                    self.progress.emit(idx, total, eta)
                else:
                    LOGGER.warning(f"Received unexpected update type from run_vfi: {type(update)}")

            # Check if we got the raw path
            if not raw_mp4_path or not raw_mp4_path.exists():
                raise RuntimeError(f"Raw intermediate video path not received or file not found: {raw_mp4_path}")

            # --- Step 2: Re-encode or move raw to final --- #
            LOGGER.info(f"Step 2: Encoding/Moving raw video to final destination {self.out_file_path} using encoder '{self.encoder}'")

            encode_with_ffmpeg(
                raw_input=raw_mp4_path,
                final_output=self.out_file_path,
                encoder=self.encoder,
                fps=self.fps,
                use_interp=self.use_ffmpeg_interp,
                crf=self.crf,
                bitrate_kbps=self.bitrate_kbps,
                bufsize_kb=self.bufsize_kb,
                pix_fmt=self.pix_fmt
            )

            LOGGER.info(f"Final output created: {self.out_file_path}")
            self.finished.emit(self.out_file_path) # Emit FINAL path on success

        except Exception as exc:
            LOGGER.exception("Worker failed")
            self.error.emit(str(exc))

        finally:
            # --- Step 3: Cleanup raw intermediate --- #
            if raw_mp4_path and raw_mp4_path.exists() and raw_mp4_path != self.out_file_path:
                try:
                    LOGGER.info(f"Cleaning up raw intermediate file: {raw_mp4_path}")
                    raw_mp4_path.unlink()
                except OSError as e:
                    LOGGER.error(f"Failed to delete raw intermediate file {raw_mp4_path}: {e}")

# ──────────────────────────────── Main window ─────────────────────────────
class MainWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("GOES‑VFI") # Simplified title
        self.resize(560, 450) # Slightly taller for tabs/previews

        # Store the original base path selected by user or default
        self._base_output_path: pathlib.Path | None = None

        # ─── Persistent crop settings ───────────────────────────────────
        self.settings = QSettings("YourOrg", "GOESVFI")
        saved = self.settings.value("crop_rect", None)
        self.crop_rect = tuple(map(int, saved.split(","))) if saved else None

        # ─── Tab widget ───────────────────────────────────────────────────
        self.tabs = QTabWidget()
        self.tabs.addTab(self._makeMainTab(), "Interpolate")
        self.tabs.addTab(self._makeModelLibraryTab(), "Models")
        self.ffmpeg_tab = QWidget()
        self.tabs.addTab(self.ffmpeg_tab, "FFmpeg Quality")
        self._build_ffmpeg_tab()

        # ─── Status Bar ───────────────────────────────────────────────────
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("Ready")

        # ─── Main Layout ──────────────────────────────────────────────────
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(self.tabs)
        main_layout.addWidget(self.status_bar) # Add status bar at the bottom
        self.setLayout(main_layout)

        self.worker: VfiWorker | None = None
        self._apply_defaults()

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

    # ---------------- helpers ----------------
    def _apply_defaults(self) -> None:
        out_dir = config.get_output_dir(); out_dir.mkdir(parents=True, exist_ok=True)
        default_path = out_dir / "goes_timelapse.mp4"
        self.out_edit.setText(str(default_path))
        # Store the base path
        self._base_output_path = default_path

    def _pick_in_dir(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Input Folder")
        if not folder:
            return
        self.in_edit.setText(folder)
        # refresh previews, applying any crop
        self._update_previews()

    def _pick_out_file(self) -> None:
        # Suggest based on the base path if available, else current text
        suggested_dir = self._base_output_path.parent if self._base_output_path else config.get_output_dir()
        suggested_name = self._base_output_path.name if self._base_output_path else "goes_animated.mp4"
        suggested = str(suggested_dir / suggested_name)

        path_str, _ = QFileDialog.getSaveFileName(self, "Save MP4", suggested, "MP4 files (*.mp4)")
        if path_str:
            path = pathlib.Path(path_str)
            self.out_edit.setText(str(path))
            # Store the newly selected base path
            self._base_output_path = path

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
        skip_model = self.skip_model_cb.isChecked() # Get value from new checkbox

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

        # Calculate CRF from preset text
        preset_text = self.preset_combo.currentText()
        try:
            # Extract number after "CRF "
            crf_value = int(preset_text.split("CRF ")[-1].rstrip(")"))
        except (IndexError, ValueError):
            LOGGER.warning(f"Could not parse CRF from preset '{preset_text}', defaulting to 20.")
            crf_value = 20 # Default fallback

        bitrate_kbps = self.bitrate_spin.value()
        bufsize_kb = self.bufsize_spin.value()
        pix_fmt = self.pixfmt_combo.currentText()

        # Ensure crop_rect type matches worker's expectation using cast
        current_crop_rect = cast(Optional[Tuple[int, int, int, int]], self.crop_rect)

        # Start worker
        self.worker = VfiWorker(
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
            crf=crf_value,
            bitrate_kbps=bitrate_kbps,
            bufsize_kb=bufsize_kb,
            pix_fmt=pix_fmt,
            crop_rect=current_crop_rect
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
            self.settings.setValue("crop_rect", ",".join(map(str, self.crop_rect)))
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
        self.settings.remove("crop_rect") # Remove from persistent settings
        self._update_previews() # Refresh previews with full images
        self.status_bar.showMessage("Crop cleared.", 3000)

    # Add the new _build_ffmpeg_tab method
    def _build_ffmpeg_tab(self) -> None:
        """Builds the FFmpeg settings tab content."""
        lay = QVBoxLayout(self.ffmpeg_tab) # Use the tab widget instance

        # Preset selector (influences CRF for software codecs)
        lay.addWidget(QLabel("Software Encoder Preset:"))
        self.preset_combo = QComboBox()
        self.preset_combo.addItems(["Very High (CRF 18)", "High (CRF 20)", "Medium (CRF 23)"])
        self.preset_combo.setCurrentText("High (CRF 20)") # Default
        self.preset_combo.setToolTip("Selects the CRF value used for software encoders (libx264, libx265).")
        lay.addWidget(self.preset_combo)

        # Bitrate control (for hardware codecs)
        lay.addWidget(QLabel("Hardware Encoder Target Bitrate (kbps):"))
        self.bitrate_spin = QSpinBox()
        self.bitrate_spin.setRange(1000, 20000) # 1-20 Mbps
        self.bitrate_spin.setSuffix(" kbps")
        self.bitrate_spin.setValue(8000) # Default 8 Mbps
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
        self.pixfmt_combo.addItems(["yuv420p", "yuv444p"]) # Common options
        self.pixfmt_combo.setCurrentText("yuv420p") # Default (most compatible)
        self.pixfmt_combo.setToolTip("Video pixel format. yuv420p is standard, yuv444p retains more color (larger file).")
        lay.addWidget(self.pixfmt_combo)

        lay.addStretch()

# ────────────────────────── top‑level launcher ────────────────────────────
def main() -> None:
    app = QApplication(sys.argv)
    win = MainWindow(); win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
