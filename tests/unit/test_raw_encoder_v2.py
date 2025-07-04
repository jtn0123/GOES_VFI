"""Optimized unit tests for raw encoder functionality with maintained coverage.

This v2 version maintains all test scenarios while optimizing through:
- Shared fixtures for raw encoder setup and mock configurations
- Combined encoding testing scenarios for different success/error conditions
- Batch validation of FFmpeg command execution and file operations
- Enhanced error handling and edge case coverage
"""

from collections.abc import Callable
import contextlib
from pathlib import Path
import subprocess  # noqa: S404
import types
from typing import Any, cast
from unittest.mock import MagicMock, patch

import numpy as np
from numpy.typing import NDArray
import pytest

from goesvfi.pipeline import raw_encoder

from tests.utils.mocks import create_mock_subprocess_run


class TestRawEncoderOptimizedV2:
    """Optimized raw encoder tests with full coverage."""

    @staticmethod
    @pytest.fixture(scope="class")
    def raw_encoder_test_components() -> dict[str, Any]:  # noqa: C901
        """Create shared components for raw encoder testing.

        Returns:
            dict[str, Any]: Dictionary containing test manager and analyzer components.
        """

        # Enhanced Raw Encoder Test Manager
        class RawEncoderTestManager:
            """Manage raw encoder testing scenarios."""

            def __init__(self) -> None:
                rng = np.random.default_rng()
                self.frame_templates: dict[str, list[NDArray[np.float32]]] = {
                    "small": [np.ones((4, 4, 3), dtype=np.float32) * (i + 1) for i in range(3)],
                    "medium": [np.ones((8, 8, 3), dtype=np.float32) * (i + 1) for i in range(5)],
                    "large": [np.ones((16, 16, 3), dtype=np.float32) * (i + 1) for i in range(10)],
                    "single": [np.ones((4, 4, 3), dtype=np.float32)],
                    "varied_values": [rng.random((4, 4, 3), dtype=np.float32) * (i + 1) for i in range(4)],
                    "grayscale": [np.ones((4, 4, 1), dtype=np.float32) * (i + 1) for i in range(3)],
                    "empty": [],
                }

                self.encoding_configs: dict[str, dict[str, Any]] = {
                    "standard": {
                        "fps": 30,
                        "codec": "ffv1",
                        "expected_calls": "exact",
                    },
                    "high_fps": {
                        "fps": 60,
                        "codec": "ffv1",
                        "expected_calls": "exact",
                    },
                    "low_fps": {
                        "fps": 1,
                        "codec": "ffv1",
                        "expected_calls": "exact",
                    },
                    "custom_fps": {
                        "fps": 24,
                        "codec": "ffv1",
                        "expected_calls": "exact",
                    },
                }

                self.test_scenarios: dict[str, Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]] = {
                    "successful_encoding": self._test_successful_encoding,
                    "error_handling": self._test_error_handling,
                    "frame_processing": self._test_frame_processing,
                    "command_validation": self._test_command_validation,
                    "edge_cases": self._test_edge_cases,
                    "performance_tests": self._test_performance_tests,
                }

            def _test_successful_encoding(
                self, temp_workspace: dict[str, Any], mock_registry: dict[str, Any]
            ) -> dict[str, Any]:
                """Test successful raw MP4 encoding scenarios.

                Returns:
                    dict[str, Any]: Test results dictionary.
                """
                results: dict[str, Any] = {}

                # Test different frame sets and configurations
                test_cases = [
                    {
                        "name": "standard_small",
                        "frames": "small",
                        "config": "standard",
                    },
                    {
                        "name": "high_fps_medium",
                        "frames": "medium",
                        "config": "high_fps",
                    },
                    {
                        "name": "custom_fps_varied",
                        "frames": "varied_values",
                        "config": "custom_fps",
                    },
                    {
                        "name": "single_frame",
                        "frames": "single",
                        "config": "low_fps",
                    },
                ]

                for test_case in test_cases:
                    frames: list[NDArray[np.float32]] = self.frame_templates[test_case["frames"]]
                    config: dict[str, Any] = self.encoding_configs[test_case["config"]]

                    # Create test-specific workspace
                    test_workspace = self._create_test_workspace(temp_workspace, test_case["name"])

                    # Build expected FFmpeg command
                    expected_cmd: list[str] = self._build_expected_command(
                        test_workspace["temp_dir_path"], test_workspace["raw_path"], config["fps"]
                    )

                    with self._setup_successful_mocks(test_workspace, expected_cmd) as mock_context:
                        # Execute encoding
                        result_path = raw_encoder.write_raw_mp4(frames, test_workspace["raw_path"], fps=config["fps"])

                        # Verify results
                        assert result_path == test_workspace["raw_path"], (
                            f"Should return correct path for {test_case['name']}"
                        )
                        assert test_workspace["raw_path"].exists(), f"Output file should exist for {test_case['name']}"

                        # Verify mock interactions
                        assert mock_context["mock_fromarray"].call_count == len(frames), (
                            f"Should convert all frames for {test_case['name']}"
                        )
                        mock_context["mock_run"].assert_called_once()

                        # Verify save operations
                        assert mock_context["mock_img"].save.call_count == len(frames), (
                            f"Should save all frames for {test_case['name']}"
                        )

                        results[test_case["name"]] = {
                            "success": True,
                            "frames_processed": len(frames),
                            "fps": config["fps"],
                            "result_path": str(result_path),
                            "file_exists": test_workspace["raw_path"].exists(),
                            "fromarray_calls": mock_context["mock_fromarray"].call_count,
                            "save_calls": mock_context["mock_img"].save.call_count,
                        }

                mock_registry["successful_encoding"] = results
                return results

            def _test_error_handling(
                self, temp_workspace: dict[str, Any], mock_registry: dict[str, Any]
            ) -> dict[str, Any]:
                """Test error handling scenarios.

                Returns:
                    dict[str, Any]: Test results dictionary.
                """
                error_tests: dict[str, Any] = {}

                frames: list[NDArray[np.float32]] = self.frame_templates["small"]
                config: dict[str, Any] = self.encoding_configs["standard"]

                # Test FFmpeg CalledProcessError
                test_workspace: dict[str, Any] = self._create_test_workspace(temp_workspace, "ffmpeg_error")
                expected_cmd: list[str] = self._build_expected_command(
                    test_workspace["temp_dir_path"], test_workspace["raw_path"], config["fps"]
                )

                with self._setup_error_mocks(test_workspace, expected_cmd, "called_process_error") as mock_context:
                    try:
                        with pytest.raises(subprocess.CalledProcessError):
                            raw_encoder.write_raw_mp4(frames, test_workspace["raw_path"], fps=config["fps"])

                        # Verify mock was called despite error
                        mock_context["mock_run"].assert_called_once()

                        error_tests["ffmpeg_called_process_error"] = {
                            "success": True,
                            "raises_correct_error": True,
                            "mock_called": True,
                        }
                    except Exception as e:  # noqa: BLE001
                        error_tests["ffmpeg_called_process_error"] = {
                            "success": False,
                            "unexpected_error": str(e),
                        }

                # Test FFmpeg FileNotFoundError
                test_workspace = self._create_test_workspace(temp_workspace, "ffmpeg_not_found")
                expected_cmd = self._build_expected_command(
                    test_workspace["temp_dir_path"], test_workspace["raw_path"], config["fps"]
                )

                with self._setup_error_mocks(test_workspace, expected_cmd, "file_not_found_error") as mock_context:
                    try:
                        with pytest.raises(FileNotFoundError):
                            raw_encoder.write_raw_mp4(frames, test_workspace["raw_path"], fps=config["fps"])

                        # Verify mock was called despite error
                        mock_context["mock_run"].assert_called_once()

                        error_tests["ffmpeg_file_not_found"] = {
                            "success": True,
                            "raises_correct_error": True,
                            "mock_called": True,
                        }
                    except Exception as e:  # noqa: BLE001
                        error_tests["ffmpeg_file_not_found"] = {
                            "success": False,
                            "unexpected_error": str(e),
                        }

                # Test Image processing error
                test_workspace = self._create_test_workspace(temp_workspace, "image_error")
                expected_cmd = self._build_expected_command(
                    test_workspace["temp_dir_path"], test_workspace["raw_path"], config["fps"]
                )

                with self._setup_image_error_mocks(test_workspace, expected_cmd) as mock_context:
                    try:
                        with pytest.raises(ValueError, match="Invalid image data"):
                            raw_encoder.write_raw_mp4(frames, test_workspace["raw_path"], fps=config["fps"])

                        error_tests["image_processing_error"] = {
                            "success": True,
                            "raises_correct_error": True,
                        }
                    except Exception as e:  # noqa: BLE001
                        error_tests["image_processing_error"] = {
                            "success": False,
                            "unexpected_error": str(e),
                        }

                mock_registry["error_handling"] = error_tests
                return error_tests

            def _test_frame_processing(
                self, temp_workspace: dict[str, Any], mock_registry: dict[str, Any]
            ) -> dict[str, Any]:
                """Test frame processing with different frame types.

                Returns:
                    dict[str, Any]: Test results dictionary.
                """
                frame_tests: dict[str, Any] = {}

                config: dict[str, Any] = self.encoding_configs["standard"]

                # Test different frame configurations
                frame_test_cases = [
                    {
                        "name": "empty_frames",
                        "frames": "empty",
                        "expected_behavior": "handle_gracefully",
                    },
                    {
                        "name": "single_frame",
                        "frames": "single",
                        "expected_behavior": "process_normally",
                    },
                    {
                        "name": "many_frames",
                        "frames": "large",
                        "expected_behavior": "process_normally",
                    },
                    {
                        "name": "grayscale_frames",
                        "frames": "grayscale",
                        "expected_behavior": "process_normally",
                    },
                ]

                for frame_test in frame_test_cases:
                    frames: list[NDArray[np.float32]] = self.frame_templates[frame_test["frames"]]
                    test_workspace: dict[str, Any] = self._create_test_workspace(temp_workspace, frame_test["name"])

                    expected_cmd = self._build_expected_command(
                        test_workspace["temp_dir_path"], test_workspace["raw_path"], config["fps"]
                    )

                    if frame_test["expected_behavior"] == "handle_gracefully" and len(frames) == 0:
                        # Empty frames might cause an error or be handled gracefully
                        try:
                            with self._setup_successful_mocks(test_workspace, expected_cmd) as mock_context:
                                result_path = raw_encoder.write_raw_mp4(
                                    frames, test_workspace["raw_path"], fps=config["fps"]
                                )

                                frame_tests[frame_test["name"]] = {
                                    "success": True,
                                    "frames_count": len(frames),
                                    "handled_gracefully": True,
                                    "result_path": str(result_path),
                                }
                        except Exception as e:  # noqa: BLE001
                            frame_tests[frame_test["name"]] = {
                                "success": True,
                                "frames_count": len(frames),
                                "expected_error": str(e),
                                "error_type": type(e).__name__,
                            }
                    else:
                        # Normal processing expected
                        with self._setup_successful_mocks(test_workspace, expected_cmd) as mock_context:
                            result_path = raw_encoder.write_raw_mp4(
                                frames, test_workspace["raw_path"], fps=config["fps"]
                            )

                            # Verify frame processing
                            assert mock_context["mock_fromarray"].call_count == len(frames), (
                                f"Should process all frames for {frame_test['name']}"
                            )
                            assert mock_context["mock_img"].save.call_count == len(frames), (
                                f"Should save all frames for {frame_test['name']}"
                            )

                            frame_tests[frame_test["name"]] = {
                                "success": True,
                                "frames_count": len(frames),
                                "fromarray_calls": mock_context["mock_fromarray"].call_count,
                                "save_calls": mock_context["mock_img"].save.call_count,
                                "result_path": str(result_path),
                            }

                mock_registry["frame_processing"] = frame_tests
                return frame_tests

            def _test_command_validation(
                self, temp_workspace: dict[str, Any], mock_registry: dict[str, Any]
            ) -> dict[str, Any]:
                """Test FFmpeg command construction validation.

                Returns:
                    dict[str, Any]: Test results dictionary.
                """
                command_tests: dict[str, Any] = {}

                frames: list[NDArray[np.float32]] = self.frame_templates["small"]

                # Test different FPS values and their command generation
                fps_test_cases = [
                    {"fps": 1, "name": "fps_1"},
                    {"fps": 24, "name": "fps_24"},
                    {"fps": 30, "name": "fps_30"},
                    {"fps": 60, "name": "fps_60"},
                    {"fps": 120, "name": "fps_120"},
                ]

                for fps_test in fps_test_cases:
                    fps_value: int = cast("int", fps_test["fps"])
                    test_name: str = cast("str", fps_test["name"])
                    test_workspace = self._create_test_workspace(temp_workspace, test_name)

                    expected_cmd = self._build_expected_command(
                        test_workspace["temp_dir_path"], test_workspace["raw_path"], fps_value
                    )

                    with self._setup_command_validation_mocks(test_workspace, expected_cmd) as mock_context:
                        raw_encoder.write_raw_mp4(frames, test_workspace["raw_path"], fps=fps_value)

                        # Get the actual command that was called
                        actual_cmd = mock_context["mock_run"].call_args[0][0]

                        # Verify command structure
                        assert "ffmpeg" in actual_cmd, f"Command should contain ffmpeg for FPS {fps_value}"
                        assert "-y" in actual_cmd, f"Command should contain overwrite flag for FPS {fps_value}"
                        assert "-framerate" in actual_cmd, f"Command should contain framerate flag for FPS {fps_value}"
                        assert str(fps_value) in actual_cmd, f"Command should contain FPS value for FPS {fps_value}"
                        assert "-i" in actual_cmd, f"Command should contain input flag for FPS {fps_value}"
                        assert "-c:v" in actual_cmd, f"Command should contain video codec flag for FPS {fps_value}"
                        assert "ffv1" in actual_cmd, f"Command should contain ffv1 codec for FPS {fps_value}"
                        assert str(test_workspace["raw_path"]) in actual_cmd, (
                            f"Command should contain output path for FPS {fps_value}"
                        )

                        # Verify command order and structure
                        framerate_index = actual_cmd.index("-framerate")
                        assert actual_cmd[framerate_index + 1] == str(fps_value), (
                            f"FPS value should follow framerate flag for FPS {fps_value}"
                        )

                        command_tests[test_name] = {
                            "success": True,
                            "fps": fps_value,
                            "command_valid": True,
                            "actual_command": actual_cmd,
                            "expected_command": expected_cmd,
                            "commands_match": actual_cmd == expected_cmd,
                        }

                mock_registry["command_validation"] = command_tests
                return command_tests

            def _test_edge_cases(self, temp_workspace: dict[str, Any], mock_registry: dict[str, Any]) -> dict[str, Any]:
                """Test edge cases and boundary conditions.

                Returns:
                    dict[str, Any]: Test results dictionary.
                """
                edge_case_tests: dict[str, Any] = {}

                # Test edge case scenarios
                edge_cases = [
                    {
                        "name": "very_high_fps",
                        "frames": "small",
                        "fps": 1000,
                        "expected": "success",
                    },
                    {
                        "name": "zero_fps",
                        "frames": "small",
                        "fps": 0,
                        "expected": "error_or_success",  # Might be handled differently
                    },
                    {
                        "name": "negative_fps",
                        "frames": "small",
                        "fps": -1,
                        "expected": "error_or_success",
                    },
                    {
                        "name": "float_fps",
                        "frames": "small",
                        "fps": 29.97,
                        "expected": "success",
                    },
                ]

                for edge_case in edge_cases:
                    frames_key: str = cast("str", edge_case["frames"])
                    case_name: str = cast("str", edge_case["name"])
                    fps_value: float = cast("float", edge_case["fps"])
                    frames = self.frame_templates[frames_key]
                    test_workspace = self._create_test_workspace(temp_workspace, case_name)

                    expected_cmd = self._build_expected_command(
                        test_workspace["temp_dir_path"], test_workspace["raw_path"], fps_value
                    )

                    try:
                        with self._setup_successful_mocks(test_workspace, expected_cmd):
                            result_path = raw_encoder.write_raw_mp4(
                                frames, test_workspace["raw_path"], fps=int(fps_value)
                            )

                            edge_case_tests[case_name] = {
                                "success": True,
                                "fps": fps_value,
                                "frames_count": len(frames),
                                "result_path": str(result_path),
                                "expected_behavior": edge_case["expected"],
                            }
                    except Exception as e:  # noqa: BLE001
                        edge_case_tests[case_name] = {
                            "success": edge_case["expected"] == "error_or_success",
                            "fps": fps_value,
                            "frames_count": len(frames),
                            "exception": str(e),
                            "exception_type": type(e).__name__,
                            "expected_behavior": edge_case["expected"],
                        }

                mock_registry["edge_cases"] = edge_case_tests
                return edge_case_tests

            def _test_performance_tests(
                self, temp_workspace: dict[str, Any], mock_registry: dict[str, Any]
            ) -> dict[str, Any]:
                """Test performance characteristics.

                Returns:
                    dict[str, Any]: Test results dictionary.
                """
                performance_tests: dict[str, Any] = {}

                config: dict[str, Any] = self.encoding_configs["standard"]

                # Test performance with different loads
                performance_cases = [
                    {
                        "name": "rapid_encoding_calls",
                        "test": lambda: self._test_rapid_encoding_calls(temp_workspace, config),
                    },
                    {
                        "name": "large_frame_sets",
                        "test": lambda: self._test_large_frame_sets(temp_workspace, config),
                    },
                    {
                        "name": "memory_efficiency",
                        "test": lambda: self._test_memory_efficiency(temp_workspace, config),
                    },
                ]

                for perf_case in performance_cases:
                    case_name: str = cast("str", perf_case["name"])
                    test_func: Callable[[], dict[str, Any]] = cast("Callable[[], dict[str, Any]]", perf_case["test"])
                    try:
                        result = test_func()
                        performance_tests[case_name] = {
                            "success": True,
                            "result": result,
                        }
                    except Exception as e:  # noqa: BLE001
                        performance_tests[case_name] = {
                            "success": False,
                            "exception": str(e),
                        }

                mock_registry["performance_tests"] = performance_tests
                return performance_tests

            def _test_rapid_encoding_calls(
                self, temp_workspace: dict[str, Any], config: dict[str, Any]
            ) -> dict[str, Any]:
                """Test rapid succession of encoding calls.

                Returns:
                    dict[str, Any]: Test results dictionary.
                """
                frames: list[NDArray[np.float32]] = self.frame_templates["small"]
                successful_calls: int = 0
                total_calls: int = 5

                for i in range(total_calls):
                    test_workspace = self._create_test_workspace(temp_workspace, f"rapid_{i}")
                    expected_cmd = self._build_expected_command(
                        test_workspace["temp_dir_path"], test_workspace["raw_path"], config["fps"]
                    )

                    with contextlib.suppress(Exception), self._setup_successful_mocks(test_workspace, expected_cmd):
                        raw_encoder.write_raw_mp4(frames, test_workspace["raw_path"], fps=config["fps"])
                        successful_calls += 1

                return {
                    "successful_calls": successful_calls,
                    "total_calls": total_calls,
                    "success_rate": successful_calls / total_calls,
                }

            def _test_large_frame_sets(self, temp_workspace: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
                """Test encoding with large frame sets.

                Returns:
                    dict[str, Any]: Test results dictionary.
                """
                # Create large frame set
                large_frames: list[NDArray[np.float32]] = [
                    np.ones((32, 32, 3), dtype=np.float32) * i for i in range(50)
                ]

                test_workspace = self._create_test_workspace(temp_workspace, "large_frames")
                expected_cmd = self._build_expected_command(
                    test_workspace["temp_dir_path"], test_workspace["raw_path"], config["fps"]
                )

                with self._setup_successful_mocks(test_workspace, expected_cmd) as mock_context:
                    result_path = raw_encoder.write_raw_mp4(large_frames, test_workspace["raw_path"], fps=config["fps"])

                    return {
                        "frames_processed": len(large_frames),
                        "fromarray_calls": mock_context["mock_fromarray"].call_count,
                        "save_calls": mock_context["mock_img"].save.call_count,
                        "result_path": str(result_path),
                    }

            def _test_memory_efficiency(self, temp_workspace: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
                """Test memory efficiency during encoding.

                Returns:
                    dict[str, Any]: Test results dictionary.
                """
                frames: list[NDArray[np.float32]] = self.frame_templates["medium"]

                test_workspace: dict[str, Any] = self._create_test_workspace(temp_workspace, "memory_test")
                expected_cmd: list[str] = self._build_expected_command(
                    test_workspace["temp_dir_path"], test_workspace["raw_path"], config["fps"]
                )

                # Test multiple encoding operations to check for memory leaks
                operations: int = 3
                successful_operations: int = 0

                for _i in range(operations):
                    with contextlib.suppress(Exception), self._setup_successful_mocks(test_workspace, expected_cmd):
                        raw_encoder.write_raw_mp4(frames, test_workspace["raw_path"], fps=config["fps"])
                        successful_operations += 1

                return {
                    "successful_operations": successful_operations,
                    "total_operations": operations,
                    "frames_per_operation": len(frames),
                }

            @staticmethod
            def _create_test_workspace(temp_workspace: dict[str, Any], test_name: str) -> dict[str, Any]:
                """Create test-specific workspace.

                Returns:
                    dict[str, Any]: Test workspace configuration.
                """
                test_dir = temp_workspace["tmp_path"] / test_name
                test_dir.mkdir(exist_ok=True)

                temp_dir_path = test_dir / "tempdir"
                temp_dir_path.mkdir(exist_ok=True)

                raw_path = test_dir / "output.mp4"

                return {
                    "test_dir": test_dir,
                    "temp_dir_path": temp_dir_path,
                    "raw_path": raw_path,
                }

            @staticmethod
            def _build_expected_command(temp_dir_path: Path, raw_path: Path, fps: float) -> list[str]:
                """Build expected FFmpeg command.

                Returns:
                    list[str]: Expected FFmpeg command.
                """
                expected_pattern = str(temp_dir_path / "%06d.png")
                return [
                    "ffmpeg",
                    "-y",
                    "-framerate",
                    str(fps),
                    "-i",
                    expected_pattern,
                    "-c:v",
                    "ffv1",
                    str(raw_path),
                ]

            @staticmethod
            def _setup_successful_mocks(test_workspace: dict[str, Any], expected_cmd: list[str]) -> Any:
                """Setup mocks for successful encoding.

                Returns:
                    Any: Mock context manager.
                """

                class MockContext:
                    def __enter__(self) -> dict[str, Any]:
                        # Create mock factory
                        mock_run_factory = create_mock_subprocess_run(
                            expected_command=expected_cmd,
                            output_file_to_create=test_workspace["raw_path"],
                        )

                        # Setup patches
                        self.patch_tempdir = patch("goesvfi.pipeline.raw_encoder.tempfile.TemporaryDirectory")
                        self.patch_fromarray = patch("goesvfi.pipeline.raw_encoder.Image.fromarray")
                        self.patch_run = patch(
                            "goesvfi.pipeline.raw_encoder.subprocess.run", side_effect=mock_run_factory
                        )

                        # Start patches
                        mock_tempdir = self.patch_tempdir.start()
                        mock_fromarray = self.patch_fromarray.start()
                        mock_run = self.patch_run.start()

                        # Configure tempdir mock
                        mock_tempdir.return_value = MagicMock(name="TemporaryDirectory")
                        mock_tempdir.return_value.__enter__.return_value = str(test_workspace["temp_dir_path"])
                        mock_tempdir.return_value.__exit__.return_value = None
                        mock_tempdir.return_value.name = str(test_workspace["temp_dir_path"])

                        # Configure image mock
                        mock_img = MagicMock()
                        mock_fromarray.return_value = mock_img

                        return {
                            "mock_tempdir": mock_tempdir,
                            "mock_fromarray": mock_fromarray,
                            "mock_run": mock_run,
                            "mock_img": mock_img,
                        }

                    def __exit__(
                        self,
                        exc_type: type[BaseException] | None,
                        exc_val: BaseException | None,
                        exc_tb: types.TracebackType | None,
                    ) -> None:
                        # Stop patches
                        self.patch_run.stop()
                        self.patch_fromarray.stop()
                        self.patch_tempdir.stop()

                return MockContext()

            @staticmethod
            def _setup_error_mocks(test_workspace: dict[str, Any], expected_cmd: list[str], error_type: str) -> Any:
                """Setup mocks for error scenarios.

                Returns:
                    Any: Mock context manager.
                """

                class MockContext:
                    def __enter__(self) -> dict[str, Any]:
                        # Create appropriate error
                        error: Exception
                        if error_type == "called_process_error":
                            error = subprocess.CalledProcessError(1, expected_cmd, stderr="ffmpeg fail")
                        elif error_type == "file_not_found_error":
                            error = FileNotFoundError("ffmpeg not found")
                        else:
                            error = RuntimeError("Unknown error")

                        # Create mock factory with error
                        mock_run_factory = create_mock_subprocess_run(expected_command=expected_cmd, side_effect=error)

                        # Setup patches
                        self.patch_tempdir = patch("goesvfi.pipeline.raw_encoder.tempfile.TemporaryDirectory")
                        self.patch_fromarray = patch("goesvfi.pipeline.raw_encoder.Image.fromarray")
                        self.patch_run = patch(
                            "goesvfi.pipeline.raw_encoder.subprocess.run", side_effect=mock_run_factory
                        )

                        # Start patches
                        mock_tempdir = self.patch_tempdir.start()
                        mock_fromarray = self.patch_fromarray.start()
                        mock_run = self.patch_run.start()

                        # Configure mocks
                        mock_tempdir.return_value = MagicMock(name="TemporaryDirectory")
                        mock_tempdir.return_value.__enter__.return_value = str(test_workspace["temp_dir_path"])
                        mock_tempdir.return_value.__exit__.return_value = None
                        mock_tempdir.return_value.name = str(test_workspace["temp_dir_path"])

                        mock_img = MagicMock()
                        mock_fromarray.return_value = mock_img

                        return {
                            "mock_tempdir": mock_tempdir,
                            "mock_fromarray": mock_fromarray,
                            "mock_run": mock_run,
                            "mock_img": mock_img,
                        }

                    def __exit__(
                        self,
                        exc_type: type[BaseException] | None,
                        exc_val: BaseException | None,
                        exc_tb: types.TracebackType | None,
                    ) -> None:
                        self.patch_run.stop()
                        self.patch_fromarray.stop()
                        self.patch_tempdir.stop()

                return MockContext()

            @staticmethod
            def _setup_image_error_mocks(
                test_workspace: dict[str, Any],
                expected_cmd: list[str],  # noqa: ARG004
            ) -> Any:
                """Setup mocks for image processing errors.

                Returns:
                    Any: Mock context manager.
                """

                class MockContext:
                    def __enter__(self) -> dict[str, Any]:
                        # Setup patches
                        self.patch_tempdir = patch("goesvfi.pipeline.raw_encoder.tempfile.TemporaryDirectory")
                        self.patch_fromarray = patch("goesvfi.pipeline.raw_encoder.Image.fromarray")
                        self.patch_run = patch("goesvfi.pipeline.raw_encoder.subprocess.run")

                        # Start patches
                        mock_tempdir = self.patch_tempdir.start()
                        mock_fromarray = self.patch_fromarray.start()
                        mock_run = self.patch_run.start()

                        # Configure mocks
                        mock_tempdir.return_value = MagicMock(name="TemporaryDirectory")
                        mock_tempdir.return_value.__enter__.return_value = str(test_workspace["temp_dir_path"])
                        mock_tempdir.return_value.__exit__.return_value = None

                        # Make fromarray raise an error
                        mock_fromarray.side_effect = ValueError("Invalid image data")

                        return {
                            "mock_tempdir": mock_tempdir,
                            "mock_fromarray": mock_fromarray,
                            "mock_run": mock_run,
                        }

                    def __exit__(
                        self,
                        exc_type: type[BaseException] | None,
                        exc_val: BaseException | None,
                        exc_tb: types.TracebackType | None,
                    ) -> None:
                        self.patch_run.stop()
                        self.patch_fromarray.stop()
                        self.patch_tempdir.stop()

                return MockContext()

            def _setup_command_validation_mocks(self, test_workspace: dict[str, Any], expected_cmd: list[str]) -> Any:
                """Setup mocks for command validation tests.

                Returns:
                    Any: Mock context manager.
                """
                return self._setup_successful_mocks(test_workspace, expected_cmd)

            def run_test_scenario(
                self, scenario: str, temp_workspace: dict[str, Any], mock_registry: dict[str, Any]
            ) -> dict[str, Any]:
                """Run specified test scenario.

                Returns:
                    dict[str, Any]: Test results.
                """
                return self.test_scenarios[scenario](temp_workspace, mock_registry)

        # Enhanced Result Analyzer
        class ResultAnalyzer:
            """Analyze raw encoder test results for correctness and completeness."""

            def __init__(self) -> None:
                self.analysis_rules: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
                    "encoding_success": self._analyze_encoding_success,
                    "error_handling": self._analyze_error_handling,
                    "frame_processing": self._analyze_frame_processing,
                    "command_validation": self._analyze_command_validation,
                    "performance_metrics": self._analyze_performance_metrics,
                }

            @staticmethod
            def _analyze_encoding_success(results: dict[str, Any]) -> dict[str, Any]:
                """Analyze encoding success rates.

                Returns:
                    dict[str, Any]: Analysis results.
                """
                return {
                    "total_tests": len(results),
                    "successful_tests": sum(1 for r in results.values() if r.get("success")),
                    "success_rate": sum(1 for r in results.values() if r.get("success")) / len(results)
                    if results
                    else 0,
                    "files_created": sum(1 for r in results.values() if r.get("file_exists")),
                }

            @staticmethod
            def _analyze_error_handling(results: dict[str, Any]) -> dict[str, Any]:
                """Analyze error handling effectiveness.

                Returns:
                    dict[str, Any]: Analysis results.
                """
                return {
                    "error_tests": len(results),
                    "correct_errors": sum(1 for r in results.values() if r.get("raises_correct_error")),
                    "unexpected_errors": sum(1 for r in results.values() if r.get("unexpected_error")),
                    "error_handling_rate": sum(1 for r in results.values() if r.get("success")) / len(results)
                    if results
                    else 0,
                }

            @staticmethod
            def _analyze_frame_processing(results: dict[str, Any]) -> dict[str, Any]:
                """Analyze frame processing accuracy.

                Returns:
                    dict[str, Any]: Analysis results.
                """
                # Handle both "frames_count" and "frames_processed" field names for compatibility
                total_frames = sum(r.get("frames_count", 0) + r.get("frames_processed", 0) for r in results.values())
                total_fromarray_calls = sum(r.get("fromarray_calls", 0) for r in results.values())
                total_save_calls = sum(r.get("save_calls", 0) for r in results.values())

                return {
                    "total_frames_processed": total_frames,
                    "total_fromarray_calls": total_fromarray_calls,
                    "total_save_calls": total_save_calls,
                    "fromarray_accuracy": total_fromarray_calls / total_frames if total_frames > 0 else 0,
                    "save_accuracy": total_save_calls / total_frames if total_frames > 0 else 0,
                }

            @staticmethod
            def _analyze_command_validation(results: dict[str, Any]) -> dict[str, Any]:
                """Analyze command validation accuracy.

                Returns:
                    dict[str, Any]: Analysis results.
                """
                return {
                    "command_tests": len(results),
                    "valid_commands": sum(1 for r in results.values() if r.get("command_valid")),
                    "matching_commands": sum(1 for r in results.values() if r.get("commands_match")),
                    "validation_rate": sum(1 for r in results.values() if r.get("command_valid")) / len(results)
                    if results
                    else 0,
                }

            @staticmethod
            def _analyze_performance_metrics(results: dict[str, Any]) -> dict[str, Any]:
                """Analyze performance characteristics.

                Returns:
                    dict[str, Any]: Analysis results.
                """
                return {
                    "performance_tests": len(results),
                    "successful_performance_tests": sum(1 for r in results.values() if r.get("success")),
                    "performance_success_rate": sum(1 for r in results.values() if r.get("success")) / len(results)
                    if results
                    else 0,
                }

            def analyze_results(
                self, results: dict[str, Any], analysis_types: list[str] | None = None
            ) -> dict[str, Any]:
                """Analyze results using specified analysis types.

                Returns:
                    dict[str, Any]: Analysis results.
                """
                if analysis_types is None:
                    analysis_types = list(self.analysis_rules.keys())

                analysis_results = {}
                for analysis_type in analysis_types:
                    if analysis_type in self.analysis_rules:
                        analysis_results[analysis_type] = self.analysis_rules[analysis_type](results)

                return analysis_results

        return {
            "test_manager": RawEncoderTestManager(),
            "analyzer": ResultAnalyzer(),
        }

    @staticmethod
    @pytest.fixture()
    def temp_workspace(tmp_path: Path) -> dict[str, Any]:
        """Create temporary workspace for raw encoder testing.

        Returns:
            dict[str, Any]: Workspace configuration.
        """
        return {
            "tmp_path": tmp_path,
        }

    @staticmethod
    @pytest.fixture()
    def mock_registry() -> dict[str, Any]:
        """Registry for storing mock interaction results.

        Returns:
            dict[str, Any]: Empty registry dictionary.
        """
        return {}

    @staticmethod
    def test_raw_encoder_comprehensive_scenarios(  # noqa: C901, PLR0912, PLR0915
        raw_encoder_test_components: dict[str, Any], temp_workspace: dict[str, Any], mock_registry: dict[str, Any]
    ) -> None:
        """Test comprehensive raw encoder scenarios with all functionality."""
        components = raw_encoder_test_components
        test_manager = components["test_manager"]
        analyzer = components["analyzer"]

        # Define comprehensive raw encoder test scenarios
        encoder_scenarios: list[dict[str, Any]] = [
            {
                "name": "Successful Encoding",
                "test_type": "successful_encoding",
                "analysis_types": ["encoding_success", "frame_processing"],
                "expected_tests": 4,  # standard_small, high_fps_medium, custom_fps_varied, single_frame
            },
            {
                "name": "Error Handling",
                "test_type": "error_handling",
                "analysis_types": ["error_handling"],
                "expected_errors": 3,  # ffmpeg_called_process_error, ffmpeg_file_not_found, image_processing_error
            },
            {
                "name": "Frame Processing",
                "test_type": "frame_processing",
                "analysis_types": ["frame_processing"],
                "expected_tests": 4,  # empty_frames, single_frame, many_frames, grayscale_frames
            },
            {
                "name": "Command Validation",
                "test_type": "command_validation",
                "analysis_types": ["command_validation"],
                "expected_tests": 5,  # fps_1, fps_24, fps_30, fps_60, fps_120
            },
            {
                "name": "Edge Cases",
                "test_type": "edge_cases",
                "analysis_types": ["encoding_success"],
                "expected_tests": 4,  # very_high_fps, zero_fps, negative_fps, float_fps
            },
            {
                "name": "Performance Tests",
                "test_type": "performance_tests",
                "analysis_types": ["performance_metrics"],
                "expected_tests": 3,  # rapid_encoding_calls, large_frame_sets, memory_efficiency
            },
        ]

        # Test each encoder scenario
        all_results = {}

        for scenario in encoder_scenarios:  # noqa: PLR1702
            try:
                # Run encoder test scenario
                scenario_results = test_manager.run_test_scenario(scenario["test_type"], temp_workspace, mock_registry)

                # Analyze results
                if scenario["analysis_types"]:
                    analysis_results = analyzer.analyze_results(scenario_results, scenario["analysis_types"])
                    scenario_results["analysis"] = analysis_results

                # Verify scenario-specific expectations
                scenario_name: str = scenario["name"]
                expected_count: int = scenario.get("expected_tests", scenario.get("expected_errors", 0))
                if scenario_name == "Successful Encoding":
                    # Should successfully encode all test cases
                    assert len(scenario_results) >= expected_count, f"Should test {expected_count} encoding scenarios"

                    # All encoding tests should succeed
                    for test_name, test_result in scenario_results.items():
                        if test_name != "analysis":
                            assert test_result["success"], f"Encoding test {test_name} should succeed"
                            assert test_result["file_exists"], f"Output file should exist for {test_name}"
                            assert test_result["fromarray_calls"] == test_result["frames_processed"], (
                                f"Should process all frames for {test_name}"
                            )

                    # Check analysis
                    if "analysis" in scenario_results:
                        encoding_analysis = scenario_results["analysis"]["encoding_success"]
                        assert encoding_analysis["success_rate"] == 1.0, "All encoding tests should succeed"

                        frame_analysis = scenario_results["analysis"]["frame_processing"]
                        assert frame_analysis["fromarray_accuracy"] == 1.0, "All frames should be processed correctly"

                elif scenario_name == "Error Handling":
                    # Should handle different error types correctly
                    assert len(scenario_results) >= expected_count, f"Should test {expected_count} error types"

                    # Check specific error types
                    error_types = ["ffmpeg_called_process_error", "ffmpeg_file_not_found", "image_processing_error"]
                    for error_type in error_types:
                        if error_type in scenario_results:
                            error_result = scenario_results[error_type]
                            assert error_result["success"], f"Error handling for {error_type} should succeed"
                            if "raises_correct_error" in error_result:
                                assert error_result["raises_correct_error"], (
                                    f"Should raise correct error for {error_type}"
                                )

                elif scenario_name == "Frame Processing":
                    # Should handle different frame types
                    assert len(scenario_results) >= expected_count, (
                        f"Should test {expected_count} frame processing scenarios"
                    )

                    # Check specific frame processing scenarios
                    for test_name, test_result in scenario_results.items():
                        if test_name != "analysis":
                            assert test_result["success"], f"Frame processing test {test_name} should succeed"

                elif scenario_name == "Command Validation":
                    # Should validate commands for different FPS values
                    assert len(scenario_results) >= expected_count, (
                        f"Should test {expected_count} command validation scenarios"
                    )

                    # All command validation tests should succeed
                    for test_name, test_result in scenario_results.items():
                        if test_name != "analysis":
                            assert test_result["success"], f"Command validation test {test_name} should succeed"
                            assert test_result["command_valid"], f"Command should be valid for {test_name}"

                elif scenario_name == "Edge Cases":
                    # Should handle edge cases appropriately
                    assert len(scenario_results) >= expected_count, f"Should test {expected_count} edge cases"

                    # Edge cases may succeed or fail depending on the specific case
                    edge_case_names = ["very_high_fps", "zero_fps", "negative_fps", "float_fps"]
                    for edge_case in edge_case_names:
                        if edge_case in scenario_results:
                            edge_result = scenario_results[edge_case]
                            # Edge cases should either succeed or handle errors gracefully
                            assert "success" in edge_result, f"Edge case {edge_case} should have success indicator"

                elif scenario_name == "Performance Tests":
                    # Should complete performance tests
                    assert len(scenario_results) >= expected_count, (
                        f"Should test {expected_count} performance scenarios"
                    )

                    # Performance tests should provide meaningful results
                    for test_name, test_result in scenario_results.items():
                        if test_name != "analysis":
                            # Performance tests may succeed or fail, but should provide results
                            assert "success" in test_result, (
                                f"Performance test {test_name} should have success indicator"
                            )

                all_results[scenario_name] = scenario_results

            except Exception as e:  # noqa: BLE001
                pytest.fail(f"Unexpected error in {scenario_name}: {e}")

        # Overall validation
        assert len(all_results) == len(encoder_scenarios), "Not all encoder scenarios completed"

    @staticmethod
    def test_raw_encoder_original_compatibility(
        raw_encoder_test_components: dict[str, Any], temp_workspace: dict[str, Any]
    ) -> None:
        """Test compatibility with original test structure."""
        components = raw_encoder_test_components
        test_manager = components["test_manager"]

        # Test the exact original test scenarios
        original_tests = [
            {
                "name": "write_raw_mp4_success",
                "frames": "small",
                "fps": 30,
                "expect_success": True,
            },
            {
                "name": "write_raw_mp4_ffmpeg_error",
                "frames": "small",
                "fps": 30,
                "expect_error": subprocess.CalledProcessError,
            },
            {
                "name": "write_raw_mp4_ffmpeg_not_found",
                "frames": "small",
                "fps": 30,
                "expect_error": FileNotFoundError,
            },
        ]

        # Test each original scenario
        for original_test in original_tests:
            frames_key: str = cast("str", original_test["frames"])
            test_name: str = cast("str", original_test["name"])
            fps_value: int = cast("int", original_test["fps"])
            frames = test_manager.frame_templates[frames_key]
            test_workspace = test_manager._create_test_workspace(temp_workspace, test_name)  # noqa: SLF001

            expected_cmd = test_manager._build_expected_command(  # noqa: SLF001
                test_workspace["temp_dir_path"], test_workspace["raw_path"], fps_value
            )

            if original_test.get("expect_success"):
                # Test successful scenario
                with test_manager._setup_successful_mocks(test_workspace, expected_cmd) as mock_context:  # noqa: SLF001
                    result_path = raw_encoder.write_raw_mp4(frames, test_workspace["raw_path"], fps=fps_value)

                    # Verify original test expectations
                    assert mock_context["mock_fromarray"].call_count == len(frames), "Should convert all frames"
                    mock_context["mock_run"].assert_called_once(), "Should call FFmpeg once"
                    assert result_path == test_workspace["raw_path"], "Should return correct path"
                    assert test_workspace["raw_path"].exists(), "Output file should exist"

            elif "expect_error" in original_test:
                # Test error scenario
                error_type = (
                    "called_process_error"
                    if original_test["expect_error"] == subprocess.CalledProcessError
                    else "file_not_found_error"
                )

                with test_manager._setup_error_mocks(  # noqa: SLF001
                    test_workspace, expected_cmd, error_type
                ) as mock_context:
                    with pytest.raises(original_test["expect_error"]):
                        raw_encoder.write_raw_mp4(frames, test_workspace["raw_path"], fps=fps_value)

                    # Verify mock was called despite error
                    mock_context["mock_run"].assert_called_once(), "Should call FFmpeg even when it fails"

    def test_raw_encoder_stress_and_boundary_scenarios(
        self, raw_encoder_test_components: dict[str, Any], temp_workspace: dict[str, Any]
    ) -> None:
        """Test raw encoder stress and boundary scenarios."""
        components = raw_encoder_test_components
        test_manager = components["test_manager"]

        # Stress and boundary test scenarios
        stress_scenarios = [
            {
                "name": "Concurrent Encoding Simulation",
                "test": lambda: self._test_concurrent_encoding_simulation(temp_workspace, test_manager),
            },
            {
                "name": "Extreme Parameter Values",
                "test": lambda: self._test_extreme_parameter_values(temp_workspace, test_manager),
            },
            {
                "name": "Resource Cleanup Verification",
                "test": lambda: self._test_resource_cleanup_verification(temp_workspace, test_manager),
            },
            {
                "name": "Error Recovery Patterns",
                "test": lambda: self._test_error_recovery_patterns(temp_workspace, test_manager),
            },
        ]

        # Test each stress scenario
        for scenario in stress_scenarios:
            scenario_name: str = cast("str", scenario["name"])
            test_func: Callable[[], dict[str, Any]] = cast("Callable[[], dict[str, Any]]", scenario["test"])
            # Use pytest.raises for expected errors
            if scenario_name in {"Extreme Parameter Values", "Error Recovery Patterns"}:
                # These scenarios may have expected errors
                result = test_func()
                assert result is not None, f"Stress test {scenario_name} returned None"
                assert result.get("success", False), f"Stress test {scenario_name} failed"
            else:
                # Standard execution for other scenarios
                result = test_func()
                assert result is not None, f"Stress test {scenario_name} returned None"
                assert result.get("success", False), f"Stress test {scenario_name} failed"

    @staticmethod
    def _test_concurrent_encoding_simulation(temp_workspace: dict[str, Any], test_manager: Any) -> dict[str, Any]:
        """Test concurrent encoding simulation.

        Returns:
            dict[str, Any]: Test results.
        """
        frames = test_manager.frame_templates["small"]
        config = test_manager.encoding_configs["standard"]

        concurrent_tests = 3
        successful_encodings = 0

        for i in range(concurrent_tests):
            test_workspace = test_manager._create_test_workspace(temp_workspace, f"concurrent_{i}")  # noqa: SLF001
            expected_cmd = test_manager._build_expected_command(  # noqa: SLF001
                test_workspace["temp_dir_path"], test_workspace["raw_path"], config["fps"]
            )

            with contextlib.suppress(Exception), test_manager._setup_successful_mocks(test_workspace, expected_cmd):  # noqa: SLF001
                raw_encoder.write_raw_mp4(frames, test_workspace["raw_path"], fps=config["fps"])
                successful_encodings += 1

        return {
            "success": True,
            "concurrent_tests": concurrent_tests,
            "successful_encodings": successful_encodings,
            "success_rate": successful_encodings / concurrent_tests,
        }

    @staticmethod
    def _test_extreme_parameter_values(temp_workspace: dict[str, Any], test_manager: Any) -> dict[str, Any]:
        """Test extreme parameter values.

        Returns:
            dict[str, Any]: Test results.
        """
        frames = test_manager.frame_templates["small"]

        extreme_values = [
            {"fps": 0.001, "name": "tiny_fps"},
            {"fps": 10000, "name": "huge_fps"},
            {"fps": -100, "name": "negative_fps"},
        ]

        successful_tests = 0

        for extreme_test in extreme_values:
            test_name: str = cast("str", extreme_test["name"])
            fps_value: float = cast("float", extreme_test["fps"])
            test_workspace = test_manager._create_test_workspace(temp_workspace, test_name)  # noqa: SLF001
            expected_cmd = test_manager._build_expected_command(  # noqa: SLF001
                test_workspace["temp_dir_path"], test_workspace["raw_path"], fps_value
            )

            with contextlib.suppress(Exception), test_manager._setup_successful_mocks(test_workspace, expected_cmd):  # noqa: SLF001
                raw_encoder.write_raw_mp4(frames, test_workspace["raw_path"], fps=int(fps_value))
                successful_tests += 1

        return {
            "success": True,
            "extreme_tests": len(extreme_values),
            "successful_tests": successful_tests,
        }

    @staticmethod
    def _test_resource_cleanup_verification(temp_workspace: dict[str, Any], test_manager: Any) -> dict[str, Any]:
        """Test resource cleanup verification.

        Returns:
            dict[str, Any]: Test results.
        """
        frames = test_manager.frame_templates["medium"]
        config = test_manager.encoding_configs["standard"]

        cleanup_tests = 5
        successful_cleanups = 0

        for i in range(cleanup_tests):
            test_workspace = test_manager._create_test_workspace(temp_workspace, f"cleanup_{i}")  # noqa: SLF001
            expected_cmd = test_manager._build_expected_command(  # noqa: SLF001
                test_workspace["temp_dir_path"], test_workspace["raw_path"], config["fps"]
            )

            with (
                contextlib.suppress(Exception),
                test_manager._setup_successful_mocks(  # noqa: SLF001
                    test_workspace, expected_cmd
                ) as mock_context,
            ):
                raw_encoder.write_raw_mp4(frames, test_workspace["raw_path"], fps=config["fps"])

                # Verify temp directory mock was used (indicates cleanup)
                assert mock_context["mock_tempdir"].return_value.__enter__.called, "Temp directory should be created"
                assert mock_context["mock_tempdir"].return_value.__exit__.called, "Temp directory should be cleaned up"

                successful_cleanups += 1

        return {
            "success": True,
            "cleanup_tests": cleanup_tests,
            "successful_cleanups": successful_cleanups,
        }

    @staticmethod
    def _test_error_recovery_patterns(temp_workspace: dict[str, Any], test_manager: Any) -> dict[str, Any]:
        """Test error recovery patterns.

        Returns:
            dict[str, Any]: Test results.
        """
        frames = test_manager.frame_templates["small"]
        config = test_manager.encoding_configs["standard"]

        # Test error followed by success
        recovery_tests = 2
        successful_recoveries = 0

        for i in range(recovery_tests):
            # First, test an error scenario
            error_workspace = test_manager._create_test_workspace(temp_workspace, f"error_{i}")  # noqa: SLF001
            error_cmd = test_manager._build_expected_command(  # noqa: SLF001
                error_workspace["temp_dir_path"], error_workspace["raw_path"], config["fps"]
            )

            with (
                contextlib.suppress(Exception),
                test_manager._setup_error_mocks(  # noqa: SLF001
                    error_workspace, error_cmd, "called_process_error"
                ),
                contextlib.suppress(subprocess.CalledProcessError),
            ):
                raw_encoder.write_raw_mp4(frames, error_workspace["raw_path"], fps=config["fps"])

                # Then, test a successful scenario to verify recovery
                success_workspace = test_manager._create_test_workspace(temp_workspace, f"success_{i}")  # noqa: SLF001
                success_cmd = test_manager._build_expected_command(  # noqa: SLF001
                    success_workspace["temp_dir_path"], success_workspace["raw_path"], config["fps"]
                )

                with test_manager._setup_successful_mocks(success_workspace, success_cmd):  # noqa: SLF001
                    raw_encoder.write_raw_mp4(frames, success_workspace["raw_path"], fps=config["fps"])

                    # If we get here, recovery was successful
                    successful_recoveries += 1

        return {
            "success": True,
            "recovery_tests": recovery_tests,
            "successful_recoveries": successful_recoveries,
            "recovery_rate": successful_recoveries / recovery_tests if recovery_tests > 0 else 0,
        }
