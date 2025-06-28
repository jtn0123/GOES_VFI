"""Image processing functionality for VFI pipeline.

This module provides focused image processing functionality extracted from
VFIProcessor to improve maintainability and testability.
"""

import pathlib
import time
from typing import Any

from PIL import Image

from goesvfi.sanchez.runner import colourise
from goesvfi.utils import log

LOGGER = log.get_logger(__name__)


class VFIImageProcessor:
    """Handles image processing operations for VFI pipeline."""

    def __init__(self, crop_handler: Any) -> None:
        """Initialize image processor.

        Args:
            crop_handler: VFICropHandler instance for crop validation
        """
        self.crop_handler = crop_handler

    def process_single_image(
        self,
        image_path: pathlib.Path,
        crop_rect_pil: tuple[int, int, int, int] | None,
        false_colour: bool,
        res_km: int,
        sanchez_temp_dir: pathlib.Path,
        output_dir: pathlib.Path,
        target_width: int | None = None,
        target_height: int | None = None
    ) -> pathlib.Path:
        """Process a single image with optional Sanchez coloring and cropping.

        Args:
            image_path: Path to the input image
            crop_rect_pil: Crop rectangle in PIL format or None
            false_colour: Whether to apply Sanchez false coloring
            res_km: Resolution in km for Sanchez processing
            sanchez_temp_dir: Temporary directory for Sanchez operations
            output_dir: Output directory for processed image
            target_width: Expected width (for validation, optional)
            target_height: Expected height (for validation, optional)

        Returns:
            Path to the processed image

        Raises:
            ValueError: If image processing fails
            OSError: If file operations fail
        """
        try:
            # Load original image
            img = Image.open(image_path)
            orig_width, orig_height = img.size

            LOGGER.debug(
                "Processing image %s (size: %dx%d)",
                image_path.name, orig_width, orig_height
            )

            # Apply Sanchez false coloring if requested
            if false_colour:
                img = self._apply_sanchez_coloring(
                    img, image_path, res_km, sanchez_temp_dir
                )

            # Apply crop if requested
            if crop_rect_pil:
                # Validate crop against image dimensions
                self.crop_handler.validate_crop_against_image(
                    crop_rect_pil, orig_width, orig_height, image_path.name
                )
                img = self._apply_crop(img, crop_rect_pil, image_path.name)

            # Save processed image
            processed_path = self._save_processed_image(
                img, image_path.stem, output_dir
            )

            LOGGER.info(
                "Processed %s: output size %s, saved to %s",
                image_path.name, img.size, processed_path.name
            )

            return processed_path

        except Exception:
            LOGGER.exception("Failed to process image %s", image_path.name)
            raise

    def _apply_sanchez_coloring(
        self,
        img: Image.Image,
        original_path: pathlib.Path,
        res_km: int,
        sanchez_temp_dir: pathlib.Path
    ) -> Image.Image:
        """Apply Sanchez false coloring to an image.

        Args:
            img: PIL Image to process
            original_path: Original image path (for naming)
            res_km: Resolution in km
            sanchez_temp_dir: Temporary directory for Sanchez

        Returns:
            Processed PIL Image
        """
        img_stem = original_path.stem
        temp_in_path = sanchez_temp_dir / f"{img_stem}.png"
        temp_out_path = sanchez_temp_dir / f"{img_stem}_{time.monotonic_ns()}_fc.png"

        try:
            LOGGER.debug("Applying Sanchez coloring to %s", original_path.name)

            # Save input for Sanchez
            img.save(temp_in_path, "PNG")

            # Run Sanchez coloring
            LOGGER.info(
                "Running Sanchez on %s (res=%skm) -> %s",
                temp_in_path.name, res_km, temp_out_path.name
            )
            colourise(str(temp_in_path), str(temp_out_path), res_km=res_km)

            # Load colored result
            img_colored = Image.open(temp_out_path)

            LOGGER.debug("Sanchez coloring completed for %s", original_path.name)
            return img_colored

        except Exception as e:
            LOGGER.error(
                "Sanchez coloring failed for %s: %s",
                original_path.name, e, exc_info=True
            )
            # Return original image on failure
            return img

        finally:
            # Clean up temporary files
            if temp_in_path.exists():
                temp_in_path.unlink(missing_ok=True)
            if temp_out_path.exists():
                temp_out_path.unlink(missing_ok=True)

    def _apply_crop(
        self,
        img: Image.Image,
        crop_rect_pil: tuple[int, int, int, int],
        image_name: str
    ) -> Image.Image:
        """Apply crop to an image.

        Args:
            img: PIL Image to crop
            crop_rect_pil: Crop rectangle in PIL format
            image_name: Image name for logging

        Returns:
            Cropped PIL Image

        Raises:
            ValueError: If crop fails
        """
        try:
            LOGGER.debug(
                "Applying crop %s to image %s",
                self.crop_handler.format_crop_for_logging(crop_rect_pil),
                image_name
            )

            img_cropped = img.crop(crop_rect_pil)

            LOGGER.debug(
                "Crop successful: %s -> %s for %s",
                img.size, img_cropped.size, image_name
            )

            return img_cropped

        except Exception as e:
            LOGGER.error(
                "Failed to crop image %s with rect %s: %s",
                image_name, crop_rect_pil, e, exc_info=True
            )
            msg = f"Crop failed for {image_name}: {e}"
            raise ValueError(msg) from e

    def _save_processed_image(
        self,
        img: Image.Image,
        original_stem: str,
        output_dir: pathlib.Path
    ) -> pathlib.Path:
        """Save processed image to output directory.

        Args:
            img: PIL Image to save
            original_stem: Original filename stem
            output_dir: Output directory

        Returns:
            Path to saved image
        """
        # Generate unique filename
        output_path = output_dir / f"processed_{original_stem}_{time.monotonic_ns()}.png"

        # Save image
        img.save(output_path, "PNG")

        return output_path

    def get_image_dimensions(self, image_path: pathlib.Path) -> tuple[int, int]:
        """Get dimensions of an image without fully loading it.

        Args:
            image_path: Path to the image

        Returns:
            Tuple of (width, height)

        Raises:
            OSError: If image cannot be read
        """
        try:
            with Image.open(image_path) as img:
                return img.size
        except Exception as e:
            LOGGER.exception("Failed to get dimensions for %s: %s", image_path, e)
            msg = f"Cannot read image dimensions: {e}"
            raise OSError(msg) from e

    def validate_image_format(self, image_path: pathlib.Path) -> bool:
        """Validate that a file is a valid PNG image.

        Args:
            image_path: Path to check

        Returns:
            True if valid PNG, False otherwise
        """
        try:
            with Image.open(image_path) as img:
                return img.format == "PNG"
        except Exception:
            return False
