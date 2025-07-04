"""image_loader.py.

Provides the ImageLoader class, an ImageProcessor implementation for loading images
from disk using Pillow and converting them to ImageData objects for the GOES_VFI pipeline.
"""

import os
from typing import Any

import numpy as np
from PIL import Image

from goesvfi.utils.log import get_logger
from goesvfi.utils.memory_manager import (
    MemoryOptimizer,
    estimate_memory_requirement,
    log_memory_usage,
)

from .exceptions import InputError, ProcessingError
from .image_processing_interfaces import ImageData, ImageProcessor

LOGGER = get_logger(__name__)


class ImageLoader(ImageProcessor):
    """ImageProcessor implementation for loading images from disk using Pillow.

    This class loads image files into ImageData objects, extracting pixel data and
    basic metadata. It does not implement processing, cropping, or saving.
    """

    def __init__(self, optimize_memory: bool = True, max_image_size_mb: int | None = None) -> None:
        """Initialize ImageLoader with optional memory optimization.

        Args:
            optimize_memory: Whether to optimize memory usage
            max_image_size_mb: Maximum image size in MB (None for no limit)
        """
        self.optimize_memory = optimize_memory
        self.max_image_size_mb = max_image_size_mb
        self.memory_optimizer = MemoryOptimizer() if optimize_memory else None

    def load(self, source_path: str) -> ImageData:
        """Load image data from a specified source path using Pillow.

        Args:
            source_path (str): The path to the image file to load.

        Returns:
            ImageData: An ImageData object containing the loaded image and metadata.

        Raises:
            FileNotFoundError: If the source_path does not exist.
            IOError: If there's an error reading the file.
            ValueError: If the file cannot be loaded as an image.
            MemoryError: If image is too large for available memory.
        """
        if not os.path.exists(source_path):
            msg = f"Image file not found: {source_path}"
            raise InputError(msg)

        # Log memory before loading
        if self.optimize_memory:
            log_memory_usage("Before loading image")

        try:
            with Image.open(source_path) as img:
                # Check image size
                width, height = img.size
                channels = len(img.mode) if img.mode != "L" else 1

                # Estimate memory requirement
                if self.optimize_memory:
                    # Calculate expected memory usage
                    shape = (height, width, channels) if channels > 1 else (height, width)
                    estimated_mb = estimate_memory_requirement(shape, np.dtype(np.uint8))

                    LOGGER.info(
                        "Loading image %s: %sx%s %s (~%sMB)",
                        os.path.basename(source_path),
                        width,
                        height,
                        img.mode,
                        estimated_mb,
                    )

                    # Check against limit
                    if self.max_image_size_mb and estimated_mb > self.max_image_size_mb:
                        msg = f"Image too large: {estimated_mb}MB exceeds limit of {self.max_image_size_mb}MB"
                        raise ValueError(msg)

                    # Check available memory
                    if self.memory_optimizer:
                        has_memory, msg = self.memory_optimizer.check_available_memory(estimated_mb + 100)  # Add buffer
                        if not has_memory:
                            msg = f"Insufficient memory to load image: {msg}"
                            raise MemoryError(msg)

                # Convert Pillow Image to NumPy array
                image_data_array = np.array(img)

                # Optimize array dtype if enabled
                if self.optimize_memory and self.memory_optimizer:
                    original_dtype = image_data_array.dtype
                    image_data_array = self.memory_optimizer.optimize_array_dtype(image_data_array, preserve_range=True)
                    if image_data_array.dtype != original_dtype:
                        LOGGER.debug(
                            "Optimized array dtype from %s to %s",
                            original_dtype,
                            image_data_array.dtype,
                        )

                # Create initial metadata
                metadata = {
                    "format": img.format,
                    "mode": img.mode,
                    "width": img.width,
                    "height": img.height,
                    "source_path": source_path,
                    "memory_optimized": self.optimize_memory,
                    "dtype": str(image_data_array.dtype),
                    "size_mb": image_data_array.nbytes / (1024 * 1024),
                }

                # Log memory after loading
                if self.optimize_memory:
                    log_memory_usage("After loading image")

                return ImageData(
                    image_data=image_data_array,
                    source_path=source_path,
                    metadata=metadata,
                )

        except OSError as e:
            # Re-raise other IOErrors encountered by Pillow
            msg = f"Error reading image file {source_path}: {e}"
            raise InputError(msg) from e
        except MemoryError:  # pylint: disable=try-except-raise
            # Re-raise memory errors unchanged - let caller handle OOM
            raise
        except (KeyError, ValueError, RuntimeError) as e:
            # Catch any other unexpected errors during loading
            msg = f"Could not load image from {source_path}: {e}"
            raise ProcessingError(msg) from e

    def process(self, image_data: ImageData, **kwargs: Any) -> ImageData:
        """Not implemented. ImageLoader does not perform processing.

        Raises:
            NotImplementedError: Always.
        """
        msg = "ImageLoader does not implement the process method."
        raise NotImplementedError(msg)

    def crop(self, image_data: ImageData, crop_area: tuple[int, int, int, int]) -> ImageData:
        """Not implemented. ImageLoader does not perform cropping.

        Raises:
            NotImplementedError: Always.
        """
        msg = "ImageLoader does not implement the crop method."
        raise NotImplementedError(msg)

    def save(self, image_data: ImageData, destination_path: str) -> None:
        """Not implemented. ImageLoader does not perform saving.

        Raises:
            NotImplementedError: Always.
        """
        msg = "ImageLoader does not implement the save method."
        raise NotImplementedError(msg)
