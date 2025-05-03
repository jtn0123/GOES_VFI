"""image_loader.py

Provides the ImageLoader class, an ImageProcessor implementation for loading images
from disk using Pillow and converting them to ImageData objects for the GOES_VFI pipeline.
"""

import os
import abc
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

# Try importing numpy, fall back to Any if not available initially
try:
    import numpy as np

    ImageType = np.ndarray
except ImportError:
    ImageType = Any  # type: ignore

from PIL import Image

from .image_processing_interfaces import ImageData, ImageProcessor


class ImageLoader(ImageProcessor):
    """ImageProcessor implementation for loading images from disk using Pillow.

    This class loads image files into ImageData objects, extracting pixel data and
    basic metadata. It does not implement processing, cropping, or saving.
    """

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
        """
        if not os.path.exists(source_path):
            raise FileNotFoundError(f"Image file not found: {source_path}")

        try:
            with Image.open(source_path) as img:
                # Convert Pillow Image to NumPy array
                image_data_array = np.array(img)

                # Create initial metadata
                metadata = {
                    "format": img.format,
                    "mode": img.mode,
                    "width": img.width,
                    "height": img.height,
                    "source_path": source_path,  # Also store source path in metadata
                }

                return ImageData(
                    image_data=image_data_array,
                    source_path=source_path,
                    metadata=metadata,
                )
        except IOError as e:
            # Re-raise other IOErrors encountered by Pillow
            raise IOError(f"Error reading image file {source_path}: {e}")
        except Exception as e:
            # Catch any other unexpected errors during loading
            raise ValueError(f"Could not load image from {source_path}: {e}")

    def process(self, image_data: ImageData, **kwargs: Any) -> ImageData:
        """Not implemented. ImageLoader does not perform processing.

        Raises:
            NotImplementedError: Always.
        """
        raise NotImplementedError("ImageLoader does not implement the process method.")

    def crop(
        self, image_data: ImageData, crop_area: Tuple[int, int, int, int]
    ) -> ImageData:
        """Not implemented. ImageLoader does not perform cropping.

        Raises:
            NotImplementedError: Always.
        """
        raise NotImplementedError("ImageLoader does not implement the crop method.")

    def save(self, image_data: ImageData, destination_path: str) -> None:
        """Not implemented. ImageLoader does not perform saving.

        Raises:
            NotImplementedError: Always.
        """
        raise NotImplementedError("ImageLoader does not implement the save method.")
