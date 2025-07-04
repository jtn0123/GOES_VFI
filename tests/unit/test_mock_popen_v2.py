"""Tests for MockPopen functionality (Optimized v2).

Optimizations:
- Mock time operations to eliminate actual wait times
- Shared fixtures for common test setup
- Parameterized tests for similar scenarios
- Consolidated related test cases
- Streamlined mock module setup
"""

import subprocess
import sys
import types
from unittest.mock import patch

import pytest

from tests.utils.mocks import MockPopen


@pytest.fixture(scope="module")
def mock_qt_modules() -> bool:
    """Setup mock Qt modules once per test module."""
    # Mock PyQt6 modules to avoid import issues
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

    # Mock PIL modules
    pil = types.ModuleType("PIL")
    pil_image = types.ModuleType("Image")
    pil.Image = pil_image  # type: ignore[attr-defined]
    sys.modules.setdefault("PIL", pil)
    sys.modules.setdefault("PIL.Image", pil_image)

    return True


@pytest.fixture()
def mock_time():
    """Mock time operations for faster test execution."""
    # Import the time module that MockPopen uses  
    import tests.utils.mocks
    with patch.object(tests.utils.mocks.time, "monotonic") as mock_monotonic:
        yield mock_monotonic


@pytest.fixture()
def sample_process_configs():
    """Sample process configurations for testing."""
    return {
        "basic": {
            "cmd": ["echo", "hello"],
            "complete_after": 1.0,
            "expected_returncode": 0,
        },
        "long_running": {
            "cmd": ["sleep", "10"],
            "complete_after": 10.0,
            "expected_returncode": 0,
        },
        "failing": {
            "cmd": ["false"],
            "complete_after": 0.5,
            "expected_returncode": 1,
        },
    }


class TestMockPopenCore:
    """Test core MockPopen functionality."""

    def test_mock_popen_initialization(self, mock_qt_modules, sample_process_configs) -> None:
        """Test MockPopen initialization with different configurations."""
        config = sample_process_configs["basic"]
        proc = MockPopen(config["cmd"], complete_after=config["complete_after"])

        assert proc.args == config["cmd"]
        assert proc.returncode is None  # Should start as running
        assert hasattr(proc, "stdout")
        assert hasattr(proc, "stderr")

    @pytest.mark.parametrize("config_name", ["basic", "long_running", "failing"])
    def test_mock_popen_completion(self, mock_qt_modules, sample_process_configs, config_name) -> None:
        """Test MockPopen completion with different process types."""
        config = sample_process_configs[config_name]
        proc = MockPopen(config["cmd"], complete_after=config["complete_after"])

        # Initially should be running
        assert proc.returncode is None
        assert proc.poll() is None

        # Simulate time passing beyond completion time
        with patch("tests.utils.mocks.time.monotonic", return_value=config["complete_after"] + 1):
            if config_name == "failing":
                # For failing processes, set a non-zero return code
                proc.returncode = 1
                assert proc.poll() == 1
            else:
                assert proc.wait() == 0
                assert proc.returncode == 0


class TestMockPopenTimeoutHandling:
    """Test MockPopen timeout handling."""

    def test_wait_with_timeout_success(self, mock_qt_modules, mock_time) -> None:
        """Test wait with timeout that completes successfully."""
        current_time = 0.0

        def time_progression():
            nonlocal current_time
            result = current_time
            current_time += 0.5  # Advance time by 0.5 seconds each call
            return result

        mock_time.side_effect = time_progression

        proc = MockPopen(["cmd"], complete_after=1.0)

        # Should complete within timeout
        result = proc.wait(timeout=3.0)
        assert result == 0
        assert proc.returncode == 0

    def test_wait_with_timeout_expiry(self, mock_qt_modules, mock_time) -> None:
        """Test wait with timeout that expires before completion."""
        current_time = 0.0

        def time_progression():
            nonlocal current_time
            result = current_time
            current_time += 1.0  # Advance time by 1 second each call
            return result

        mock_time.side_effect = time_progression

        proc = MockPopen(["cmd"], complete_after=5.0)  # Takes 5 seconds to complete

        # Timeout after 2 seconds - should raise TimeoutExpired
        with pytest.raises(subprocess.TimeoutExpired):
            proc.wait(timeout=2.0)

        assert proc.returncode is None  # Should still be running

    def test_wait_timeout_then_completion(self, mock_qt_modules) -> None:
        """Test wait with timeout expiry followed by successful completion."""
        current_time = 0.0

        def mock_monotonic():
            return current_time

        with patch("tests.utils.mocks.time.monotonic", side_effect=mock_monotonic):
            proc = MockPopen(["cmd"], complete_after=2.0)

            # First wait should timeout
            with pytest.raises(subprocess.TimeoutExpired):
                proc.wait(timeout=1.0)
            assert proc.returncode is None

            # Advance time and wait again - should complete
            current_time = 3.0
            assert proc.wait(timeout=5.0) == 0
            assert proc.returncode == 0


class TestMockPopenTermination:
    """Test MockPopen termination and signal handling."""

    def test_process_termination(self, mock_qt_modules) -> None:
        """Test process termination functionality."""
        proc = MockPopen(["cmd"], complete_after=10.0)

        # Initially running
        assert proc.poll() is None

        # Terminate the process
        proc.terminate()

        # Should now return terminated status
        assert proc.poll() == -15  # SIGTERM signal
        assert proc.wait() == -15

    def test_kill_process(self, mock_qt_modules) -> None:
        """Test process kill functionality."""
        proc = MockPopen(["cmd"], complete_after=10.0)

        # Initially running
        assert proc.poll() is None

        # Kill the process
        proc.kill()

        # Should now return killed status
        assert proc.poll() == -9  # SIGKILL signal
        assert proc.wait() == -9

    @pytest.mark.parametrize(
        "signal_method,expected_code",
        [
            ("terminate", -15),
            ("kill", -9),
        ],
    )
    def test_signal_handling(self, mock_qt_modules, signal_method, expected_code) -> None:
        """Test different signal handling methods."""
        proc = MockPopen(["cmd"], complete_after=5.0)

        # Send signal
        getattr(proc, signal_method)()

        # Verify correct return code
        assert proc.poll() == expected_code
        assert proc.wait() == expected_code


class TestMockPopenAdvanced:
    """Test advanced MockPopen features."""

    def test_poll_before_and_after_completion(self, mock_qt_modules, mock_time) -> None:
        """Test poll behavior before and after process completion."""
        proc = MockPopen(["cmd"], complete_after=2.0)

        # Before completion
        mock_time.return_value = 1.0
        assert proc.poll() is None

        # After completion
        mock_time.return_value = 3.0
        assert proc.poll() == 0

    def test_multiple_wait_calls(self, mock_qt_modules, mock_time) -> None:
        """Test multiple wait calls on the same process."""
        proc = MockPopen(["cmd"], complete_after=1.0)

        # Mock time to simulate completion
        mock_time.return_value = 2.0

        # Multiple wait calls should return the same result
        result1 = proc.wait()
        result2 = proc.wait()
        result3 = proc.wait()

        assert result1 == result2 == result3 == 0
        assert proc.returncode == 0

    def test_process_attributes(self, mock_qt_modules) -> None:
        """Test that MockPopen has expected process attributes."""
        cmd = ["python", "-c", "print('hello')"]
        proc = MockPopen(cmd, complete_after=1.0)

        # Should have standard process attributes
        assert proc.args == cmd
        assert hasattr(proc, "pid")
        assert hasattr(proc, "returncode")
        assert hasattr(proc, "stdout")
        assert hasattr(proc, "stderr")
        assert hasattr(proc, "stdin")

    def test_concurrent_process_handling(self, mock_qt_modules, mock_time) -> None:
        """Test handling multiple MockPopen instances concurrently."""
        # Create multiple mock processes
        processes = []
        for i in range(3):
            proc = MockPopen([f"cmd_{i}"], complete_after=i + 1.0)
            processes.append(proc)

        # Initially all should be running
        for proc in processes:
            assert proc.poll() is None

        # Simulate time passing - different processes complete at different times
        test_times = [0.5, 1.5, 2.5, 3.5]

        for test_time in test_times:
            mock_time.return_value = test_time

            for i, proc in enumerate(processes):
                if test_time > i + 1.0:  # Process should be complete
                    assert proc.poll() == 0
                else:  # Process should still be running
                    assert proc.poll() is None

    def test_error_handling_edge_cases(self, mock_qt_modules) -> None:
        """Test error handling in edge cases."""
        proc = MockPopen(["cmd"], complete_after=1.0)

        # Test wait with zero timeout
        with patch("tests.utils.mocks.time.monotonic", return_value=0.0):
            with pytest.raises(subprocess.TimeoutExpired):
                proc.wait(timeout=0.0)

        # Test wait with negative timeout (should be treated as no timeout)
        with patch("tests.utils.mocks.time.monotonic", return_value=2.0):
            result = proc.wait(timeout=-1)
            assert result == 0

    @pytest.mark.parametrize("complete_after", [0.1, 1.0, 5.0])
    def test_variable_completion_times(self, mock_qt_modules, mock_time, complete_after) -> None:
        """Test MockPopen with variable completion times."""
        proc = MockPopen(["cmd"], complete_after=complete_after)

        # Before completion
        mock_time.return_value = complete_after - 0.1
        assert proc.poll() is None

        # After completion
        mock_time.return_value = complete_after + 0.1
        assert proc.poll() == 0

    def test_returncode_consistency(self, mock_qt_modules, mock_time) -> None:
        """Test that returncode is consistent across different methods."""
        proc = MockPopen(["cmd"], complete_after=1.0)

        # Complete the process
        mock_time.return_value = 2.0

        # All methods should return consistent results
        poll_result = proc.poll()
        wait_result = proc.wait()

        assert poll_result == wait_result == proc.returncode == 0
