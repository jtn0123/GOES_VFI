"""
Optimized integration tests for pipeline functionality with maintained coverage.

This v2 version maintains all test scenarios while optimizing through:
- Shared fixtures for expensive setup operations
- Combined pipeline testing scenarios
- Batch validation of processing workflows
- Enhanced mock and subprocess handling
"""

import os
import pathlib
import subprocess  # noqa: S404
import time
from typing import Any, Never
from unittest.mock import MagicMock, patch

from PIL import Image
import psutil
import pytest

from goesvfi.pipeline.image_loader import ImageLoader
from goesvfi.pipeline.image_processing_interfaces import ImageData
from goesvfi.pipeline.run_vfi import run_vfi
from goesvfi.utils.rife_analyzer import RifeCapabilityDetector


class TestPipelineOptimizedV2:
    """Optimized pipeline integration tests with full coverage."""

    @pytest.fixture(scope="class")
    @staticmethod
    def pipeline_test_constants() -> dict[str, Any]:
        """Shared constants for pipeline testing.

        Returns:
            dict[str, Any]: Dictionary containing pipeline test constants.
        """
        return {
            "default_img_size": (64, 32),
            "default_fps": 30,
            "default_intermediate_frames": 1,
            "mock_rife_exe": pathlib.Path("/mock/rife-cli"),
            "mock_ffmpeg_exe": "ffmpeg",
        }

    @pytest.fixture(scope="class")
    @staticmethod
    def comprehensive_mock_suite() -> dict[str, Any]:  # noqa: C901
        """Create comprehensive mock suite for pipeline testing.

        Returns:
            dict[str, Any]: Dictionary containing mock managers for different testing scenarios.
        """

        # Enhanced Mock Popen Manager
        class MockPopenManager:
            """Manage Popen mocks with different scenarios."""

            def __init__(self) -> None:
                self.scenarios = {
                    "success": MockPopenManager._create_success_mock,
                    "failure": MockPopenManager._create_failure_mock,
                    "timeout": MockPopenManager._create_timeout_mock,
                    "partial_output": MockPopenManager._create_partial_output_mock,
                }
                self.active_scenario = "success"

            @staticmethod
            def _create_success_mock() -> MagicMock:
                mock_process = MagicMock()
                mock_process.stdin = MagicMock()
                mock_process.stdout = MagicMock()
                mock_process.stderr = MagicMock()
                mock_process.wait.return_value = 0
                mock_process.poll.return_value = None
                mock_process.returncode = 0
                mock_process.communicate.return_value = (b"success output", b"")
                return mock_process

            @staticmethod
            def _create_failure_mock() -> MagicMock:
                mock_process = MagicMock()
                mock_process.wait.return_value = 1
                mock_process.poll.return_value = 1
                mock_process.returncode = 1
                mock_process.communicate.return_value = (b"", b"error output")
                return mock_process

            @staticmethod
            def _create_timeout_mock() -> MagicMock:
                mock_process = MagicMock()
                mock_process.wait.side_effect = subprocess.TimeoutExpired("cmd", 30)
                mock_process.poll.return_value = None
                return mock_process

            @staticmethod
            def _create_partial_output_mock() -> MagicMock:
                mock_process = MagicMock()
                mock_process.wait.return_value = 0
                mock_process.returncode = 0
                # Simulate partial output during processing
                mock_process.communicate.return_value = (b"partial output", b"warning")
                return mock_process

            def get_mock(self, scenario: str = "success") -> MagicMock:
                return self.scenarios[scenario]()

        # Enhanced Mock Run Manager
        class MockRunManager:
            """Manage subprocess.run mocks with different scenarios."""

            def __init__(self) -> None:
                self.scenarios = {
                    "success": MagicMock(returncode=0, stdout="", stderr=""),
                    "failure": MagicMock(returncode=1, stdout="", stderr="error"),
                    "timeout": MagicMock(side_effect=subprocess.TimeoutExpired("cmd", 30)),
                    "file_not_found": MagicMock(side_effect=FileNotFoundError("Command not found")),
                }

            def get_mock(self, scenario: str = "success") -> MagicMock:
                return self.scenarios[scenario]

        # Enhanced RIFE Capabilities Manager
        class RifeCapabilitiesManager:
            """Manage RIFE capabilities for different testing scenarios."""

            def __init__(self) -> None:
                self.capability_sets = {
                    "full": {
                        "supports_tiling": True,
                        "supports_uhd": True,
                        "supports_tta_spatial": True,
                        "supports_tta_temporal": True,
                        "supports_thread_spec": True,
                        "supports_model_path": True,
                        "supports_timestep": True,
                        "supports_gpu_id": True,
                    },
                    "limited": {
                        "supports_tiling": True,
                        "supports_uhd": False,
                        "supports_tta_spatial": False,
                        "supports_tta_temporal": False,
                        "supports_thread_spec": True,
                        "supports_model_path": True,
                        "supports_timestep": False,
                        "supports_gpu_id": False,
                    },
                    "minimal": {
                        "supports_tiling": False,
                        "supports_uhd": False,
                        "supports_tta_spatial": False,
                        "supports_tta_temporal": False,
                        "supports_thread_spec": False,
                        "supports_model_path": True,
                        "supports_timestep": False,
                        "supports_gpu_id": False,
                    },
                }

            def create_mock_detector(self, capability_set: str = "full") -> MagicMock:
                capabilities = self.capability_sets[capability_set]
                mock_instance = MagicMock(spec=RifeCapabilityDetector)

                for cap, value in capabilities.items():
                    setattr(mock_instance, cap, MagicMock(return_value=value))

                return mock_instance

        # Enhanced Sanchez Mock Manager
        class SanchezMockManager:
            """Manage Sanchez mocking for different scenarios."""

            def __init__(self) -> None:
                self.scenarios = {
                    "success": SanchezMockManager._create_success_mock,
                    "failure": SanchezMockManager._create_failure_mock,
                    "file_exists": SanchezMockManager._create_file_exists_mock,
                    "permission_error": SanchezMockManager._create_permission_error_mock,
                }

            @staticmethod
            def _create_success_mock(output_path: pathlib.Path) -> Any:
                def mock_colourise(*args: Any, **kwargs: Any) -> int:
                    output_path.write_bytes(b"mock sanchez output")
                    return 0

                return mock_colourise

            @staticmethod
            def _create_failure_mock(output_path: pathlib.Path) -> Any:  # noqa: ARG004
                def mock_colourise(*args: Any, **kwargs: Any) -> Never:
                    msg = "Sanchez processing failed"
                    raise RuntimeError(msg)

                return mock_colourise

            @staticmethod
            def _create_file_exists_mock(output_path: pathlib.Path) -> Any:
                def mock_colourise(*args: Any, **kwargs: Any) -> int:
                    if output_path.exists():
                        msg = f"Output file {output_path} already exists"
                        raise FileExistsError(msg)
                    output_path.write_bytes(b"mock sanchez output")
                    return 0

                return mock_colourise

            @staticmethod
            def _create_permission_error_mock(output_path: pathlib.Path) -> Any:  # noqa: ARG004
                def mock_colourise(*args: Any, **kwargs: Any) -> Never:
                    msg = "Permission denied writing output file"
                    raise PermissionError(msg)

                return mock_colourise

            def get_mock_factory(self, scenario: str = "success") -> Any:
                return self.scenarios[scenario]

        return {
            "popen_manager": MockPopenManager(),
            "run_manager": MockRunManager(),
            "rife_manager": RifeCapabilitiesManager(),
            "sanchez_manager": SanchezMockManager(),
        }

    @pytest.fixture()
    @staticmethod
    def temp_workspace(tmp_path: pathlib.Path) -> dict[str, Any]:
        """Create temporary workspace with test images.

        Returns:
            dict[str, Any]: Dictionary containing paths to workspace directories and files.
        """
        input_dir = tmp_path / "input"
        output_dir = tmp_path / "output"
        input_dir.mkdir()
        output_dir.mkdir()

        # Create various test images
        image_configs = [
            ("frame_001.png", (64, 32), (255, 0, 0)),
            ("frame_002.png", (64, 32), (0, 255, 0)),
            ("frame_003.png", (64, 32), (0, 0, 255)),
            ("frame_004.png", (64, 32), (255, 255, 0)),
            ("frame_005.png", (64, 32), (255, 0, 255)),
        ]

        image_paths = []
        for filename, size, color in image_configs:
            img = Image.new("RGB", size, color)
            img_path = input_dir / filename
            img.save(img_path)
            image_paths.append(img_path)

        return {
            "input_dir": input_dir,
            "output_dir": output_dir,
            "image_paths": image_paths,
            "output_file": output_dir / "output.mp4",
        }

    @staticmethod
    def test_pipeline_comprehensive_scenarios(
        temp_workspace: dict[str, Any],
        comprehensive_mock_suite: dict[str, Any],
        pipeline_test_constants: dict[str, Any],  # noqa: ARG004
    ) -> None:
        """Test comprehensive pipeline scenarios with different configurations."""
        workspace = temp_workspace
        mock_suite = comprehensive_mock_suite

        # Define comprehensive test scenarios
        pipeline_scenarios = [
            {
                "name": "Basic RIFE Processing",
                "encoder": "RIFE",
                "fps": 30,
                "mid_count": 1,
                "sanchez": False,
                "crop_rect": None,
                "rife_capabilities": "full",
                "expected_success": True,
            },
            {
                "name": "RIFE with Sanchez Enhancement",
                "encoder": "RIFE",
                "fps": 60,
                "mid_count": 2,
                "sanchez": True,
                "crop_rect": None,
                "rife_capabilities": "full",
                "expected_success": True,
            },
            {
                "name": "RIFE with Cropping",
                "encoder": "RIFE",
                "fps": 30,
                "mid_count": 1,
                "sanchez": False,
                "crop_rect": (10, 10, 50, 20),
                "rife_capabilities": "full",
                "expected_success": True,
            },
            {
                "name": "FFmpeg Fallback",
                "encoder": "FFmpeg",
                "fps": 24,
                "mid_count": 3,
                "sanchez": False,
                "crop_rect": None,
                "rife_capabilities": "minimal",
                "expected_success": True,
            },
            {
                "name": "Limited RIFE Capabilities",
                "encoder": "RIFE",
                "fps": 30,
                "mid_count": 1,
                "sanchez": False,
                "crop_rect": None,
                "rife_capabilities": "limited",
                "expected_success": True,
            },
        ]

        # Test each scenario
        for scenario in pipeline_scenarios:
            with (
                patch("goesvfi.pipeline.run_vfi.subprocess.Popen") as mock_popen,
                patch("goesvfi.pipeline.run_vfi.subprocess.run") as mock_run,
                patch("goesvfi.pipeline.run_vfi.RifeCapabilityDetector") as mock_detector_class,
                patch("goesvfi.pipeline.run_vfi.colourise") as mock_colourise,
            ):
                # Configure mocks for this scenario
                mock_popen.return_value = mock_suite["popen_manager"].get_mock("success")
                mock_run.return_value = mock_suite["run_manager"].get_mock("success")

                # Configure RIFE capabilities
                mock_detector = mock_suite["rife_manager"].create_mock_detector(scenario["rife_capabilities"])
                mock_detector_class.return_value = mock_detector

                # Configure Sanchez if needed
                if scenario["sanchez"]:
                    mock_factory = mock_suite["sanchez_manager"].get_mock_factory("success")
                    mock_colourise.side_effect = mock_factory(workspace["output_dir"] / "sanchez_output.png")

                # Create output file mock
                def create_output_file(*args: Any, **kwargs: Any) -> MagicMock:
                    workspace["output_file"].write_bytes(b"mock video content")
                    return mock_popen.return_value

                mock_popen.side_effect = create_output_file

                # Run pipeline
                try:
                    result_gen = run_vfi(
                        folder=workspace["input_dir"],
                        output_mp4_path=workspace["output_file"],
                        fps=scenario["fps"],
                        intermediate_frames=scenario["mid_count"],
                        encoder=scenario["encoder"],
                        crop_rect=scenario["crop_rect"],
                        sanchez=scenario["sanchez"],
                        skip_model=True,  # Skip model for testing
                        debug_mode=True,
                    )

                    # Consume generator
                    results = list(result_gen)

                    if scenario["expected_success"]:
                        assert len(results) > 0, f"No results from {scenario['name']}"
                        # Verify mocks were called appropriately
                        if scenario["encoder"] == "RIFE":
                            mock_run.assert_called()
                        mock_popen.assert_called()

                        if scenario["sanchez"]:
                            mock_colourise.assert_called()

                        # Verify output file exists (mocked)
                        assert workspace["output_file"].exists(), f"Output file missing for {scenario['name']}"

                except Exception as e:  # noqa: BLE001
                    if scenario["expected_success"]:
                        pytest.fail(f"Unexpected failure in {scenario['name']}: {e}")
                    # Expected failure scenarios would be handled here

    @staticmethod
    def test_pipeline_error_handling_comprehensive(
        temp_workspace: dict[str, Any],
        comprehensive_mock_suite: dict[str, Any],
        pipeline_test_constants: dict[str, Any],  # noqa: ARG004
    ) -> None:
        """Test comprehensive error handling in pipeline scenarios."""
        workspace = temp_workspace
        mock_suite = comprehensive_mock_suite

        # Define error scenarios
        error_scenarios = [
            {
                "name": "RIFE Execution Failure",
                "mock_config": {
                    "popen": "success",
                    "run": "failure",
                    "rife_caps": "full",
                    "sanchez": "success",
                },
                "encoder": "RIFE",
                "should_raise": True,
            },
            {
                "name": "FFmpeg Process Failure",
                "mock_config": {
                    "popen": "failure",
                    "run": "success",
                    "rife_caps": "full",
                    "sanchez": "success",
                },
                "encoder": "RIFE",
                "should_raise": True,
            },
            {
                "name": "Sanchez Processing Failure",
                "mock_config": {
                    "popen": "success",
                    "run": "success",
                    "rife_caps": "full",
                    "sanchez": "failure",
                },
                "encoder": "RIFE",
                "sanchez": True,
                "should_raise": True,
            },
            {
                "name": "Process Timeout",
                "mock_config": {
                    "popen": "timeout",
                    "run": "success",
                    "rife_caps": "full",
                    "sanchez": "success",
                },
                "encoder": "RIFE",
                "should_raise": True,
            },
            {
                "name": "Command Not Found",
                "mock_config": {
                    "popen": "success",
                    "run": "file_not_found",
                    "rife_caps": "full",
                    "sanchez": "success",
                },
                "encoder": "RIFE",
                "should_raise": True,
            },
        ]

        # Test each error scenario
        for scenario in error_scenarios:
            with (
                patch("goesvfi.pipeline.run_vfi.subprocess.Popen") as mock_popen,
                patch("goesvfi.pipeline.run_vfi.subprocess.run") as mock_run,
                patch("goesvfi.pipeline.run_vfi.RifeCapabilityDetector") as mock_detector_class,
                patch("goesvfi.pipeline.run_vfi.colourise") as mock_colourise,
            ):
                # Configure mocks based on scenario
                config = scenario["mock_config"]

                mock_popen.return_value = mock_suite["popen_manager"].get_mock(config["popen"])
                mock_run.return_value = mock_suite["run_manager"].get_mock(config["run"])

                mock_detector = mock_suite["rife_manager"].create_mock_detector(config["rife_caps"])
                mock_detector_class.return_value = mock_detector

                if scenario.get("sanchez"):
                    mock_factory = mock_suite["sanchez_manager"].get_mock_factory(config["sanchez"])
                    mock_colourise.side_effect = mock_factory(workspace["output_dir"] / "sanchez_output.png")

                # Run pipeline and expect error
                if scenario["should_raise"]:
                    with pytest.raises((  # noqa: PT012
                        RuntimeError,
                        subprocess.CalledProcessError,
                        FileNotFoundError,
                        subprocess.TimeoutExpired,
                    )):
                        result_gen = run_vfi(
                            folder=workspace["input_dir"],
                            output_mp4_path=workspace["output_file"],
                            fps=30,
                            intermediate_frames=1,
                            encoder=scenario["encoder"],
                            sanchez=scenario.get("sanchez", False),
                            skip_model=True,
                            debug_mode=True,
                        )
                        list(result_gen)  # Consume generator to trigger execution
                else:
                    # Should not raise
                    result_gen = run_vfi(
                        folder=workspace["input_dir"],
                        output_mp4_path=workspace["output_file"],
                        fps=30,
                        intermediate_frames=1,
                        encoder=scenario["encoder"],
                        sanchez=scenario.get("sanchez", False),
                        skip_model=True,
                        debug_mode=True,
                    )
                    results = list(result_gen)
                    assert len(results) >= 0

    @staticmethod
    def test_image_processing_workflow_comprehensive(  # noqa: C901, PLR0914
        temp_workspace: dict[str, Any],
        comprehensive_mock_suite: dict[str, Any],  # noqa: ARG004
    ) -> None:
        """Test comprehensive image processing workflows within pipeline."""
        workspace = temp_workspace

        # Define image processing scenarios
        processing_scenarios = [
            {
                "name": "Basic Image Loading",
                "test_type": "loader",
                "image_formats": [".png", ".jpg", ".jpeg"],
                "expected_count": 5,
            },
            {
                "name": "Image Size Validation",
                "test_type": "size_validation",
                "min_size": (32, 16),
                "max_size": (1920, 1080),
            },
            {
                "name": "Image Format Conversion",
                "test_type": "format_conversion",
                "input_format": "RGB",
                "output_format": "RGB",
            },
            {
                "name": "Cropping Functionality",
                "test_type": "cropping",
                "crop_regions": [(0, 0, 32, 16), (16, 8, 48, 24), (10, 5, 54, 27)],
            },
        ]

        # Test each processing scenario
        for scenario in processing_scenarios:
            if scenario["test_type"] == "loader":
                # Test image loader
                loader = ImageLoader()
                loaded_images = loader.load_images_from_directory(
                    workspace["input_dir"], supported_formats=scenario["image_formats"]
                )

                assert len(loaded_images) == scenario["expected_count"], (
                    f"Expected {scenario['expected_count']} images, got {len(loaded_images)}"
                )

                # Verify each loaded image
                for img_data in loaded_images:
                    assert isinstance(img_data, ImageData)
                    assert img_data.array is not None
                    assert img_data.path.exists()

            elif scenario["test_type"] == "size_validation":
                # Test size validation
                loader = ImageLoader()
                images = loader.load_images_from_directory(workspace["input_dir"])

                for img_data in images:
                    height, width = img_data.array.shape[:2]
                    min_w, min_h = scenario["min_size"]
                    max_w, max_h = scenario["max_size"]

                    assert width >= min_w, f"Image width {width} below minimum {min_w}"
                    assert height >= min_h, f"Image height {height} below minimum {min_h}"
                    assert width <= max_w, f"Image width {width} above maximum {max_w}"
                    assert height <= max_h, f"Image height {height} above maximum {max_h}"

            elif scenario["test_type"] == "format_conversion":
                # Test format conversion
                loader = ImageLoader()
                images = loader.load_images_from_directory(workspace["input_dir"])

                for img_data in images:
                    # Verify RGB format
                    if len(img_data.array.shape) == 3:
                        assert img_data.array.shape[2] == 3, "Expected RGB format (3 channels)"

            elif scenario["test_type"] == "cropping":
                # Test cropping functionality
                loader = ImageLoader()
                images = loader.load_images_from_directory(workspace["input_dir"])

                for crop_region in scenario["crop_regions"]:
                    x, y, w, h = crop_region

                    for img_data in images:
                        orig_height, orig_width = img_data.array.shape[:2]

                        # Verify crop region is valid
                        if x + w <= orig_width and y + h <= orig_height:
                            cropped = img_data.array[y : y + h, x : x + w]
                            assert cropped.shape[:2] == (h, w), (
                                f"Cropped size mismatch: expected {(h, w)}, got {cropped.shape[:2]}"
                            )

    @staticmethod
    def test_pipeline_performance_and_optimization(
        temp_workspace: dict[str, Any],
        comprehensive_mock_suite: dict[str, Any],
    ) -> None:
        """Test pipeline performance characteristics and optimizations."""
        workspace = temp_workspace
        mock_suite = comprehensive_mock_suite

        # Performance test scenarios
        performance_scenarios = [
            {
                "name": "Memory Usage Tracking",
                "test_type": "memory",
                "max_memory_increase_mb": 100,
            },
            {
                "name": "Processing Time Validation",
                "test_type": "timing",
                "max_processing_time_sec": 5.0,
            },
            {
                "name": "Resource Cleanup",
                "test_type": "cleanup",
                "check_temp_files": True,
            },
            {
                "name": "Concurrent Processing",
                "test_type": "concurrency",
                "max_workers": 4,
            },
        ]

        # Test each performance scenario
        for scenario in performance_scenarios:
            if scenario["test_type"] == "memory":
                # Monitor memory usage
                process = psutil.Process(os.getpid())
                initial_memory = process.memory_info().rss / 1024 / 1024  # MB

                with (
                    patch("goesvfi.pipeline.run_vfi.subprocess.Popen") as mock_popen,
                    patch("goesvfi.pipeline.run_vfi.subprocess.run") as mock_run,
                    patch("goesvfi.pipeline.run_vfi.RifeCapabilityDetector") as mock_detector_class,
                ):
                    # Configure mocks
                    mock_popen.return_value = mock_suite["popen_manager"].get_mock("success")
                    mock_run.return_value = mock_suite["run_manager"].get_mock("success")
                    mock_detector = mock_suite["rife_manager"].create_mock_detector("full")
                    mock_detector_class.return_value = mock_detector

                    # Create output file
                    def create_output(*args: Any, **kwargs: Any) -> MagicMock:
                        workspace["output_file"].write_bytes(b"mock output")
                        return mock_popen.return_value

                    mock_popen.side_effect = create_output

                    # Run pipeline
                    result_gen = run_vfi(
                        folder=workspace["input_dir"],
                        output_mp4_path=workspace["output_file"],
                        fps=30,
                        intermediate_frames=1,
                        encoder="RIFE",
                        skip_model=True,
                        debug_mode=True,
                    )
                    list(result_gen)

                final_memory = process.memory_info().rss / 1024 / 1024  # MB
                memory_increase = final_memory - initial_memory

                assert memory_increase < scenario["max_memory_increase_mb"], (
                    f"Memory increase {memory_increase:.1f}MB exceeds limit {scenario['max_memory_increase_mb']}MB"
                )

            elif scenario["test_type"] == "timing":
                # Monitor processing time
                with (
                    patch("goesvfi.pipeline.run_vfi.subprocess.Popen") as mock_popen,
                    patch("goesvfi.pipeline.run_vfi.subprocess.run") as mock_run,
                    patch("goesvfi.pipeline.run_vfi.RifeCapabilityDetector") as mock_detector_class,
                ):
                    # Configure fast mocks
                    mock_popen.return_value = mock_suite["popen_manager"].get_mock("success")
                    mock_run.return_value = mock_suite["run_manager"].get_mock("success")
                    mock_detector = mock_suite["rife_manager"].create_mock_detector("full")
                    mock_detector_class.return_value = mock_detector

                    def quick_output(*args: Any, **kwargs: Any) -> MagicMock:
                        workspace["output_file"].write_bytes(b"quick output")
                        return mock_popen.return_value

                    mock_popen.side_effect = quick_output

                    # Time the pipeline
                    start_time = time.perf_counter()

                    result_gen = run_vfi(
                        folder=workspace["input_dir"],
                        output_mp4_path=workspace["output_file"],
                        fps=30,
                        intermediate_frames=1,
                        encoder="RIFE",
                        skip_model=True,
                        debug_mode=True,
                    )
                    list(result_gen)

                    processing_time = time.perf_counter() - start_time

                assert processing_time < scenario["max_processing_time_sec"], (
                    f"Processing time {processing_time:.2f}s exceeds limit {scenario['max_processing_time_sec']}s"
                )

            elif scenario["test_type"] == "cleanup":
                # Check for proper resource cleanup
                initial_temp_files = len(list(workspace["output_dir"].glob("*"))) + len(
                    list(workspace["input_dir"].glob("*"))
                )

                with (
                    patch("goesvfi.pipeline.run_vfi.subprocess.Popen") as mock_popen,
                    patch("goesvfi.pipeline.run_vfi.subprocess.run") as mock_run,
                    patch("goesvfi.pipeline.run_vfi.RifeCapabilityDetector") as mock_detector_class,
                ):
                    mock_popen.return_value = mock_suite["popen_manager"].get_mock("success")
                    mock_run.return_value = mock_suite["run_manager"].get_mock("success")
                    mock_detector = mock_suite["rife_manager"].create_mock_detector("full")
                    mock_detector_class.return_value = mock_detector

                    def cleanup_output(*args: Any, **kwargs: Any) -> MagicMock:
                        workspace["output_file"].write_bytes(b"cleanup test")
                        return mock_popen.return_value

                    mock_popen.side_effect = cleanup_output

                    result_gen = run_vfi(
                        folder=workspace["input_dir"],
                        output_mp4_path=workspace["output_file"],
                        fps=30,
                        intermediate_frames=1,
                        encoder="RIFE",
                        skip_model=True,
                        debug_mode=True,
                    )
                    list(result_gen)

                # Check temp files haven't accumulated excessively
                final_temp_files = len(list(workspace["output_dir"].glob("*"))) + len(
                    list(workspace["input_dir"].glob("*"))
                )
                temp_file_increase = final_temp_files - initial_temp_files

                # Allow for the output file itself
                assert temp_file_increase <= 1, f"Too many temp files created: {temp_file_increase}"
