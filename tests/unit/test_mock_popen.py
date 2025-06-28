import subprocess
import sys
import types
from unittest.mock import patch

import pytest

from tests.utils.mocks import MockPopen

sys.modules.setdefault("PyQt6", types.ModuleType("PyQt6"))
qtcore = types.ModuleType("QtCore")
qtcore.QCoreApplication = type("QCoreApplication", (), {})  # type: ignore[attr-defined]
qtcore.QObject = type("QObject", (), {})  # type: ignore[attr-defined]
sys.modules.setdefault("PyQt6.QtCore", qtcore)
qtwidgets = types.ModuleType("QtWidgets")
qtwidgets.QApplication = type("QApplication", (), {})  # type: ignore[attr-defined]
sys.modules.setdefault("PyQt6.QtWidgets", qtwidgets)
sys.modules.setdefault("PyQt6.QtGui", types.ModuleType("QtGui"))
sys.modules.setdefault("numpy", types.ModuleType("numpy"))
pil = types.ModuleType("PIL")
pil_image = types.ModuleType("Image")
pil.Image = pil_image  # type: ignore[attr-defined]
sys.modules.setdefault("PIL", pil)
sys.modules.setdefault("PIL.Image", pil_image)


def test_wait_timeout_then_complete() -> None:
    current_time = 0.0

    def fake_monotonic():
        return current_time

    with patch("tests.utils.mocks.time.monotonic", side_effect=lambda: current_time):
        proc = MockPopen(["cmd"], complete_after=2)
        with pytest.raises(subprocess.TimeoutExpired):
            proc.wait(timeout=1)
        assert proc.returncode is None
        current_time = 3.0
        assert proc.wait(timeout=5) == 0
        assert proc.returncode == 0


def test_terminate_and_poll() -> None:
    proc = MockPopen(["cmd"], complete_after=10)
    assert proc.poll() is None
    proc.terminate()
    assert proc.poll() == -15
    assert proc.wait() == -15
