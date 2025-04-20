# TODO: PyQt6 main window implementation
from __future__ import annotations
"""
GOES‑VFI PyQt6 GUI – v0.1
Run with:  python -m goesvfi.gui
"""

import sys
import pathlib
import importlib.resources as pkgres
from typing import Optional, Any
from datetime import datetime # Add datetime import
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QSize
from PyQt6.QtWidgets import (
    QApplication, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QProgressBar, QSpinBox, QVBoxLayout, QWidget,
    QMessageBox, QComboBox, QCheckBox, QTabWidget, QTableWidget, QTableWidgetItem, QStatusBar,
    QDialog # Add QDialog import
)
from PyQt6.QtGui import QPixmap, QMouseEvent # Added for thumbnails, Add QMouseEvent

from goesvfi.utils import config, log
from goesvfi.run_vfi import run_vfi
from goesvfi.pipeline.encode import encode_with_ffmpeg

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
        use_ffmpeg_interp: bool
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
        raw_mp4_path: Optional[pathlib.Path] = None # To store the intermediate raw path
        try:
            LOGGER.info("Starting VFI worker for %s -> %s", self.in_dir, self.out_file_path)
            LOGGER.info("Step 1: Generating raw intermediate video...")

            # run_vfi yields progress updates and finally the RAW mp4 path
            run_vfi_iterator = run_vfi(
                folder=self.in_dir,
                # Pass the FINAL path, run_vfi derives raw path from it
                output_mp4_path=self.out_file_path,
                rife_exe_path=self.rife_exe_path,
                fps=self.fps,
                num_intermediate_frames=self.mid_count,
                tile_enable=self.tile_enable,
                max_workers=self.max_workers
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
                use_interp=self.use_ffmpeg_interp
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

        # ─── Tab widget ───────────────────────────────────────────────────
        self.tabs = QTabWidget()
        self.tabs.addTab(self._makeMainTab(), "Interpolate")
        self.tabs.addTab(self._makeModelLibraryTab(), "Models")

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
        self.fps_spin   = QSpinBox(); self.fps_spin.setRange(1, 240); self.fps_spin.setValue(60)
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
            "None (copy original)",            # new "no re-encode" option
            "Software x265",
            "Hardware HEVC (VideoToolbox)", # Assuming macOS VideoToolbox
            "Hardware H.264 (VideoToolbox)",
            # TODO: Add Windows/Linux hardware options if desired
        ])
        self.encode_combo.setToolTip(
            "Pick your output codec, or None to skip re-encoding."
        )
        # Set a reasonable default, e.g., H.264 if available
        if "Hardware H.264 (VideoToolbox)" in [self.encode_combo.itemText(i) for i in range(self.encode_combo.count())]:
            self.encode_combo.setCurrentText("Hardware H.264 (VideoToolbox)")
        else:
            self.encode_combo.setCurrentText("Software x265") # Fallback

        # ─── FFmpeg motion interpolation toggle ───────────────────────────
        self.ffmpeg_interp_cb = QCheckBox("Use FFmpeg motion interpolation (doubles FPS again)")
        self.ffmpeg_interp_cb.setChecked(False)
        self.ffmpeg_interp_cb.setToolTip(
            "Apply FFmpeg's 'minterpolate' filter before encoding.\n"
            "Generates additional frames via motion interpolation, effectively doubling the FPS set above."
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
        # Add layout row for FFmpeg interpolation checkbox
        interp_row = QHBoxLayout()
        interp_row.addWidget(self.ffmpeg_interp_cb)
        interp_row.addStretch()

        layout.addLayout(in_row); layout.addLayout(out_row);
        # Update layout adding order
        layout.addLayout(fps_row)
        layout.addLayout(mid_row)
        layout.addLayout(tile_row)      # Add tile row
        layout.addLayout(workers_row)   # Add workers row
        layout.addLayout(model_row)
        layout.addLayout(encode_row)    # Add encode row
        layout.addLayout(interp_row)     # Add FFmpeg interp row
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
        folder = QFileDialog.getExistingDirectory(self, "Select GOES image folder")
        # Use early return if no folder selected
        if not folder:
            return
        self.in_edit.setText(folder)

        # Reset previews initially
        self.preview_first.setText("First frame\nLoading...")
        self.preview_last.setText("Last frame\nLoading...")
        self.preview_mid.setText("Mid frame") # Reset mid preview too
        self.preview_first.setPixmap(QPixmap()) # Clear pixmaps
        self.preview_last.setPixmap(QPixmap())
        self.preview_mid.setPixmap(QPixmap())

        # load & show first/last thumbnails
        try:
            files = sorted(pathlib.Path(folder).glob("*.png")) # Assuming PNG
            if files:
                # First frame
                first = files[0]
                pix1 = QPixmap(str(first)).scaled(128, 128, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self.preview_first.setPixmap(pix1)
                self.preview_first.file_path = str(first)

                # Middle frame (floor of count/2)
                # Ensure index is valid even for list with 1 element
                mid_idx = min(len(files) // 2, len(files) - 1)
                middle = files[mid_idx]
                pixm = QPixmap(str(middle)).scaled(128, 128, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self.preview_mid.setPixmap(pixm)
                self.preview_mid.file_path = str(middle)

                # Last frame
                last = files[-1]
                pix2 = QPixmap(str(last)).scaled(128, 128, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self.preview_last.setPixmap(pix2)
                self.preview_last.file_path = str(last)

                # Clear text if pixmap loaded
                if not pix1.isNull(): self.preview_first.setText("")
                if not pixm.isNull(): self.preview_mid.setText("") # Check mid pixmap
                if not pix2.isNull(): self.preview_last.setText("")
            else:
                self.preview_first.setText("First frame\n(no PNGs)")
                self.preview_last.setText("Last frame\n(no PNGs)")
                self.preview_mid.setText("Mid frame") # Reset text
                # Clear file paths
                self.preview_first.file_path = None
                self.preview_last.file_path = None
                self.preview_mid.file_path = None
        except Exception as e:
            LOGGER.error(f"Error loading thumbnails: {e}")
            self.preview_first.setText("First frame\n(Error)")
            self.preview_last.setText("Last frame\n(Error)")

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

        # Pass the specific out_mp4 path and new params to the worker
        # Keep existing mid_count and model_key arguments
        self.worker = VfiWorker(
            in_dir, final_out_mp4, fps, mid_count, model_key,
            tile_enable=tile_enable,
            max_workers=max_workers,
            encoder=encoder,
            use_ffmpeg_interp=use_ffmpeg_interp
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

# ────────────────────────── top‑level launcher ────────────────────────────
def main() -> None:
    app = QApplication(sys.argv)
    win = MainWindow(); win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
