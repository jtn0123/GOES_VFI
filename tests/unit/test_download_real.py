#!/usr/bin/env python3
"""
Direct test of the GOES imagery download functionality with real data.
This tests the actual download capabilities with real NOAA servers.
"""

from datetime import datetime
import logging
from pathlib import Path

from goesvfi.integrity_check.goes_imagery import ProductType
from goesvfi.integrity_check.sample_processor import SampleProcessor
from goesvfi.integrity_check.visualization_manager import VisualizationManager

# Configure logging to see detailed output
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def test_download_functionality() -> None:
    """Test the actual download functionality with real NOAA data."""

    # Create the sample processor
    viz_manager = VisualizationManager()
    processor = SampleProcessor(visualization_manager=viz_manager)

    # Test with a few different channels and dates
    result_current = processor.download_sample_data(13, ProductType.FULL_DISK)
    if result_current:
        pass

    # Test with a known good historical date
    historical_date = datetime(2023, 5, 1, 19, 0)
    result_historical = processor.download_sample_data(13, ProductType.FULL_DISK, historical_date)
    if result_historical:
        pass

    # Test web sample downloading
    web_result = processor.download_web_sample(13, ProductType.FULL_DISK)
    if web_result:
        pass

    # Test different channel (visible)
    visible_result = processor.download_sample_data(2, ProductType.FULL_DISK)
    if visible_result:
        pass

    # Test create_sample_comparison functionality
    comparison = processor.create_sample_comparison(13, ProductType.FULL_DISK)
    if comparison:
        comparison_path = Path("test_comparison.png")
        comparison.save(comparison_path)

    # Cleanup temporary files
    processor.cleanup()


if __name__ == "__main__":
    test_download_functionality()
