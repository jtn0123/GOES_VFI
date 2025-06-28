"""Crop parameter handling for VFI processing pipeline.

This module provides focused crop parameter validation and conversion
functionality extracted from VFIProcessor to improve maintainability.
"""

from typing import Any

from goesvfi.utils import log
from goesvfi.utils.validation import validate_positive_int

LOGGER = log.get_logger(__name__)


class VFICropHandler:
    """Handles crop parameter validation and conversion for VFI processing."""

    def __init__(self) -> None:
        """Initialize crop handler."""

    def validate_crop_parameters(
        self, crop_rect_xywh: tuple[int, int, int, int] | None
    ) -> tuple[int, int, int, int] | None:
        """Validate and convert crop rectangle from XYWH to PIL LURB format.

        Args:
            crop_rect_xywh: Crop rectangle in (x, y, width, height) format or None

        Returns:
            Crop rectangle in PIL format (left, upper, right, bottom) or None

        Raises:
            ValueError: If crop parameters are invalid
        """
        if not crop_rect_xywh:
            LOGGER.info("No crop rectangle provided")
            return None

        try:
            x, y, w, h = crop_rect_xywh

            # Validate coordinates are non-negative (zero is valid)
            if x < 0:
                msg = f"crop x coordinate must be non-negative, got {x}"
                raise ValueError(msg)
            if y < 0:
                msg = f"crop y coordinate must be non-negative, got {y}"
                raise ValueError(msg)

            # Validate width and height are positive (zero is invalid)
            validate_positive_int(w, "crop width")
            validate_positive_int(h, "crop height")

            # Convert to PIL format (left, upper, right, bottom)
            crop_for_pil = (x, y, x + w, y + h)

            LOGGER.info(
                "Converted crop rectangle (x,y,w,h): %s -> PIL format (l,u,r,b): %s",
                crop_rect_xywh,
                crop_for_pil
            )

            return crop_for_pil

        except (TypeError, ValueError):
            LOGGER.exception(
                "Invalid crop rectangle format provided: %s. Cropping will be disabled.",
                crop_rect_xywh
            )
            # Return None to disable cropping rather than raising
            return None

    def validate_crop_against_image(
        self,
        crop_rect_pil: tuple[int, int, int, int],
        image_width: int,
        image_height: int,
        image_name: str = "image"
    ) -> None:
        """Validate crop rectangle against image dimensions.

        Args:
            crop_rect_pil: Crop rectangle in PIL format (left, upper, right, bottom)
            image_width: Width of the image
            image_height: Height of the image
            image_name: Name of the image for error messages

        Raises:
            ValueError: If crop rectangle exceeds image boundaries
        """
        left, upper, right, bottom = crop_rect_pil

        # Check boundaries
        if left < 0 or upper < 0:
            msg = f"Crop rectangle {crop_rect_pil} has negative coordinates for {image_name}"
            LOGGER.error(msg)
            raise ValueError(msg)

        if right > image_width or bottom > image_height:
            msg = (
                f"Crop rectangle {crop_rect_pil} exceeds image dimensions "
                f"({image_width}x{image_height}) for {image_name}"
            )
            LOGGER.error(msg)
            raise ValueError(msg)

        if right <= left or bottom <= upper:
            msg = f"Invalid crop rectangle {crop_rect_pil} - right <= left or bottom <= upper for {image_name}"
            LOGGER.error(msg)
            raise ValueError(msg)

        crop_width = right - left
        crop_height = bottom - upper

        LOGGER.debug(
            "Crop validation passed for %s: crop size %dx%d within image %dx%d",
            image_name, crop_width, crop_height, image_width, image_height
        )

    def get_crop_info(
        self, crop_rect_pil: tuple[int, int, int, int] | None
    ) -> dict[str, Any]:
        """Get information about the crop configuration.

        Args:
            crop_rect_pil: Crop rectangle in PIL format or None

        Returns:
            Dictionary with crop information
        """
        if crop_rect_pil is None:
            return {
                "enabled": False,
                "rectangle": None,
                "width": None,
                "height": None
            }

        left, upper, right, bottom = crop_rect_pil
        return {
            "enabled": True,
            "rectangle": crop_rect_pil,
            "left": left,
            "upper": upper,
            "right": right,
            "bottom": bottom,
            "width": right - left,
            "height": bottom - upper
        }

    def format_crop_for_logging(
        self, crop_rect_pil: tuple[int, int, int, int] | None
    ) -> str:
        """Format crop rectangle for logging output.

        Args:
            crop_rect_pil: Crop rectangle in PIL format or None

        Returns:
            Formatted string for logging
        """
        if crop_rect_pil is None:
            return "no crop"

        left, upper, right, bottom = crop_rect_pil
        width = right - left
        height = bottom - upper

        return f"crop({left},{upper})+{width}x{height}"
