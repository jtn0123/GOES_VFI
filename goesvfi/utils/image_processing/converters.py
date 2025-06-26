"""
Image format converters for the image processing framework.

Provides converters between different image formats (numpy arrays, QImage, QPixmap)
to reduce complexity in image handling functions.
"""

from typing import Any, Dict, Optional

import numpy as np
from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QImage, QPixmap

from .base import ImageProcessingResult, ProcessorBase


class ArrayToImageConverter(ProcessorBase):
    """Converts numpy arrays to QImage objects."""

    def __init__(self, format_hint: Optional[QImage.Format] = None) -> None:
        super().__init__("array_to_image")
        self.format_hint = format_hint

    def process(
        self, input_data: Any, context: Optional[Dict[str, Any]] = None
    ) -> ImageProcessingResult:
        """Convert numpy array to QImage."""
        try:
            if not isinstance(input_data, np.ndarray):
                return ImageProcessingResult.failure_result(
                    self._create_error(f"Expected numpy array, got {type(input_data)}")
                )

            array = input_data

            # Handle different array shapes and types
            if array.ndim == 2:
                # Grayscale image
                qimage = self._array_to_qimage_grayscale(array)
            elif array.ndim == 3:
                if array.shape[2] == 3:
                    # RGB image
                    qimage = self._array_to_qimage_rgb(array)
                elif array.shape[2] == 4:
                    # RGBA image
                    qimage = self._array_to_qimage_rgba(array)
                else:
                    return ImageProcessingResult.failure_result(
                        self._create_error(f"Unsupported array shape: {array.shape}")
                    )
            else:
                return ImageProcessingResult.failure_result(
                    self._create_error(f"Unsupported array dimensions: {array.ndim}")
                )

            if qimage.isNull():
                return ImageProcessingResult.failure_result(
                    self._create_error("Failed to create QImage from array")
                )

            return ImageProcessingResult.success_result(
                qimage,
                {"original_shape": array.shape, "original_dtype": str(array.dtype)},
            )

        except Exception as e:
            return ImageProcessingResult.failure_result(
                self._create_error(f"Array to QImage conversion failed: {e}", e)
            )

    def _array_to_qimage_grayscale(self, array: np.ndarray) -> QImage:
        """Convert grayscale array to QImage."""
        # Ensure 8-bit
        if array.dtype != np.uint8:
            array = ((array - array.min()) / (array.max() - array.min()) * 255).astype(
                np.uint8
            )

        height, width = array.shape
        return QImage(array.data, width, height, width, QImage.Format.Format_Grayscale8)

    def _array_to_qimage_rgb(self, array: np.ndarray) -> QImage:
        """Convert RGB array to QImage."""
        # Ensure 8-bit
        if array.dtype != np.uint8:
            array = ((array - array.min()) / (array.max() - array.min()) * 255).astype(
                np.uint8
            )

        height, width, channels = array.shape
        bytes_per_line = width * channels
        return QImage(
            array.data, width, height, bytes_per_line, QImage.Format.Format_RGB888
        )

    def _array_to_qimage_rgba(self, array: np.ndarray) -> QImage:
        """Convert RGBA array to QImage."""
        # Ensure 8-bit
        if array.dtype != np.uint8:
            array = ((array - array.min()) / (array.max() - array.min()) * 255).astype(
                np.uint8
            )

        height, width, channels = array.shape
        bytes_per_line = width * channels
        return QImage(
            array.data, width, height, bytes_per_line, QImage.Format.Format_RGBA8888
        )


class ImageToPixmapConverter(ProcessorBase):
    """Converts QImage to QPixmap with optional scaling."""

    def __init__(
        self,
        target_size: Optional[QSize] = None,
        aspect_ratio_mode: Qt.AspectRatioMode = Qt.AspectRatioMode.KeepAspectRatio,
        transformation_mode: Qt.TransformationMode = Qt.TransformationMode.SmoothTransformation,
    ) -> None:
        super().__init__("image_to_pixmap")
        self.target_size = target_size
        self.aspect_ratio_mode = aspect_ratio_mode
        self.transformation_mode = transformation_mode

    def process(
        self, input_data: Any, context: Optional[Dict[str, Any]] = None
    ) -> ImageProcessingResult:
        """Convert QImage to QPixmap with optional scaling."""
        try:
            if not isinstance(input_data, QImage):
                return ImageProcessingResult.failure_result(
                    self._create_error(f"Expected QImage, got {type(input_data)}")
                )

            qimage = input_data

            # Get target size from context or instance variable
            target_size = self.target_size
            if context and "target_size" in context:
                target_size = context["target_size"]

            # Scale if target size is specified
            if target_size and (target_size.width() > 0 and target_size.height() > 0):
                scaled_image = qimage.scaled(
                    target_size, self.aspect_ratio_mode, self.transformation_mode
                )
            else:
                scaled_image = qimage

            # Convert to pixmap
            pixmap = QPixmap.fromImage(scaled_image)

            if pixmap.isNull():
                return ImageProcessingResult.failure_result(
                    self._create_error("Failed to create QPixmap from QImage")
                )

            metadata = {
                "original_size": qimage.size(),
                "final_size": pixmap.size(),
                "scaled": target_size is not None,
            }

            return ImageProcessingResult.success_result(pixmap, metadata)

        except Exception as e:
            return ImageProcessingResult.failure_result(
                self._create_error(f"QImage to QPixmap conversion failed: {e}", e)
            )


class ImageDataConverter(ProcessorBase):
    """Converts ImageData objects to numpy arrays."""

    def __init__(self) -> None:
        super().__init__("imagedata_to_array")

    def process(
        self, input_data: Any, context: Optional[Dict[str, Any]] = None
    ) -> ImageProcessingResult:
        """Convert ImageData to numpy array."""
        try:
            # Import here to avoid circular imports
            from goesvfi.pipeline.image_processing_interfaces import ImageData

            if not isinstance(input_data, ImageData):
                return ImageProcessingResult.failure_result(
                    self._create_error(f"Expected ImageData, got {type(input_data)}")
                )

            image_data = input_data

            if image_data.image_data is None:
                return ImageProcessingResult.failure_result(
                    self._create_error("ImageData contains no image data")
                )

            array = image_data.image_data

            if not isinstance(array, np.ndarray):
                return ImageProcessingResult.failure_result(
                    self._create_error(
                        f"ImageData contains non-array data: {type(array)}"
                    )
                )

            metadata = {
                "original_metadata": image_data.metadata,
                "array_shape": array.shape,
                "array_dtype": str(array.dtype),
            }

            return ImageProcessingResult.success_result(array, metadata)

        except Exception as e:
            return ImageProcessingResult.failure_result(
                self._create_error(f"ImageData to array conversion failed: {e}", e)
            )


class CropProcessor(ProcessorBase):
    """Crops numpy arrays based on crop rectangle."""

    def __init__(self) -> None:
        super().__init__("crop")

    def process(
        self, input_data: Any, context: Optional[Dict[str, Any]] = None
    ) -> ImageProcessingResult:
        """Crop numpy array."""
        try:
            if not isinstance(input_data, np.ndarray):
                return ImageProcessingResult.failure_result(
                    self._create_error(f"Expected numpy array, got {type(input_data)}")
                )

            array = input_data

            if not context or "crop_rect" not in context:
                # No crop requested, pass through
                return ImageProcessingResult.success_result(array, {"cropped": False})

            crop_rect = context["crop_rect"]
            if crop_rect is None:
                # No crop requested, pass through
                return ImageProcessingResult.success_result(array, {"cropped": False})

            # Extract crop coordinates
            if isinstance(crop_rect, (tuple, list)) and len(crop_rect) == 4:
                x, y, width, height = crop_rect
            else:
                return ImageProcessingResult.failure_result(
                    self._create_error(f"Invalid crop_rect format: {crop_rect}")
                )

            # Validate crop bounds
            if array.ndim == 2:
                img_height, img_width = array.shape
            elif array.ndim == 3:
                img_height, img_width = array.shape[:2]
            else:
                return ImageProcessingResult.failure_result(
                    self._create_error(
                        f"Unsupported array shape for cropping: {array.shape}"
                    )
                )

            # Clamp crop coordinates to image bounds
            x = max(0, min(x, img_width))
            y = max(0, min(y, img_height))
            width = max(1, min(width, img_width - x))
            height = max(1, min(height, img_height - y))

            # Perform crop
            if array.ndim == 2:
                cropped = array[y : y + height, x : x + width]
            else:
                cropped = array[y : y + height, x : x + width, :]

            metadata = {
                "cropped": True,
                "original_shape": array.shape,
                "crop_rect": (x, y, width, height),
                "cropped_shape": cropped.shape,
            }

            return ImageProcessingResult.success_result(cropped, metadata)

        except Exception as e:
            return ImageProcessingResult.failure_result(
                self._create_error(f"Crop processing failed: {e}", e)
            )
