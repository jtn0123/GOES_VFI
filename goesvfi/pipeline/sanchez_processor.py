from typing import Any
from pathlib import Path # Import Path

"""sanchez_processor.py

Provides the SanchezProcessor class, an ImageProcessor implementation that
invokes the external Sanchez tool for advanced image processing in the GOES_VFI pipeline.
"""

import abc
import subprocess
import sys
import tempfile
import os
import typing
import numpy as np
from typing import NoReturn # Import NoReturn
from PIL import Image
from .image_processing_interfaces import ImageData, ImageProcessor
from goesvfi.exceptions import ExternalToolError, ConfigurationError
from goesvfi.utils import log

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
        os.makedirs(self._temp_dir, exist_ok=True) # Ensure directory exists

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
        temp_dir = None
        input_file = None
        output_file = None

        try:
            # 1. Save input image data to a temporary file using original filename
            # Assuming original filename is in metadata, adjust key if needed
            original_filename = image_data.metadata.get('filename', 'input.png') # Fallback just in case
            if not original_filename: # Handle empty string case
                original_filename = 'input.png'
            input_file_path = self._temp_dir / Path(original_filename).name # Use only the filename part
            # LOGGER.debug(f"Using temporary input filename: {input_file_path.name}") # Removed debug log
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
            output_file_path = self._temp_dir / "output.png"
            output_file = output_file_path  # Keep track for cleanup

            # Command structure based on --help output: executable -s <input> -o <output> [options]
            sanchez_dir = Path(sanchez_executable).parent # Get the directory of the executable
            sanchez_name = Path(sanchez_executable).name # Get just the executable name
            command: list[str | Path] = [
                f"./{sanchez_name}", # Use ./ to specify executable in cwd
                "geostationary",    # ADD the required subcommand
                "-s", input_file_path,
                "-o", output_file_path
            ]

            # Add kwargs as command-line arguments, mapping to correct flags
            for key, value in kwargs.items():
                # Map Python kwargs to Sanchez CLI options
                if key == 'res_km':
                    # Use -r for resolution, formatting to remove '.0' for whole numbers
                    try:
                        res_val = float(value)
                        if res_val == int(res_val):
                            res_str = str(int(res_val)) # Format as integer string (e.g., "4")
                        else:
                            res_str = str(res_val) # Format as float string (e.g., "0.5")
                    except ValueError:
                        # Fallback if conversion fails, though it shouldn't normally
                        res_str = str(value)
                    command.extend(["-r", res_str])
                elif key == 'false_colour' and isinstance(value, bool) and value:
                    # Only add false colour flags if the 'false_colour' kwarg is explicitly True
                    command.append("-c")
                    command.append("0.0-1.0") # Add required intensity range argument
                    # Construct absolute path to gradient file relative to sanchez_dir
                    abs_gradient_path = (sanchez_dir / "Resources" / "Gradients" / "Atmosphere.json").resolve()
                    command.extend(["-g", abs_gradient_path])
                    LOGGER.debug(f"Adding false colour arguments: -c 0.0-1.0 -g {abs_gradient_path}")
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
                LOGGER.debug(f"Running Sanchez command: {' '.join(map(str, command))} in CWD: {sanchez_dir}")
                # Create a copy of the current environment
                run_env = os.environ.copy()
                # Add the Sanchez directory to the dynamic library path (macOS)
                # Use DYLD_FALLBACK_LIBRARY_PATH to avoid overriding system paths entirely
                run_env['DYLD_FALLBACK_LIBRARY_PATH'] = str(sanchez_dir.resolve()) + os.pathsep + run_env.get('DYLD_FALLBACK_LIBRARY_PATH', '')
                LOGGER.debug(f"Setting DYLD_FALLBACK_LIBRARY_PATH to: {run_env['DYLD_FALLBACK_LIBRARY_PATH']}")

                result = subprocess.run(
                    command,
                    check=True, # Restore check=True
                    capture_output=True,
                    text=True,
                    cwd=sanchez_dir, # Set the working directory
                    env=run_env # Pass the modified environment
                )
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
                    stderr=e.stderr # Keep stderr in the exception too
                ) from e

            # 5. Load the resulting image file
            # Debug logs removed
            processed_img = Image.open(output_file_path)
            processed_image_data_array = np.array(processed_img)

            # 6. Create a new ImageData object
            processed_image_data = ImageData(
                image_data=processed_image_data_array,
                metadata={
                    **image_data.metadata,
                    "processing_steps": image_data.metadata.get("processing_steps", [])
                    + ["sanchez"],
                },
                # Add/update other relevant metadata from kwargs or Sanchez output if available
            )

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
