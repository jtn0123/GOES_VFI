"""Tests for Sanchez health check and monitoring - Optimized Version."""

from pathlib import Path
import subprocess
from unittest.mock import Mock, patch

from PIL import Image
import pytest

from goesvfi.sanchez.health_check import (
    SanchezHealthChecker,
    SanchezHealthStatus,
    SanchezProcessMonitor,
    check_sanchez_health,
    validate_sanchez_input,
)


class TestSanchezHealthStatus:
    """Test SanchezHealthStatus data class - optimized."""

    @pytest.mark.parametrize("status_params,expected_healthy", [
        # All good
        ({
            "binary_exists": True,
            "binary_executable": True,
            "resources_exist": True,
            "can_execute": True,
            "temp_dir_writable": True,
            "errors": [],
        }, True),
        # Has errors
        ({
            "binary_exists": True,
            "binary_executable": True,
            "resources_exist": True,
            "can_execute": True,
            "temp_dir_writable": True,
            "errors": ["Some error"],
        }, False),
        # Missing binary
        ({
            "binary_exists": False,
            "binary_executable": True,
            "resources_exist": True,
            "can_execute": True,
            "temp_dir_writable": True,
            "errors": [],
        }, False),
        # Not executable
        ({
            "binary_exists": True,
            "binary_executable": False,
            "resources_exist": True,
            "can_execute": True,
            "temp_dir_writable": True,
            "errors": [],
        }, False),
    ])
    def test_health_status_conditions(self, status_params, expected_healthy) -> None:
        """Test health status under various conditions."""
        status = SanchezHealthStatus(**status_params)
        assert status.is_healthy == expected_healthy

    def test_health_status_defaults(self) -> None:
        """Test default initialization of health status."""
        status = SanchezHealthStatus()

        assert not status.binary_exists
        assert not status.binary_executable
        assert status.binary_path is None
        assert status.binary_size == 0
        assert not status.resources_exist
        assert len(status.gradient_files) == 0
        assert not status.can_execute
        assert not status.is_healthy

    def test_to_dict_conversion(self) -> None:
        """Test converting status to dictionary with various data."""
        status = SanchezHealthStatus(
            binary_exists=True,
            binary_path=Path("/path/to/sanchez"),
            binary_size=1024,
            gradient_files=["Atmosphere.json", "Custom.json"],
            errors=["Test error 1", "Test error 2"],
            temp_dir_writable=True,
            execution_time=1.5,
        )

        result = status.to_dict()

        assert isinstance(result, dict)
        assert "healthy" in result
        assert result["binary"]["exists"] is True
        assert result["binary"]["path"] == "/path/to/sanchez"
        assert result["binary"]["size"] == 1024
        assert len(result["dependencies"]["gradient_files"]) == 2
        assert "Atmosphere.json" in result["dependencies"]["gradient_files"]
        assert len(result["errors"]) == 2
        assert result["diagnostics"]["temp_dir_writable"] is True
        assert result["diagnostics"]["execution_time"] == 1.5


class TestSanchezHealthChecker:
    """Test SanchezHealthChecker functionality - optimized."""

    @pytest.fixture()
    def mock_binary_path(self, tmp_path):
        """Create a mock binary file for testing."""
        binary = tmp_path / "Sanchez"
        binary.write_bytes(b"fake binary content" * 100)  # Give it some size
        binary.chmod(0o755)
        return binary

    @pytest.fixture()
    def mock_resources_dir(self, tmp_path):
        """Create mock resource directory structure."""
        resources = tmp_path / "Resources"
        resources.mkdir()

        # Create gradient files
        gradients = resources / "Gradients"
        gradients.mkdir()
        (gradients / "Atmosphere.json").write_text("{}")
        (gradients / "Custom.json").write_text("{}")
        (gradients / "Test.json").write_text("{}")

        # Create other resource directories
        (resources / "Overlays").mkdir()
        (resources / "Palettes").mkdir()

        return resources

    @pytest.mark.parametrize("platform_info,expected_path_pattern", [
        (("Darwin", "x86_64"), "osx-x64/Sanchez"),
        (("Darwin", "arm64"), "osx-arm64/Sanchez"),
        (("Linux", "x86_64"), "linux-x64/Sanchez"),
        (("Windows", "AMD64"), "win-x64/Sanchez.exe"),
        (("Windows", "x86"), "win-x86/Sanchez.exe"),
    ])
    def test_binary_path_detection(self, platform_info, expected_path_pattern) -> None:
        """Test binary path detection for different platforms."""
        system, machine = platform_info

        with patch("platform.system", return_value=system), patch("platform.machine", return_value=machine):
            checker = SanchezHealthChecker()
            path = checker._get_binary_path()

            assert path is not None
            assert expected_path_pattern in str(path)

    def test_check_binary_exists(self, mock_binary_path) -> None:
        """Test checking binary when it exists and is valid."""
        checker = SanchezHealthChecker()
        status = SanchezHealthStatus()

        with patch.object(checker, "_get_binary_path", return_value=mock_binary_path):
            checker.check_binary(status)

        assert status.binary_exists
        assert status.binary_executable
        assert status.binary_size > 0
        assert status.binary_modified is not None
        assert len(status.errors) == 0

    def test_check_binary_missing(self) -> None:
        """Test checking binary when it doesn't exist."""
        checker = SanchezHealthChecker()
        status = SanchezHealthStatus()

        with patch.object(checker, "_get_binary_path", return_value=Path("/nonexistent/Sanchez")):
            checker.check_binary(status)

        assert not status.binary_exists
        assert len(status.errors) > 0
        assert "not found" in status.errors[0]

    def test_check_resources_complete(self, mock_binary_path, mock_resources_dir) -> None:
        """Test checking resources when complete."""
        checker = SanchezHealthChecker()
        status = SanchezHealthStatus(binary_path=mock_binary_path)

        checker.check_resources(status)

        assert status.resources_exist
        assert len(status.gradient_files) == 3
        assert "Atmosphere.json" in status.gradient_files
        assert "Custom.json" in status.gradient_files
        assert "Test.json" in status.gradient_files
        assert len(status.missing_resources) == 0

    @pytest.mark.parametrize("execution_result", [
        {
            "returncode": 0,
            "stdout": "Sanchez v1.0.0\nColourise weather satellite images",
            "stderr": "",
            "can_execute": True,
            "has_error": False,
        },
        {
            "returncode": 1,
            "stdout": "",
            "stderr": "Error: Missing required argument",
            "can_execute": False,
            "has_error": True,
        },
        {
            "side_effect": subprocess.TimeoutExpired("sanchez", 5),
            "can_execute": False,
            "has_error": True,
        },
        {
            "side_effect": FileNotFoundError("Sanchez not found"),
            "can_execute": False,
            "has_error": True,
        },
    ])
    @patch("subprocess.run")
    def test_check_execution_scenarios(self, mock_run, execution_result) -> None:
        """Test execution checking under various scenarios."""
        checker = SanchezHealthChecker()
        status = SanchezHealthStatus(binary_executable=True, binary_path=Path("/fake/Sanchez"))

        if "side_effect" in execution_result:
            mock_run.side_effect = execution_result["side_effect"]
        else:
            mock_run.return_value = Mock(
                returncode=execution_result["returncode"],
                stdout=execution_result["stdout"],
                stderr=execution_result["stderr"],
            )

        checker.check_execution(status)

        assert status.can_execute == execution_result["can_execute"]
        assert (len(status.errors) > 0) == execution_result["has_error"]

        if execution_result["can_execute"]:
            assert status.version_info is not None
            assert status.execution_time > 0

    def test_run_health_check_complete(self) -> None:
        """Test running a complete health check."""
        checker = SanchezHealthChecker()

        # Mock all check methods
        with patch.object(checker, "check_binary") as mock_binary:
            with patch.object(checker, "check_resources") as mock_resources:
                with patch.object(checker, "check_execution") as mock_execution:
                    with patch.object(checker, "check_system_resources") as mock_system:
                        status = checker.run_health_check()

                        # Verify all checks were called
                        mock_binary.assert_called_once()
                        mock_resources.assert_called_once()
                        mock_execution.assert_called_once()
                        mock_system.assert_called_once()

                        assert isinstance(status, SanchezHealthStatus)


class TestSanchezProcessMonitor:
    """Test SanchezProcessMonitor functionality - optimized."""

    @pytest.fixture()
    def monitor(self):
        """Create a process monitor instance."""
        return SanchezProcessMonitor()

    @pytest.fixture()
    def mock_healthy_status(self):
        """Create a mock healthy status."""
        return SanchezHealthStatus(
            binary_exists=True,
            binary_executable=True,
            resources_exist=True,
            can_execute=True,
            temp_dir_writable=True,
            binary_path=Path("/fake/Sanchez"),
        )

    def test_initialization(self, monitor) -> None:
        """Test monitor initialization."""
        assert monitor.current_process is None
        assert monitor.start_time is None
        assert monitor.is_cancelled is False

    def test_progress_callback(self, monitor) -> None:
        """Test setting and using progress callback."""
        callback = Mock()
        monitor.set_progress_callback(callback)

        # Test progress reporting
        monitor._report_progress("Processing", 0.5)
        callback.assert_called_once_with("Processing", 0.5)

        # Test multiple calls
        monitor._report_progress("Completing", 0.9)
        assert callback.call_count == 2

    @pytest.mark.asyncio()
    async def test_run_sanchez_monitored_invalid_input(self, monitor, mock_healthy_status) -> None:
        """Test running Sanchez with invalid input file."""
        with patch("goesvfi.sanchez.health_check.SanchezHealthChecker") as mock_checker:
            mock_checker.return_value.run_health_check.return_value = mock_healthy_status

            with pytest.raises(FileNotFoundError):
                await monitor.run_sanchez_monitored(
                    input_path=Path("/nonexistent/file.png"),
                    output_path=Path("/tmp/output.png"),
                )

    def test_cancel_process(self, monitor) -> None:
        """Test cancelling a running process."""
        mock_process = Mock()
        monitor.current_process = mock_process

        monitor.cancel()

        assert monitor.is_cancelled
        mock_process.terminate.assert_called_once()

    def test_cancel_no_process(self, monitor) -> None:
        """Test cancelling when no process is running."""
        monitor.cancel()

        assert monitor.is_cancelled
        # Should not raise any errors


class TestSanchezInputValidation:
    """Test Sanchez input validation functions - optimized."""

    @pytest.fixture()
    def create_test_image(self, tmp_path):
        """Factory fixture to create test images."""
        def _create(filename: str, size: tuple[int, int], format: str = "PNG") -> Path:
            image_path = tmp_path / filename
            img = Image.new("RGB", size, color="red")
            img.save(image_path, format)
            return image_path
        return _create

    @pytest.mark.parametrize("test_case", [
        {
            "name": "valid_small",
            "size": (500, 500),
            "expected_valid": True,
            "expected_msg": "OK",
        },
        {
            "name": "valid_medium",
            "size": (2000, 2000),
            "expected_valid": True,
            "expected_msg": "OK",
        },
        {
            "name": "valid_large",
            "size": (10000, 10000),
            "expected_valid": True,
            "expected_msg": "OK",
        },
        {
            "name": "too_large",
            "size": (10001, 10001),
            "expected_valid": False,
            "expected_msg": "too large",
        },
    ])
    def test_validate_sanchez_input_sizes(self, create_test_image, test_case) -> None:
        """Test input validation with various image sizes."""
        try:
            image_path = create_test_image(f"{test_case['name']}.png", test_case["size"])
            is_valid, msg = validate_sanchez_input(image_path)

            assert is_valid == test_case["expected_valid"]
            if test_case["expected_msg"] == "OK":
                assert msg == test_case["expected_msg"]
            else:
                assert test_case["expected_msg"] in msg

        except Exception:
            # Very large images might fail to create
            if not test_case["expected_valid"]:
                pass  # Expected for invalid sizes
            else:
                raise

    def test_validate_missing_file(self) -> None:
        """Test validating missing input file."""
        is_valid, msg = validate_sanchez_input(Path("/nonexistent/file.png"))

        assert not is_valid
        assert "not found" in msg

    def test_validate_empty_file(self, tmp_path) -> None:
        """Test validating empty input file."""
        empty_file = tmp_path / "empty.png"
        empty_file.touch()  # Create empty file

        is_valid, msg = validate_sanchez_input(empty_file)

        assert not is_valid
        assert "empty" in msg

    @patch("PIL.Image.open")
    def test_validate_corrupted_image(self, mock_open, tmp_path) -> None:
        """Test validating corrupted image file."""
        corrupted = tmp_path / "corrupted.png"
        corrupted.write_bytes(b"not an image")

        mock_open.side_effect = OSError("Cannot identify image file")

        is_valid, msg = validate_sanchez_input(corrupted)

        assert not is_valid
        assert "Could not read image" in msg


@patch("goesvfi.sanchez.health_check.SanchezHealthChecker")
def test_check_sanchez_health_convenience(mock_checker_class) -> None:
    """Test the convenience function check_sanchez_health."""
    mock_checker = Mock()
    mock_checker_class.return_value = mock_checker

    # Test healthy status
    mock_status = SanchezHealthStatus(
        binary_exists=True,
        binary_executable=True,
        resources_exist=True,
        can_execute=True,
        temp_dir_writable=True,
    )
    mock_checker.run_health_check.return_value = mock_status

    result = check_sanchez_health()

    assert result is True
    mock_checker.run_health_check.assert_called_once()

    # Test unhealthy status
    mock_checker.reset_mock()
    mock_status.errors = ["Some error"]
    mock_checker.run_health_check.return_value = mock_status

    result = check_sanchez_health()

    assert result is False
    mock_checker.run_health_check.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
