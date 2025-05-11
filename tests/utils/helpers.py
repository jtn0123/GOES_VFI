"""
Test utility helper functions for the GOES-VFI test suite.
"""

import pathlib
from typing import Tuple

import numpy as np
from PIL import Image


def create_dummy_png(
    path: pathlib.Path,
    size: Tuple[int, int] = (10, 10),
    color: Tuple[int, int, int] = (0, 0, 0),
):
    """
    Creates a dummy PNG image file at the specified path.

    Args:
        path: The path where the PNG file should be saved.
        size: A tuple representing the (width, height) of the image. Defaults to (10, 10).
        color: A tuple representing the RGB color (0-255). Defaults to black (0, 0, 0).
    """
    try:
        img_array = np.zeros((size[1], size[0], 3), dtype=np.uint8)
        img_array[:, :] = color
        img = Image.fromarray(img_array, "RGB")
        path.parent.mkdir(parents=True, exist_ok=True)  # Ensure directory exists
        img.save(path, format="PNG")
    except Exception as e:
        print(f"Error creating dummy PNG at {path}: {e}")
        raise


def compare_images(path1: pathlib.Path, path2: pathlib.Path) -> bool:
    """
    Compares two images pixel by pixel.

    Args:
        path1: Path to the first image.
        path2: Path to the second image.

    Returns:
        True if the images are identical, False otherwise.
    """
    try:
        img1 = Image.open(path1)
        img2 = Image.open(path2)

        if img1.size != img2.size or img1.mode != img2.mode:
            return False

        arr1 = np.array(img1)
        arr2 = np.array(img2)

        return np.array_equal(arr1, arr2)
    except FileNotFoundError:
        return False
    except Exception as e:
        print(f"Error comparing images {path1} and {path2}: {e}")
        return False


# Add more helper functions as needed, e.g., for creating sequences of images,
# checking video properties, etc.
