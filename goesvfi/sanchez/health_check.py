"""Sanchez health check and monitoring system.

This module provides comprehensive health checks for the Sanchez
external tool, including binary validation, dependency checks,
and runtime monitoring.
"""

import asyncio
import asyncio.subprocess
from collections.abc import Callable
import contextlib
from dataclasses import dataclass, field
from datetime import datetime
import os
from pathlib import Path
import platform
import subprocess
import tempfile
import time
from typing import Any

from PIL import Image

from goesvfi.exceptions import ConfigurationError, ExternalToolError
from goesvfi.utils import config
from goesvfi.utils.log import get_logger

LOGGER = get_logger(__name__)


@dataclass
class SanchezHealthStatus:
    """Container for Sanchez health check results."""

    # Basic checks
    binary_exists: bool = False
    binary_executable: bool = False
    binary_path: Path | None = None
    binary_size: int = 0
    binary_modified: datetime | None = None

    # Dependency checks
    resources_exist: bool = False
    gradient_files: list[str] = field(default_factory=list)
    missing_resources: list[str] = field(default_factory=list)

    # Runtime checks
    can_execute: bool = False
    execution_time: float = 0.0
    version_info: str | None = None
    help_available: bool = False

    # System checks
    temp_dir_writable: bool = False
    memory_available_mb: int = 0
    disk_space_available_mb: int = 0

    # Error information
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_healthy(self) -> bool:
        """Check if Sanchez is healthy and ready to use."""
        return (
            self.binary_exists
            and self.binary_executable
            and self.resources_exist
            and self.can_execute
            and self.temp_dir_writable
            and len(self.errors) == 0
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging/serialization."""
        return {
            "healthy": self.is_healthy,
            "binary": {
                "exists": self.binary_exists,
                "executable": self.binary_executable,
                "path": str(self.binary_path) if self.binary_path else None,
                "size": self.binary_size,
                "modified": (self.binary_modified.isoformat() if self.binary_modified else None),
            },
            "dependencies": {
                "resources_exist": self.resources_exist,
                "gradient_files": self.gradient_files,
                "missing_resources": self.missing_resources,
            },
            "runtime": {
                "can_execute": self.can_execute,
                "execution_time": self.execution_time,
                "version": self.version_info,
                "help_available": self.help_available,
            },
            "system": {
                "temp_writable": self.temp_dir_writable,
                "memory_mb": self.memory_available_mb,
                "disk_mb": self.disk_space_available_mb,
            },
            "errors": self.errors,
            "warnings": self.warnings,
        }


class SanchezHealthChecker:
    """Performs health checks on the Sanchez installation."""

    def __init__(self) -> None:
        """Initialize the health checker."""
        self.platform_key = (platform.system(), platform.machine())
        self.sanchez_dir = config.get_sanchez_bin_dir()

    def _get_binary_path(self) -> Path | None:
        """Get the expected Sanchez binary path for this platform."""
        lookup = {
            ("Darwin", "x86_64"): self.sanchez_dir / "osx-x64" / "Sanchez",
            ("Darwin", "arm64"): self.sanchez_dir / "osx-x64" / "Sanchez",
            ("Windows", "AMD64"): self.sanchez_dir / "win-x64" / "Sanchez.exe",
        }

        return lookup.get(self.platform_key)

    def check_binary(self, status: SanchezHealthStatus) -> None:
        """Check if the Sanchez binary exists and is executable."""
        binary_path = self._get_binary_path()

        if binary_path is None:
            status.errors.append(f"Sanchez not supported on platform: {self.platform_key}")
            return

        status.binary_path = binary_path

        # Check existence
        if not binary_path.exists():
            status.errors.append(f"Sanchez binary not found at: {binary_path}")
            return

        status.binary_exists = True

        # Check file properties
        try:
            stat = binary_path.stat()
            status.binary_size = stat.st_size
            status.binary_modified = datetime.fromtimestamp(stat.st_mtime)

            # Check if executable
            if os.access(binary_path, os.X_OK):
                status.binary_executable = True
            else:
                status.errors.append(f"Sanchez binary is not executable: {binary_path}")

        except OSError as e:
            status.errors.append(f"Error checking binary properties: {e}")

    def check_resources(self, status: SanchezHealthStatus) -> None:
        """Check if required Sanchez resources exist."""
        if not status.binary_path:
            return

        binary_dir = status.binary_path.parent
        resources_dir = binary_dir / "Resources"

        # Check main resources directory
        if not resources_dir.exists():
            status.errors.append(f"Resources directory not found: {resources_dir}")
            return

        # Check for gradient files
        gradients_dir = resources_dir / "Gradients"
        if gradients_dir.exists():
            gradient_files = list(gradients_dir.glob("*.json"))
            status.gradient_files = [f.name for f in gradient_files]

            # Check for essential gradient
            if not (gradients_dir / "Atmosphere.json").exists():
                status.warnings.append("Default Atmosphere.json gradient not found")
        else:
            status.missing_resources.append("Gradients directory")

        # Check for other resources
        expected_resources = [
            "Overlays",
            "Palettes",
        ]

        for resource in expected_resources:
            if not (resources_dir / resource).exists():
                status.missing_resources.append(resource)

        # Overall resources check
        status.resources_exist = len(status.gradient_files) > 0 and len(status.missing_resources) == 0

    def check_execution(self, status: SanchezHealthStatus) -> None:
        """Check if Sanchez can actually execute."""
        if not status.binary_executable:
            return

        binary_path = status.binary_path
        if binary_path is None:
            return
        binary_dir = binary_path.parent

        # Try to get version/help
        try:
            # First try --version
            start_time = time.time()
            result = subprocess.run(
                [str(binary_path), "--version"],
                capture_output=True,
                text=True,
                timeout=5,
                cwd=binary_dir,
                check=False,
            )
            elapsed = time.time() - start_time

            if result.returncode == 0:
                status.version_info = result.stdout.strip()
                status.execution_time = elapsed
                status.can_execute = True
            else:
                # Try --help as fallback
                result = subprocess.run(
                    [str(binary_path), "--help"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    cwd=binary_dir,
                    check=False,
                )

                if result.returncode == 0 or "Usage:" in result.stdout:
                    status.help_available = True
                    status.can_execute = True
                    # Extract version from help if possible
                    for line in result.stdout.split("\n"):
                        if "version" in line.lower():
                            status.version_info = line.strip()
                            break
                else:
                    status.errors.append(f"Sanchez execution failed: {result.stderr}")

        except subprocess.TimeoutExpired:
            status.errors.append("Sanchez execution timed out (>5 seconds)")
        except (OSError, ValueError) as e:
            status.errors.append(f"Error executing Sanchez: {e}")

    def check_system_resources(self, status: SanchezHealthStatus) -> None:
        """Check system resources (memory, disk space, temp directory)."""
        # Check temp directory
        try:
            with tempfile.NamedTemporaryFile(dir=tempfile.gettempdir(), delete=True) as tmp:
                tmp.write(b"test")
                tmp.flush()
                status.temp_dir_writable = True
        except OSError:
            status.errors.append("Cannot write to temporary directory")

        # Check available memory
        try:
            import psutil

            memory = psutil.virtual_memory()
            status.memory_available_mb = memory.available // (1024 * 1024)

            # Warn if less than 500MB available
            if status.memory_available_mb < 500:
                status.warnings.append(f"Low memory available: {status.memory_available_mb}MB")

        except ImportError:
            # psutil not available, try platform-specific
            status.warnings.append("psutil not available for memory checking")
        except Exception as e:
            status.warnings.append(f"Could not check memory: {e}")

        # Check disk space
        try:
            if status.binary_path:
                stat = os.statvfs(status.binary_path.parent)
                # Available space in MB
                status.disk_space_available_mb = (stat.f_bavail * stat.f_frsize) // (1024 * 1024)

                # Warn if less than 100MB
                if status.disk_space_available_mb < 100:
                    status.warnings.append(f"Low disk space: {status.disk_space_available_mb}MB")
        except (OSError, AttributeError):
            # Windows doesn't have statvfs
            try:
                import shutil

                if status.binary_path:
                    _total, _used, free = shutil.disk_usage(status.binary_path.parent)
                    status.disk_space_available_mb = free // (1024 * 1024)
            except Exception as e:
                status.warnings.append(f"Could not check disk space: {e}")

    def run_health_check(self) -> SanchezHealthStatus:
        """Run a complete health check on Sanchez.

        Returns:
            SanchezHealthStatus with all check results
        """
        LOGGER.info("Starting Sanchez health check...")
        status = SanchezHealthStatus()

        # Run all checks
        self.check_binary(status)
        self.check_resources(status)
        self.check_execution(status)
        self.check_system_resources(status)

        # Log results
        if status.is_healthy:
            LOGGER.info("Sanchez health check PASSED")
        else:
            LOGGER.error("Sanchez health check FAILED: %s", status.errors)
            if status.warnings:
                LOGGER.warning("Warnings: %s", status.warnings)

        return status

    async def run_health_check_async(self) -> SanchezHealthStatus:
        """Run health check asynchronously."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.run_health_check)


class SanchezProcessMonitor:
    """Monitor Sanchez process execution with progress tracking."""

    def __init__(self) -> None:
        """Initialize the process monitor."""
        self.current_process: asyncio.subprocess.Process | None = None
        self.start_time: float | None = None
        self.input_file: Path | None = None
        self.output_file: Path | None = None
        self.progress_callback: Callable[[str, float], None] | None = None
        self.is_cancelled: bool = False

    def set_progress_callback(self, callback: Callable[[str, float], None]) -> None:
        """Set a callback for progress updates.

        The callback should accept (current_step: str, progress: float)
        where progress is 0.0 to 1.0.
        """
        self.progress_callback = callback

    def _report_progress(self, step: str, progress: float) -> None:
        """Report progress if callback is set."""
        if self.progress_callback and not self.is_cancelled:
            try:
                self.progress_callback(step, progress)
            except Exception as e:
                LOGGER.exception("Error in progress callback: %s", e)

    async def run_sanchez_monitored(
        self,
        input_path: Path,
        output_path: Path,
        res_km: int = 4,
        timeout: int = 120,
        _memory_limit_mb: int | None = None,
    ) -> Path:
        """Run Sanchez with monitoring and progress tracking.

        Args:
            input_path: Input image path
            output_path: Output image path
            res_km: Resolution in km/pixel
            timeout: Maximum execution time in seconds
            memory_limit_mb: Optional memory limit in MB

        Returns:
            Path to the output file

        Raises:
            ExternalToolError: If Sanchez execution fails
            TimeoutError: If execution exceeds timeout
        """
        self.input_file = input_path
        self.output_file = output_path
        self.is_cancelled = False

        # First do a health check
        LOGGER.info("Performing Sanchez health check before execution...")
        health_checker = SanchezHealthChecker()
        health_status = health_checker.run_health_check()

        if not health_status.is_healthy:
            msg = f"Sanchez is not healthy: {health_status.errors}"
            raise ConfigurationError(msg)

        # Verify input file
        if not input_path.exists():
            msg = f"Input file not found: {input_path}"
            raise FileNotFoundError(msg)

        input_size = input_path.stat().st_size
        LOGGER.info(
            "Processing %s (%.1fMB) at %skm/pixel resolution", input_path.name, input_size / 1024 / 1024, res_km
        )

        # Create output directory
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Build command
        binary_path = health_status.binary_path
        if binary_path is None:
            msg = "Sanchez binary path not found"
            raise ConfigurationError(msg)
        binary_dir = binary_path.parent

        cmd = [
            str(binary_path),
            "geostationary",
            "-s",
            str(input_path),
            "-o",
            str(output_path),
            "-r",
            str(res_km),
        ]

        # Add gradient if available
        gradient_path = binary_dir / "Resources" / "Gradients" / "Atmosphere.json"
        if gradient_path.exists():
            cmd.extend(["-c", "0.0-1.0", "-g", str(gradient_path)])

        # Monitor execution
        self._report_progress("Starting Sanchez", 0.0)
        self.start_time = time.time()

        try:
            # Start process
            self.current_process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=binary_dir,
            )

            # Monitor with timeout
            monitor_task = asyncio.create_task(self._monitor_process())

            try:
                # Wait for completion with timeout
                if self.current_process is None:
                    msg = "Process not started"
                    raise RuntimeError(msg)
                _stdout, stderr = await asyncio.wait_for(self.current_process.communicate(), timeout=timeout)

                # Cancel monitor
                monitor_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await monitor_task

                # Check result
                if self.current_process is None:
                    msg = "Process not started"
                    raise RuntimeError(msg)
                if self.current_process.returncode != 0:
                    raise ExternalToolError(
                        tool_name="Sanchez",
                        message=f"Sanchez failed with exit code {self.current_process.returncode}",
                        stderr=(stderr.decode("utf-8", errors="replace") if stderr else None),
                    )

                # Verify output
                if not output_path.exists():
                    raise ExternalToolError(
                        tool_name="Sanchez",
                        message="Sanchez completed but output file not found",
                    )

                output_size = output_path.stat().st_size
                elapsed = time.time() - self.start_time

                LOGGER.info(
                    f"Sanchez completed successfully in {elapsed:.1f}s. Output: {output_size / 1024 / 1024:.1f}MB"
                )

                self._report_progress("Complete", 1.0)
                return output_path

            except TimeoutError:
                # Kill the process
                if self.current_process:
                    try:
                        self.current_process.terminate()
                        await asyncio.sleep(2)
                        if self.current_process.returncode is None:
                            self.current_process.kill()
                    except ProcessLookupError:
                        pass

                msg = f"Sanchez execution timed out after {timeout} seconds"
                raise TimeoutError(msg)

        except Exception:
            self._report_progress("Error", 0.0)
            raise
        finally:
            self.current_process = None

    async def _monitor_process(self) -> None:
        """Monitor the running process and report progress."""
        check_interval = 0.5  # Check every 500ms
        last_size = 0
        no_progress_count = 0

        while self.current_process and not self.is_cancelled:
            try:
                # Check if process is still running
                if self.current_process.returncode is not None:
                    break

                # Estimate progress based on output file growth
                if self.output_file and self.output_file.exists():
                    current_size = self.output_file.stat().st_size

                    if current_size > last_size:
                        # Progress is happening
                        no_progress_count = 0
                        # Estimate progress (rough heuristic)
                        estimated_progress = min(
                            0.9,
                            current_size / (self.input_file.stat().st_size * 2 if self.input_file else 1000000),
                        )
                        self._report_progress("Processing", estimated_progress)
                    else:
                        no_progress_count += 1

                    last_size = current_size
                else:
                    # Output file doesn't exist yet
                    self._report_progress("Initializing", 0.1)

                # Check memory usage if psutil available
                try:
                    import psutil

                    if self.current_process.pid:
                        process = psutil.Process(self.current_process.pid)
                        memory_mb = process.memory_info().rss / 1024 / 1024

                        if memory_mb > 1000:  # Warn if > 1GB
                            LOGGER.warning("Sanchez using %.0fMB of memory", memory_mb)
                except (ImportError, psutil.NoSuchProcess):
                    pass

                await asyncio.sleep(check_interval)

            except Exception as e:
                LOGGER.exception("Error monitoring Sanchez process: %s", e)
                break

    def cancel(self) -> None:
        """Cancel the current Sanchez process."""
        self.is_cancelled = True
        if self.current_process:
            with contextlib.suppress(ProcessLookupError):
                self.current_process.terminate()


def validate_sanchez_input(input_path: Path) -> tuple[bool, str]:
    """Validate that an input file is suitable for Sanchez.

    Args:
        input_path: Path to input image

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check file exists
    if not input_path.exists():
        return False, f"Input file not found: {input_path}"

    # Check file size
    size = input_path.stat().st_size
    if size == 0:
        return False, "Input file is empty"
    if size > 500 * 1024 * 1024:  # 500MB
        return False, f"Input file too large: {size / 1024 / 1024:.1f}MB (max 500MB)"

    # Check if it's an image
    try:
        with Image.open(input_path) as img:
            # Check format
            if img.format not in {"PNG", "JPEG", "TIFF"}:
                return False, f"Unsupported image format: {img.format}"

            # Check dimensions
            width, height = img.size
            if width < 100 or height < 100:
                return False, f"Image too small: {width}x{height} (min 100x100)"
            if width > 10000 or height > 10000:
                return False, f"Image too large: {width}x{height} (max 10000x10000)"

            # Check mode
            if img.mode not in {"L", "RGB", "RGBA"}:
                return False, f"Unsupported image mode: {img.mode}"

    except Exception as e:
        return False, f"Could not read image: {e}"

    return True, "OK"


# Convenience function
def check_sanchez_health() -> bool:
    """Quick health check for Sanchez.

    Returns:
        True if Sanchez is healthy and ready to use
    """
    checker = SanchezHealthChecker()
    status = checker.run_health_check()
    return status.is_healthy
