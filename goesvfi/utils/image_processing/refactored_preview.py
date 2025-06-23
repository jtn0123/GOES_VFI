"""
Refactored preview processing function using the image processing framework.

This module demonstrates how the complex _load_process_scale_preview function
can be simplified using the composable image processing framework.
"""

from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from PyQt6.QtCore import QSize
from PyQt6.QtGui import QPixmap

from goesvfi.utils import log

from .cache import SanchezCacheProcessor
from .converters import (
    ArrayToImageConverter,
    CropProcessor,
    ImageDataConverter,
    ImageToPixmapConverter,
)
from .pipeline import ConditionalPipeline, ImageProcessingPipeline
from .preview import SanchezWarningOverlay

LOGGER = log.get_logger(__name__)


class RefactoredPreviewProcessor:
    """
    Refactored version of _load_process_scale_preview using the image processing framework.

    This class demonstrates how to reduce complexity by breaking down the monolithic
    350-line function into composable processing stages.
    """

    def __init__(self, sanchez_cache: Dict[Path, Any]):
        self.sanchez_cache = sanchez_cache

    def load_process_scale_preview(
        self,
        image_path: Path,
        target_label: Any,  # ClickableLabel
        image_loader: Any,  # ImageLoader
        sanchez_processor: Any,  # SanchezProcessor
        image_cropper: Any,  # ImageCropper (unused in new implementation)
        apply_sanchez: bool,
        crop_rect: Optional[Tuple[int, int, int, int]],
    ) -> QPixmap | None:
        """
        Refactored preview processing function with dramatically reduced complexity.

        Original function: F-grade complexity (54), 350 lines
        Refactored function: Expected A-B grade complexity, <50 lines
        """
        try:
            # Clear previous state
            self._clear_label_state(target_label)

            # Build processing context
            context = self._build_processing_context(
                image_path, target_label, apply_sanchez, crop_rect
            )

            # Load initial image data
            initial_data = self._load_initial_data(
                image_path, image_loader, sanchez_processor, apply_sanchez, context
            )

            if initial_data is None:
                return None

            # Process through pipeline
            result = self._process_through_pipeline(initial_data, context)

            if not result.success:
                LOGGER.error(f"Preview processing failed: {result.errors}")
                return None

            # Update label state with results
            self._update_label_state(target_label, image_path, result)

            return result.data

        except Exception as e:
            LOGGER.exception(f"Unhandled error in preview processing for {image_path}")
            self._clear_label_state(target_label)
            return None

    def _clear_label_state(self, target_label: Any) -> None:
        """Clear label state safely."""
        try:
            target_label.file_path = None
            target_label.processed_image = None
        except (RuntimeError, AttributeError):
            pass  # Label may be deleted

    def _build_processing_context(
        self,
        image_path: Path,
        target_label: Any,
        apply_sanchez: bool,
        crop_rect: Optional[Tuple[int, int, int, int]],
    ) -> Dict[str, Any]:
        """Build processing context with all required parameters."""
        # Get target size safely
        target_size = QSize(100, 100)  # Default
        try:
            if hasattr(target_label, "size") and target_label is not None:
                label_size = target_label.size()
                if label_size.width() > 0 and label_size.height() > 0:
                    target_size = label_size
        except (RuntimeError, AttributeError):
            pass

        return {
            "image_path": image_path,
            "apply_sanchez": apply_sanchez,
            "crop_rect": crop_rect,
            "target_size": target_size,
            "sanchez_cache": self.sanchez_cache,
            "draw_sanchez_warning": False,  # Will be updated if Sanchez fails
            "sanchez_error_message": "",
        }

    def _load_initial_data(
        self,
        image_path: Path,
        image_loader: Any,
        sanchez_processor: Any,
        apply_sanchez: bool,
        context: Dict[str, Any],
    ) -> Any:
        """Load initial image data, handling Sanchez cache and processing."""
        if apply_sanchez:
            # Try cache first
            if image_path in self.sanchez_cache:
                LOGGER.debug(f"Using cached Sanchez result for {image_path.name}")
                return self._create_cached_image_data(image_path)
            else:
                # Process with Sanchez
                return self._process_with_sanchez(
                    image_path, image_loader, sanchez_processor, context
                )
        else:
            # Load original image
            return self._load_original_image(image_path, image_loader)

    def _create_cached_image_data(self, image_path: Path) -> Any:
        """Create ImageData from cached Sanchez result."""
        from goesvfi.integrity_check.render.netcdf import ImageData

        cached_array = self.sanchez_cache[image_path]
        return ImageData(
            image_data=cached_array,
            metadata={"source_path": image_path, "cached": True},
        )

    def _process_with_sanchez(
        self,
        image_path: Path,
        image_loader: Any,
        sanchez_processor: Any,
        context: Dict[str, Any],
    ) -> Any:
        """Process image with Sanchez, handling errors gracefully."""
        try:
            # Load original first
            original_data = image_loader.load(str(image_path))
            if not original_data or original_data.image_data is None:
                LOGGER.error(f"Failed to load original image: {image_path}")
                return None

            # Get resolution setting (simplified)
            res_km_str = "4"  # Default resolution

            # Process with Sanchez
            processed_data = sanchez_processor.process(original_data, res_km_str)

            if processed_data and processed_data.image_data is not None:
                # Cache the result
                self.sanchez_cache[image_path] = processed_data.image_data
                return processed_data
            else:
                # Sanchez failed, update context and return original
                context["draw_sanchez_warning"] = True
                context["sanchez_error_message"] = "Sanchez processing failed"
                return original_data

        except Exception as e:
            LOGGER.error(f"Sanchez processing failed for {image_path}: {e}")
            context["draw_sanchez_warning"] = True
            context["sanchez_error_message"] = str(e)
            # Return original data as fallback
            return self._load_original_image(image_path, image_loader)

    def _load_original_image(self, image_path: Path, image_loader: Any) -> Any:
        """Load original image data."""
        try:
            return image_loader.load(str(image_path))
        except Exception as e:
            LOGGER.error(f"Failed to load original image {image_path}: {e}")
            return None

    def _process_through_pipeline(
        self, input_data: Any, context: Dict[str, Any]
    ) -> Any:
        """Process data through the image processing pipeline."""
        # Build pipeline with conditional Sanchez cache checking
        pipeline_stages = [
            ImageDataConverter(),  # Convert ImageData to numpy array
            CropProcessor(),  # Apply crop if requested
            ArrayToImageConverter(),  # Convert array to QImage
            ImageToPixmapConverter(),  # Convert to scaled QPixmap
            SanchezWarningOverlay(),  # Add warning overlay if needed
        ]

        pipeline = ImageProcessingPipeline(pipeline_stages)
        return pipeline.process(input_data, context)

    def _update_label_state(
        self, target_label: Any, image_path: Path, result: Any
    ) -> None:
        """Update label state with processing results."""
        try:
            target_label.file_path = str(image_path)
            # Store the full-resolution processed image if available
            if "processed_qimage" in result.metadata:
                target_label.processed_image = result.metadata["processed_qimage"]
        except (RuntimeError, AttributeError):
            pass  # Label may be deleted
