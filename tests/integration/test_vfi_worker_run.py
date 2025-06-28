import pathlib
import sys
from types import ModuleType
from unittest.mock import MagicMock

from PIL import Image

from goesvfi.pipeline.run_vfi import VfiWorker

# Provide minimal PyQt6 mocks for headless test execution
qtcore = ModuleType("PyQt6.QtCore")
qtcore.QThread = object  # type: ignore
qtcore.pyqtSignal = lambda *_a, **_k: MagicMock()  # type: ignore

pyqt6 = ModuleType("PyQt6")
pyqt6.QtCore = qtcore  # type: ignore

sys.modules.setdefault("PyQt6", pyqt6)
sys.modules.setdefault("PyQt6.QtCore", qtcore)


def create_dummy_png(path: pathlib.Path, size=(10, 10)) -> None:
    img = Image.new("RGB", size, color=(0, 0, 0))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, format="PNG")


def test_vfi_worker_run(tmp_path, monkeypatch) -> None:
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    for i in range(2):
        create_dummy_png(input_dir / f"frame_{i}.png")

    output_file = tmp_path / "out.mp4"

    monkeypatch.setattr(
        "goesvfi.pipeline.run_vfi.VfiWorker._get_rife_executable",
        lambda self: pathlib.Path("/fake/rife"),
    )

    def fake_run_vfi(**kwargs):
        yield (1, 2, 0.0)
        yield pathlib.Path(kwargs["output_mp4_path"])

    monkeypatch.setattr("goesvfi.pipeline.run_vfi.run_vfi", fake_run_vfi)

    worker = VfiWorker(in_dir=str(input_dir), out_file_path=str(output_file))

    prog = MagicMock()
    fin = MagicMock()
    err = MagicMock()

    # Connect to signals instead of trying to replace emit
    worker.progress.connect(prog)
    worker.finished.connect(fin)
    worker.error.connect(err)

    worker.run()

    prog.assert_called_with(1, 2, 0.0)
    fin.assert_called_with(str(output_file))
    err.assert_not_called()
