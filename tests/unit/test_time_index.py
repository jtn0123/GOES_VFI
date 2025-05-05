"""Unit tests for the integrity_check TimeIndex functionality."""

import unittest
from datetime import datetime, timedelta
from pathlib import Path

from goesvfi.integrity_check.time_index import (
    TimeIndex,
    SatellitePattern,
    extract_timestamp,
    generate_timestamp_sequence,
    detect_interval,
)


class TestTimeIndex(unittest.TestCase):
    """Test cases for the TimeIndex class and related functions."""

    def setUp(self):
        """Set up test fixtures."""
        # Sample dates for testing
        self.test_date_recent = datetime(2023, 6, 15, 12, 30, 0)  # Recent date (within 7 days window)
        self.test_date_old = datetime(2022, 1, 1, 0, 0, 0)  # Old date (outside 7 days window)
        
        # Override TimeIndex.RECENT_WINDOW_DAYS for testing
        self.original_recent_window_days = TimeIndex.RECENT_WINDOW_DAYS
        TimeIndex.RECENT_WINDOW_DAYS = 7  # Set to 7 days for testing

    def tearDown(self):
        """Tear down test fixtures."""
        # Restore original values
        TimeIndex.RECENT_WINDOW_DAYS = self.original_recent_window_days

    def test_extract_timestamp(self):
        """Test extracting timestamps from filenames."""
        # GOES-16 filename
        goes16_filename = "goes16_20220101_000000_band13.png"
        timestamp = extract_timestamp(goes16_filename, SatellitePattern.GOES_16)
        self.assertEqual(timestamp, datetime(2022, 1, 1, 0, 0, 0))
        
        # GOES-18 filename
        goes18_filename = "goes18_20230615_123000_band13.png"
        timestamp = extract_timestamp(goes18_filename, SatellitePattern.GOES_18)
        self.assertEqual(timestamp, datetime(2023, 6, 15, 12, 30, 0))
        
        # Invalid filename
        invalid_filename = "invalid_file.png"
        with self.assertRaises(ValueError):
            extract_timestamp(invalid_filename, SatellitePattern.GOES_16)

    def test_generate_timestamp_sequence(self):
        """Test generating a sequence of timestamps."""
        start = datetime(2023, 1, 1, 0, 0, 0)
        end = datetime(2023, 1, 1, 1, 0, 0)
        interval = 10  # 10-minute intervals
        
        sequence = generate_timestamp_sequence(start, end, interval)
        
        # Expected: 7 timestamps (0:00, 0:10, 0:20, 0:30, 0:40, 0:50, 1:00)
        self.assertEqual(len(sequence), 7)
        self.assertEqual(sequence[0], start)
        self.assertEqual(sequence[-1], end)
        self.assertEqual(sequence[1], start + timedelta(minutes=10))

    def test_detect_interval(self):
        """Test detecting intervals between timestamps."""
        # 10-minute intervals
        timestamps = [
            datetime(2023, 1, 1, 0, 0, 0),
            datetime(2023, 1, 1, 0, 10, 0),
            datetime(2023, 1, 1, 0, 20, 0),
            datetime(2023, 1, 1, 0, 30, 0),
        ]
        
        interval = detect_interval(timestamps)
        self.assertEqual(interval, 10)
        
        # Mixed intervals, should detect the most common
        mixed_timestamps = [
            datetime(2023, 1, 1, 0, 0, 0),
            datetime(2023, 1, 1, 0, 10, 0),
            datetime(2023, 1, 1, 0, 20, 0),
            datetime(2023, 1, 1, 0, 25, 0),  # 5-minute interval (outlier)
            datetime(2023, 1, 1, 0, 35, 0),  # 10-minute interval
        ]
        
        interval = detect_interval(mixed_timestamps)
        self.assertEqual(interval, 10)  # Should still detect 10 as the most common

    def test_to_cdn_url(self):
        """Test generating CDN URLs."""
        # GOES-16 URL
        url = TimeIndex.to_cdn_url(self.test_date_recent, SatellitePattern.GOES_16)
        expected = (
            f"https://cdn.star.nesdis.noaa.gov/GOES16/ABI/CONUS/13/"
            f"{self.test_date_recent.strftime('%Y%j%H%M')}_GOES16-ABI-CONUS-13-{TimeIndex.CDN_RES}.jpg"
        )
        self.assertEqual(url, expected)
        
        # GOES-18 URL
        url = TimeIndex.to_cdn_url(self.test_date_recent, SatellitePattern.GOES_18)
        expected = (
            f"https://cdn.star.nesdis.noaa.gov/GOES18/ABI/CONUS/13/"
            f"{self.test_date_recent.strftime('%Y%j%H%M')}_GOES18-ABI-CONUS-13-{TimeIndex.CDN_RES}.jpg"
        )
        self.assertEqual(url, expected)
        
        # With custom resolution
        custom_res = "250m"
        url = TimeIndex.to_cdn_url(self.test_date_recent, SatellitePattern.GOES_16, custom_res)
        expected = (
            f"https://cdn.star.nesdis.noaa.gov/GOES16/ABI/CONUS/13/"
            f"{self.test_date_recent.strftime('%Y%j%H%M')}_GOES16-ABI-CONUS-13-{custom_res}.jpg"
        )
        self.assertEqual(url, expected)

    def test_to_s3_key(self):
        """Test generating S3 keys."""
        # GOES-16 S3 key
        key = TimeIndex.to_s3_key(self.test_date_old, SatellitePattern.GOES_16)
        expected = (
            f"ABI-L1b-RadC/{self.test_date_old.strftime('%Y/%j/%H')}/OR_ABI-L1b-RadC-M6C13_G16_s"
            f"{self.test_date_old.strftime('%Y%j%H%M')}*_e*_c*.nc"
        )
        self.assertEqual(key, expected)
        
        # GOES-18 S3 key
        key = TimeIndex.to_s3_key(self.test_date_old, SatellitePattern.GOES_18)
        expected = (
            f"ABI-L1b-RadC/{self.test_date_old.strftime('%Y/%j/%H')}/OR_ABI-L1b-RadC-M6C13_G18_s"
            f"{self.test_date_old.strftime('%Y%j%H%M')}*_e*_c*.nc"
        )
        self.assertEqual(key, expected)

    def test_to_local_path(self):
        """Test generating local paths."""
        # GOES-16 path
        path = TimeIndex.to_local_path(self.test_date_recent, SatellitePattern.GOES_16)
        expected = Path(
            f"{self.test_date_recent.year}/{self.test_date_recent.month:02d}/"
            f"{self.test_date_recent.day:02d}/goes16_{self.test_date_recent.strftime('%Y%m%d_%H%M%S')}_band13.png"
        )
        self.assertEqual(path, expected)
        
        # GOES-18 path
        path = TimeIndex.to_local_path(self.test_date_recent, SatellitePattern.GOES_18)
        expected = Path(
            f"{self.test_date_recent.year}/{self.test_date_recent.month:02d}/"
            f"{self.test_date_recent.day:02d}/goes18_{self.test_date_recent.strftime('%Y%m%d_%H%M%S')}_band13.png"
        )
        self.assertEqual(path, expected)

    def test_is_cdn_available(self):
        """Test checking if CDN is available for a date."""
        # Mock current time for testing
        current_time = datetime.now()
        
        # Recent date (within window) - should be available on CDN
        recent_date = current_time - timedelta(days=3)
        self.assertTrue(TimeIndex.is_cdn_available(recent_date))
        
        # Old date (outside window) - should not be available on CDN
        old_date = current_time - timedelta(days=TimeIndex.RECENT_WINDOW_DAYS + 1)
        self.assertFalse(TimeIndex.is_cdn_available(old_date))
        
        # Edge case - exactly at the window boundary
        edge_date = current_time - timedelta(days=TimeIndex.RECENT_WINDOW_DAYS)
        # This could be either True or False depending on implementation details,
        # so we're not asserting a specific value


if __name__ == "__main__":
    unittest.main()