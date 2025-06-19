from pathlib import Path  # Import Path
from typing import Any, Callable, Optional

"""sanchez_processor.py

Provides the SanchezProcessor class, an ImageProcessor implementation that
invokes the external Sanchez tool for advanced image processing in the GOES_VFI pipeline.
"""

import asyncio
import os
import subprocess
import time
from typing import NoReturn  # Import NoReturn

import numpy as np
from PIL import Image

from goesvfi.exceptions import ConfigurationError, ExternalToolError
from goesvfi.sanchez.health_check import (
    SanchezHealthChecker,
    SanchezProcessMonitor,
    validate_sanchez_input,
)
from goesvfi.utils import log
from goesvfi.utils.security import InputValidator, SecurityError, secure_subprocess_call

from .image_processing_interfaces import ImageData, ImageProcessor

LOGGER = log.get_logger(__name__)

class SanchezProcessor(ImageProcessor):
    pass
    """ImageProcessor implementation for running the external Sanchez tool.

    This class processes images by invoking the Sanchez executable as a subprocess,
    passing input and output file paths and additional arguments. It is used for
    advanced reprojection or enhancement steps in the GOES_VFI pipeline.

    Only the process method is implemented; load, crop, and save are not supported.
    """

    def __init__(self,
    temp_dir: Path,
    progress_callback: Optional[Callable[[str, float], None]] = None,
    ):
        """
        Initializes the SanchezProcessor with a temporary directory.

        Args:
            temp_dir: The path to a temporary directory for Sanchez to use.
            progress_callback: Optional callback for progress updates (step, progress)
        """
        self._temp_dir = temp_dir  # pylint: disable=attribute-defined-outside-init
        os.makedirs(self._temp_dir, exist_ok=True)  # Ensure directory exists
        self._progress_callback = progress_callback  # pylint: disable=attribute-defined-outside-init
        self._health_status_cached = None  # pylint: disable=attribute-defined-outside-init
        self._last_health_check = 0.0  # pylint: disable=attribute-defined-outside-init
        self._health_check_interval = 300  # Re-check health every 5 minutes  # pylint: disable=attribute-defined-outside-init

    def process(self, image_data: ImageData, **kwargs: Any) -> ImageData:
        """Process image data using the external Sanchez tool.

        Args:
            image_data (ImageData): The input ImageData object.
            **kwargs: Additional parameters to pass to the Sanchez tool as command-line arguments.
            Special kwargs:
                         - use_monitoring (bool): Use async monitoring (default: False)
            - timeout (int): Timeout in seconds (default: 120)
            - memory_limit_mb (int): Memory limit in MB (optional)

        Returns:
            ImageData: A new ImageData object containing the processed image.

        Raises:
            ConfigurationError: If the Sanchez executable is not found for the current OS.
            ExternalToolError: If the Sanchez command fails to execute or returns an error.
        """
        # Extract special kwargs
        use_monitoring = kwargs.pop("use_monitoring", False)
        timeout = kwargs.pop("timeout", 120)
        memory_limit_mb = kwargs.pop("memory_limit_mb", None)

        if use_monitoring:
            pass
            # Use async monitoring
            return asyncio.run(
            self._process_async(image_data, timeout, memory_limit_mb, **kwargs)
            )
        else:
            # Use traditional synchronous processing
            return self._process_sync(image_data, timeout, **kwargs)

    async def _process_async(
    self,
    image_data: ImageData,
    timeout: int,
    memory_limit_mb: Optional[int],
    **kwargs: Any,
    ) -> ImageData:
        """Process image data asynchronously with monitoring."""
        input_file = None
        output_file = None

        try:
            # Save input image
            original_filename = self._get_original_filename(image_data)
            input_file_path = self._temp_dir / Path(original_filename).name

            img = Image.fromarray(image_data.image_data)
            img.save(input_file_path)
            input_file = input_file_path

            # Create output path
            output_file_path = (
            self._temp_dir
            / f"{Path(original_filename).stem}_sanchez_output_{int(time.time())}.png"
            )
            output_file = output_file_path

            # Use process monitor
            monitor = SanchezProcessMonitor()
            if self._progress_callback:
                pass
                monitor.set_progress_callback(self._progress_callback)

            # Extract res_km from kwargs
            res_km = kwargs.get("res_km", 4)
            if isinstance(res_km, (int, float)):
                pass
                res_km = int(res_km) if res_km == int(res_km) else res_km
            else:
                pass
                res_km = 4  # Default

            # Run with monitoring
            await monitor.run_sanchez_monitored(
            input_path=input_file_path,
            output_path=output_file_path,
            res_km=res_km,
            timeout=timeout,
            memory_limit_mb=memory_limit_mb,
            )

            # Load result
            return self._load_output(output_file_path, image_data)

        finally:
            # Cleanup
            if input_file and input_file.exists():
                pass
                input_file.unlink()
            if output_file and output_file.exists():
                pass
                output_file.unlink()

    def _process_sync(self, image_data: ImageData, timeout: int, **kwargs: Any
    ) -> ImageData:
        """Process image data synchronously (original implementation)."""
        input_file = None
        output_file = None

        try:
            # Prepare input file for Sanchez
            input_file = self._prepare_input_file(image_data)

            # Ensure Sanchez is healthy and ready
            sanchez_executable = self._ensure_sanchez_health()

            # Validate input before processing
            self._validate_sanchez_input(input_file)

            # Prepare output file path
            output_file = self._prepare_output_file(input_file)

            # Build and execute Sanchez command
            self._execute_sanchez_command(sanchez_executable, input_file, output_file, **kwargs)

            # Load and return processed image
            return self._load_processed_image(output_file, image_data)

        finally:
            self._cleanup_temporary_files(input_file, output_file)

    def _prepare_input_file(self, image_data: ImageData) -> Path:
        """Prepare input file for Sanchez processing with security validation."""
        original_filename = self._get_original_filename(image_data)
        LOGGER.info("Using original filename for Sanchez: %s", original_filename)

        try:
            # Validate and sanitize the filename
            sanitized_filename = InputValidator.sanitize_filename(original_filename)
            InputValidator.validate_file_path(
            sanitized_filename,
            allowed_extensions=InputValidator.ALLOWED_IMAGE_EXTENSIONS
            )
        except SecurityError as e:
            pass
            LOGGER.warning("Security validation failed for filename '%s': %s", original_filename, e)
            # Use a safe default filename
            sanitized_filename = f"abi_image_{int(time.time())}.png"

        input_file_path = self._temp_dir / sanitized_filename
        LOGGER.debug("Saving temporary input for Sanchez at: %s", input_file_path)

        img = Image.fromarray(image_data.image_data)
        img.save(input_file_path)

        return input_file_path

    def _ensure_sanchez_health(self) -> str:
        """Ensure Sanchez is healthy and return executable path."""
        current_time = time.time()

        if (
        self._health_status_cached is None
        or (current_time - self._last_health_check) > self._health_check_interval
        ):
            pass
            LOGGER.info("Performing Sanchez health check...")
            health_checker = SanchezHealthChecker()
            self._health_status_cached = health_checker.run_health_check()  # pylint: disable=attribute-defined-outside-init
            self._last_health_check = current_time  # pylint: disable=attribute-defined-outside-init

            if not self._health_status_cached.is_healthy:
                pass
                errors = "; ".join(self._health_status_cached.errors)
                raise ConfigurationError(f"Sanchez health check failed: {errors}")

        sanchez_executable = self._health_status_cached.binary_path
        if not sanchez_executable:
            pass
            raise ConfigurationError("Sanchez executable path not found in health check")

        return sanchez_executable

    def _validate_sanchez_input(self, input_file_path: Path) -> None:
        """Validate input file for Sanchez processing."""
        is_valid, error_msg = validate_sanchez_input(input_file_path)
        if not is_valid:
            pass
            raise ExternalToolError(
            tool_name="Sanchez",
            message=f"Invalid input for Sanchez: {error_msg}",
            )

    def _prepare_output_file(self, input_file_path: Path) -> Path:
        """Prepare output file path for Sanchez with security validation."""
        original_filename = input_file_path.name

        try:
            # Sanitize the filename components
            sanitized_stem = InputValidator.sanitize_filename(Path(original_filename).stem)
            output_filename = f"{sanitized_stem}_sanchez_output_{int(time.time())}.png"

            # Validate the complete output path
            InputValidator.validate_file_path(
            output_filename,
            allowed_extensions=['.png']
            )
        except SecurityError as e:
            pass
            LOGGER.warning("Security validation failed for output filename: %s", e)
            # Use a safe default filename
            output_filename = f"sanchez_output_{int(time.time())}.png"

        output_file_path = self._temp_dir / output_filename
        LOGGER.info("Setting Sanchez output path to: %s", output_file_path)

        # Ensure the output directory exists
        os.makedirs(output_file_path.parent, exist_ok=True)

        return output_file_path

    def _execute_sanchez_command(self, sanchez_executable: str, input_file: Path, output_file: Path, **kwargs: Any
    ) -> None:
        """Execute the Sanchez command with proper environment setup."""
        sanchez_dir, sanchez_name = self._parse_sanchez_executable(sanchez_executable)
        command = self._build_sanchez_command(sanchez_name, input_file, output_file, **kwargs)

        self._log_execution_details(sanchez_dir, sanchez_name, input_file, output_file)

        try:
            run_env = self._prepare_execution_environment(sanchez_dir)
            clean_command = self._clean_command_list(command)

            self._run_sanchez_subprocess(clean_command, sanchez_dir, run_env)
            self._verify_output_created(output_file)

        except subprocess.CalledProcessError as e:
            pass
    pass
    self._handle_sanchez_execution_error(e)

    def _parse_sanchez_executable(self, sanchez_executable: str) -> tuple[Path, str]:
        """Parse Sanchez executable path into directory and name."""
        sanchez_dir = Path(sanchez_executable).parent
        sanchez_name = Path(sanchez_executable).name
        return sanchez_dir, sanchez_name

    def _build_sanchez_command(self, sanchez_name: str, input_file: Path, output_file: Path, **kwargs: Any
    ) -> list[str | Path]:
        """Build the Sanchez command with all arguments."""
        command: list[str | Path] = [
        f"./{sanchez_name}",
        "geostationary",
        "-s", input_file,
        "-o", output_file,
        ]

        self._add_kwargs_to_command(command, **kwargs)
        return command

    def _add_kwargs_to_command(self, command: list[str | Path], **kwargs: Any) -> None:
        """Add keyword arguments to the Sanchez command."""
        for key, value in kwargs.items():
            if key == "res_km":
                pass
                self._add_resolution_arg(command, value)
            elif key == "false_colour":
                pass
                # Skip handling false_colour to respect user's setting
                pass
            else:
                self._add_generic_arg(command, key, value)

    def _add_resolution_arg(self, command: list[str | Path], value: Any) -> None:
        """Add resolution argument to command."""
        try:
            res_val = float(value)
            res_str = str(int(res_val)) if res_val == int(res_val) else str(res_val)
        except ValueError:
            pass
    pass
    res_str = str(value)
    command.extend(["-r", res_str])

    def _add_generic_arg(self, command: list[str | Path], key: str, value: Any) -> None:
        """Add generic argument to command with security validation."""
        try:
            # Validate the argument using security module
            InputValidator.validate_sanchez_argument(key, value)
        except SecurityError as e:
            pass
            LOGGER.error("Security validation failed for Sanchez argument: %s", e)
            raise ConfigurationError(f"Invalid Sanchez argument: {e}") from e

        arg_name = f"--{key.replace('_', '-')}"
        if isinstance(value, bool):
            pass
            if value:
                pass
                command.append(arg_name)
        else:
            command.extend([arg_name, str(value)])

    def _log_execution_details(self, sanchez_dir: Path, sanchez_name: str, input_file: Path, output_file: Path
    ) -> None:
        """Log details about the Sanchez execution."""
        LOGGER.debug("Sanchez executable directory: %s", sanchez_dir)
        LOGGER.debug("Sanchez executable name: %s", sanchez_name)
        LOGGER.debug("Input file path: %s", input_file)
        LOGGER.debug("Output file path: %s", output_file)

    def _prepare_execution_environment(self, sanchez_dir: Path) -> dict[str, str]:
        """Prepare environment variables for Sanchez execution."""
        run_env = os.environ.copy()
        run_env["DYLD_FALLBACK_LIBRARY_PATH"] = (
        str(sanchez_dir.resolve())
        + os.pathsep
        + run_env.get("DYLD_FALLBACK_LIBRARY_PATH", "")
        )
        LOGGER.debug(
        "Setting DYLD_FALLBACK_LIBRARY_PATH to: %s",
        run_env["DYLD_FALLBACK_LIBRARY_PATH"],
        )
        return run_env

    def _clean_command_list(self, command: list[str | Path]) -> list[str]:
        """Clean command list by removing None values and converting to strings."""
        clean_command = [str(item) for item in command if item is not None]
        LOGGER.debug("Cleaned command: %s", clean_command)
        return clean_command

    def _run_sanchez_subprocess(self, clean_command: list[str], sanchez_dir: Path, run_env: dict[str, str]
    ) -> subprocess.CompletedProcess[str]:
        """Run the Sanchez subprocess with security validation."""
        LOGGER.debug(
        "Running Sanchez command: %s in CWD: %s",
        " ".join(clean_command),
        sanchez_dir,
        )

        print(f"Running Sanchez command in {sanchez_dir}: {' '.join(clean_command)}")

        try:
            # Use secure subprocess execution with validation
            result = secure_subprocess_call(
            clean_command,
            cwd=sanchez_dir,
            env=run_env,
            timeout=120  # 2 minute timeout for Sanchez processing
            )
        except SecurityError as e:
            pass
            LOGGER.error("Security validation failed for Sanchez command: %s", e)
            raise ExternalToolError()
            tool_name="Sanchez",
            message=f"Command security validation failed: {e}",
            ) from e

        LOGGER.info("Sanchez stdout: %s", result.stdout)
        LOGGER.info("Sanchez stderr: %s", result.stderr)

        return result

    def _verify_output_created(self, output_file_path: Path) -> None:
        """Verify that the Sanchez output file was created."""
        if output_file_path.exists():
            pass
            LOGGER.info("Sanchez output file created successfully: %s", output_file_path)
        else:
            LOGGER.warning()
            "Sanchez command completed but output file not found at: %s",
            output_file_path,
            )
            dir_files = list(self._temp_dir.glob("*"))
            LOGGER.warning("Files in temp directory: %s", dir_files)

    def _handle_sanchez_execution_error(self, e: subprocess.CalledProcessError) -> None:
        """Handle errors from Sanchez execution."""
        LOGGER.error("Sanchez process failed!")
        LOGGER.error("Exit Code: %s", e.returncode)
        LOGGER.error("Stdout:\n%s", e.stdout)
        LOGGER.error("Stderr:\n%s", e.stderr)

        raise ExternalToolError()
        tool_name="Sanchez",
        message=f"Execution failed with exit code {e.returncode}",
        stderr=e.stderr,
        ) from e

    def _load_processed_image(self,:)
    output_file_path: Path,
    original_image_data: ImageData) -> ImageData:
                                  """Load the processed image from Sanchez output."""
    try:
            if not output_file_path.exists():
                pass
                return self._handle_missing_output(output_file_path, original_image_data)

            LOGGER.info("Loading Sanchez output from %s", output_file_path)
            processed_img = Image.open(output_file_path)
            processed_image_data_array = np.array(processed_img)

            return self._create_processed_image_data(processed_image_data_array,
            original_image_data)

    except FileNotFoundError as fnf_error:
            pass
            return self._handle_file_not_found_error(fnf_error, original_image_data)
    except Exception as img_error:
            pass
            return self._handle_image_loading_error(img_error, original_image_data)

    def _handle_missing_output(self,:)
    output_file_path: Path,
    original_image_data: ImageData) -> ImageData:
                                   """Handle case where Sanchez output file is missing."""
    LOGGER.error("Output file not found at %s", output_file_path)

    try:
            dir_contents = list(output_file_path.parent.glob("*"))
            LOGGER.error("Files in temp directory: %s", dir_contents)
    except Exception as dir_err:
            pass
            LOGGER.error("Error listing temp directory: %s", dir_err)

    LOGGER.warning("Sanchez processing failed, using original image as fallback")
    processed_img = Image.fromarray(original_image_data.image_data)
    processed_image_data_array = np.array(processed_img)

    return self._create_processed_image_data(processed_image_data_array, original_image_data)

    def _handle_file_not_found_error(self, fnf_error: FileNotFoundError, original_image_data: ImageData
    ) -> ImageData:
        """Handle FileNotFoundError when loading Sanchez output."""
        LOGGER.exception("Output file not found error: %s", fnf_error)
        LOGGER.warning("Sanchez processing failed, using original image as fallback")

        processed_image_data = original_image_data
        processed_image_data.metadata["error"] = f"Sanchez output file not found: {fnf_error}"

        return processed_image_data

    def _handle_image_loading_error(self,:)
    img_error: Exception,
    original_image_data: ImageData) -> ImageData:
                                        """Handle general errors when loading Sanchez output."""
    LOGGER.exception("Error loading Sanchez output: %s", img_error)
    LOGGER.warning("Sanchez processing failed, using original image as fallback")

    processed_image_data = original_image_data
    processed_image_data.metadata["error"] = f"Sanchez processing error: {img_error}"

    return processed_image_data

    def _create_processed_image_data(self, processed_image_data_array: np.ndarray, original_image_data: ImageData
    ) -> ImageData:
        """Create ImageData object from processed image array."""
        return ImageData()
        image_data=processed_image_data_array,
        metadata={
        **original_image_data.metadata,
        "processing_steps": original_image_data.metadata.get("processing_steps", [])
        + ["sanchez"],
        },
        )

    def _cleanup_temporary_files(self,:)
    input_file: Optional[Path],
    output_file: Optional[Path]) -> None:
                                     """Clean up temporary files created during processing."""
    if input_file and os.path.exists(input_file):
            pass
            os.remove(input_file)
    if output_file and os.path.exists(output_file):
            pass
            os.remove(output_file)

    def _get_original_filename(self, image_data: ImageData) -> str:
        """Extract or generate original filename for Sanchez."""
        original_filename = image_data.metadata.get("filename", "")

        if not original_filename or original_filename == "input.png":
            pass
            # Check if we can make a better guess about the filename
            if "source_path" in image_data.metadata:
                pass
                source_path = image_data.metadata.get("source_path", "")
                if source_path:
                    pass
                    original_filename = Path(source_path).name

            # If still no valid filename, generate one with timestamp
            if not original_filename or original_filename == "input.png":
                pass
                original_filename = f"abi_image_{int(time.time())}.png"

        return original_filename

    def _load_output(self, output_path: Path, original_image_data: ImageData
    ) -> ImageData:
        """Load Sanchez output and create new ImageData."""
        if not output_path.exists():
            pass
            raise ExternalToolError()
            tool_name="Sanchez",
            message=f"Output file not found at {output_path}",
            )

        processed_img = Image.open(output_path)
        processed_image_data_array = np.array(processed_img)

        # Create a new ImageData object
        return ImageData()
        image_data=processed_image_data_array,
        metadata={
        **original_image_data.metadata,
        "processing_steps": original_image_data.metadata.get()
        "processing_steps", []
        )
        + ["sanchez"],
        "sanchez_health_check": ()
        self._health_status_cached.is_healthy
        if self._health_status_cached
        else None
        ),
        },
        )

    def load(self, *args: Any, **kwargs: Any) -> NoReturn:
        """Not implemented. SanchezProcessor does not support loading images.

        Raises:
            NotImplementedError: Always.
        """
        raise NotImplementedError("SanchezProcessor does not implement load")

    def crop(self, *args: Any, **kwargs: Any) -> NoReturn:
        """Not implemented. SanchezProcessor does not support cropping images.

        Raises:
            NotImplementedError: Always.
        """
        raise NotImplementedError("SanchezProcessor does not implement crop")

    def save(self, *args: Any, **kwargs: Any) -> NoReturn:
        """Not implemented. SanchezProcessor does not support saving images.

        Raises:
            NotImplementedError: Always.
        """
        raise NotImplementedError("SanchezProcessor does not implement save")
