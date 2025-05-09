#!/usr/bin/env python3
"""
Test script for GOES imagery enhancements

This script tests the enhanced functionality for GOES imagery handling without
requiring active internet connections or satellite data access.
"""

import sys
import logging
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from goesvfi.integrity_check.sample_processor import SampleProcessor
from goesvfi.integrity_check.visualization_manager import VisualizationManager
from goesvfi.integrity_check.goes_imagery import ChannelType, ProductType

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_fallback_strategies():
    """Test the fallback strategies in the sample processor."""
    print("\n===== Testing Fallback Strategies =====")
    
    # Create visualization manager
    viz_manager = VisualizationManager()
    
    # Create sample processor with mocked S3 client
    with patch('boto3.client') as mock_client:
        # Mock S3 client's list_objects_v2 to always return no contents
        mock_s3 = MagicMock()
        mock_s3.list_objects_v2.return_value = {'Contents': []}
        mock_client.return_value = mock_s3
        
        # Create processor
        processor = SampleProcessor(visualization_manager=viz_manager)
        
        # Patch the search_day_hours method to track calls
        with patch.object(processor, '_search_day_hours') as mock_search:
            # Set return value to None to force fallbacks
            mock_search.return_value = None
            
            # Call download_sample_data
            result = processor.download_sample_data(13, ProductType.FULL_DISK)
            
            # Check that it tried multiple strategies
            assert mock_search.call_count > 1, f"Expected multiple search strategies, got {mock_search.call_count}"
            print(f"✓ Tried {mock_search.call_count} different search strategies")
    
    print("Fallback strategy test completed successfully")

def test_web_sample_fallbacks():
    """Test the web sample download fallbacks."""
    print("\n===== Testing Web Sample Fallbacks =====")
    
    # Create visualization manager
    viz_manager = VisualizationManager()
    
    # Create sample processor
    processor = SampleProcessor(visualization_manager=viz_manager)
    
    # Mock the download_image method to fail
    with patch.object(processor, '_download_image', return_value=None):
        # Mock all the web source methods to track calls
        with patch.object(processor, '_try_noaa_cdn') as mock_cdn:
            with patch.object(processor, '_try_rammb_slider') as mock_rammb:
                with patch.object(processor, '_try_archived_imagery') as mock_archive:
                    # Make them all return None to force trying all strategies
                    mock_cdn.return_value = None
                    mock_rammb.return_value = None
                    mock_archive.return_value = None
                    
                    # Call the method
                    result = processor._try_all_web_sources(13, ProductType.FULL_DISK)
                    
                    # Verify all strategies were tried
                    assert mock_cdn.call_count >= 1, "Should try NOAA CDN"
                    assert mock_rammb.call_count >= 1, "Should try RAMMB SLIDER"
                    assert mock_archive.call_count >= 1, "Should try archived imagery"
                    
                    print("✓ Tried all web source fallback strategies")
    
    print("Web sample fallback test completed successfully")

def test_error_handling():
    """Test error handling in the download attempts."""
    print("\n===== Testing Error Handling =====")
    
    # Create visualization manager
    viz_manager = VisualizationManager()
    
    # Create sample processor with mocked requests
    processor = SampleProcessor(visualization_manager=viz_manager)
    
    # Track retry attempts
    retry_count = 0
    
    # Mock the requests.get function to fail with timeout then succeed
    def mock_requests_get(*args, **kwargs):
        nonlocal retry_count
        retry_count += 1
        
        if retry_count < 2:
            # First attempt fails with timeout
            import requests
            raise requests.exceptions.Timeout("Connection timed out")
        else:
            # Second attempt succeeds
            mock_response = MagicMock()
            mock_response.content = b'fake_content'
            return mock_response
    
    # Mock image opening
    mock_image = MagicMock()
    mock_image.width = 100
    mock_image.height = 100
    
    # Run the test with patches
    with patch('requests.get', side_effect=mock_requests_get):
        with patch('PIL.Image.open', return_value=mock_image):
            with patch('os.unlink'):  # Mock file deletion
                # Call download_image directly
                result = processor._download_image("https://example.com/test.jpg")
                
                # Check that retry happened
                assert retry_count > 1, f"Expected multiple attempts, got {retry_count}"
                print(f"✓ Successfully retried after failure ({retry_count} attempts)")
    
    print("Error handling test completed successfully")

def main():
    """Run all tests."""
    print("Starting GOES Imagery Enhancement Tests...")
    
    test_fallback_strategies()
    test_web_sample_fallbacks()
    test_error_handling()
    
    print("\nAll tests completed successfully!")
    return 0

if __name__ == "__main__":
    sys.exit(main())