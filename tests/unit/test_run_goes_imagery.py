#!/usr/bin/env python
"""
Test runner for GOES Satellite Imagery functionality

This script demonstrates how to use the GOES Imagery module to:
1. Download pre-colorized imagery from NOAA
2. Compare different channels and product types
3. Test both raw data and pre-processed image modes
"""

import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from goesvfi.integrity_check.goes_imagery import (
    ChannelType,
    GOESImageryManager,
    ImageryMode,
    ProcessingMode,
    ProductType,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def download_single_channel(
    manager, channel, product_type, mode=ImageryMode.IMAGE_PRODUCT
):
    """Download a single channel of data."""
    logger.info(
        f"Downloading {channel.display_name} for {product_type.name} in {mode.name} mode"
    )

    # Get image
    image_path = manager.get_imagery(
        channel=channel, product_type=product_type, mode=mode
    )

    if image_path:
        logger.info(f"Successfully downloaded to: {image_path}")
        return image_path
    else:
        logger.error("Download failed")
        return None


def download_channel_comparison(manager, product_type=ProductType.FULL_DISK):
    """Download multiple channels for comparison."""
    logger.info(f"Downloading channel comparison for {product_type.name}")

    # Define channels to compare
    channels = [
        ChannelType.CH13,  # Clean IR
        ChannelType.CH02,  # Red Visible
        ChannelType.TRUE_COLOR,  # RGB composite
        ChannelType.WATER_VAPOR,  # Water vapor
    ]

    # Download each channel
    results = {}
    for channel in channels:
        logger.info(f"Downloading {channel.display_name}...")
        image_path = manager.get_imagery(
            channel=channel, product_type=product_type, mode=ImageryMode.IMAGE_PRODUCT
        )

        if image_path:
            logger.info(
                f"Successfully downloaded {channel.display_name} to: {image_path}"
            )
            results[channel.display_name] = image_path
        else:
            logger.error(f"Failed to download {channel.display_name}")

    return results


def compare_imagery_modes(
    manager, channel=ChannelType.CH13, product_type=ProductType.FULL_DISK
):
    """Compare different imagery modes."""
    logger.info(
        f"Comparing imagery modes for {channel.display_name}, {product_type.name}"
    )

    # Download with Image Product mode
    logger.info("Downloading with Image Product mode...")
    product_image = manager.get_imagery(
        channel=channel, product_type=product_type, mode=ImageryMode.IMAGE_PRODUCT
    )

    if product_image:
        logger.info(f"Image Product mode result: {product_image}")
    else:
        logger.error("Image Product mode failed")

    # Download with Raw Data mode
    # Note: This will only create placeholders in test mode
    logger.info("Downloading with Raw Data mode...")
    raw_image = manager.get_imagery(
        channel=channel,
        product_type=product_type,
        mode=ImageryMode.RAW_DATA,
        processing=ProcessingMode.BASIC,
    )

    if raw_image:
        logger.info(f"Raw Data mode result: {raw_image}")
    else:
        logger.error("Raw Data mode failed")

    return {"product_image": product_image, "raw_image": raw_image}


def main():
    """Main function to run the test."""
    parser = argparse.ArgumentParser(description="Test GOES Imagery functionality")
    parser.add_argument(
        "--mode",
        type=str,
        choices=["single", "compare", "modes"],
        default="single",
        help="Test mode",
    )
    parser.add_argument(
        "--channel",
        type=int,
        default=13,
        help="Channel number (default: 13 - Clean IR)",
    )
    parser.add_argument(
        "--product",
        type=str,
        choices=["full_disk", "meso1", "meso2", "cmip", "rain_rate"],
        default="full_disk",
        help="Product type",
    )

    args = parser.parse_args()

    # Create output directory
    output_dir = Path("goes_test_output")
    os.makedirs(output_dir, exist_ok=True)

    # Create manager
    manager = GOESImageryManager(output_dir=output_dir)

    # Map product type string to enum
    product_map = {
        "full_disk": ProductType.FULL_DISK,
        "meso1": ProductType.MESO1,
        "meso2": ProductType.MESO2,
        "cmip": ProductType.CMIP,
        "rain_rate": ProductType.RAIN_RATE,
    }
    product_type = product_map[args.product]

    # Run selected test mode
    if args.mode == "single":
        # Get channel from number or use default
        channel = ChannelType.from_number(args.channel) or ChannelType.CH13
        download_single_channel(manager, channel, product_type)

    elif args.mode == "compare":
        download_channel_comparison(manager, product_type)

    elif args.mode == "modes":
        # Get channel from number or use default
        channel = ChannelType.from_number(args.channel) or ChannelType.CH13
        compare_imagery_modes(manager, channel, product_type)


if __name__ == "__main__":
    main()
