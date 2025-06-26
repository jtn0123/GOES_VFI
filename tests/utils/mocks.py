# tests/utils/mocks.py
"""Reusable mocks for testing external process interactions."""

import io  # Import io
import pathlib
import subprocess
import time
from typing import Callable, List, Optional, Tuple
from unittest.mock import MagicMock

# Add imports for creating PNG test images
import numpy as np
from PIL import Image


# A helper function to create a valid minimal PNG for testing
def create_test_png(path: pathlib.Path, size: Tuple[int, int] = (10, 10)):
    """Create a minimal valid PNG file at the given path."""
    # Create a small black image
    img_array = np.zeros((size[1], size[0], 3), dtype=np.uint8)
    img = Image.fromarray(img_array)

    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    # Save as PNG
    img.save(path, format="PNG")
    return path


# Placeholder for future mock implementations
class MockSubprocessResult:
    """Mimics the result of subprocess.run."""

    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout.encode()  # Store as bytes like subprocess does
        self.stderr = stderr.encode()

    def check_returncode(self):
        """Raises CalledProcessError if returncode is non-zero."""
        if self.returncode != 0:
            raise subprocess.CalledProcessError(self.returncode, self.args, output=self.stdout, stderr=self.stderr)


class MockPopen:
    """Mimics ``subprocess.Popen`` for testing purposes."""

    def __init__(
        self,
        args: List[str],
        returncode: int = 0,
        stdout: bytes = b"",
        stderr: bytes = b"",
        stdin_write_limit: Optional[int] = None,
        complete_after: float = 0.0,
    ):
        self.args = args
        self._desired_returncode = returncode
        self.returncode: Optional[int] = None
        self._stdout_data = stdout
        self._stderr_data = stderr
        self._start_time = time.monotonic()
        self._complete_after = float(complete_after)
        self._terminated = False
        # Use a plain MagicMock for stdin, allowing .write to be created
        self.stdin = MagicMock()
        # Replace MagicMock for stdout/stderr with StringIO for iteration
        # Note: We use BytesIO if text=False, StringIO if text=True (default in _run_ffmpeg_command)
        self.stdout = (
            io.BytesIO(self._stdout_data) if isinstance(self._stdout_data, bytes) else io.StringIO(self._stdout_data)
        )
        self.stderr = (
            io.BytesIO(self._stderr_data) if isinstance(self._stderr_data, bytes) else io.StringIO(self._stderr_data)
        )
        self.pid = 12345

        # Remove simulation of read attribute, StringIO handles it
        # self.stdout.read.return_value = self._stdout_data
        # self.stderr.read.return_value = self._stderr_data

        # Simulate stdin writing and potential BrokenPipeError
        self._stdin_bytes_written = 0
        self._stdin_write_limit = stdin_write_limit
        self.stdin.write.side_effect = self._handle_stdin_write
        self.stdin.close = MagicMock()

    def _handle_stdin_write(self, data: bytes):
        if self._stdin_write_limit is not None and (self._stdin_bytes_written + len(data)) > self._stdin_write_limit:
            raise BrokenPipeError("Mock Popen: stdin write limit exceeded")
        self._stdin_bytes_written += len(data)
        # In a real scenario, the process would consume this data.
        # For the mock, we just track the amount written.

    def _check_completion(self) -> bool:
        """Return True if the process has reached its completion time."""
        if self.returncode is not None:
            return True
        if (time.monotonic() - self._start_time) >= self._complete_after:
            self.returncode = self._desired_returncode
            return True
        return False

    def wait(self, timeout: Optional[float] = None) -> int:
        """Simulates waiting for the process to terminate."""
        if self._check_completion():
            return self.returncode or 0

        if timeout is not None:
            elapsed = time.monotonic() - self._start_time
            remaining = self._complete_after - elapsed
            if remaining > timeout:
                raise subprocess.TimeoutExpired(self.args, timeout)

        self.returncode = self._desired_returncode
        return self.returncode

    def communicate(self, input: Optional[bytes] = None, timeout: Optional[float] = None) -> Tuple[bytes, bytes]:
        """Simulates communicating with the process."""
        if input:
            self.stdin.write(input)
        self.stdin.close()
        if timeout is not None:
            try:
                self.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                raise  # pylint: disable=try-except-raise
        else:
            self.wait()
        return self._stdout_data, self._stderr_data

    def poll(self) -> Optional[int]:
        """Simulates checking if the process has terminated."""
        if self._check_completion():
            return self.returncode
        return None

    def terminate(self) -> None:
        """Simulate sending SIGTERM to the process."""
        if self.returncode is None:
            self.returncode = -15
            self._terminated = True

    def kill(self) -> None:
        """Simulate forcefully killing the process."""
        if self.returncode is None:
            self.returncode = -9
            self._terminated = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Ensure stdin is closed, etc., if needed
        if self.stdin and not self.stdin.closed:
            self.stdin.close()
        # No specific cleanup needed for this simple mock


# --- Mock Factory Functions ---


def create_mock_subprocess_run(
    expected_command: Optional[List[str]] = None,
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
    output_file_to_create: Optional[pathlib.Path] = None,
    side_effect: Optional[Exception] = None,
) -> Callable:
    """Creates a mock function to replace subprocess.run."""

    def mock_run(*args, **kwargs):
        # Extract command list (first argument)
        cmd_list = args[0]
        if not isinstance(cmd_list, list):
            cmd_list = list(cmd_list)  # Ensure it's a list for comparison

        # Optional: Assert the command matches expectations
        if expected_command:
            assert cmd_list == expected_command, (
                "Mock subprocess.run called with unexpected command.\n"
                f"Expected: {expected_command}\n"
                f"Got:      {cmd_list}"
            )

        # Simulate output file creation first IF return code is 0
        # Check if this is a RIFE command by looking for -o flag
        output_path = None
        if "-o" in cmd_list:
            try:
                o_index = cmd_list.index("-o")
                if o_index + 1 < len(cmd_list):
                    output_path = pathlib.Path(cmd_list[o_index + 1])
            except ValueError:
                pass

        # Use the specified output path if found, otherwise use the provided one
        file_to_create = output_path or output_file_to_create

        if file_to_create and returncode == 0:
            try:
                # Create a valid PNG file instead of just touching it
                # create_test_png(file_to_create)
                # FIX: Just create a dummy file to avoid calling Image.fromarray via create_test_png
                file_to_create.parent.mkdir(parents=True, exist_ok=True)
                file_to_create.touch()
                print(f"Mock run created dummy file: {file_to_create}")  # Debug print
            except Exception as e:
                print(f"Mock run failed to create file {file_to_create}: {e}")

        # Handle side effect (e.g., raise exception)
        if side_effect:
            # Only raise if it's actually an exception instance
            if isinstance(side_effect, BaseException):
                raise side_effect
            # If it's callable, call it (though less common for run)
            elif callable(side_effect):
                return side_effect(*args, **kwargs)
            # Otherwise, maybe it's an iterator? (Less likely for run)
            # else: return next(side_effect)

        # Return a result object
        result = MockSubprocessResult(returncode=returncode, stdout=stdout, stderr=stderr)
        result.args = cmd_list
        return result

    return mock_run


def create_mock_popen(
    expected_command: Optional[List[str]] = None,
    returncode: int = 0,
    stdout: bytes = b"",
    stderr: bytes = b"",
    stdin_write_limit: Optional[int] = None,
    output_file_to_create: Optional[pathlib.Path] = None,
    side_effect: Optional[Exception] = None,
    complete_after: float = 0.0,
) -> Callable:
    """Creates a mock function that returns a MockPopen instance."""

    def mock_popen_factory(*args, **kwargs):
        # Extract command list (first argument)
        cmd_list = args[0]
        if not isinstance(cmd_list, list):
            cmd_list = list(cmd_list)  # Ensure it's a list for comparison

        # Optional: Assert the command matches expectations
        if expected_command:
            assert cmd_list == expected_command, (
                "Mock subprocess.Popen called with unexpected command.\n"
                f"Expected: {expected_command}\n"
                f"Got:      {cmd_list}"
            )

        # Handle side effect (e.g., raise exception *during Popen call*)
        if side_effect:
            raise side_effect

        mock_instance = MockPopen(
            args=cmd_list,
            returncode=returncode,
            stdout=stdout,
            stderr=stderr,
            stdin_write_limit=stdin_write_limit,
            complete_after=complete_after,
        )

        original_wait = mock_instance.wait

        def wait_with_file_creation(*wait_args, **wait_kwargs):
            res = original_wait(*wait_args, **wait_kwargs)
            if output_file_to_create and res == 0:
                try:
                    # Create a valid MP4-like file or PNG if it's a path with .png extension
                    if str(output_file_to_create).endswith(".png"):
                        create_test_png(output_file_to_create)
                    else:
                        # For MP4 or other files, create a dummy file with some content
                        output_file_to_create.parent.mkdir(parents=True, exist_ok=True)
                        # Write dummy data instead of touch for Popen mocks (ffmpeg)
                        with open(output_file_to_create, "wb") as f:
                            f.write(b"dummy ffmpeg output")
                    print(f"Mock Popen created file: {output_file_to_create}")  # Debug print
                except Exception as e:
                    print(f"Mock Popen failed to create file {output_file_to_create}: {e}")
            return res

        mock_instance.wait = wait_with_file_creation

        return mock_instance

    return mock_popen_factory


def create_mock_colourise(
    expected_input: Optional[str] = None,
    expected_output: Optional[str] = None,
    expected_res_km: Optional[int] = None,
    output_file_to_create: Optional[pathlib.Path] = None,
    side_effect: Optional[Exception] = None,
) -> Callable:
    """Creates a mock function to replace goesvfi.sanchez.runner.colourise."""

    def mock_colourise(input_path: str, output_path: str, res_km: int):
        # Assert arguments
        if expected_input:
            assert input_path == expected_input, f"Mock colourise: Expected input {expected_input}, got {input_path}"
        if expected_output:
            assert (
                output_path == expected_output
            ), f"Mock colourise: Expected output {expected_output}, got {output_path}"
        if expected_res_km:
            assert res_km == expected_res_km, f"Mock colourise: Expected res_km {expected_res_km}, got {res_km}"

        # Handle side effect
        if side_effect:
            raise side_effect

        # Simulate output file creation
        output_file = pathlib.Path(output_path)
        if output_file_to_create:  # Allow specifying a different path if needed, otherwise use output_path
            output_file = output_file_to_create

        # Create a valid PNG instead of just touching the file
        create_test_png(output_file)
        print(f"Mock colourise created valid PNG file: {output_file}")  # Add print for debugging tests

    return mock_colourise


# --- S3Store Mock ---


class MockS3Store:
    """Comprehensive mock for S3Store that implements all required methods."""

    def __init__(self, bucket_name: str = "noaa-goes", *args, **kwargs):
        self.bucket_name = bucket_name
        self._closed = False
        self._client = MagicMock()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def close(self):
        self._closed = True

    async def _get_s3_client(self):
        """Mock S3 client creation."""
        return self._client

    def _get_bucket_and_key(self, timestamp, satellite):
        """Mock bucket and key extraction."""
        return self.bucket_name, f"mock/key/{timestamp}/{satellite}"

    async def exists(self, timestamp, satellite=None):
        """Mock file existence check."""
        return True

    async def download(self, timestamp, satellite, local_path):
        """Mock file download."""
        # Create a dummy file at the local path
        local_path = pathlib.Path(local_path)
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(b"mock s3 download content")
        return local_path

    async def check_file_exists(self, timestamp, satellite):
        """Mock file existence check."""
        return True

    async def download_file(self, timestamp, satellite, local_path):
        """Mock file download."""
        return await self.download(timestamp, satellite, local_path)

    async def get_file_url(self, timestamp, satellite):
        """Mock URL generation."""
        return f"https://s3.amazonaws.com/{self.bucket_name}/mock/key/{timestamp}/{satellite}"

    def session_kwargs(self):
        """Mock session kwargs."""
        return {"config": MagicMock()}


class MockCDNStore:
    """Comprehensive mock for CDNStore."""

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def exists(self, timestamp, satellite=None):
        return True

    async def download(self, timestamp, satellite, local_path):
        local_path = pathlib.Path(local_path)
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(b"mock cdn download content")
        return local_path

    async def download_file(self, key, local_path):
        """Mock download_file method for compatibility."""
        local_path = pathlib.Path(local_path)
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(b"mock cdn download_file content")
        return local_path
