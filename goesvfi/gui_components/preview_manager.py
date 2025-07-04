"""Preview management functionality for the main GUI window."""

import contextlib
import os
from pathlib import Path
import tempfile
from typing import Any

import numpy as np
from PIL import Image
from PyQt6.QtCore import QObject, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap

from goesvfi.gui_components.thumbnail_manager import THUMBNAIL_LARGE, ThumbnailManager
from goesvfi.gui_components.update_manager import register_update, request_update
from goesvfi.pipeline.image_cropper import ImageCropper
from goesvfi.pipeline.image_loader import ImageLoader
from goesvfi.pipeline.image_processing_interfaces import ImageData
from goesvfi.pipeline.sanchez_processor import SanchezProcessor
from goesvfi.utils.log import get_logger

LOGGER = get_logger(__name__)

# Image dimensions
GRAYSCALE_DIMENSIONS = 2
COLOR_DIMENSIONS = 3
RGB_CHANNELS = 3
RGBA_CHANNELS = 4

# Image count thresholds
SINGLE_IMAGE_COUNT = 1
TWO_IMAGE_COUNT = 2

# Sanchez resolution thresholds (in pixels)
HIGH_RESOLUTION_THRESHOLD = 1000
MEDIUM_RESOLUTION_THRESHOLD = 500

# Sanchez km/pixel values
SANCHEZ_LOW_RES_KM = 4  # Lower resolution for high pixel values
SANCHEZ_MEDIUM_RES_KM = 2  # Medium resolution
SANCHEZ_HIGH_RES_KM = 1  # Higher resolution for smaller values


class PreviewManager(QObject):
    """Manages preview image functionality for the main window."""

    # Signals
    preview_updated = pyqtSignal(QPixmap, QPixmap, QPixmap)  # first, middle, last
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

        self.current_input_dir: Path | None = None
        self.current_crop_rect: tuple[int, int, int, int] | None = None
        self.first_frame_data: ImageData | None = None
        self.middle_frame_data: ImageData | None = None
        self.last_frame_data: ImageData | None = None

        # Initialize thumbnail manager for memory efficiency
        self.thumbnail_manager = ThumbnailManager()

        # Register with UpdateManager for batched preview updates
        self._setup_update_manager()

    def _setup_update_manager(self) -> None:
        """Register preview updates with the UpdateManager."""
        register_update("preview_load", self._load_preview_internal, priority=1)
        register_update("preview_emit", self._emit_preview_signal, priority=2)
        LOGGER.debug("PreviewManager registered with UpdateManager")

    def _load_preview_internal(self) -> None:
        """Internal method for batched preview loading."""
        # This will be called by the UpdateManager in batches
        if self.current_input_dir:
            self.load_preview_images(
                self.current_input_dir,
                self.current_crop_rect,
                apply_sanchez=False,  # Can be made configurable
            )

    @staticmethod
    def _convert_to_numpy_safely(image_data: Any) -> np.ndarray:
        """Convert image data to numpy array with memory optimization.

        Args:
            image_data: Image data to convert, can be PIL Image or numpy array

        Returns:
            Numpy array representation of the image data
        """
        if isinstance(image_data, Image.Image):
            # Use memory-efficient conversion
            array = np.asarray(image_data)  # No copy unless necessary
            return array.copy() if not array.flags.writeable else array
        # Assume it's already a numpy array
        return image_data if isinstance(image_data, np.ndarray) else np.array(image_data)

    def _emit_preview_signal(self) -> None:
        """Emit preview update signal if data is available."""
        if all([self.first_frame_data, self.middle_frame_data, self.last_frame_data]):
            try:
                # Type narrowing - we know these are not None from the all() check above
                assert self.first_frame_data is not None
                assert self.middle_frame_data is not None
                assert self.last_frame_data is not None

                # Extract numpy arrays from ImageData objects
                first_array = self.first_frame_data.image_data
                middle_array = self.middle_frame_data.image_data
                last_array = self.last_frame_data.image_data

                # Convert PIL Images to numpy arrays with memory optimization
                first_array = PreviewManager._convert_to_numpy_safely(first_array)
                middle_array = PreviewManager._convert_to_numpy_safely(middle_array)
                last_array = PreviewManager._convert_to_numpy_safely(last_array)

                # Convert to QPixmaps and immediately clean up arrays
                pixmaps = [
                    self.numpy_to_qpixmap(first_array),
                    self.numpy_to_qpixmap(middle_array),
                    self.numpy_to_qpixmap(last_array),
                ]

                # Clear large arrays from memory
                del first_array, middle_array, last_array

                self.preview_updated.emit(*pixmaps)
            except Exception as e:
                LOGGER.exception("Error converting preview data to pixmaps")
                self.preview_error.emit(f"Error creating preview: {e}")

    def request_preview_update(
        self,
        input_dir: Path | None = None,
        crop_rect: tuple[int, int, int, int] | None = None,
        *,
        immediate: bool = False,
    ) -> None:
        """Request a preview update through UpdateManager.

        Args:
            input_dir: Input directory (if None, uses current)
            crop_rect: Crop rectangle (if None, uses current)
            immediate: If True, skip batching for immediate update
        """
        if input_dir:
            self.current_input_dir = input_dir
        if crop_rect is not None:
            self.current_crop_rect = crop_rect

        if immediate:
            # Immediate update for user-triggered changes
            self._load_preview_internal()
            self._emit_preview_signal()
        else:
            # Request batched update for automatic changes
            request_update("preview_load")

    def load_preview_images(  # noqa: C901
        self,
        input_dir: Path,
        crop_rect: tuple[int, int, int, int] | None = None,
        apply_sanchez: bool = False,  # noqa: FBT001, FBT002
        sanchez_resolution: tuple[int, int] | None = None,
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
            # Ensure input_dir is a Path object
            if isinstance(input_dir, str):
                input_dir = Path(input_dir)

            # Validate that the directory exists
            if not input_dir.exists() or not input_dir.is_dir():
                LOGGER.debug("Input directory does not exist or is not a directory: %s", input_dir)
                self.preview_error.emit("Input directory does not exist")
                return False

            self.current_input_dir = input_dir
            self.current_crop_rect = crop_rect

            # Load first, middle, and last frames
            first_path, middle_path, last_path = self._get_first_middle_last_paths(input_dir)

            if not first_path or not last_path:
                self.preview_error.emit("No images found in directory")
                return False

            # Load images
            self.first_frame_data = self._load_and_process_image(
                first_path, crop_rect, apply_sanchez, sanchez_resolution
            )
            self.last_frame_data = self._load_and_process_image(last_path, crop_rect, apply_sanchez, sanchez_resolution)

            # Load middle frame if available
            if middle_path:
                self.middle_frame_data = self._load_and_process_image(
                    middle_path, crop_rect, apply_sanchez, sanchez_resolution
                )
            else:
                self.middle_frame_data = None

            if not self.first_frame_data or not self.last_frame_data:
                self.preview_error.emit("Failed to load preview images")
                return False

            # Convert to QPixmaps
            # Extract numpy array from ImageData
            first_array = self.first_frame_data.image_data
            last_array = self.last_frame_data.image_data

            # Convert PIL Image to numpy if needed
            if isinstance(first_array, Image.Image):
                first_array = np.array(first_array)
            if isinstance(last_array, Image.Image):
                last_array = np.array(last_array)

            first_pixmap = self.numpy_to_qpixmap(first_array)
            last_pixmap = self.numpy_to_qpixmap(last_array)

            # Handle middle frame
            if self.middle_frame_data and self.middle_frame_data.image_data is not None:
                middle_array = self.middle_frame_data.image_data
                if isinstance(middle_array, Image.Image):
                    middle_array = np.array(middle_array)
                middle_pixmap = self.numpy_to_qpixmap(middle_array)
            else:
                # Create empty pixmap if no middle frame
                middle_pixmap = QPixmap()

            # Emit update signal
            self.preview_updated.emit(first_pixmap, middle_pixmap, last_pixmap)

            return True  # noqa: TRY300

        except Exception as e:
            LOGGER.exception("Error loading preview images")
            self.preview_error.emit(str(e))
            return False

    def load_preview_thumbnails(
        self,
        input_dir: Path,
        crop_rect: tuple[int, int, int, int] | None = None,
        apply_sanchez: bool = False,  # noqa: FBT001, FBT002
        sanchez_resolution: tuple[int, int] | None = None,
        thumbnail_size: QSize = THUMBNAIL_LARGE,
    ) -> bool:
        """Load preview images as memory-efficient thumbnails.

        This method generates thumbnails instead of loading full-resolution images,
        significantly reducing memory usage for preview display.

        Args:
            input_dir: Directory containing input images
            crop_rect: Optional crop rectangle (x, y, width, height)
            apply_sanchez: Whether to apply Sanchez processing
            sanchez_resolution: Resolution for Sanchez processing
            thumbnail_size: Size for thumbnail generation

        Returns:
            True if thumbnails were loaded successfully
        """
        try:
            # Ensure input_dir is a Path object
            if isinstance(input_dir, str):
                input_dir = Path(input_dir)

            # Validate that the directory exists
            if not input_dir.exists() or not input_dir.is_dir():
                LOGGER.debug("Input directory does not exist or is not a directory: %s", input_dir)
                self.preview_error.emit("Input directory does not exist")
                return False

            self.current_input_dir = input_dir
            self.current_crop_rect = crop_rect

            # Get image paths
            first_path, middle_path, last_path = self._get_first_middle_last_paths(input_dir)

            if not first_path or not last_path:
                self.preview_error.emit("No images found in directory")
                return False

            # For Sanchez processing, we need to generate temporary processed images
            if apply_sanchez:
                # Process with Sanchez first, then generate thumbnails
                first_pixmap = self._load_and_process_sanchez_thumbnail(
                    first_path, crop_rect, sanchez_resolution, thumbnail_size
                )
                last_pixmap = self._load_and_process_sanchez_thumbnail(
                    last_path, crop_rect, sanchez_resolution, thumbnail_size
                )

                if middle_path:
                    middle_pixmap = self._load_and_process_sanchez_thumbnail(
                        middle_path, crop_rect, sanchez_resolution, thumbnail_size
                    )
                else:
                    middle_pixmap = QPixmap()
            else:
                # Generate thumbnails directly without Sanchez
                first_pixmap = self.thumbnail_manager.get_thumbnail(first_path, thumbnail_size, crop_rect)
                last_pixmap = self.thumbnail_manager.get_thumbnail(last_path, thumbnail_size, crop_rect)

                if middle_path:
                    middle_pixmap = self.thumbnail_manager.get_thumbnail(middle_path, thumbnail_size, crop_rect)
                else:
                    middle_pixmap = QPixmap()

            # Validate thumbnails
            if not first_pixmap or first_pixmap.isNull() or not last_pixmap or last_pixmap.isNull():
                self.preview_error.emit("Failed to generate preview thumbnails")
                return False

            # Store minimal frame data for compatibility
            # Note: For thumbnail mode, we don't load full image data to save memory
            # Set frame_data to None since we only have thumbnails
            self.first_frame_data = None
            self.last_frame_data = None
            self.middle_frame_data = None

            # Emit update signal with thumbnails
            self.preview_updated.emit(first_pixmap, middle_pixmap, last_pixmap)

            LOGGER.info("Loaded preview thumbnails (size: %dx%d)", thumbnail_size.width(), thumbnail_size.height())
            return True  # noqa: TRY300

        except Exception as e:
            LOGGER.exception("Error loading preview thumbnails")
            self.preview_error.emit(str(e))
            return False

    def _load_and_process_sanchez_thumbnail(
        self,
        image_path: Path,
        crop_rect: tuple[int, int, int, int] | None,
        sanchez_resolution: tuple[int, int] | None,
        thumbnail_size: QSize,
    ) -> QPixmap | None:
        """Load image, process with Sanchez, then generate thumbnail.

        Args:
            image_path: Path to image file
            crop_rect: Optional crop rectangle
            sanchez_resolution: Sanchez processing resolution
            thumbnail_size: Final thumbnail size

        Returns:
            QPixmap thumbnail or None if failed
        """
        try:
            # Load and process image with existing method
            image_data = self._load_and_process_image(image_path, crop_rect, True, sanchez_resolution)  # noqa: FBT003

            if not image_data or image_data.image_data is None:
                return None

            # Save processed image to temp file
            temp_path = self._temp_dir / f"sanchez_{image_path.stem}.png"

            # Convert to PIL Image if needed
            img_array = image_data.image_data
            img = Image.fromarray(img_array) if isinstance(img_array, np.ndarray) else img_array

            # Save temporarily
            img.save(temp_path, "PNG")

            # Generate thumbnail from processed image
            thumbnail = self.thumbnail_manager.get_thumbnail(temp_path, thumbnail_size)

            # Clean up temp file
            with contextlib.suppress(Exception):
                temp_path.unlink()

            return thumbnail  # noqa: TRY300

        except Exception:
            LOGGER.exception("Error processing Sanchez thumbnail for %s", image_path)
            return None

    def _get_first_middle_last_paths(self, input_dir: Path) -> tuple[Path | None, Path | None, Path | None]:  # noqa: PLR6301
        """Get the first, middle, and last image paths from a directory.

        Args:
            input_dir: Directory to scan

        Returns:
            Tuple of (first_path, middle_path, last_path), any may be None
        """
        try:
            # Ensure input_dir is a Path object
            if isinstance(input_dir, str):
                input_dir = Path(input_dir)

            # Get all image files
            image_extensions = {".png", ".jpg", ".jpeg", ".bmp", ".tiff"}
            image_files = [
                file for file in input_dir.iterdir() if file.is_file() and file.suffix.lower() in image_extensions
            ]

            if not image_files:
                return None, None, None

            # Sort by name
            image_files.sort()

            # Calculate middle index
            if len(image_files) == SINGLE_IMAGE_COUNT:
                # Only one image - use it for all three
                return image_files[0], image_files[0], image_files[0]
            if len(image_files) == TWO_IMAGE_COUNT:
                # Two images - no middle
                return image_files[0], None, image_files[1]
            # Three or more images - calculate middle
            middle_index = len(image_files) // 2
            return image_files[0], image_files[middle_index], image_files[-1]

        except Exception:
            LOGGER.exception("Error getting first/middle/last paths")
            return None, None, None

    def _load_and_process_image(  # noqa: C901, PLR0912
        self,
        path: Path,
        crop_rect: tuple[int, int, int, int] | None,
        apply_sanchez: bool,  # noqa: FBT001
        sanchez_resolution: tuple[int, int] | None,
    ) -> ImageData | None:
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
                return None

            # Apply cropping if specified
            if crop_rect:
                # Convert from (x, y, width, height) to (left, top, right, bottom)
                x, y, width, height = crop_rect
                left, top, right, bottom = x, y, x + width, y + height

                # Get image dimensions for validation
                from typing import cast

                image_array = cast("ndarray[Any, Any]", image_data.image_data)
                img_height, img_width = image_array.shape[:2]

                # Validate crop dimensions and coordinates
                if width <= 0 or height <= 0:
                    LOGGER.error("Invalid crop dimensions: width=%d, height=%d", width, height)
                    return None

                # Validate crop coordinates are within image bounds
                if not (0 <= left < right <= img_width and 0 <= top < bottom <= img_height):
                    LOGGER.error(
                        "Crop area %s exceeds image dimensions %dx%d, skipping crop", crop_rect, img_width, img_height
                    )
                    # Return the original image data without cropping rather than None
                    LOGGER.debug("Continuing without crop due to invalid bounds")
                else:
                    crop_coords = (left, top, right, bottom)
                    LOGGER.debug("Converting crop rect %s to coordinates %s", crop_rect, crop_coords)
                    cropped_data = self.cropper.crop(image_data, crop_coords)
                    if cropped_data:
                        image_data = cropped_data
                    else:
                        LOGGER.warning("Crop operation failed, using original image")

            # Apply Sanchez processing if specified
            if apply_sanchez:
                # Convert resolution to valid Sanchez format
                # Sanchez expects km per pixel, valid values: 0.5, 1, 2, 4
                if isinstance(sanchez_resolution, tuple | list):
                    # If tuple/list provided, use a default valid value
                    res_km = SANCHEZ_MEDIUM_RES_KM  # 2 km/pixel default
                elif isinstance(sanchez_resolution, int | float):
                    # Map common pixel values to km/pixel values
                    if sanchez_resolution >= HIGH_RESOLUTION_THRESHOLD:
                        res_km = SANCHEZ_LOW_RES_KM  # Lower resolution for high pixel values
                    elif sanchez_resolution >= MEDIUM_RESOLUTION_THRESHOLD:
                        res_km = SANCHEZ_MEDIUM_RES_KM  # Medium resolution
                    else:
                        res_km = SANCHEZ_HIGH_RES_KM  # Higher resolution for smaller values
                else:
                    res_km = SANCHEZ_MEDIUM_RES_KM  # Default fallback

                image_data = self.sanchez_processor.process(image_data, res_km=res_km)
                if not image_data:
                    return None

            return image_data  # noqa: TRY300

        except Exception:
            LOGGER.exception("Error loading/processing image %s", path)
            return None

    def numpy_to_qpixmap(self, array: np.ndarray[Any, np.dtype[np.uint8]]) -> QPixmap:  # noqa: PLR6301
        """Convert a numpy array to QPixmap.

        Args:
            array: Numpy array with shape (H, W, C) and dtype uint8

        Returns:
            QPixmap of the image

        Raises:
            ValueError: If array has unsupported shape
        """
        try:
            # Check if array is actually a numpy array
            if not isinstance(array, np.ndarray):
                LOGGER.error("Expected numpy array, got %s: %s", type(array), array)
                return QPixmap()

            height, width = array.shape[:2]

            # Handle different channel counts
            if array.ndim == GRAYSCALE_DIMENSIONS:
                # Grayscale
                qimage = QImage(
                    array.data.tobytes(),
                    width,
                    height,
                    width,
                    QImage.Format.Format_Grayscale8,
                )
            elif array.ndim == COLOR_DIMENSIONS and array.shape[2] == RGB_CHANNELS:
                # RGB
                bytes_per_line = 3 * width
                qimage = QImage(
                    array.data.tobytes(),
                    width,
                    height,
                    bytes_per_line,
                    QImage.Format.Format_RGB888,
                )
            elif array.ndim == COLOR_DIMENSIONS and array.shape[2] == RGBA_CHANNELS:
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
                msg = f"Unsupported array shape: {array.shape}"
                raise ValueError(msg)  # noqa: TRY301

            return QPixmap.fromImage(qimage)

        except Exception:
            LOGGER.exception("Error converting numpy array to QPixmap")
            if isinstance(array, np.ndarray):
                LOGGER.exception("Array shape: %s, dtype: %s", array.shape, array.dtype)
            else:
                LOGGER.exception("Input is not a numpy array: %s", type(array))
            # Return empty pixmap on error
            return QPixmap()

    def scale_preview_pixmap(self, pixmap: QPixmap, target_size: QSize) -> QPixmap:  # noqa: PLR6301
        """Scale a pixmap to fit within target size while maintaining aspect ratio.

        Args:
            pixmap: The pixmap to scale
            target_size: Maximum size for the scaled pixmap

        Returns:
            Scaled pixmap that fits within the target size
        """
        if pixmap.isNull():
            return pixmap

        return pixmap.scaled(
            target_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    def get_current_frame_data(
        self,
    ) -> tuple[ImageData | None, ImageData | None, ImageData | None]:
        """Get the current frame data.

        Returns:
            Tuple of (first_frame_data, middle_frame_data, last_frame_data)
        """
        return self.first_frame_data, self.middle_frame_data, self.last_frame_data

    def clear_previews(self) -> None:
        """Clear all preview data."""
        self.first_frame_data = None
        self.middle_frame_data = None
        self.last_frame_data = None
        self.current_input_dir = None
        self.current_crop_rect = None

    def clear_cache(self) -> None:
        """Clear the thumbnail cache to free memory."""
        if hasattr(self, "thumbnail_manager"):
            self.thumbnail_manager.clear_cache()
            LOGGER.info("Preview thumbnail cache cleared")

    def get_memory_usage_info(self) -> dict[str, int]:
        """Get information about memory usage.

        Returns:
            Dictionary with memory statistics
        """
        if hasattr(self, "thumbnail_manager"):
            return self.thumbnail_manager.get_cache_info()
        return {"cache_limit_mb": 0, "items_cached": 0}
