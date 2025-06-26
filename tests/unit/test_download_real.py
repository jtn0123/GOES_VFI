#!/usr/bin/env python3
"""
Direct test of the GOES imagery download functionality with real data.
This tests the actual download capabilities with real NOAA servers.
"""

import logging
from datetime import datetime
from pathlib import Path

from goesvfi.integrity_check.goes_imagery import ProductType
from goesvfi.integrity_check.sample_processor import SampleProcessor
from goesvfi.integrity_check.visualization_manager import VisualizationManager

# Configure logging to see detailed output
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def test_download_functionality():
    """Test the actual download functionality with real NOAA data."""
    print("\n===== Testing Enhanced Download Functionality =====")

    # Create the sample processor
    viz_manager = VisualizationManager()
    processor = SampleProcessor(visualization_manager=viz_manager)

    # Test with a few different channels and dates
    print("\n1. Testing IR band (13) download with current date")
    result_current = processor.download_sample_data(13, ProductType.FULL_DISK)
    if result_current:
        print(f"✓ Successfully downloaded current IR data to: {result_current}")
    else:
        print("✗ Could not download current IR data - fallback system should have activated")

    # Test with a known good historical date
    print("\n2. Testing with historical date (known good data)")
    historical_date = datetime(2023, 5, 1, 19, 0)
    result_historical = processor.download_sample_data(13, ProductType.FULL_DISK, historical_date)
    if result_historical:
        print(f"✓ Successfully downloaded historical IR data to: {result_historical}")
    else:
        print("✗ Could not download historical IR data")

    # Test web sample downloading
    print("\n3. Testing web sample download for IR band")
    web_result = processor.download_web_sample(13, ProductType.FULL_DISK)
    if web_result:
        print(f"✓ Successfully downloaded web sample - size: {web_result.width}x{web_result.height}")
    else:
        print("✗ Could not download web sample - fallback system should have activated")

    # Test different channel (visible)
    print("\n4. Testing visible band (2) download")
    visible_result = processor.download_sample_data(2, ProductType.FULL_DISK)
    if visible_result:
        print(f"✓ Successfully downloaded visible data to: {visible_result}")
    else:
        print("✗ Could not download visible data - fallback system should have activated")

    # Test create_sample_comparison functionality
    print("\n5. Testing sample comparison creation")
    comparison = processor.create_sample_comparison(13, ProductType.FULL_DISK)
    if comparison:
        comparison_path = Path("test_comparison.png")
        comparison.save(comparison_path)
        print(f"✓ Successfully created sample comparison - saved to: {comparison_path}")
    else:
        print("✗ Failed to create sample comparison")

    # Cleanup temporary files
    print("\nCleaning up...")
    processor.cleanup()

    print("\nTest completed - check the logs above to see if downloads worked")
    print("Note: It's normal for some downloads to fail, as long as the fallback systems activate.")


if __name__ == "__main__":
    test_download_functionality()
