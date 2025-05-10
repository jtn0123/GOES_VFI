from pathlib import Path  # Import Path
from typing import Any

"""sanchez_processor.py

Provides the SanchezProcessor class, an ImageProcessor implementation that
invokes the external Sanchez tool for advanced image processing in the GOES_VFI pipeline.
"""

import os
import subprocess
import sys
import time
from typing import NoReturn  # Import NoReturn

import numpy as np
from PIL import Image

from goesvfi.exceptions import ConfigurationError, ExternalToolError
from goesvfi.utils import log

from .image_processing_interfaces import ImageData, ImageProcessor

LOGGER = log.get_logger(__name__)


class SanchezProcessor(ImageProcessor):
    """ImageProcessor implementation for running the external Sanchez tool.

    This class processes images by invoking the Sanchez executable as a subprocess,
    passing input and output file paths and additional arguments. It is used for
    advanced reprojection or enhancement steps in the GOES_VFI pipeline.

    Only the process method is implemented; load, crop, and save are not supported.
    """

    def __init__(self, temp_dir: Path):
        """
        Initializes the SanchezProcessor with a temporary directory.

        Args:
            temp_dir: The path to a temporary directory for Sanchez to use.
        """
        self._temp_dir = temp_dir
        os.makedirs(self._temp_dir, exist_ok=True)  # Ensure directory exists

    def process(self, image_data: ImageData, **kwargs: Any) -> ImageData:
        """Process image data using the external Sanchez tool.

        Args:
            image_data (ImageData): The input ImageData object.
            **kwargs: Additional parameters to pass to the Sanchez tool as command-line arguments.

        Returns:
            ImageData: A new ImageData object containing the processed image.

        Raises:
            ConfigurationError: If the Sanchez executable is not found for the current OS.
            ExternalToolError: If the Sanchez command fails to execute or returns an error.
        """
        input_file = None
        output_file = None

        try:
            # 1. Save input image data to a temporary file using original filename
            # Assuming original filename is in metadata, adjust key if needed
            original_filename = image_data.metadata.get("filename", "")

            # Make sure we have a valid original filename with a proper extension
            if not original_filename or original_filename == "input.png":
                # Check if we can make a better guess about the filename
                if "source_path" in image_data.metadata:
                    source_path = image_data.metadata.get("source_path", "")
                    if source_path:
                        original_filename = Path(source_path).name

                # If still no valid filename, generate one with timestamp
                if not original_filename or original_filename == "input.png":
                    original_filename = f"abi_image_{int(time.time())}.png"

            LOGGER.info("Using original filename for Sanchez: %s", original_filename)

            # Ensure the filename uses the original name, which is critical for Sanchez to parse
            input_file_path = self._temp_dir / Path(original_filename).name
            LOGGER.debug(f"Saving temporary input for Sanchez at: {input_file_path}")

            img = Image.fromarray(image_data.image_data)
            img.save(input_file_path)
            input_file = input_file_path  # Keep track for cleanup

            # 2. Determine the correct path to the Sanchez executable
            sanchez_executable = None
            if sys.platform.startswith("darwin"):  # macOS
                sanchez_executable = "goesvfi/sanchez/bin/osx-x64/Sanchez"
            elif sys.platform.startswith("win"):  # Windows
                sanchez_executable = "goesvfi/sanchez/bin/win-x64/Sanchez.exe"
            # Add other platforms if needed

            if not sanchez_executable or not os.path.exists(sanchez_executable):
                raise ConfigurationError(
                    f"Sanchez executable not found for platform: {sys.platform}"
                )

            # 3. Build the list of command-line arguments
            # Create a uniquely named output file based on the original filename
            output_file_path = (
                self._temp_dir
                / f"{Path(original_filename).stem}_sanchez_output_{int(time.time())}.png"
            )
            output_file = output_file_path  # Keep track for cleanup
            LOGGER.info("Setting Sanchez output path to: %s", output_file_path)

            # Command structure based on --help output: executable -s <input> -o <output> [options]
            sanchez_dir = Path(
                sanchez_executable
            ).parent  # Get the directory of the executable
            sanchez_name = Path(sanchez_executable).name  # Get just the executable name

            # Add DEBUG output to help diagnose the issue
            LOGGER.debug("Sanchez executable directory: %s", sanchez_dir)
            LOGGER.debug("Sanchez executable name: %s", sanchez_name)
            LOGGER.debug("Input file path: %s", input_file_path)
            LOGGER.debug("Output file path: %s", output_file_path)

            # Ensure the output directory exists
            os.makedirs(output_file_path.parent, exist_ok=True)

            command: list[str | Path] = [
                f"./{sanchez_name}",  # Use ./ to specify executable in cwd
                "geostationary",  # ADD the required subcommand
                "-s",
                input_file_path,
                "-o",
                output_file_path,
            ]

            # Add kwargs as command-line arguments, mapping to correct flags
            for key, value in kwargs.items():
                # Map Python kwargs to Sanchez CLI options
                if key == "res_km":
                    # Use -r for resolution, formatting to remove '.0' for whole numbers
                    try:
                        res_val = float(value)
                        if res_val == int(res_val):
                            res_str = str(
                                int(res_val)
                            )  # Format as integer string (e.g., "4")
                        else:
                            res_str = str(
                                res_val
                            )  # Format as float string (e.g., "0.5")
                    except ValueError:
                        # Fallback if conversion fails, though it shouldn't normally
                        res_str = str(value)
                    command.extend(["-r", res_str])
                elif key == "false_colour":
                    # Skip handling false_colour here to respect user's setting
                    # Sanchez will apply its default behavior without explicit coloring args
                    pass
                # Note: If key is 'false_colour' but value is False, nothing is added, which is correct.
                else:
                    # For other potential arguments, convert key and add value if not boolean True
                    # (This part might need refinement if other kwargs are used)
                    arg_name = f"--{key.replace('_', '-')}"
                    if isinstance(value, bool):
                        if value:
                            command.append(arg_name)
                    else:
                        command.extend([arg_name, str(value)])

            # 4. Execute the Sanchez command
            try:
                # sanchez_dir is already defined above
                LOGGER.debug(
                    "Running Sanchez command: %s in CWD: %s",
                    ' '.join(map(str, command)),
                    sanchez_dir
                )
                # Create a copy of the current environment
                run_env = os.environ.copy()
                # Add the Sanchez directory to the dynamic library path (macOS)
                # Use DYLD_FALLBACK_LIBRARY_PATH to avoid overriding system paths entirely
                run_env["DYLD_FALLBACK_LIBRARY_PATH"] = (
                    str(sanchez_dir.resolve())
                    + os.pathsep
                    + run_env.get("DYLD_FALLBACK_LIBRARY_PATH", "")
                )
                LOGGER.debug(
                    "Setting DYLD_FALLBACK_LIBRARY_PATH to: %s",
                    run_env['DYLD_FALLBACK_LIBRARY_PATH']
                )

                # Print to stdout for diagnostics
                print(
                    f"Running Sanchez command in {sanchez_dir}: {' '.join(map(str, command))}"
                )

                # Verify command list - remove any None values or other invalid items
                clean_command = [str(item) for item in command if item is not None]
                LOGGER.debug("Cleaned command: %s", clean_command)

                result = subprocess.run(
                    clean_command,
                    check=True,  # Restore check=True
                    capture_output=True,
                    text=True,
                    cwd=sanchez_dir,  # Set the working directory
                    env=run_env,  # Pass the modified environment
                )

                # Verify the command ran and the output file exists
                if output_file_path.exists():
                    LOGGER.info(
                        "Sanchez output file created successfully: %s", output_file_path
                    )
                else:
                    LOGGER.warning(
                        "Sanchez command completed but output file not found at: %s", output_file_path
                    )
                    # List files in directory
                    dir_files = list(self._temp_dir.glob("*"))
                    LOGGER.warning("Files in temp directory: %s", dir_files)

                # Original logging for success case
                LOGGER.info("Sanchez stdout: %s", result.stdout)
                LOGGER.info("Sanchez stderr: %s", result.stderr)
            except subprocess.CalledProcessError as e:
                # Log the captured output before raising the custom exception
                LOGGER.error("Sanchez process failed!")
                LOGGER.error("Exit Code: %s", e.returncode)
                LOGGER.error("Stdout:\n%s", e.stdout)
                LOGGER.error("Stderr:\n%s", e.stderr)
                raise ExternalToolError(
                    tool_name="Sanchez",
                    message=f"Execution failed with exit code {e.returncode}",
                    stderr=e.stderr,  # Keep stderr in the exception too
                ) from e

            # 5. Load the resulting image file
            try:
                # Check if the file exists first
                if not output_file_path.exists():
                    LOGGER.error("Output file not found at %s", output_file_path)
                    # Try to inspect the directory to see what's there
                    try:
                        dir_contents = list(output_file_path.parent.glob("*"))
                        LOGGER.error("Files in temp directory: %s", dir_contents)
                    except Exception as dir_err:
                        LOGGER.error("Error listing temp directory: %s", dir_err)

                    # If output file is missing, try to use the original image as fallback
                    LOGGER.warning(
                        "Sanchez processing failed, using original image as fallback"
                    )
                    processed_img = Image.fromarray(image_data.image_data)
                else:
                    LOGGER.info("Loading Sanchez output from %s", output_file_path)
                    processed_img = Image.open(output_file_path)

                processed_image_data_array = np.array(processed_img)

                # 6. Create a new ImageData object
                processed_image_data = ImageData(
                    image_data=processed_image_data_array,
                    metadata={
                        **image_data.metadata,
                        "processing_steps": image_data.metadata.get(
                            "processing_steps", []
                        )
                        + ["sanchez"],
                    },
                    # Add/update other relevant metadata from kwargs or Sanchez output if available
                )
            except FileNotFoundError as fnf_error:
                LOGGER.exception("Output file not found error: %s", fnf_error)
                # Use original image as fallback
                LOGGER.warning(
                    "Sanchez processing failed, using original image as fallback"
                )
                processed_image_data = image_data
            except Exception as img_error:
                LOGGER.exception("Error loading Sanchez output: %s", img_error)
                # Use original image as fallback
                LOGGER.warning(
                    "Sanchez processing failed, using original image as fallback"
                )
                processed_image_data = image_data

            return processed_image_data

        finally:
            # 7. Cleanup temporary files (the directory is managed by the caller)
            if input_file and os.path.exists(input_file):
                os.remove(input_file)
            if output_file and os.path.exists(output_file):
                os.remove(output_file)

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
