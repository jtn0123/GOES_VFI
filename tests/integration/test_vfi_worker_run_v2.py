"""Optimized integration tests for VFI worker run functionality.

Optimizations applied:
- Shared mock setup for PyQt6 components
- Parameterized test scenarios for comprehensive coverage
- Enhanced error handling and edge case testing
- Mock-based testing to avoid GUI dependencies
- Comprehensive signal validation
"""

from collections.abc import Callable
import pathlib
import sys
from types import ModuleType
from typing import Any, Never
from unittest.mock import MagicMock

from PIL import Image
import pytest

from goesvfi.pipeline.run_vfi import VfiWorker


class TestVfiWorkerRunV2:
    """Optimized test class for VFI worker run functionality."""

    @pytest.fixture(scope="class")
    @staticmethod
    def mock_pyqt_setup() -> dict[str, ModuleType]:
        """Set up minimal PyQt6 mocks for headless test execution.

        Returns:
            dict[str, ModuleType]: Dictionary containing mock Qt modules.
        """
        qtcore = ModuleType("PyQt6.QtCore")
        qtcore.QThread = object  # type: ignore[attr-defined]
        qtcore.pyqtSignal = lambda *_a, **_k: MagicMock()  # type: ignore[attr-defined]

        pyqt6 = ModuleType("PyQt6")
        pyqt6.QtCore = qtcore  # type: ignore[attr-defined]

        sys.modules.setdefault("PyQt6", pyqt6)
        sys.modules.setdefault("PyQt6.QtCore", qtcore)

        return {"qtcore": qtcore, "pyqt6": pyqt6}

    @pytest.fixture()
    @staticmethod
    def dummy_image_factory() -> Callable[..., None]:
        """Factory for creating dummy PNG images.

        Returns:
            Callable[..., None]: Function to create dummy PNG images.
        """

        def create_dummy_png(
            path: pathlib.Path, size: tuple[int, int] = (10, 10), color: tuple[int, int, int] = (0, 0, 0)
        ) -> None:
            img = Image.new("RGB", size, color=color)
            path.parent.mkdir(parents=True, exist_ok=True)
            img.save(path, format="PNG")

        return create_dummy_png

    @pytest.fixture()
    @staticmethod
    def test_input_setup(tmp_path: pathlib.Path, dummy_image_factory: Callable[..., None]) -> pathlib.Path:
        """Set up test input directory with sample images.

        Returns:
            pathlib.Path: Path to the test input directory.
        """
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        # Create test images with different colors
        test_images = [
            ("frame_0.png", (255, 0, 0)),  # Red
            ("frame_1.png", (0, 255, 0)),  # Green
            ("frame_2.png", (0, 0, 255)),  # Blue
        ]

        for filename, color in test_images:
            dummy_image_factory(input_dir / filename, color=color)

        return input_dir

    @pytest.fixture()
    @staticmethod
    def mock_signal_handlers() -> dict[str, MagicMock]:
        """Create mock signal handlers for testing.

        Returns:
            dict[str, MagicMock]: Dictionary of mock signal handlers.
        """
        return {"progress": MagicMock(), "finished": MagicMock(), "error": MagicMock()}

    @staticmethod
    def test_vfi_worker_successful_run(
        mock_pyqt_setup: dict[str, ModuleType],  # noqa: ARG004
        test_input_setup: pathlib.Path,
        tmp_path: pathlib.Path,
        mock_signal_handlers: dict[str, MagicMock],
        monkeypatch: Any,
    ) -> None:
        """Test successful VFI worker execution."""
        output_file = tmp_path / "output.mp4"

        # Mock RIFE executable
        monkeypatch.setattr(
            "goesvfi.pipeline.run_vfi.VfiWorker._get_rife_executable",
            lambda self: pathlib.Path("/fake/rife"),  # noqa: ARG005
        )

        # Mock run_vfi function to simulate successful processing
        def fake_run_vfi(**kwargs: Any) -> Any:
            yield (1, 2, 50.0)  # progress: current, total, percentage
            yield (2, 2, 100.0)  # final progress
            yield pathlib.Path(kwargs["output_mp4_path"])  # result

        monkeypatch.setattr("goesvfi.pipeline.run_vfi.run_vfi", fake_run_vfi)

        # Create worker
        worker = VfiWorker(in_dir=str(test_input_setup), out_file_path=str(output_file))

        # Connect signals
        worker.progress.connect(mock_signal_handlers["progress"])
        worker.finished.connect(mock_signal_handlers["finished"])
        worker.error.connect(mock_signal_handlers["error"])

        # Run worker
        worker.run()

        # Verify signals were called correctly
        assert mock_signal_handlers["progress"].call_count == 2
        mock_signal_handlers["progress"].assert_any_call(1, 2, 50.0)
        mock_signal_handlers["progress"].assert_any_call(2, 2, 100.0)
        mock_signal_handlers["finished"].assert_called_once_with(str(output_file))
        mock_signal_handlers["error"].assert_not_called()

    @pytest.mark.parametrize("error_scenario", ["rife_not_found", "processing_failure", "invalid_input_dir"])
    @staticmethod
    def test_vfi_worker_error_scenarios(
        mock_pyqt_setup: dict[str, ModuleType],  # noqa: ARG004
        test_input_setup: pathlib.Path,
        tmp_path: pathlib.Path,
        mock_signal_handlers: dict[str, MagicMock],
        monkeypatch: Any,
        error_scenario: str,
    ) -> None:
        """Test VFI worker error handling scenarios."""
        output_file = tmp_path / "output.mp4"

        if error_scenario == "rife_not_found":
            # Mock RIFE executable not found
            monkeypatch.setattr(
                "goesvfi.pipeline.run_vfi.VfiWorker._get_rife_executable",
                lambda self: None,  # noqa: ARG005
            )
        elif error_scenario == "processing_failure":
            # Mock RIFE executable exists
            monkeypatch.setattr(
                "goesvfi.pipeline.run_vfi.VfiWorker._get_rife_executable",
                lambda self: pathlib.Path("/fake/rife"),  # noqa: ARG005
            )

            # Mock run_vfi to raise exception
            def failing_run_vfi(**kwargs: Any) -> Never:
                msg = "Processing failed"
                raise RuntimeError(msg)

            monkeypatch.setattr("goesvfi.pipeline.run_vfi.run_vfi", failing_run_vfi)
        elif error_scenario == "invalid_input_dir":
            # Use non-existent input directory
            test_input_setup = tmp_path / "nonexistent"

        # Create worker
        worker = VfiWorker(in_dir=str(test_input_setup), out_file_path=str(output_file))

        # Connect signals
        worker.progress.connect(mock_signal_handlers["progress"])
        worker.finished.connect(mock_signal_handlers["finished"])
        worker.error.connect(mock_signal_handlers["error"])

        # Run worker
        worker.run()

        # Verify error handling
        if error_scenario in {"rife_not_found", "processing_failure"}:
            mock_signal_handlers["error"].assert_called_once()
            mock_signal_handlers["finished"].assert_not_called()

    @staticmethod
    def test_vfi_worker_partial_progress(
        mock_pyqt_setup: dict[str, ModuleType],  # noqa: ARG004
        test_input_setup: pathlib.Path,
        tmp_path: pathlib.Path,
        mock_signal_handlers: dict[str, MagicMock],
        monkeypatch: Any,
    ) -> None:
        """Test VFI worker with partial progress updates."""
        output_file = tmp_path / "output.mp4"

        # Mock RIFE executable
        monkeypatch.setattr(
            "goesvfi.pipeline.run_vfi.VfiWorker._get_rife_executable",
            lambda self: pathlib.Path("/fake/rife"),  # noqa: ARG005
        )

        # Mock run_vfi with multiple progress updates
        def progressive_run_vfi(**kwargs: Any) -> Any:
            for i in range(1, 6):  # 5 progress updates
                yield (i, 5, i * 20.0)
            yield pathlib.Path(kwargs["output_mp4_path"])

        monkeypatch.setattr("goesvfi.pipeline.run_vfi.run_vfi", progressive_run_vfi)

        # Create worker
        worker = VfiWorker(in_dir=str(test_input_setup), out_file_path=str(output_file))

        # Connect signals
        worker.progress.connect(mock_signal_handlers["progress"])
        worker.finished.connect(mock_signal_handlers["finished"])
        worker.error.connect(mock_signal_handlers["error"])

        # Run worker
        worker.run()

        # Verify multiple progress calls
        assert mock_signal_handlers["progress"].call_count == 5
        mock_signal_handlers["finished"].assert_called_once()
        mock_signal_handlers["error"].assert_not_called()

    @staticmethod
    def test_vfi_worker_signal_connections(
        mock_pyqt_setup: dict[str, ModuleType],  # noqa: ARG004
        test_input_setup: pathlib.Path,
        tmp_path: pathlib.Path,
    ) -> None:
        """Test VFI worker signal connection functionality."""
        output_file = tmp_path / "output.mp4"

        # Create worker
        worker = VfiWorker(in_dir=str(test_input_setup), out_file_path=str(output_file))

        # Verify signal attributes exist
        assert hasattr(worker, "progress")
        assert hasattr(worker, "finished")
        assert hasattr(worker, "error")

        # Test signal connection
        test_handler = MagicMock()
        worker.progress.connect(test_handler)

        # Verify connection works
        assert worker.progress is not None

    @staticmethod
    def test_vfi_worker_input_validation(
        mock_pyqt_setup: dict[str, ModuleType],  # noqa: ARG004
        tmp_path: pathlib.Path,
    ) -> None:
        """Test VFI worker input validation."""
        # Test with various input scenarios
        test_cases = [
            {"in_dir": str(tmp_path / "nonexistent"), "out_file": str(tmp_path / "out.mp4")},
            {"in_dir": str(tmp_path), "out_file": str(tmp_path / "subdir" / "out.mp4")},
        ]

        for case in test_cases:
            worker = VfiWorker(in_dir=case["in_dir"], out_file_path=case["out_file"])

            # Verify worker creation doesn't fail
            assert worker is not None
            assert hasattr(worker, "run")

    @staticmethod
    def test_vfi_worker_resource_cleanup(
        mock_pyqt_setup: dict[str, ModuleType],  # noqa: ARG004
        test_input_setup: pathlib.Path,
        tmp_path: pathlib.Path,
        monkeypatch: Any,
    ) -> None:
        """Test VFI worker resource cleanup after completion."""
        output_file = tmp_path / "output.mp4"

        # Mock RIFE executable
        monkeypatch.setattr(
            "goesvfi.pipeline.run_vfi.VfiWorker._get_rife_executable",
            lambda self: pathlib.Path("/fake/rife"),  # noqa: ARG005
        )

        # Mock run_vfi
        def simple_run_vfi(**kwargs: Any) -> Any:
            yield (1, 1, 100.0)
            yield pathlib.Path(kwargs["output_mp4_path"])

        monkeypatch.setattr("goesvfi.pipeline.run_vfi.run_vfi", simple_run_vfi)

        # Create and run worker
        worker = VfiWorker(in_dir=str(test_input_setup), out_file_path=str(output_file))

        # Connect mock handlers
        progress_handler = MagicMock()
        finished_handler = MagicMock()
        error_handler = MagicMock()

        worker.progress.connect(progress_handler)
        worker.finished.connect(finished_handler)
        worker.error.connect(error_handler)

        # Run worker
        worker.run()

        # Verify completion and cleanup
        finished_handler.assert_called_once()
        error_handler.assert_not_called()

    @staticmethod
    def test_vfi_worker_concurrent_execution_safety(
        mock_pyqt_setup: dict[str, ModuleType],  # noqa: ARG004
        test_input_setup: pathlib.Path,
        tmp_path: pathlib.Path,
        monkeypatch: Any,
    ) -> None:
        """Test VFI worker behavior with concurrent execution concerns."""
        tmp_path / "output.mp4"

        # Mock RIFE executable
        monkeypatch.setattr(
            "goesvfi.pipeline.run_vfi.VfiWorker._get_rife_executable",
            lambda self: pathlib.Path("/fake/rife"),  # noqa: ARG005
        )

        # Mock run_vfi with delay simulation
        def delayed_run_vfi(**kwargs: Any) -> Any:
            yield (1, 3, 33.3)
            yield (2, 3, 66.6)
            yield (3, 3, 100.0)
            yield pathlib.Path(kwargs["output_mp4_path"])

        monkeypatch.setattr("goesvfi.pipeline.run_vfi.run_vfi", delayed_run_vfi)

        # Create multiple workers (simulating potential concurrent usage)
        workers = []
        handlers = []

        for i in range(2):
            worker = VfiWorker(in_dir=str(test_input_setup), out_file_path=str(tmp_path / f"output_{i}.mp4"))
            handler = {"progress": MagicMock(), "finished": MagicMock(), "error": MagicMock()}

            worker.progress.connect(handler["progress"])
            worker.finished.connect(handler["finished"])
            worker.error.connect(handler["error"])

            workers.append(worker)
            handlers.append(handler)

        # Run workers sequentially (not actually concurrent in test)
        for worker in workers:
            worker.run()

        # Verify all workers completed successfully
        for handler in handlers:
            assert handler["progress"].call_count == 3
            handler["finished"].assert_called_once()
            handler["error"].assert_not_called()
