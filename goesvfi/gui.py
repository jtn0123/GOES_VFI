# TODO: PyQt6 main window implementation
from __future__ import annotations
"""
GOES‑VFI PyQt6 GUI – v0.1
Run with:  python -m goesvfi.gui
"""

import sys
import pathlib
import importlib.resources as pkgres
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QProgressBar, QSpinBox, QVBoxLayout, QWidget,
    QMessageBox, QComboBox, QCheckBox
)

from goesvfi.utils import config, log
from goesvfi.run_vfi import run_vfi

LOGGER = log.get_logger(__name__)

# ────────────────────────────── Worker thread ──────────────────────────────
class VfiWorker(QThread):
    progress = pyqtSignal(int, int)
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
        max_workers: int
    ) -> None:
        super().__init__()
        self.in_dir        = in_dir
        self.out_file_path = out_file_path
        self.fps           = fps
        self.mid_count     = mid_count
        self.model_key     = model_key
        self.tile_enable   = tile_enable
        self.max_workers   = max_workers
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
        try:
            LOGGER.info("Interpolating %s -> %s", self.in_dir, self.out_file_path)
            mp4_path = run_vfi(
                folder=self.in_dir,
                output_mp4_path=self.out_file_path,
                rife_exe_path=self.rife_exe_path,
                fps=self.fps,
                num_intermediate_frames=self.mid_count,
                tile_enable=self.tile_enable,
                max_workers=self.max_workers
            )
            self.finished.emit(mp4_path)
        except Exception as exc:
            LOGGER.exception("Worker failed")
            self.error.emit(str(exc))

# ──────────────────────────────── Main window ─────────────────────────────
class MainWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("GOES‑VFI  v0.1")
        self.resize(560, 350)

        # Widgets
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
            "Number of in‑between frames per original pair:\n"
            "• 1 = single midpoint (fastest)\n"
            "• 3 = recursive three‑step (smoother)"
        )
        self.model_combo = QComboBox()
        self.model_combo.addItems([
            "RIFE v4.6 (default)",
        ])
        self.model_combo.setToolTip(
            "Choose your interpolation model.\\n"
            "Currently only the built-in RIFE model is used."
        )
        self.start_btn  = QPushButton("Start")
        self.progress   = QProgressBar(); self.progress.setRange(0, 1)

        # ─── Max parallel workers ─────────────────────────────────────────
        self.workers_spin = QSpinBox()
        # Get cpu_count safely for default value
        import os
        cpu_cores = os.cpu_count() or 1 # Default to 1 if None
        default_workers = max(1, cpu_cores - 1) # Leave one free if possible
        self.workers_spin.setRange(1, max(8, cpu_cores)) # Allow up to cpu_count or 8
        self.workers_spin.setValue(min(default_workers, 8)) # Default, capped at 8
        self.workers_spin.setToolTip(
            f"Max number of parallel interpolation processes (CPU has {cpu_cores}).\\n"
            "Reduce if you experience memory issues."
        )

        # ─── Tiling toggle ────────────────────────────────────────────────
        self.tile_checkbox = QCheckBox("Enable tiling for large frames (>2k)")
        self.tile_checkbox.setChecked(True) # Default to ON
        self.tile_checkbox.setToolTip(
            "Split large frames into tiles before interpolating.\\n"
            "Faster & uses less RAM, but may have edge artifacts.\\n"
            "Disable if RAM allows or edges look bad."
        )

        # Layout
        layout  = QVBoxLayout(self)
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
        layout.addLayout(in_row); layout.addLayout(out_row);
        # Update layout adding order
        layout.addLayout(fps_row)
        layout.addLayout(mid_row)
        layout.addLayout(tile_row)      # Add tile row
        layout.addLayout(workers_row)   # Add workers row
        layout.addLayout(model_row)
        layout.addWidget(self.start_btn); layout.addWidget(self.progress)

        # ─── Open in VLC button ───────────────────────────────────────────
        self.open_btn = QPushButton("Open in VLC")
        self.open_btn.setEnabled(False)
        self.open_btn.setToolTip("Launch the finished MP4 in VLC")
        layout.addWidget(self.open_btn) # Add button to layout

        # Signals
        self.in_browse.clicked.connect(self._pick_in_dir)
        self.out_browse.clicked.connect(self._pick_out_file)
        self.start_btn.clicked.connect(self._start)
        self.open_btn.clicked.connect(self._open_in_vlc) # Connect new button

        self.worker: VfiWorker | None = None
        self._apply_defaults()

    # ---------------- helpers ----------------
    def _apply_defaults(self) -> None:
        out_dir = config.get_output_dir(); out_dir.mkdir(parents=True, exist_ok=True)
        self.out_edit.setText(str(out_dir / "goes_timelapse.mp4"))

    def _pick_in_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select GOES image folder")
        if path: self.in_edit.setText(path)

    def _pick_out_file(self) -> None:
        suggested = str(config.get_output_dir() / "goes_animated.mp4")
        path, _ = QFileDialog.getSaveFileName(self, "Save MP4", suggested, "MP4 files (*.mp4)")
        if path: self.out_edit.setText(path)

    def _start(self) -> None:
        in_dir  = pathlib.Path(self.in_edit.text()).expanduser()
        out_mp4 = pathlib.Path(self.out_edit.text()).expanduser()
        fps     = self.fps_spin.value()
        mid_count = self.mid_spin.value()
        model_key = self.model_combo.currentText()
        # Get values from new widgets
        tile_enable = self.tile_checkbox.isChecked()
        max_workers = self.workers_spin.value()

        # disable the Open button until we finish
        self.open_btn.setEnabled(False)

        if not in_dir.is_dir():
            self._show_error("Input folder does not exist."); return
        # Ensure output directory exists, but use the full path for the worker
        out_mp4.parent.mkdir(parents=True, exist_ok=True)

        # Disable UI & launch worker
        self.start_btn.setEnabled(False); self.progress.setRange(0, 0)
        self.progress.setValue(0) # Explicitly reset progress value

        # Pass the specific out_mp4 path and new params to the worker
        # Keep existing mid_count and model_key arguments
        self.worker = VfiWorker(
            in_dir, out_mp4, fps, mid_count, model_key,
            tile_enable=tile_enable,
            max_workers=max_workers
        )
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._show_error)
        self.worker.start()

    # ------------- callbacks --------------
    def _on_progress(self, current: int, total: int) -> None:
        self.progress.setRange(0, total); self.progress.setValue(current)

    def _on_finished(self, mp4: pathlib.Path) -> None:
        # mark progress done
        self.progress.setRange(0, 1)
        self.progress.setValue(1)
        self.start_btn.setEnabled(True)
        self._show_info(f"Done! MP4 saved to {mp4}")
        # store path and enable Open button
        self._last_out = mp4
        self.open_btn.setEnabled(True)

    def _show_error(self, msg: str) -> None:
        QMessageBox.critical(self, "Error", msg)
        self.start_btn.setEnabled(True)
        self.progress.setRange(0, 1); self.progress.setValue(0)
        # Disable open button on error too
        self.open_btn.setEnabled(False)

    def _show_info(self, msg: str) -> None:
        QMessageBox.information(self, "Info", msg)

    # ------------- Add VLC opener method -----------
    def _open_in_vlc(self) -> None:
        """Launch the last output MP4 in VLC (cross‑platform)."""
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

# ────────────────────────── top‑level launcher ────────────────────────────
def main() -> None:
    app = QApplication(sys.argv)
    win = MainWindow(); win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
