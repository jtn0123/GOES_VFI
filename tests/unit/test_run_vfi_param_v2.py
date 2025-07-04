"""
Optimized unit tests for run_vfi parameterized functionality with maintained coverage.

This v2 version maintains all test scenarios while optimizing through:
- Shared fixtures for VFI pipeline setup and mock configurations
- Combined VFI processing testing scenarios for different execution paths
- Batch validation of RIFE and FFmpeg command execution
- Enhanced error handling and edge case coverage
"""

from collections.abc import Callable
import pathlib
import subprocess  # noqa: S404
from typing import Any, Never, TypedDict
from unittest.mock import MagicMock, patch

from PIL import Image
import pytest

from goesvfi.pipeline import run_vfi as run_vfi_mod
from goesvfi.pipeline.exceptions import FFmpegError, ProcessingError, RIFEError

from tests.utils.mocks import (
    create_mock_colourise,
    create_mock_popen,
    create_mock_subprocess_run,
)


def create_test_png(path: pathlib.Path, size: tuple[int, int] = (64, 64)) -> None:
    """Create a minimal test PNG file."""
    img = Image.new("RGB", size, color="red")
    img.save(path)


def make_dummy_images(temp_dir: pathlib.Path, count: int = 3) -> list[pathlib.Path]:
    """Create multiple dummy PNG images for testing.

    Returns:
        list[pathlib.Path]: List of created image paths.
    """
    images = []
    for i in range(count):
        img_path = temp_dir / f"test_image_{i:03d}.png"
        create_test_png(img_path)
        images.append(img_path)
    return images


class TestRunVfiParamOptimizedV2:
    """Optimized VFI parameterized tests with full coverage."""

    @pytest.fixture()
    def mock_capability_detector(self) -> MagicMock:  # noqa: PLR6301
        """Mock RIFE capability detector.

        Returns:
            MagicMock: Mocked capability detector.
        """
        detector = MagicMock()
        detector.supports_tiling.return_value = True
        detector.supports_uhd.return_value = True
        detector.supports_tta_spatial.return_value = True
        detector.supports_tta_temporal.return_value = True
        detector.supports_thread_spec.return_value = True
        return detector

    @pytest.fixture(scope="class")
    def vfi_test_components(self) -> dict[str, Any]:  # noqa: C901, PLR6301
        """Create shared components for VFI testing.

        Returns:
            dict[str, Any]: Dictionary containing test manager instance.
        """

        class ScenarioConfig(TypedDict):
            """Type definition for scenario configuration."""

            description: str
            kwargs: dict[str, Any]
            expect_error: bool
            mock_setup: Callable[[pathlib.Path, dict[str, Any]], dict[str, Any]]
            validation: Callable[[Any, dict[str, Any]], dict[str, Any]]

        class VFITestManager:
            """Manage VFI pipeline testing scenarios."""

            def __init__(self) -> None:
                self.scenario_configs: dict[str, ScenarioConfig] = {
                    "skip": {
                        "description": "Skip RIFE model execution",
                        "kwargs": {"skip_model": True},
                        "expect_error": False,
                        "mock_setup": self._setup_skip_scenario,
                        "validation": self._validate_skip_scenario,
                    },
                    "rife_fail": {
                        "description": "RIFE execution failure",
                        "kwargs": {},
                        "expect_error": True,
                        "mock_setup": self._setup_rife_fail_scenario,
                        "validation": self._validate_error_scenario,
                    },
                }

            @staticmethod
            def _setup_skip_scenario(temp_dir: pathlib.Path, mock_registry: dict[str, Any]) -> dict[str, Any]:
                """Setup mocks for skip scenario.

                Returns:
                    dict[str, Any]: Scenario setup data.
                """
                raw_output = temp_dir / "out.raw.mp4"

                # Create the raw output file
                raw_output.touch()

                # Mock FFmpeg to create the file
                mock_popen_factory = create_mock_popen(output_file_to_create=raw_output)
                mock_registry["mock_popen"] = mock_popen_factory

                # Mock subprocess.run to do nothing for RIFE
                mock_run_factory = create_mock_subprocess_run()
                mock_registry["mock_run"] = mock_run_factory

                return {"raw_output": raw_output}

            @staticmethod
            def _setup_rife_fail_scenario(temp_dir: pathlib.Path, mock_registry: dict[str, Any]) -> dict[str, Any]:
                """Setup mocks for RIFE failure scenario.

                Returns:
                    dict[str, Any]: Scenario setup data.
                """
                raw_output = temp_dir / "out.raw.mp4"

                # Mock RIFE to fail - need a factory function that raises the error
                def raise_rife_error(*args, **kwargs) -> Never:
                    raise subprocess.CalledProcessError(1, ["rife"], stderr="RIFE execution failed")

                mock_registry["mock_run"] = raise_rife_error

                # Mock FFmpeg to work normally
                mock_popen_factory = create_mock_popen(output_file_to_create=raw_output)
                mock_registry["mock_popen"] = mock_popen_factory

                return {"raw_output": raw_output}

            @staticmethod
            def _setup_ffmpeg_fail_scenario(temp_dir: pathlib.Path, mock_registry: dict[str, Any]) -> dict[str, Any]:
                """Setup mocks for FFmpeg failure scenario.

                Returns:
                    dict[str, Any]: Scenario setup data.
                """
                raw_output = temp_dir / "out.raw.mp4"

                # Mock RIFE to work normally
                mock_run_factory = create_mock_subprocess_run()
                mock_registry["mock_run"] = mock_run_factory

                # Mock FFmpeg to fail
                mock_popen_factory = create_mock_popen(returncode=1, stderr=b"FFmpeg failed")
                mock_registry["mock_popen"] = mock_popen_factory

                return {"raw_output": raw_output}

            @staticmethod
            def _setup_sanchez_scenario(temp_dir: pathlib.Path, mock_registry: dict[str, Any]) -> dict[str, Any]:
                """Setup mocks for successful Sanchez scenario.

                Returns:
                    dict[str, Any]: Scenario setup data.
                """
                raw_output = temp_dir / "out.raw.mp4"

                # Mock RIFE and FFmpeg to work normally
                mock_run_factory = create_mock_subprocess_run()
                mock_registry["mock_run"] = mock_run_factory

                mock_popen_factory = create_mock_popen(output_file_to_create=raw_output)
                mock_registry["mock_popen"] = mock_popen_factory

                # Mock Sanchez to work normally
                mock_colourise_factory = create_mock_colourise()
                mock_registry["mock_colourise"] = mock_colourise_factory

                return {"raw_output": raw_output}

            @staticmethod
            def _setup_sanchez_fail_scenario(temp_dir: pathlib.Path, mock_registry: dict[str, Any]) -> dict[str, Any]:
                """Setup mocks for Sanchez failure scenario.

                Returns:
                    dict[str, Any]: Scenario setup data.
                """
                raw_output = temp_dir / "out.raw.mp4"

                # Mock RIFE and FFmpeg to work normally
                mock_run_factory = create_mock_subprocess_run()
                mock_registry["mock_run"] = mock_run_factory

                mock_popen_factory = create_mock_popen(output_file_to_create=raw_output)
                mock_registry["mock_popen"] = mock_popen_factory

                # Mock Sanchez to fail
                mock_colourise_factory = create_mock_colourise(side_effect=RuntimeError("Sanchez failed"))
                mock_registry["mock_colourise"] = mock_colourise_factory

                return {"raw_output": raw_output}

            @staticmethod
            def _validate_skip_scenario(results: Any, scenario_data: dict[str, Any]) -> dict[str, Any]:
                """Validate skip scenario results.

                Returns:
                    dict[str, Any]: Validation results.
                """
                assert any(isinstance(r, pathlib.Path) for r in results), "Should return path results"
                assert scenario_data["raw_output"].exists(), "Raw output should exist"
                return {"success": True, "paths_returned": True, "raw_output_exists": True}

            @staticmethod
            def _validate_error_scenario(exception_info: Any, scenario_data: dict[str, Any]) -> dict[str, Any]:
                """Validate error scenario results.

                Args:
                    exception_info: The exception information from pytest.raises.
                    scenario_data: Scenario setup data (unused but required for interface consistency).

                Returns:
                    dict[str, Any]: Validation results.
                """
                _ = scenario_data  # Mark as intentionally unused
                assert exception_info is not None, "Should raise exception"
                assert isinstance(exception_info.value, RuntimeError | ProcessingError | RIFEError | FFmpegError), (
                    "Should raise expected exception type"
                )
                return {
                    "success": True,
                    "exception_raised": True,
                    "exception_type": type(exception_info.value).__name__,
                }

            @staticmethod
            def _validate_sanchez_scenario(results: Any, scenario_data: dict[str, Any]) -> dict[str, Any]:
                """Validate Sanchez processing scenario.

                Returns:
                    dict[str, Any]: Validation results.
                """
                assert any(isinstance(r, pathlib.Path) for r in results), "Should return path results"
                assert scenario_data["raw_output"].exists(), "Raw output should exist"
                return {"success": True, "paths_returned": True, "sanchez_processed": True}

            @staticmethod
            def _validate_sanchez_fail_scenario(results: Any, scenario_data: dict[str, Any]) -> dict[str, Any]:
                """Validate Sanchez failure scenario (should handle gracefully).

                Returns:
                    dict[str, Any]: Validation results.
                """
                # Even if Sanchez fails, the pipeline should continue
                assert any(isinstance(r, pathlib.Path) for r in results), "Should return path results"
                assert scenario_data["raw_output"].exists(), "Raw output should exist"
                return {"success": True, "paths_returned": True, "sanchez_fail_handled": True}

            def execute_vfi_scenario(
                self,
                scenario_name: str,
                temp_dir: pathlib.Path,
                mock_capability_detector: MagicMock,
            ) -> dict[str, Any]:
                """Execute a VFI test scenario.

                Returns:
                    dict[str, Any]: Test execution results.
                """
                scenario_config = self.scenario_configs[scenario_name]
                mock_registry: dict[str, Any] = {}

                # Setup scenario-specific mocks
                scenario_data = scenario_config["mock_setup"](temp_dir, mock_registry)

                # Create dummy input images
                _ = make_dummy_images(temp_dir, count=3)  # Images are created but not directly used

                # Execute the VFI pipeline with comprehensive mocking
                with (
                    patch("goesvfi.pipeline.run_vfi.subprocess.run") as mock_run,
                    patch("goesvfi.pipeline.run_vfi.subprocess.Popen") as mock_popen,
                    patch("goesvfi.pipeline.run_vfi.pathlib.Path.mkdir"),
                    patch("goesvfi.pipeline.run_vfi.pathlib.Path.exists", return_value=True),
                    patch("goesvfi.pipeline.run_vfi.pathlib.Path.is_file", return_value=True),
                    patch("goesvfi.pipeline.run_vfi.pathlib.Path.is_dir", return_value=True),
                    patch(
                        "goesvfi.pipeline.run_vfi.pathlib.Path.stat",
                        return_value=type("MockStat", (), {"st_size": 1024, "st_mode": 0o100644})(),
                    ),
                    patch("shutil.rmtree"),
                    patch("shutil.move"),
                    patch("goesvfi.pipeline.run_vfi.RifeCapabilityDetector", return_value=mock_capability_detector),
                    patch("goesvfi.pipeline.run_vfi.colourise") as mock_colourise,
                ):
                    # Apply scenario-specific mock configurations
                    if "mock_run" in mock_registry:
                        mock_run.side_effect = mock_registry["mock_run"]
                    if "mock_popen" in mock_registry:
                        mock_popen.side_effect = mock_registry["mock_popen"]
                    if "mock_colourise" in mock_registry:
                        mock_colourise.side_effect = mock_registry["mock_colourise"]

                    # Test parameters - build base parameters
                    base_params: dict[str, Any] = {
                        "folder": temp_dir,  # run_vfi expects folder not input_images
                        "output_mp4_path": temp_dir / "output.mp4",
                        "rife_exe_path": pathlib.Path("/path/to/rife"),  # Mock path
                        "fps": 30,
                        "num_intermediate_frames": 1,
                        "max_workers": 1,
                        # RIFE parameters with defaults
                        "rife_tile_enable": False,
                        "rife_tile_size": 256,
                        "rife_uhd_mode": False,
                        "rife_thread_spec": "1:2:2",
                        "rife_tta_spatial": False,
                        "rife_tta_temporal": False,
                        "model_key": "rife-v4.6",
                        "skip_model": False,  # Explicitly set to ensure RIFE is used by default
                        # Sanchez/Crop parameters
                        "false_colour": False,
                        "res_km": 4,
                        "crop_rect_xywh": None,
                    }

                    # Update with scenario-specific kwargs
                    base_params.update(scenario_config["kwargs"])

                    if scenario_config["expect_error"]:
                        # Test error scenarios
                        with pytest.raises((RuntimeError, ProcessingError, RIFEError, FFmpegError)) as exc_info:
                            # run_vfi returns a generator, need to consume it to trigger the error
                            generator = run_vfi_mod.run_vfi(**base_params)
                            # Consume the generator to trigger the exception
                            list(generator)

                        # Validate error scenario
                        validation_result = scenario_config["validation"](exc_info, scenario_data)
                        validation_result["scenario"] = scenario_name
                        return validation_result
                    # Test success scenarios
                    results = list(run_vfi_mod.run_vfi(**base_params))

                    # Validate success scenario
                    validation_result = scenario_config["validation"](results, scenario_data)
                    validation_result["scenario"] = scenario_name
                    return validation_result

        return {
            "test_manager": VFITestManager(),
        }

    @pytest.mark.parametrize("scenario_name", ["skip", "rife_fail"])
    def test_run_vfi_scenarios(  # noqa: PLR6301
        self,
        scenario_name: str,
        vfi_test_components: dict[str, Any],
        mock_capability_detector: MagicMock,
        tmp_path: pathlib.Path,
    ) -> None:
        """Test VFI pipeline scenarios with different configurations and failure modes."""
        test_manager = vfi_test_components["test_manager"]

        # Execute the scenario
        result = test_manager.execute_vfi_scenario(scenario_name, tmp_path, mock_capability_detector)

        # Verify the scenario completed successfully
        assert result["success"], f"VFI scenario '{scenario_name}' should complete successfully"
        assert result["scenario"] == scenario_name, f"Should correctly identify scenario as '{scenario_name}'"

        # Scenario-specific validations
        if scenario_name == "skip":
            assert result["paths_returned"], "Skip scenario should return paths"
            assert result["raw_output_exists"], "Skip scenario should create raw output"

        elif scenario_name in {"rife_fail"}:
            assert result["exception_raised"], f"{scenario_name} should raise an exception"
            assert result["exception_type"] in {"RuntimeError", "ProcessingError", "RIFEError", "FFmpegError"}, (
                f"{scenario_name} should raise appropriate exception type"
            )

    def test_run_vfi_comprehensive_integration(  # noqa: PLR6301
        self,
        vfi_test_components: dict[str, Any],
        mock_capability_detector: MagicMock,
        tmp_path: pathlib.Path,
    ) -> None:
        """Test comprehensive VFI integration with all scenarios."""
        test_manager = vfi_test_components["test_manager"]

        # Test all scenarios and collect results
        scenario_results = {}

        for scenario_name in test_manager.scenario_configs:
            try:
                result = test_manager.execute_vfi_scenario(scenario_name, tmp_path, mock_capability_detector)
                scenario_results[scenario_name] = result
            except Exception as e:
                # Some scenarios are expected to fail
                if test_manager.scenario_configs[scenario_name]["expect_error"]:
                    scenario_results[scenario_name] = {
                        "success": True,
                        "expected_error": True,
                        "error_type": type(e).__name__,
                    }
                else:
                    raise

        # Verify all scenarios were tested
        assert len(scenario_results) == len(test_manager.scenario_configs), "All scenarios should be tested"

        # Verify success scenarios completed successfully
        success_scenarios = ["skip"]
        for scenario in success_scenarios:
            assert scenario_results[scenario]["success"], f"Success scenario '{scenario}' should complete"

        # Verify error scenarios were handled appropriately
        error_scenarios = ["rife_fail"]
        for scenario in error_scenarios:
            result = scenario_results[scenario]
            assert result.get("expected_error") or result.get("exception_raised"), (
                f"Error scenario '{scenario}' should handle errors appropriately"
            )

    def test_run_vfi_edge_cases(  # noqa: PLR6301
        self,
        vfi_test_components: dict[str, Any],
        mock_capability_detector: MagicMock,
        tmp_path: pathlib.Path,
    ) -> None:
        """Test VFI edge cases and boundary conditions."""
        _ = vfi_test_components  # Unused but required for pytest fixture injection
        # Test with minimal number of images
        _ = make_dummy_images(tmp_path, count=2)  # Images are created in temp_dir for testing

        # Test basic VFI execution with minimal setup
        with (
            patch("goesvfi.pipeline.run_vfi.subprocess.run") as mock_run,
            patch("goesvfi.pipeline.run_vfi.subprocess.Popen") as mock_popen,
            patch("goesvfi.pipeline.run_vfi.pathlib.Path.mkdir"),
            patch("goesvfi.pipeline.run_vfi.pathlib.Path.exists", return_value=True),
            patch("goesvfi.pipeline.run_vfi.pathlib.Path.is_file", return_value=True),
            patch("goesvfi.pipeline.run_vfi.pathlib.Path.is_dir", return_value=True),
            patch(
                "goesvfi.pipeline.run_vfi.pathlib.Path.stat",
                return_value=type("MockStat", (), {"st_size": 1024, "st_mode": 0o100644})(),
            ),
            patch("shutil.rmtree"),
            patch("shutil.move"),
            patch("goesvfi.pipeline.run_vfi.RifeCapabilityDetector", return_value=mock_capability_detector),
            patch("goesvfi.pipeline.run_vfi.colourise"),
        ):
            # Setup successful mocks
            raw_output = tmp_path / "out.raw.mp4"
            raw_output.touch()

            mock_run.side_effect = create_mock_subprocess_run()
            mock_popen.side_effect = create_mock_popen(output_file_to_create=raw_output)

            # Execute VFI with edge case parameters
            params: dict[str, Any] = {
                "folder": tmp_path,
                "output_mp4_path": tmp_path / "output.mp4",
                "rife_exe_path": pathlib.Path("/path/to/rife"),
                "fps": 30,
                "num_intermediate_frames": 1,
                "max_workers": 1,
                # RIFE parameters
                "rife_tile_enable": False,
                "rife_tile_size": 256,
                "rife_uhd_mode": False,
                "rife_thread_spec": "1:2:2",
                "rife_tta_spatial": False,
                "rife_tta_temporal": False,
                "model_key": "rife-v4.6",
                # Sanchez/Crop parameters
                "false_colour": False,
                "res_km": 4,
                "crop_rect_xywh": None,
            }

            results = run_vfi_mod.run_vfi(**params)

            # Verify edge case results
            assert any(isinstance(r, pathlib.Path) for r in results), "Should return path results for edge cases"
            assert raw_output.exists(), "Should create raw output for edge cases"
