"""
Preview-specific image processing utilities.

Provides specialized processors for generating preview images with annotations
and overlays.
"""

from typing import Any, Dict, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter, QPixmap

from .base import ImageProcessingResult, ProcessorBase


class SanchezWarningOverlay(ProcessorBase):
    """Adds warning overlay for Sanchez processing failures."""

    def __init__(self):
        super().__init__("sanchez_warning_overlay")

    def process(
        self, input_data: Any, context: Optional[Dict[str, Any]] = None
    ) -> ImageProcessingResult:
        """Add Sanchez warning overlay to pixmap."""
        try:
            if not isinstance(input_data, QPixmap):
                return ImageProcessingResult.failure_result(
                    self._create_error(f"Expected QPixmap, got {type(input_data)}")
                )

            pixmap = input_data.copy()  # Work on a copy

            # Check if warning should be drawn
            should_draw = False
            error_message = ""

            if context:
                should_draw = context.get("draw_sanchez_warning", False)
                error_message = context.get(
                    "sanchez_error_message", "Sanchez processing failed"
                )

            if not should_draw:
                # No warning needed, pass through
                return ImageProcessingResult.success_result(
                    pixmap, {"warning_added": False}
                )

            # Draw warning overlay
            try:
                painter = QPainter(pixmap)
                font = painter.font()
                font.setBold(True)
                painter.setFont(font)

                # Draw semi-transparent background
                painter.fillRect(0, 0, pixmap.width(), 20, QColor(0, 0, 0, 150))

                # Draw error text
                painter.setPen(Qt.GlobalColor.red)
                truncated_message = (
                    error_message[:35] + "..."
                    if len(error_message) > 35
                    else error_message
                )
                painter.drawText(5, 15, f"Sanchez failed: {truncated_message}")
                painter.end()

                return ImageProcessingResult.success_result(
                    pixmap, {"warning_added": True, "error_message": error_message}
                )

            except Exception as paint_error:
                return ImageProcessingResult.failure_result(
                    self._create_error(
                        f"Failed to draw warning overlay: {paint_error}", paint_error
                    )
                )

        except Exception as e:
            return ImageProcessingResult.failure_result(
                self._create_error(f"Warning overlay processing failed: {e}", e)
            )


class PreviewProcessor(ProcessorBase):
    """High-level processor for creating preview images with all processing steps."""

    def __init__(self):
        super().__init__("preview_processor")

    def process(
        self, input_data: Any, context: Optional[Dict[str, Any]] = None
    ) -> ImageProcessingResult:
        """Process input through complete preview pipeline."""
        from .cache import SanchezCacheProcessor
        from .converters import (
            ArrayToImageConverter,
            CropProcessor,
            ImageDataConverter,
            ImageToPixmapConverter,
        )
        from .pipeline import ImageProcessingPipeline

        try:
            # Build processing pipeline based on context
            pipeline_stages = []

            # 1. Check Sanchez cache first (if applicable)
            if context and context.get("apply_sanchez", False):
                sanchez_cache = context.get("sanchez_cache", {})
                cache_processor = SanchezCacheProcessor(sanchez_cache)
                pipeline_stages.append(cache_processor)

            # 2. Convert ImageData to array (if needed)
            pipeline_stages.append(ImageDataConverter())

            # 3. Crop if requested
            pipeline_stages.append(CropProcessor())

            # 4. Convert array to QImage
            pipeline_stages.append(ArrayToImageConverter())

            # 5. Convert QImage to scaled QPixmap
            pipeline_stages.append(ImageToPixmapConverter())

            # 6. Add warning overlay if needed
            pipeline_stages.append(SanchezWarningOverlay())

            # Create and run pipeline
            pipeline = ImageProcessingPipeline(pipeline_stages)
            result = pipeline.process(input_data, context)

            return result

        except Exception as e:
            return ImageProcessingResult.failure_result(
                self._create_error(f"Preview processing failed: {e}", e)
            )
