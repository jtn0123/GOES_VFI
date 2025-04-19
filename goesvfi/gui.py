# TODO: PyQt6 main window implementation
from __future__ import annotations
"""
GOES‑VFI PyQt6 GUI – v0.1
Run with:  python -m goesvfi.gui
"""

import sys
import pathlib
import importlib.resources as pkgres
from PyQt6.QtCore import QThread, pyqtSignal  # type: ignore
from PyQt6.QtWidgets import (  # type: ignore
    QApplication, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QProgressBar, QSpinBox, QVBoxLayout, QWidget,
)

from goesvfi.utils import config, log
from goesvfi.run_vfi import run_vfi

LOGGER = log.get_logger(__name__)

# ────────────────────────────── Worker thread ──────────────────────────────
class VfiWorker(QThread):
    progress = pyqtSignal(int, int)          # current, total
    finished = pyqtSignal(pathlib.Path)      # final MP4
    error    = pyqtSignal(str)

    def __init__(self, in_dir: pathlib.Path, out_file: pathlib.Path, fps: int):
        super().__init__()
        self.in_dir   = in_dir
        self.out_file = out_file
        self.fps      = fps
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

    def run(self):
        try:
            LOGGER.info("Interpolating %s → %s", self.in_dir, self.out_file)
            # run_vfi now expects the path to the RIFE executable
            mp4_path = run_vfi(self.in_dir, self.rife_exe_path, fps=self.fps)
            self.finished.emit(mp4_path)
        except Exception as exc:
            LOGGER.exception("Worker failed")
            self.error.emit(str(exc))

# ──────────────────────────────── Main window ─────────────────────────────
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GOES‑VFI  v0.1")
        self.resize(560, 260)

        # Widgets
        self.in_edit   = QLineEdit()
        self.in_browse = QPushButton("Browse…")
        self.out_edit   = QLineEdit()
        self.out_browse = QPushButton("Save As…")
        self.fps_spin   = QSpinBox(); self.fps_spin.setRange(1, 240); self.fps_spin.setValue(60)
        self.start_btn  = QPushButton("Start")
        self.progress   = QProgressBar(); self.progress.setRange(0, 1)

        # Layout
        layout  = QVBoxLayout(self)
        in_row  = QHBoxLayout();  in_row.addWidget(QLabel("Input folder:"));  in_row.addWidget(self.in_edit);  in_row.addWidget(self.in_browse)
        out_row = QHBoxLayout(); out_row.addWidget(QLabel("Output MP4:"));  out_row.addWidget(self.out_edit); out_row.addWidget(self.out_browse)
        fps_row = QHBoxLayout(); fps_row.addWidget(QLabel("Target FPS:")); fps_row.addWidget(self.fps_spin); fps_row.addStretch()
        layout.addLayout(in_row); layout.addLayout(out_row); layout.addLayout(fps_row)
        layout.addWidget(self.start_btn); layout.addWidget(self.progress)

        # Signals
        self.in_browse.clicked.connect(self._pick_in_dir)
        self.out_browse.clicked.connect(self._pick_out_file)
        self.start_btn.clicked.connect(self._start)

        self.worker: VfiWorker | None = None
        self._apply_defaults()

    # ---------------- helpers ----------------
    def _apply_defaults(self):
        out_dir = config.get_output_dir(); out_dir.mkdir(parents=True, exist_ok=True)
        self.out_edit.setText(str(out_dir / "goes_timelapse.mp4"))

    def _pick_in_dir(self):
        path = QFileDialog.getExistingDirectory(self, "Select GOES image folder")
        if path: self.in_edit.setText(path)

    def _pick_out_file(self):
        suggested = str(config.get_output_dir() / "goes_animated.mp4")
        path, _ = QFileDialog.getSaveFileName(self, "Save MP4", suggested, "MP4 files (*.mp4)")
        if path: self.out_edit.setText(path)

    def _start(self):
        in_dir  = pathlib.Path(self.in_edit.text()).expanduser()
        out_mp4 = pathlib.Path(self.out_edit.text()).expanduser()
        fps     = self.fps_spin.value()

        if not in_dir.is_dir():
            self._show_error("Input folder does not exist."); return
        out_mp4.parent.mkdir(parents=True, exist_ok=True)

        # Disable UI & launch worker
        self.start_btn.setEnabled(False); self.progress.setRange(0, 0)
        self.worker = VfiWorker(in_dir, out_mp4, fps)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._show_error)
        self.worker.start()

    # ------------- callbacks --------------
    def _on_progress(self, current: int, total: int):
        self.progress.setRange(0, total); self.progress.setValue(current)

    def _on_finished(self, mp4: pathlib.Path):
        self.progress.setValue(self.progress.maximum())
        self.start_btn.setEnabled(True)
        self._show_info(f"Done! MP4 saved to {mp4}")

    def _show_error(self, msg: str):
        from PyQt6.QtWidgets import QMessageBox  # type: ignore
        QMessageBox.critical(self, "Error", msg)
        self.start_btn.setEnabled(True)
        self.progress.setRange(0, 1); self.progress.setValue(0)

    def _show_info(self, msg: str):
        from PyQt6.QtWidgets import QMessageBox  # type: ignore
        QMessageBox.information(self, "Info", msg)

# ────────────────────────── top‑level launcher ────────────────────────────
def main():
    app = QApplication(sys.argv)
    win = MainWindow(); win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
