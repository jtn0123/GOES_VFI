"""Sanchez Processor for GOES satellite imagery colorization.

This module provides functionality to apply Sanchez colorization to GOES infrared
satellite imagery using the Sanchez binary.
"""

import time
from pathlib import Path
from typing import Any, Callable, Optional

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
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ):
        """Initialize the SanchezProcessor.

        Args:
            temp_dir: Directory for temporary files
            progress_callback: Optional callback for progress updates
        """
        self._temp_dir = Path(temp_dir)
        self._temp_dir.mkdir(parents=True, exist_ok=True)
        self._progress_callback = progress_callback
        LOGGER.info(f"SanchezProcessor initialized with temp dir: {self._temp_dir}")

    def process(self, image_data: ImageData, **kwargs: Any) -> ImageData:
        """Process image data using Sanchez colorization.

        Args:
            image_data: Input image data to process
            **kwargs: Additional processing options (res_km, etc.)

        Returns:
            Processed ImageData with colorized image
        """
        start_time = time.time()

        if self._progress_callback:
            self._progress_callback("Starting Sanchez processing", 0.0)

        try:
            # Extract parameters
            res_km = kwargs.get("res_km", 4)

            # Create temporary files
            input_temp = self._temp_dir / f"sanchez_input_{time.time_ns()}.png"
            output_temp = self._temp_dir / f"sanchez_output_{time.time_ns()}.png"

            try:
                # Save input image as PNG
                if self._progress_callback:
                    self._progress_callback("Saving input image", 0.2)

                # Convert numpy array to PIL Image if needed
                if isinstance(image_data.data, np.ndarray):
                    # Normalize to 0-255 range if needed
                    img_array = image_data.data
                    if img_array.dtype != np.uint8:
                        if img_array.max() <= 1.0:
                            img_array = (img_array * 255).astype(np.uint8)
                        else:
                            img_array = img_array.astype(np.uint8)

                    # Handle different array shapes
                    if len(img_array.shape) == 3 and img_array.shape[2] == 1:
                        img_array = img_array.squeeze(axis=2)

                    pil_image = Image.fromarray(
                        img_array, mode="L" if len(img_array.shape) == 2 else "RGB"
                    )
                else:
                    pil_image = image_data.data

                pil_image.save(input_temp, "PNG")

                # Run Sanchez colorization
                if self._progress_callback:
                    self._progress_callback("Running Sanchez colorization", 0.5)

                LOGGER.debug(
                    f"Running Sanchez: {input_temp} -> {output_temp} (res={res_km}km)"
                )
                colourise(input_temp, output_temp, res_km=res_km)

                if not output_temp.exists():
                    raise RuntimeError(
                        "Sanchez processing failed - output file not created"
                    )

                # Load processed image
                if self._progress_callback:
                    self._progress_callback("Loading processed image", 0.8)

                processed_pil = Image.open(output_temp)
                processed_array = np.array(processed_pil)

                # Create new ImageData with processed result
                processed_data = ImageData(
                    data=processed_array,
                    width=processed_array.shape[1],
                    height=processed_array.shape[0],
                    channels=(
                        len(processed_array.shape)
                        if len(processed_array.shape) == 2
                        else processed_array.shape[2]
                    ),
                    source_path=image_data.source_path,
                    metadata={
                        **image_data.metadata,
                        "processed_by": "sanchez",
                        "sanchez_res_km": res_km,
                        "processing_time": time.time() - start_time,
                    },
                )

                if self._progress_callback:
                    self._progress_callback("Sanchez processing completed", 1.0)

                LOGGER.info(
                    f"Sanchez processing completed in {time.time() - start_time:.2f}s"
                )
                return processed_data

            finally:
                # Clean up temporary files
                for temp_file in [input_temp, output_temp]:
                    if temp_file.exists():
                        temp_file.unlink()

        except Exception as e:
            error_msg = f"Sanchez processing failed: {e}"
            LOGGER.error(error_msg, exc_info=True)
            if self._progress_callback:
                self._progress_callback(error_msg, 1.0)

            # Return original image if processing fails
            return image_data

    def process_image(self, image_data: ImageData, **kwargs: Any) -> ImageData:
        """Alias for process method for compatibility."""
        return self.process(image_data, **kwargs)

    def load(self, path: str) -> ImageData:
        """Not implemented."""
        raise NotImplementedError("SanchezProcessor does not implement load")

    def crop(self, image_data: ImageData, crop_area: tuple) -> ImageData:
        """Not implemented."""
        raise NotImplementedError("SanchezProcessor does not implement crop")

    def save(self, image_data: ImageData, path: str) -> None:
        """Not implemented."""
        raise NotImplementedError("SanchezProcessor does not implement save")
