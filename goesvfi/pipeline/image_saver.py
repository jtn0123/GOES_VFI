"""image_saver.py

Provides the ImageSaver class, an ImageProcessor implementation for saving images
to disk using Pillow.
"""

import os
from typing import Any, Tuple

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
            pass
            image_data (ImageData): The image data to save.
            destination_path (str): The path where the image will be saved.

        Raises:
            IOError: If there's an error writing the file.
            ValueError: If the image data cannot be saved.
        """
        try:
            # Ensure the directory exists
            os.makedirs(os.path.dirname(destination_path), exist_ok=True)

            # Convert NumPy array to Pillow Image and save
            img = Image.fromarray(image_data.image_data)
            img.save(destination_path)
        except IOError as e:
            raise IOError(f"Error writing image file {destination_path}: {e}") from e
        except Exception as e:
            raise ValueError(f"Could not save image to {destination_path}: {e}") from e

    def load(self, source_path: str) -> ImageData:
        """Not implemented. ImageSaver does not perform loading.

        Raises:
            NotImplementedError: Always.
        """
        raise NotImplementedError("ImageSaver does not implement the load method.")

    def process(self, image_data: ImageData, **kwargs: Any) -> ImageData:
        """Not implemented. ImageSaver does not perform processing.

        Raises:
            NotImplementedError: Always.
        """
        raise NotImplementedError("ImageSaver does not implement the process method.")

    def crop(self, image_data: ImageData, crop_area: Tuple[int, int, int, int]) -> ImageData:
        """Not implemented. ImageSaver does not perform cropping.

        Raises:
            NotImplementedError: Always.
        """
        raise NotImplementedError("ImageSaver does not implement the crop method.")
