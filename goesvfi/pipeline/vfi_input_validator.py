"""Input validation for VFI processing pipeline.

This module provides focused input validation functionality extracted from VFIProcessor
to improve maintainability and testability.
"""

import pathlib
from typing import Any

from goesvfi.utils import log
from goesvfi.utils.validation import validate_path_exists, validate_positive_int

LOGGER = log.get_logger(__name__)


class VFIInputValidator:
    """Handles validation of inputs for VFI processing pipeline."""

    def __init__(self, fps: int, num_intermediate_frames: int) -> None:
        """Initialize validator with processing parameters.

        Args:
            fps: Target frames per second
            num_intermediate_frames: Number of intermediate frames to generate
        """
        self.fps = fps
        self.num_intermediate_frames = num_intermediate_frames

    def validate_processing_parameters(self) -> None:
        """Validate processing parameters.

        Raises:
            ValueError: If parameters are invalid
        """
        validate_positive_int(self.fps, "fps")
        validate_positive_int(self.num_intermediate_frames, "num_intermediate_frames")

        LOGGER.debug(
            "Processing parameters validated: fps=%d, num_intermediate_frames=%d",
            self.fps,
            self.num_intermediate_frames,
        )

    def validate_input_folder(self, folder: pathlib.Path) -> pathlib.Path:
        """Validate input folder exists and is accessible.

        Args:
            folder: Path to input folder

        Returns:
            Validated folder path

        Raises:
            ValueError: If folder is invalid
        """
        validated_folder = validate_path_exists(folder, must_be_dir=True, field_name="folder")
        LOGGER.debug("Input folder validated: %s", validated_folder)
        return validated_folder

    def validate_intermediate_frames_support(self, skip_model: bool) -> None:
        """Validate that intermediate frames configuration is supported.

        Args:
            skip_model: Whether model processing is being skipped

        Raises:
            NotImplementedError: If configuration is not supported
        """
        if self.num_intermediate_frames != 1 and not skip_model:
            msg = "Currently only num_intermediate_frames=1 is supported when not skipping model."
            LOGGER.error(msg)
            raise NotImplementedError(msg)

        LOGGER.debug("Intermediate frames configuration validated")

    def find_and_validate_images(self, folder: pathlib.Path, skip_model: bool) -> list[pathlib.Path]:
        """Find PNG images in folder and validate count requirements.

        Args:
            folder: Input folder path
            skip_model: Whether model processing is being skipped

        Returns:
            Sorted list of PNG image paths

        Raises:
            ValueError: If insufficient images found
        """
        paths = sorted(folder.glob("*.png"))

        if not paths:
            msg = "No PNG images found in the input folder."
            LOGGER.error(msg)
            raise ValueError(msg)

        # Validate minimum image count based on processing mode
        min_required = 1 if skip_model else 2
        mode_description = "skipping model" if skip_model else "interpolation"

        if len(paths) < min_required:
            msg = f"At least {min_required} PNG image{'s' if min_required > 1 else ''} required for {mode_description}."
            LOGGER.error("Found %d images, need %d for %s", len(paths), min_required, mode_description)
            raise ValueError(msg)

        LOGGER.info("Found %d PNG images for processing", len(paths))
        return paths

    def validate_inputs(self, folder: pathlib.Path, skip_model: bool) -> list[pathlib.Path]:
        """Comprehensive input validation combining all checks.

        Args:
            folder: Input folder path
            skip_model: Whether model processing is being skipped

        Returns:
            Sorted list of validated PNG image paths

        Raises:
            ValueError: If any validation fails
            NotImplementedError: If configuration is not supported
        """
        # Validate processing parameters
        self.validate_processing_parameters()

        # Validate and get folder
        validated_folder = self.validate_input_folder(folder)

        # Validate intermediate frames support
        self.validate_intermediate_frames_support(skip_model)

        # Find and validate images
        image_paths = self.find_and_validate_images(validated_folder, skip_model)

        LOGGER.info("Input validation complete: %d images found in %s", len(image_paths), validated_folder)

        return image_paths

    def get_validation_summary(self) -> dict[str, Any]:
        """Get a summary of current validation configuration.

        Returns:
            Dictionary with validation parameters
        """
        return {
            "fps": self.fps,
            "num_intermediate_frames": self.num_intermediate_frames,
            "max_supported_intermediate_frames": 1,
            "required_images_with_model": 2,
            "required_images_skip_model": 1,
        }
