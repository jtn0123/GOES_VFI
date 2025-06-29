"""
Optimized unit tests for RIFE interpolation functionality with maintained coverage.

This v2 version maintains all test scenarios while optimizing through:
- Shared fixtures for interpolation setup and mock configurations
- Combined interpolation testing scenarios for different backend configurations
- Batch validation of RIFE command execution and file operations
- Enhanced error handling and edge case coverage
"""

import subprocess  # noqa: S404
from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

import goesvfi.pipeline.interpolate as interpolate_mod

from tests.utils.mocks import create_mock_subprocess_run


class TestInterpolateOptimizedV2:
    """Optimized RIFE interpolation tests with full coverage."""

    @pytest.fixture(scope="class")
    @staticmethod
    def interpolation_test_components() -> dict[str, Any]:
        """Create shared components for interpolation testing.

        Returns:
            dict[str, Any]: Dictionary containing test manager instance.
        """

        # Enhanced Interpolation Test Manager
        class InterpolationTestManager:
            """Manage RIFE interpolation testing scenarios."""

            def __init__(self) -> None:
                self.image_templates = {
                    "small": np.ones((4, 4, 3), dtype=np.float32),
                    "medium": np.ones((16, 16, 3), dtype=np.float32),
                    "large": np.ones((64, 64, 3), dtype=np.float32),
                    "rgb_pattern": np.ones((8, 8, 3), dtype=np.float32) * 0.5,  # Fixed pattern instead of random
                }

                self.backend_configs = {
                    "basic": {
                        "supports_tiling": True,
                        "supports_uhd": True,
                        "supports_tta_spatial": False,
                        "supports_tta_temporal": False,
                        "supports_thread_spec": True,
                    },
                    "advanced": {
                        "supports_tiling": True,
                        "supports_uhd": True,
                        "supports_tta_spatial": True,
                        "supports_tta_temporal": True,
                        "supports_thread_spec": True,
                    },
                    "limited": {
                        "supports_tiling": False,
                        "supports_uhd": False,
                        "supports_tta_spatial": False,
                        "supports_tta_temporal": False,
                        "supports_thread_spec": False,
                    },
                }

                self.interpolation_options = {
                    "basic": {"timestep": 0.5, "tile_enable": True},
                    "high_quality": {"timestep": 0.5, "tile_enable": True, "tile_size": 256},
                    "fast": {"timestep": 0.5, "tile_enable": False},
                    "custom_timestep": {"timestep": 0.25, "tile_enable": True},
                }

            def execute_pair_interpolation_test(
                self, test_case: dict[str, Any], temp_workspace: dict[str, Any]
            ) -> dict[str, Any]:
                """Execute a pair interpolation test scenario.

                Returns:
                    dict[str, Any]: Test execution results.
                """
                with (
                    patch.object(interpolate_mod, "RifeCommandBuilder") as mock_cmd_builder_cls,
                    patch("goesvfi.pipeline.interpolate.subprocess.run") as mock_run_patch,
                    patch("goesvfi.pipeline.interpolate.Image.fromarray"),
                    patch("goesvfi.pipeline.interpolate.Image.open") as mock_image_open,
                    patch("goesvfi.pipeline.interpolate.shutil.rmtree") as mock_rmtree,
                    patch("goesvfi.pipeline.interpolate.pathlib.Path.exists", return_value=True) as mock_exists,
                ):
                    # Setup command builder mock
                    mock_cmd_builder = MagicMock()
                    expected_rife_cmd = ["rife", "args", f"--test-{test_case['name']}"]
                    mock_cmd_builder.build_command.return_value = expected_rife_cmd

                    # Setup detector capabilities
                    mock_cmd_builder.detector = MagicMock()
                    backend_config = self.backend_configs[test_case["backend_config"]]
                    for capability, value in backend_config.items():
                        getattr(mock_cmd_builder.detector, capability).return_value = value

                    mock_cmd_builder_cls.return_value = mock_cmd_builder

                    # Setup subprocess run mock
                    mock_run_factory = create_mock_subprocess_run(expected_command=expected_rife_cmd)
                    mock_run_patch.side_effect = mock_run_factory

                    # Setup PIL image mock
                    mock_pil_image = MagicMock(spec=interpolate_mod.Image.Image)
                    mock_pil_image.convert.return_value = mock_pil_image
                    mock_pil_image.size = test_case["image"].shape[:2][::-1]  # PIL uses (width, height)
                    mock_image_open.return_value.__enter__.return_value = mock_pil_image

                    # Mock numpy array conversion
                    with patch("numpy.array", return_value=test_case["image"].astype(np.uint8)) as mock_np_array:
                        # Create backend
                        dummy_exe_path = temp_workspace["temp_dir"] / "rife-cli"
                        dummy_exe_path.touch()
                        backend = interpolate_mod.RifeBackend(exe_path=dummy_exe_path)

                        # Execute interpolation
                        result = backend.interpolate_pair(
                            test_case["image"], test_case["image"], options=test_case["options"]
                        )

                        # Verify results
                        assert isinstance(result, np.ndarray), f"Result should be numpy array for {test_case['name']}"
                        assert result.dtype == np.float32, f"Result should be float32 for {test_case['name']}"

                        # Verify mocks were called correctly
                        mock_cmd_builder.build_command.assert_called_once()
                        mock_run_patch.assert_called_once_with(
                            expected_rife_cmd,
                            check=True,
                            capture_output=True,
                            text=True,
                            timeout=120,
                        )
                        assert mock_exists.called, f"Path.exists should be called for {test_case['name']}"
                        mock_image_open.assert_called_once()
                        mock_np_array.assert_called_once()
                        mock_rmtree.assert_called_once()

                        return {
                            "success": True,
                            "result_shape": result.shape,
                            "result_dtype": str(result.dtype),
                            "command_built": True,
                            "subprocess_called": True,
                            "cleanup_performed": True,
                        }

            def execute_error_handling_test(self, temp_workspace: dict[str, Any]) -> dict[str, Any]:
                """Execute error handling test scenario.

                Returns:
                    dict[str, Any]: Test execution results.
                """
                with (
                    patch.object(interpolate_mod, "RifeCommandBuilder") as mock_cmd_builder_cls,
                    patch("goesvfi.pipeline.interpolate.subprocess.run") as mock_run_patch,
                    patch("goesvfi.pipeline.interpolate.Image.fromarray"),
                    patch("goesvfi.pipeline.interpolate.Image.open"),
                    patch("goesvfi.pipeline.interpolate.shutil.rmtree") as mock_rmtree,
                    patch("goesvfi.pipeline.interpolate.pathlib.Path.exists", return_value=True),
                ):
                    # Setup command builder
                    mock_cmd_builder = MagicMock()
                    expected_rife_cmd = ["rife", "args"]
                    mock_cmd_builder.build_command.return_value = expected_rife_cmd
                    mock_cmd_builder.detector = MagicMock()
                    mock_cmd_builder.detector.supports_tiling.return_value = True
                    mock_cmd_builder_cls.return_value = mock_cmd_builder

                    # Setup subprocess to raise error
                    rife_error = subprocess.CalledProcessError(1, expected_rife_cmd, stderr="RIFE execution failed")
                    mock_run_factory = create_mock_subprocess_run(
                        expected_command=expected_rife_cmd, side_effect=rife_error
                    )
                    mock_run_patch.side_effect = mock_run_factory

                    # Create backend
                    dummy_exe_path = temp_workspace["temp_dir"] / "rife-cli"
                    dummy_exe_path.touch()
                    backend = interpolate_mod.RifeBackend(exe_path=dummy_exe_path)

                    # Test subprocess error
                    with pytest.raises(RuntimeError) as excinfo:
                        backend.interpolate_pair(self.image_templates["small"], self.image_templates["small"])

                    # Verify error details
                    assert "RIFE executable failed" in str(excinfo.value), "Should have correct error message"
                    assert isinstance(excinfo.value.__cause__, subprocess.CalledProcessError), (
                        "Should have correct exception cause"
                    )

                    # Verify cleanup was still called
                    mock_run_patch.assert_called_once()
                    mock_rmtree.assert_called_once()

                    return {
                        "success": True,
                        "raises_runtime_error": True,
                        "cleanup_performed": True,
                    }

            def execute_three_frame_test(self) -> dict[str, Any]:
                """Execute three-frame interpolation test.

                Returns:
                    dict[str, Any]: Test execution results.
                """
                dummy_img = self.image_templates["small"]

                # Create mock backend
                dummy_backend = MagicMock(spec=interpolate_mod.RifeBackend)

                # Setup interpolate_pair to return different frames
                dummy_backend.interpolate_pair.side_effect = [
                    np.full((4, 4, 3), 0.25, dtype=np.float32),  # mid (first call)
                    np.full((4, 4, 3), 0.5, dtype=np.float32),  # left (second call)
                    np.full((4, 4, 3), 0.75, dtype=np.float32),  # right (third call)
                ]

                # Call interpolate_three
                result = interpolate_mod.interpolate_three(dummy_img, dummy_img, dummy_backend, {"tile_enable": True})

                # Verify call count
                assert dummy_backend.interpolate_pair.call_count == 3, "Should call interpolate_pair 3 times"

                # Verify result structure
                assert isinstance(result, list), "Result should be list"
                assert len(result) == 3, "Result should have 3 elements"
                assert all(isinstance(arr, np.ndarray) and arr.dtype == np.float32 for arr in result), (
                    "All results should be float32 arrays"
                )

                return {
                    "success": True,
                    "call_count": dummy_backend.interpolate_pair.call_count,
                    "result_length": len(result),
                    "result_dtypes": [str(arr.dtype) for arr in result],
                }

        return {
            "test_manager": InterpolationTestManager(),
        }

    @pytest.fixture()
    @staticmethod
    def temp_workspace(tmp_path: Any) -> dict[str, Any]:
        """Create temporary workspace for interpolation testing.

        Returns:
            dict[str, Any]: Dictionary containing temp directory path.
        """
        return {
            "temp_dir": tmp_path,
        }

    @staticmethod
    def test_interpolate_pair_comprehensive_scenarios(
        interpolation_test_components: dict[str, Any], temp_workspace: dict[str, Any]
    ) -> None:
        """Test comprehensive pair interpolation scenarios."""
        test_manager = interpolation_test_components["test_manager"]

        # Test different image sizes and configurations
        test_cases = [
            {
                "name": "small_basic",
                "image": test_manager.image_templates["small"],
                "backend_config": "basic",
                "options": test_manager.interpolation_options["basic"],
            },
            {
                "name": "medium_advanced",
                "image": test_manager.image_templates["medium"],
                "backend_config": "advanced",
                "options": test_manager.interpolation_options["high_quality"],
            },
            {
                "name": "pattern_fast",
                "image": test_manager.image_templates["rgb_pattern"],
                "backend_config": "basic",
                "options": test_manager.interpolation_options["fast"],
            },
            {
                "name": "custom_timestep",
                "image": test_manager.image_templates["small"],
                "backend_config": "basic",
                "options": test_manager.interpolation_options["custom_timestep"],
            },
        ]

        results = {}
        for test_case in test_cases:
            result = test_manager.execute_pair_interpolation_test(test_case, temp_workspace)
            results[test_case["name"]] = result

            # Verify each test succeeded
            assert result["success"], f"Pair interpolation test {test_case['name']} should succeed"
            assert result["result_dtype"] == "float32", f"Result should be float32 for {test_case['name']}"

        # Verify all tests completed
        assert len(results) == len(test_cases), "All test cases should complete"

    @staticmethod
    def test_interpolate_error_handling(
        interpolation_test_components: dict[str, Any], temp_workspace: dict[str, Any]
    ) -> None:
        """Test error handling in interpolation."""
        test_manager = interpolation_test_components["test_manager"]

        # Execute error handling test
        result = test_manager.execute_error_handling_test(temp_workspace)

        # Verify error handling
        assert result["success"], "Error handling test should succeed"
        assert result["raises_runtime_error"], "Should raise RuntimeError for subprocess failure"
        assert result["cleanup_performed"], "Cleanup should be performed even on errors"

    @staticmethod
    def test_interpolate_three_frame_logic(interpolation_test_components: dict[str, Any]) -> None:
        """Test three-frame interpolation logic."""
        test_manager = interpolation_test_components["test_manager"]

        # Execute three-frame test
        result = test_manager.execute_three_frame_test()

        # Verify three-frame functionality
        assert result["success"], "Three-frame interpolation should succeed"
        assert result["call_count"] == 3, "Should call interpolate_pair 3 times"
        assert result["result_length"] == 3, "Should return 3 results"
        assert all(dtype == "float32" for dtype in result["result_dtypes"]), "All results should be float32"

    @staticmethod
    def test_interpolate_backend_configurations(
        interpolation_test_components: dict[str, Any], temp_workspace: dict[str, Any]
    ) -> None:
        """Test different backend configurations."""
        test_manager = interpolation_test_components["test_manager"]

        # Test each backend configuration
        for config_name in test_manager.backend_configs:
            test_case = {
                "name": f"backend_{config_name}",
                "image": test_manager.image_templates["small"],
                "backend_config": config_name,
                "options": test_manager.interpolation_options["basic"],
            }

            result = test_manager.execute_pair_interpolation_test(test_case, temp_workspace)

            # Verify backend configuration test
            assert result["success"], f"Backend configuration {config_name} should work"
            assert result["command_built"], f"Command should be built for {config_name}"
            assert result["cleanup_performed"], f"Cleanup should be performed for {config_name}"

    @staticmethod
    def test_interpolate_edge_cases(
        interpolation_test_components: dict[str, Any], temp_workspace: dict[str, Any]
    ) -> None:
        """Test edge cases and boundary conditions."""
        test_manager = interpolation_test_components["test_manager"]

        # Test different timestep values
        timestep_values = [0.0, 0.25, 0.5, 0.75, 1.0]

        for timestep in timestep_values:
            test_case = {
                "name": f"timestep_{timestep}",
                "image": test_manager.image_templates["small"],
                "backend_config": "basic",
                "options": {"timestep": timestep, "tile_enable": True},
            }

            result = test_manager.execute_pair_interpolation_test(test_case, temp_workspace)

            # Verify timestep test
            assert result["success"], f"Timestep {timestep} should work"
            assert result["result_dtype"] == "float32", f"Result should be float32 for timestep {timestep}"
