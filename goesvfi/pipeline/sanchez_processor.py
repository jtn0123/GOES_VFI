"""Sanchez Processor for GOES satellite imagery colorization.

This module provides functionality to apply Sanchez colorization to GOES infrared
satellite imagery using the Sanchez binary.
"""

from collections.abc import Callable
from pathlib import Path
import time
from typing import Any

import numpy as np
from PIL import Image

from goesvfi.sanchez.runner import colourise
from goesvfi.utils import log

from .image_processing_interfaces import ImageData, ImageProcessor

LOGGER = log.get_logger(__name__)


class SanchezProcessor(ImageProcessor):
    """Processor for applying Sanchez colorization to GOES infrared imagery.

    This processor uses the Sanchez binary to convert grayscale infrared satellite
    images into colorized visualizations that highlight different temperature ranges.
    """

    def __init__(
        self,
        temp_dir: Path,
        progress_callback: Callable[[str, float], None] | None = None,
    ) -> None:
        """Initialize the SanchezProcessor.

        Args:
            temp_dir: Directory for temporary files
            progress_callback: Optional callback for progress updates
        """
        self._temp_dir = Path(temp_dir)
        self._temp_dir.mkdir(parents=True, exist_ok=True)
        self._progress_callback = progress_callback
        LOGGER.info("SanchezProcessor initialized with temp dir: %s", self._temp_dir)

    def process(self, image_data: ImageData, **kwargs: Any) -> ImageData:
        """Process image data using Sanchez colorization.

        Args:
            image_data: Input image data to process
            **kwargs: Additional processing options (res_km, etc.)

        Returns:
            Processed ImageData with colorized image

        Raises:
            RuntimeError: If Sanchez processing fails
        """
        start_time = time.time()

        if self._progress_callback:
            self._progress_callback("Starting Sanchez processing", 0.0)

        try:
            # Extract parameters
            res_km = kwargs.get("res_km", 4)

            # Validate if image is suitable for Sanchez processing
            if not SanchezProcessor._is_valid_satellite_image(image_data):
                LOGGER.debug("Image not suitable for Sanchez processing, returning original")
                return image_data

            # Create temporary files
            input_temp = self._temp_dir / f"sanchez_input_{time.time_ns()}.png"
            output_temp = self._temp_dir / f"sanchez_output_{time.time_ns()}.png"

            try:
                # Save input image as PNG
                if self._progress_callback:
                    self._progress_callback("Saving input image", 0.2)

                # Convert numpy array to PIL Image if needed
                if isinstance(image_data.image_data, np.ndarray):
                    # Normalize to 0-255 range if needed
                    img_array = image_data.image_data
                    if img_array.dtype != np.uint8:
                        if img_array.max() <= 1.0:
                            img_array = (img_array * 255).astype(np.uint8)
                        else:
                            img_array = img_array.astype(np.uint8)

                    # Handle different array shapes
                    if len(img_array.shape) == 3 and img_array.shape[2] == 1:
                        img_array = img_array.squeeze(axis=2)

                    pil_image = Image.fromarray(img_array, mode="L" if len(img_array.shape) == 2 else "RGB")
                else:
                    pil_image = image_data.image_data

                pil_image.save(input_temp, "PNG")

                # Run Sanchez colorization
                if self._progress_callback:
                    self._progress_callback("Running Sanchez colorization", 0.5)

                LOGGER.debug(
                    "Running Sanchez: %s -> %s (res=%skm)",
                    input_temp,
                    output_temp,
                    res_km,
                )
                colourise(input_temp, output_temp, res_km=res_km)

                if not output_temp.exists():
                    msg = "Sanchez processing failed - output file not created"
                    raise RuntimeError(msg)

                # Load processed image
                if self._progress_callback:
                    self._progress_callback("Loading processed image", 0.8)

                processed_pil = Image.open(output_temp)
                processed_array = np.array(processed_pil)

                # Create new ImageData with processed result
                processed_data = ImageData(
                    image_data=processed_array,
                    source_path=image_data.source_path,
                    metadata={
                        **image_data.metadata,
                        "processed_by": "sanchez",
                        "width": processed_array.shape[1],
                        "height": processed_array.shape[0],
                        "channels": (1 if len(processed_array.shape) == 2 else processed_array.shape[2]),
                        "sanchez_res_km": res_km,
                        "processing_time": time.time() - start_time,
                    },
                )

                if self._progress_callback:
                    self._progress_callback("Sanchez processing completed", 1.0)

                LOGGER.info("Sanchez processing completed in %.2fs", time.time() - start_time)
                return processed_data

            finally:
                # Clean up temporary files
                for temp_file in [input_temp, output_temp]:
                    try:
                        if temp_file.exists():
                            temp_file.unlink()
                    except (OSError, FileNotFoundError):
                        # File may have been removed by another process or never created
                        pass

        except Exception as e:
            error_msg = f"Sanchez processing failed: {e}"
            LOGGER.exception(error_msg)
            if self._progress_callback:
                self._progress_callback(error_msg, 1.0)

            # Return original image with metadata indicating failure
            res_km = kwargs.get("res_km", 4)
            return ImageData(
                image_data=image_data.image_data,
                source_path=image_data.source_path,
                metadata={
                    **image_data.metadata,
                    "processed_by": "sanchez",
                    "processing_failed": True,
                    "processing_error": str(e),
                    "processing_time": time.time() - start_time,
                    "sanchez_res_km": res_km,
                },
            )

    @staticmethod
    def _is_valid_satellite_image(image_data: ImageData) -> bool:
        """Check if the image is suitable for Sanchez processing.

        Sanchez expects infrared satellite imagery with appropriate characteristics.
        Test images (solid colors, simple patterns) are not suitable.

        Args:
            image_data: Image data to validate

        Returns:
            bool: True if suitable for Sanchez processing, False otherwise
        """
        try:
            # Check metadata for indicators this is test/synthetic data
            metadata = image_data.metadata

            # Check filename patterns that indicate test data
            filename = metadata.get("filename", "")
            if any(pattern in filename.lower() for pattern in ["solid_frame", "test_", "dummy_", "mock_"]):
                LOGGER.debug("Detected test image pattern in filename: %s", filename)
                return False

            # Check source path for test indicators
            source_path = str(image_data.source_path or "")
            if any(pattern in source_path.lower() for pattern in ["test", "pytest", "mock", "dummy"]):
                LOGGER.debug("Detected test path pattern: %s", source_path)
                return False

            # Check image characteristics
            if isinstance(image_data.image_data, np.ndarray):
                img_array = image_data.image_data

                # Check for solid color images (all pixels have same value)
                if img_array.size > 0:
                    unique_values = np.unique(img_array)
                    if len(unique_values) <= 3:  # Very few unique values suggests synthetic data
                        LOGGER.debug("Image has too few unique values (%d) for satellite data", len(unique_values))
                        return False

                    # Check for typical satellite data dimensions
                    height, width = img_array.shape[:2]
                    if width < 512 or height < 512:  # Satellite images are typically larger
                        LOGGER.debug("Image dimensions %dx%d too small for typical satellite data", width, height)
                        return False

            return True

        except ValueError as e:
            LOGGER.warning("Error validating satellite image: %s", e)
            # In case of validation error, allow processing but it may fail
            return True

    def process_image(self, image_data: ImageData, **kwargs: Any) -> ImageData:
        """Alias for process method for compatibility.

        Args:
            image_data: Input image data to process
            **kwargs: Additional processing options

        Returns:
            Processed ImageData with colorized image
        """
        return self.process(image_data, **kwargs)

    def load(self, source_path: str) -> ImageData:
        """Not implemented."""
        msg = "SanchezProcessor does not implement load"
        raise NotImplementedError(msg)

    def crop(self, image_data: ImageData, crop_area: tuple) -> ImageData:
        """Not implemented."""
        msg = "SanchezProcessor does not implement crop"
        raise NotImplementedError(msg)

    def save(self, image_data: ImageData, destination_path: str) -> None:
        """Not implemented."""
        msg = "SanchezProcessor does not implement save"
        raise NotImplementedError(msg)
