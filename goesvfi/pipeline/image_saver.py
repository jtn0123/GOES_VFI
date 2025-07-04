"""image_saver.py.

Provides the ImageSaver class, an ImageProcessor implementation for saving images
to disk using Pillow.
"""

import os
from typing import Any

import numpy as np
from PIL import Image

from .image_processing_interfaces import ImageData, ImageProcessor


class ImageSaver(ImageProcessor):
    """ImageProcessor implementation for saving images to disk using Pillow.

    This class saves ImageData objects to disk as image files. It does not
    implement loading, processing, or cropping.
    """

    def save(self, image_data: ImageData, destination_path: str) -> None:
        """Save image data to the specified destination path using Pillow.

        Args:
            image_data (ImageData): The image data to save.
            destination_path (str): The path where the image will be saved.

        Raises:
            IOError: If there's an error writing the file.
            ValueError: If the image data cannot be saved.
        """
        try:
            # Ensure the directory exists
            dir_path = os.path.dirname(destination_path)
            if dir_path:  # Only create directory if dirname returns a non-empty path
                os.makedirs(dir_path, exist_ok=True)

            # Handle different image data types
            raw_data = image_data.image_data

            if isinstance(raw_data, Image.Image):
                # Already a PIL Image, save directly
                raw_data.save(destination_path)
            else:
                # Handle NumPy array
                array_data = raw_data
                if np.issubdtype(array_data.dtype, np.floating):
                    # Normalize float data to 0-255 range
                    array_data = (array_data * 255).astype(np.uint8)

                # Convert NumPy array to Pillow Image and save
                img = Image.fromarray(array_data)
                img.save(destination_path)
        except OSError as e:
            msg = f"Error writing image file {destination_path}: {e}"
            raise OSError(msg) from e
        except (KeyError, ValueError, RuntimeError, TypeError) as e:
            msg = f"Could not save image to {destination_path}: {e}"
            raise ValueError(msg) from e

    def load(self, source_path: str) -> ImageData:
        """Not implemented. ImageSaver does not perform loading.

        Raises:
            NotImplementedError: Always.
        """
        msg = "ImageSaver does not implement the load method."
        raise NotImplementedError(msg)

    def process(self, image_data: ImageData, **kwargs: Any) -> ImageData:
        """Not implemented. ImageSaver does not perform processing.

        Raises:
            NotImplementedError: Always.
        """
        msg = "ImageSaver does not implement the process method."
        raise NotImplementedError(msg)

    def crop(self, image_data: ImageData, crop_area: tuple[int, int, int, int]) -> ImageData:
        """Not implemented. ImageSaver does not perform cropping.

        Raises:
            NotImplementedError: Always.
        """
        msg = "ImageSaver does not implement the crop method."
        raise NotImplementedError(msg)
