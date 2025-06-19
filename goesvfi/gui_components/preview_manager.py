"""Preview management functionality for the main GUI window."""

import os
import tempfile
from pathlib import Path
from typing import Any, Optional, Tuple

import numpy as np
from PIL import Image
from PyQt6.QtCore import QObject, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap

from goesvfi.pipeline.image_cropper import ImageCropper
from goesvfi.pipeline.image_loader import ImageLoader
from goesvfi.pipeline.image_processing_interfaces import ImageData
from goesvfi.pipeline.sanchez_processor import SanchezProcessor
from goesvfi.utils.log import get_logger

LOGGER = get_logger(__name__)


class PreviewManager(QObject):
    """Manages preview image functionality for the main window."""

    # Signals
    preview_updated = pyqtSignal(QPixmap, QPixmap)  # before, after
    preview_error = pyqtSignal(str)  # error message

    def __init__(self) -> None:
        """Initialize the preview manager."""
        super().__init__()
        self.image_loader = ImageLoader()
        self.cropper = ImageCropper()
        # Create temporary directory for Sanchez processor
        self._temp_dir = Path(tempfile.gettempdir()) / f"goes_vfi_preview_{os.getpid()}"
        self._temp_dir.mkdir(exist_ok=True)
        self.sanchez_processor = SanchezProcessor(self._temp_dir)

        self.current_input_dir: Optional[Path] = None
        self.current_crop_rect: Optional[Tuple[int, int, int, int]] = None
        self.first_frame_data: Optional[ImageData] = None
        self.last_frame_data: Optional[ImageData] = None

    def load_preview_images(
        self,
        input_dir: Path,
        crop_rect: Optional[Tuple[int, int, int, int]] = None,
        apply_sanchez: bool = False,
        sanchez_resolution: Optional[Tuple[int, int]] = None,
    ) -> bool:
        """Load preview images from the input directory.

        Args:
            input_dir: Directory containing input images
            crop_rect: Optional crop rectangle (x, y, width, height)
            apply_sanchez: Whether to apply Sanchez processing
            sanchez_resolution: Resolution for Sanchez processing

        Returns:
            True if preview images were loaded successfully
        """
        try:
            pass
            self.current_input_dir = input_dir
            self.current_crop_rect = crop_rect

            # Load first and last frames
            first_path, last_path = self._get_first_last_paths(input_dir)

            if not first_path or not last_path:
                pass
                self.preview_error.emit("No images found in directory")
                return False

            # Load images
            self.first_frame_data = self._load_and_process_image(
                first_path, crop_rect, apply_sanchez, sanchez_resolution
            )
            self.last_frame_data = self._load_and_process_image(
                last_path, crop_rect, apply_sanchez, sanchez_resolution
            )

            if not self.first_frame_data or not self.last_frame_data:
                pass
                self.preview_error.emit("Failed to load preview images")
                return False

            # Convert to QPixmaps
            # Extract numpy array from ImageData
            first_array = self.first_frame_data.image_data
            last_array = self.last_frame_data.image_data

            # Convert PIL Image to numpy if needed
            if isinstance(first_array, Image.Image):
                pass
                first_array = np.array(first_array)
            if isinstance(last_array, Image.Image):
                pass
                last_array = np.array(last_array)

            first_pixmap = self._numpy_to_qpixmap(first_array)
            last_pixmap = self._numpy_to_qpixmap(last_array)

            # Emit update signal
            self.preview_updated.emit(first_pixmap, last_pixmap)

            return True

        except Exception as e:
            pass
            LOGGER.error("Error loading preview images: %s", e)
            self.preview_error.emit(str(e))
            return False

    def _get_first_last_paths(
        self, input_dir: Path
    ) -> Tuple[Optional[Path], Optional[Path]]:
        """Get the first and last image paths from a directory.

        Args:
            input_dir: Directory to scan

        Returns:
            Tuple of (first_path, last_path), either may be None
        """
        try:
            # Get all image files
            image_extensions = {".png", ".jpg", ".jpeg", ".bmp", ".tiff"}
            image_files = []

            for file in input_dir.iterdir():
                pass
                if file.is_file() and file.suffix.lower() in image_extensions:
                    pass
                    image_files.append(file)

            if not image_files:
                pass
                return None, None

            # Sort by name
            image_files.sort()

            # Return first and last
            return image_files[0], image_files[-1]

        except Exception as e:
            pass
            LOGGER.error("Error getting first/last paths: %s", e)
            return None, None

    def _load_and_process_image(
        self,
        path: Path,
        crop_rect: Optional[Tuple[int, int, int, int]],
        apply_sanchez: bool,
        sanchez_resolution: Optional[Tuple[int, int]],
    ) -> Optional[ImageData]:
        """Load and process a single image.

        Args:
            path: Path to the image file
            crop_rect: Optional crop rectangle
            apply_sanchez: Whether to apply Sanchez processing
            sanchez_resolution: Resolution for Sanchez processing

        Returns:
            Processed ImageData or None on error
        """
        try:
            # Load image
            image_data = self.image_loader.load(str(path))

            if not image_data:
                pass
                return None

            # Apply cropping if specified
            if crop_rect:
                pass
                image_data = self.cropper.crop(image_data, crop_rect)
                if not image_data:
                    pass
                    return None

            # Apply Sanchez processing if specified
            if apply_sanchez:
                pass
                # Convert resolution to valid Sanchez format
                # Sanchez expects km per pixel, valid values: 0.5, 1, 2, 4
                if isinstance(sanchez_resolution, (tuple, list)):
                    pass
                    # If tuple/list provided, use a default valid value
                    res_km = 2  # 2 km/pixel default
                elif isinstance(sanchez_resolution, (int, float)):
                    pass
                    # Map common pixel values to km/pixel values
                    if sanchez_resolution >= 1000:
                        pass
                        res_km = 4  # Lower resolution for high pixel values
                    elif sanchez_resolution >= 500:
                        pass
                        res_km = 2  # Medium resolution
                    else:
                        res_km = 1  # Higher resolution for smaller values
                else:
                    res_km = 2  # Default fallback

                image_data = self.sanchez_processor.process(image_data, res_km=res_km)
                if not image_data:
                    pass
                    return None

            return image_data

        except Exception as e:
            pass
            LOGGER.error("Error loading/processing image %s: %s", path, e)
            return None

    def _numpy_to_qpixmap(self, array: np.ndarray[Any, np.dtype[np.uint8]]) -> QPixmap:
        """Convert a numpy array to QPixmap.

        Args:
            array: Numpy array with shape (H, W, C) and dtype uint8

        Returns:
            QPixmap of the image
        """
        try:
            height, width = array.shape[:2]

            # Handle different channel counts
            if array.ndim == 2:
                pass
                # Grayscale
                qimage = QImage(
                    array.data.tobytes(),
                    width,
                    height,
                    width,
                    QImage.Format.Format_Grayscale8,
                )
            elif array.ndim == 3 and array.shape[2] == 3:
                pass
                # RGB
                bytes_per_line = 3 * width
                qimage = QImage(
                    array.data.tobytes(),
                    width,
                    height,
                    bytes_per_line,
                    QImage.Format.Format_RGB888,
                )
            elif array.ndim == 3 and array.shape[2] == 4:
                pass
                # RGBA
                bytes_per_line = 4 * width
                qimage = QImage(
                    array.data.tobytes(),
                    width,
                    height,
                    bytes_per_line,
                    QImage.Format.Format_RGBA8888,
                )
            else:
                raise ValueError(f"Unsupported array shape: {array.shape}")

            return QPixmap.fromImage(qimage)

        except Exception as e:
            pass
            LOGGER.error("Error converting numpy array to QPixmap: %s", e)
            # Return empty pixmap on error
            return QPixmap()

    def scale_preview_pixmap(self, pixmap: QPixmap, target_size: QSize) -> QPixmap:
        """Scale a pixmap to fit within target size while maintaining aspect ratio.

        Args:
            pixmap: The pixmap to scale
            target_size: Maximum size for the scaled pixmap

        Returns:
            Scaled pixmap
        """
        if pixmap.isNull():
            pass
            return pixmap

        return pixmap.scaled(
            target_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    def get_current_frame_data(self) -> Tuple[Optional[ImageData], Optional[ImageData]]:
        """Get the current frame data.

        Returns:
            Tuple of (first_frame_data, last_frame_data)
        """
        return self.first_frame_data, self.last_frame_data

    def clear_previews(self) -> None:
        """Clear all preview data."""
        self.first_frame_data = None
        self.last_frame_data = None
        self.current_input_dir = None
        self.current_crop_rect = None
        LOGGER.debug("Preview data cleared")
