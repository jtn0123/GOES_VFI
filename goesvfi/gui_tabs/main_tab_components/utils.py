"""Utility functions for the main tab module."""

import numpy as np
from numpy.typing import NDArray
from PyQt6.QtGui import QImage

from goesvfi.utils.log import get_logger

LOGGER = get_logger(__name__)


def numpy_to_qimage(array: NDArray[np.uint8]) -> QImage:
    """Converts a NumPy array (H, W, C) in RGB format to QImage."""
    if array is None or array.size == 0:
        return QImage()

    try:
        height, width, channel = array.shape
        if channel == 3:  # RGB
            bytes_per_line = 3 * width
            image_format = QImage.Format.Format_RGB888
            # Create QImage from buffer protocol. Make a copy to be safe.
            qimage = QImage(array.data, width, height, bytes_per_line, image_format).copy()
        elif channel == 4:  # RGBA?
            bytes_per_line = 4 * width
            image_format = QImage.Format.Format_RGBA8888
            qimage = QImage(array.data, width, height, bytes_per_line, image_format).copy()
        elif channel == 1 or len(array.shape) == 2:  # Grayscale
            height, width = array.shape[:2]
            bytes_per_line = width
            image_format = QImage.Format.Format_Grayscale8
            # Ensure array is contiguous C-style for grayscale
            gray_array = np.ascontiguousarray(array.squeeze())
            qimage = QImage(gray_array.data, width, height, bytes_per_line, image_format).copy()
        else:
            LOGGER.error(f"Unsupported NumPy array shape for QImage conversion: {array.shape}")
            return QImage()

        if qimage.isNull():
            LOGGER.error("Failed to create QImage from NumPy array (check format/data).")
            return QImage()

        return qimage
    except Exception as e:
        LOGGER.exception("Error converting NumPy array to QImage: %s", e)
        return QImage()
