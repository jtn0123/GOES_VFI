"""Thumbnail generation and caching for memory-efficient preview handling."""

import hashlib
from pathlib import Path

import numpy as np
from PIL import Image
from PyQt6.QtCore import QSize
from PyQt6.QtGui import QPixmap, QPixmapCache

from goesvfi.utils import log

LOGGER = log.get_logger(__name__)

# Default thumbnail sizes
THUMBNAIL_SMALL = QSize(200, 200)
THUMBNAIL_MEDIUM = QSize(400, 400)
THUMBNAIL_LARGE = QSize(800, 800)

# Memory cache settings
CACHE_SIZE_MB = 100  # Maximum cache size in MB
PIXMAP_CACHE_SIZE_KB = CACHE_SIZE_MB * 1024  # Convert to KB for QPixmapCache


class ThumbnailManager:
    """Manages thumbnail generation and caching for preview images."""

    def __init__(self) -> None:
        """Initialize the thumbnail manager."""
        self.file_cache: dict[str, tuple[QPixmap, QPixmap, QPixmap]] = {}

        # Configure QPixmapCache
        QPixmapCache.setCacheLimit(PIXMAP_CACHE_SIZE_KB)

        LOGGER.info(f"ThumbnailManager initialized with {CACHE_SIZE_MB}MB cache")

    def get_thumbnail(
        self,
        image_path: Path,
        size: QSize = THUMBNAIL_MEDIUM,
        crop_rect: tuple[int, int, int, int] | None = None,
    ) -> QPixmap | None:
        """Get or generate a thumbnail for the given image.

        Args:
            image_path: Path to the image file
            size: Desired thumbnail size
            crop_rect: Optional crop rectangle (x, y, width, height)

        Returns:
            QPixmap thumbnail or None if failed
        """
        # Generate cache key
        cache_key = self._generate_cache_key(image_path, size, crop_rect)

        # Check QPixmapCache first
        cached_pixmap = QPixmapCache.find(cache_key)
        if cached_pixmap and not cached_pixmap.isNull():
            LOGGER.debug(f"Thumbnail cache hit for {image_path.name}")
            return cached_pixmap

        # Generate thumbnail
        thumbnail = self._generate_thumbnail(image_path, size, crop_rect)

        if thumbnail and not thumbnail.isNull():
            # Store in cache
            QPixmapCache.insert(cache_key, thumbnail)
            LOGGER.debug(f"Generated and cached thumbnail for {image_path.name}")

        return thumbnail

    def _generate_cache_key(
        self,
        image_path: Path,
        size: QSize,
        crop_rect: tuple[int, int, int, int] | None = None,
    ) -> str:
        """Generate a unique cache key for the thumbnail.

        Args:
            image_path: Path to the image file
            size: Thumbnail size
            crop_rect: Optional crop rectangle

        Returns:
            Cache key string
        """
        # Include file path, size, modification time, and crop rect in key
        try:
            mtime = image_path.stat().st_mtime
        except Exception:
            mtime = 0

        key_parts = [
            str(image_path),
            f"{size.width()}x{size.height()}",
            str(mtime),
        ]

        if crop_rect:
            key_parts.append(f"crop_{crop_rect[0]}_{crop_rect[1]}_{crop_rect[2]}_{crop_rect[3]}")

        key_string = "_".join(key_parts)

        # Use hash for shorter key
        return hashlib.md5(key_string.encode()).hexdigest()

    def _generate_thumbnail(
        self,
        image_path: Path,
        size: QSize,
        crop_rect: tuple[int, int, int, int] | None = None,
    ) -> QPixmap | None:
        """Generate a thumbnail for the given image.

        Args:
            image_path: Path to the image file
            size: Desired thumbnail size
            crop_rect: Optional crop rectangle (x, y, width, height)

        Returns:
            QPixmap thumbnail or None if failed
        """
        try:
            # Open image with PIL
            with Image.open(image_path) as img:
                # Convert to RGB if necessary
                if img.mode not in {"RGB", "RGBA"}:
                    img = img.convert("RGB")

                # Apply crop if specified
                if crop_rect:
                    x, y, width, height = crop_rect
                    img = img.crop((x, y, x + width, y + height))

                # Calculate thumbnail size maintaining aspect ratio
                img.thumbnail((size.width(), size.height()), Image.Resampling.LANCZOS)

                # Convert to numpy array
                img_array = np.array(img)

                # Convert to QPixmap
                height, width = img_array.shape[:2]

                if img.mode == "RGBA":
                    bytes_per_line = 4 * width
                    from PyQt6.QtGui import QImage
                    qimage = QImage(
                        img_array.data.tobytes(),
                        width,
                        height,
                        bytes_per_line,
                        QImage.Format.Format_RGBA8888,
                    )
                else:
                    bytes_per_line = 3 * width
                    from PyQt6.QtGui import QImage
                    qimage = QImage(
                        img_array.data.tobytes(),
                        width,
                        height,
                        bytes_per_line,
                        QImage.Format.Format_RGB888,
                    )

                return QPixmap.fromImage(qimage)

        except Exception:
            LOGGER.exception(f"Error generating thumbnail for {image_path}")
            return None

    def preload_thumbnails(
        self,
        image_paths: list[Path],
        size: QSize = THUMBNAIL_MEDIUM,
        crop_rect: tuple[int, int, int, int] | None = None,
    ) -> None:
        """Preload thumbnails for a list of images.

        Args:
            image_paths: List of image paths to preload
            size: Thumbnail size
            crop_rect: Optional crop rectangle
        """
        for path in image_paths:
            self.get_thumbnail(path, size, crop_rect)

    def clear_cache(self) -> None:
        """Clear the thumbnail cache."""
        QPixmapCache.clear()
        self.file_cache.clear()
        LOGGER.info("Thumbnail cache cleared")

    def get_cache_info(self) -> dict[str, int]:
        """Get information about the cache.

        Returns:
            Dictionary with cache statistics
        """
        return {
            "cache_limit_kb": QPixmapCache.cacheLimit(),
            "cache_limit_mb": QPixmapCache.cacheLimit() // 1024,
            "items_cached": len(self.file_cache),
        }

    def generate_multi_size_thumbnails(
        self,
        image_path: Path,
        crop_rect: tuple[int, int, int, int] | None = None,
    ) -> tuple[QPixmap | None, QPixmap | None, QPixmap | None]:
        """Generate thumbnails in multiple sizes for an image.

        Args:
            image_path: Path to the image file
            crop_rect: Optional crop rectangle

        Returns:
            Tuple of (small, medium, large) thumbnails
        """
        small = self.get_thumbnail(image_path, THUMBNAIL_SMALL, crop_rect)
        medium = self.get_thumbnail(image_path, THUMBNAIL_MEDIUM, crop_rect)
        large = self.get_thumbnail(image_path, THUMBNAIL_LARGE, crop_rect)

        return small, medium, large
