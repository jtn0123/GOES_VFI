"""Tests for Sanchez health check and monitoring."""

import os
import platform
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from PIL import Image

from goesvfi.sanchez.health_check import (
    SanchezHealthChecker,
    SanchezHealthStatus,
    SanchezProcessMonitor,
    check_sanchez_health,
    validate_sanchez_input,
)


class TestSanchezHealthStatus:
    """Test SanchezHealthStatus data class."""

    def test_health_status_initialization(self):
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

    def test_is_healthy_all_good(self):
        """Test is_healthy when all checks pass."""
        status = SanchezHealthStatus(
            binary_exists=True,
            binary_executable=True,
            resources_exist=True,
            can_execute=True,
            temp_dir_writable=True,
            errors=[],
        )

        assert status.is_healthy

    def test_is_healthy_with_errors(self):
        """Test is_healthy when there are errors."""
        status = SanchezHealthStatus(
            binary_exists=True,
            binary_executable=True,
            resources_exist=True,
            can_execute=True,
            temp_dir_writable=True,
            errors=["Some error"],
        )

        assert not status.is_healthy

    def test_to_dict(self):
        """Test converting status to dictionary."""
        status = SanchezHealthStatus(
            binary_exists=True,
            binary_path=Path("/path/to/sanchez"),
            binary_size=1024,
            gradient_files=["Atmosphere.json"],
            errors=["Test error"],
        )

        result = status.to_dict()

        assert isinstance(result, dict)
        assert "healthy" in result
        assert result["binary"]["exists"] is True
        assert result["binary"]["path"] == "/path/to/sanchez"
        assert result["binary"]["size"] == 1024
        assert result["dependencies"]["gradient_files"] == ["Atmosphere.json"]
        assert result["errors"] == ["Test error"]


class TestSanchezHealthChecker:
    """Test SanchezHealthChecker functionality."""

    def test_initialization(self):
        """Test health checker initialization."""
        checker = SanchezHealthChecker()

        assert checker.platform_key == (platform.system(), platform.machine())
        assert checker.sanchez_dir is not None

    @patch("platform.system")
    @patch("platform.machine")
    def test_get_binary_path_darwin(self, mock_machine, mock_system):
        """Test getting binary path on macOS."""
        mock_system.return_value = "Darwin"
        mock_machine.return_value = "x86_64"

        checker = SanchezHealthChecker()
        path = checker._get_binary_path()

        assert path is not None
        assert "osx-x64" in str(path)
        assert path.name == "Sanchez"

    @patch("platform.system")
    @patch("platform.machine")
    def test_get_binary_path_windows(self, mock_machine, mock_system):
        """Test getting binary path on Windows."""
        mock_system.return_value = "Windows"
        mock_machine.return_value = "AMD64"

        checker = SanchezHealthChecker()
        path = checker._get_binary_path()

        assert path is not None
        assert "win-x64" in str(path)
        assert path.name == "Sanchez.exe"

    def test_check_binary_not_found(self):
        """Test checking binary when it doesn't exist."""
        checker = SanchezHealthChecker()
        status = SanchezHealthStatus()

        with patch.object(checker, "_get_binary_path", return_value=Path("/nonexistent/path")):
            checker.check_binary(status)

        assert not status.binary_exists
        assert len(status.errors) > 0
        assert "not found" in status.errors[0]

    def test_check_binary_exists(self):
        """Test checking binary when it exists."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = Path(tmp.name)
            # Write some content so file has size > 0
            tmp.write(b"fake binary content")
            tmp.flush()

            try:
                # Make it executable
                os.chmod(tmp_path, 0o755)

                checker = SanchezHealthChecker()
                status = SanchezHealthStatus()

                with patch.object(checker, "_get_binary_path", return_value=tmp_path):
                    checker.check_binary(status)

                assert status.binary_exists
                assert status.binary_executable
                assert status.binary_size > 0
                assert status.binary_modified is not None

            finally:
                tmp_path.unlink()

    def test_check_resources_missing(self):
        """Test checking resources when they're missing."""
        checker = SanchezHealthChecker()
        status = SanchezHealthStatus(binary_path=Path("/fake/path/Sanchez"))

        with patch("pathlib.Path.exists", return_value=False):
            checker.check_resources(status)

        assert not status.resources_exist
        assert len(status.errors) > 0

    def test_check_resources_present(self):
        """Test checking resources when they're present."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create fake resource structure
            binary_dir = Path(tmpdir) / "bin"
            binary_dir.mkdir()
            resources_dir = binary_dir / "Resources"
            resources_dir.mkdir()

            # Create gradient files
            gradients_dir = resources_dir / "Gradients"
            gradients_dir.mkdir()
            (gradients_dir / "Atmosphere.json").write_text("{}")
            (gradients_dir / "Custom.json").write_text("{}")

            # Create other resources
            (resources_dir / "Overlays").mkdir()
            (resources_dir / "Palettes").mkdir()

            checker = SanchezHealthChecker()
            status = SanchezHealthStatus(binary_path=binary_dir / "Sanchez")

            checker.check_resources(status)

            assert status.resources_exist
            assert "Atmosphere.json" in status.gradient_files
            assert "Custom.json" in status.gradient_files
            assert len(status.missing_resources) == 0

    @patch("subprocess.run")
    def test_check_execution_success(self, mock_run):
        """Test checking execution when Sanchez runs successfully."""
        mock_run.return_value = Mock(returncode=0, stdout="Sanchez v1.0.0", stderr="")

        checker = SanchezHealthChecker()
        status = SanchezHealthStatus(binary_executable=True, binary_path=Path("/fake/Sanchez"))

        checker.check_execution(status)

        assert status.can_execute
        assert status.version_info == "Sanchez v1.0.0"
        assert status.execution_time > 0

    @patch("subprocess.run")
    def test_check_execution_failure(self, mock_run):
        """Test checking execution when Sanchez fails."""
        mock_run.side_effect = subprocess.TimeoutExpired("sanchez", 5)

        checker = SanchezHealthChecker()
        status = SanchezHealthStatus(binary_executable=True, binary_path=Path("/fake/Sanchez"))

        checker.check_execution(status)

        assert not status.can_execute
        assert len(status.errors) > 0
        assert "timed out" in status.errors[0]

    def test_run_health_check_complete(self):
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
    """Test SanchezProcessMonitor functionality."""

    def test_initialization(self):
        """Test monitor initialization."""
        monitor = SanchezProcessMonitor()

        assert monitor.current_process is None
        assert monitor.start_time is None
        assert monitor.is_cancelled is False

    def test_set_progress_callback(self):
        """Test setting progress callback."""
        monitor = SanchezProcessMonitor()
        callback = Mock()

        monitor.set_progress_callback(callback)
        monitor._report_progress("Test", 0.5)

        callback.assert_called_once_with("Test", 0.5)

    @pytest.mark.asyncio
    async def test_run_sanchez_monitored_invalid_input(self):
        """Test running Sanchez with invalid input."""
        monitor = SanchezProcessMonitor()

        # Mock the health check to avoid real Sanchez execution
        with patch("goesvfi.sanchez.health_check.SanchezHealthChecker") as mock_checker:
            mock_status = SanchezHealthStatus(
                binary_exists=True,
                binary_executable=True,
                resources_exist=True,
                can_execute=True,
                temp_dir_writable=True,
                binary_path=Path("/fake/Sanchez"),
            )
            mock_checker.return_value.run_health_check.return_value = mock_status

            with pytest.raises(FileNotFoundError):
                await monitor.run_sanchez_monitored(
                    input_path=Path("/nonexistent/file.png"),
                    output_path=Path("/tmp/output.png"),
                )

    def test_cancel(self):
        """Test cancelling a process."""
        monitor = SanchezProcessMonitor()
        mock_process = Mock()
        monitor.current_process = mock_process

        monitor.cancel()

        assert monitor.is_cancelled
        mock_process.terminate.assert_called_once()


def test_validate_sanchez_input_valid():
    """Test validating valid input for Sanchez."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = Path(tmp.name)

        try:
            # Create a valid image
            img = Image.new("RGB", (500, 500), color="red")
            img.save(tmp_path, "PNG")

            is_valid, msg = validate_sanchez_input(tmp_path)

            assert is_valid
            assert msg == "OK"

        finally:
            tmp_path.unlink()


def test_validate_sanchez_input_missing_file():
    """Test validating missing input file."""
    is_valid, msg = validate_sanchez_input(Path("/nonexistent/file.png"))

    assert not is_valid
    assert "not found" in msg


def test_validate_sanchez_input_empty_file():
    """Test validating empty input file."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = Path(tmp.name)
        # Don't write anything - empty file

        try:
            is_valid, msg = validate_sanchez_input(tmp_path)

            assert not is_valid
            assert "empty" in msg

        finally:
            tmp_path.unlink()


def test_validate_sanchez_input_too_large():
    """Test validating input file that's too large."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = Path(tmp.name)

        try:
            # Create a large image that won't trigger PIL's decompression bomb protection
            # but will still be too large for our check
            img = Image.new("RGB", (10001, 10001), color="red")  # Just over 10000x10000 limit
            img.save(tmp_path, "PNG")

            is_valid, msg = validate_sanchez_input(tmp_path)

            assert not is_valid
            assert "too large" in msg or "Could not read image" in msg

        finally:
            tmp_path.unlink()


@patch("goesvfi.sanchez.health_check.SanchezHealthChecker")
def test_check_sanchez_health(mock_checker_class):
    """Test the convenience function check_sanchez_health."""
    mock_checker = Mock()
    mock_checker_class.return_value = mock_checker

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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
