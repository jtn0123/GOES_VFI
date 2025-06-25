"""Comprehensive tests for the refactored time_utils modules."""

import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from goesvfi.integrity_check.time_utils import (
    BAND,
    DEFAULT_CDN_RESOLUTION,
    RADC_MINUTES,
    RADF_MINUTES,
    DirectoryScanner,
    S3KeyGenerator,
    SatellitePattern,
    TimeIndex,
    TimestampExtractor,
    TimestampFormatter,
    TimestampGenerator,
    filter_s3_keys_by_band,
    get_satellite_info,
)


class TestPatterns(unittest.TestCase):
    """Test the patterns module functionality."""

    def test_get_satellite_info(self):
        """Test getting satellite information."""
        # Test GOES-16
        info = get_satellite_info(SatellitePattern.GOES_16)
        self.assertEqual(info["name"], "GOES-16 (East)")
        self.assertEqual(info["short_name"], "GOES16")
        self.assertEqual(info["s3_bucket"], "noaa-goes16")
        self.assertEqual(info["code"], "G16")

        # Test GOES-18
        info = get_satellite_info(SatellitePattern.GOES_18)
        self.assertEqual(info["name"], "GOES-18 (West)")
        self.assertEqual(info["short_name"], "GOES18")
        self.assertEqual(info["s3_bucket"], "noaa-goes18")
        self.assertEqual(info["code"], "G18")

        # Test GENERIC
        info = get_satellite_info(SatellitePattern.GENERIC)
        self.assertEqual(info["name"], "Generic Pattern")
        self.assertIsNone(info["s3_bucket"])  # Generic doesn't have S3 bucket
        self.assertIsNone(info["code"])  # Generic doesn't have code


class TestTimestampExtractor(unittest.TestCase):
    """Test the TimestampExtractor class."""

    def test_extract_timestamp_simple_pattern(self):
        """Test extracting timestamp from simple test pattern."""
        filename = "goes16_20230615_123000_band13.png"
        ts = TimestampExtractor.extract_timestamp(filename, SatellitePattern.GOES_16)
        self.assertEqual(ts, datetime(2023, 6, 15, 12, 30, 0))

    def test_extract_timestamp_legacy_pattern(self):
        """Test extracting timestamp from legacy pattern."""
        filename = "image_G16_20230615T123000Z.png"
        ts = TimestampExtractor.extract_timestamp(filename, SatellitePattern.GOES_16)
        self.assertEqual(ts, datetime(2023, 6, 15, 12, 30, 0))

    def test_extract_timestamp_invalid_pattern(self):
        """Test extracting timestamp with invalid pattern."""
        filename = "invalid_filename.png"
        with self.assertRaises(ValueError):
            TimestampExtractor.extract_timestamp(filename, SatellitePattern.GOES_16)

    def test_extract_timestamp_and_satellite(self):
        """Test extracting both timestamp and satellite."""
        filename = "2023166123000_GOES16-ABI-FD-13-5424x5424.jpg"
        ts, sat = TimestampExtractor.extract_timestamp_and_satellite(filename)
        self.assertEqual(ts, datetime(2023, 6, 15, 12, 30))
        self.assertEqual(sat, SatellitePattern.GOES_16)

    def test_extract_timestamp_from_directory_name(self):
        """Test extracting timestamp from directory names."""
        # Test primary format
        dirname = "2024-12-21_18-00-22"
        ts = TimestampExtractor.extract_timestamp_from_directory_name(dirname)
        self.assertEqual(ts, datetime(2024, 12, 21, 18, 0, 22))

        # Test YYYYMMDD_HHMMSS format
        dirname = "20241221_180022"
        ts = TimestampExtractor.extract_timestamp_from_directory_name(dirname)
        self.assertEqual(ts, datetime(2024, 12, 21, 18, 0, 22))

        # Test satellite specific pattern
        dirname = "GOES18/FD/13/2023/166"
        ts = TimestampExtractor.extract_timestamp_from_directory_name(dirname)
        self.assertEqual(ts, datetime(2023, 6, 15, 0, 0, 0))

        # Test invalid pattern
        dirname = "invalid_directory"
        ts = TimestampExtractor.extract_timestamp_from_directory_name(dirname)
        self.assertIsNone(ts)


class TestTimestampFormatter(unittest.TestCase):
    """Test the TimestampFormatter class."""

    def test_format_timestamp(self):
        """Test formatting timestamp."""
        dt = datetime(2023, 6, 15, 12, 30, 0)
        formatted = TimestampFormatter.format_timestamp(dt)
        self.assertEqual(formatted, "20230615T123000")

    def test_get_filename_pattern(self):
        """Test getting filename pattern."""
        # Test GOES-16
        pattern = TimestampFormatter.get_filename_pattern(SatellitePattern.GOES_16)
        self.assertEqual(pattern, "image_G16_{timestamp}Z.png")

        # Test GOES-18 with custom base name
        pattern = TimestampFormatter.get_filename_pattern(
            SatellitePattern.GOES_18, "test"
        )
        self.assertEqual(pattern, "test_G18_{timestamp}Z.png")

        # Test generic pattern
        pattern = TimestampFormatter.get_filename_pattern(SatellitePattern.GENERIC)
        self.assertEqual(pattern, "image_{timestamp}Z.png")

    def test_generate_expected_filename(self):
        """Test generating expected filename."""
        dt = datetime(2023, 6, 15, 12, 30, 0)
        filename = TimestampFormatter.generate_expected_filename(
            dt, SatellitePattern.GOES_16
        )
        self.assertEqual(filename, "image_G16_20230615T123000Z.png")


class TestTimestampGenerator(unittest.TestCase):
    """Test the TimestampGenerator class."""

    def test_generate_timestamp_sequence(self):
        """Test generating timestamp sequence."""
        start = datetime(2023, 6, 15, 12, 0, 0)
        end = datetime(2023, 6, 15, 13, 0, 0)
        sequence = TimestampGenerator.generate_timestamp_sequence(start, end, 30)

        expected = [
            datetime(2023, 6, 15, 12, 0, 0),
            datetime(2023, 6, 15, 12, 30, 0),
            datetime(2023, 6, 15, 13, 0, 0),
        ]
        self.assertEqual(sequence, expected)

    def test_detect_interval(self):
        """Test detecting interval between timestamps."""
        timestamps = [
            datetime(2023, 6, 15, 12, 0, 0),
            datetime(2023, 6, 15, 12, 10, 0),
            datetime(2023, 6, 15, 12, 20, 0),
            datetime(2023, 6, 15, 12, 30, 0),
        ]
        interval = TimestampGenerator.detect_interval(timestamps)
        self.assertEqual(interval, 10)

    def test_is_recent(self):
        """Test is_recent function."""
        # Mock datetime.now
        with patch("goesvfi.integrity_check.time_utils.timestamp.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2023, 6, 20, 0, 0, 0)
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

            # Recent date (3 days ago)
            recent = datetime(2023, 6, 17, 0, 0, 0)
            self.assertTrue(TimestampGenerator.is_recent(recent))

            # Old date (10 days ago)
            old = datetime(2023, 6, 10, 0, 0, 0)
            self.assertFalse(TimestampGenerator.is_recent(old))


class TestS3KeyGenerator(unittest.TestCase):
    """Test the S3KeyGenerator class."""

    def test_to_cdn_url(self):
        """Test generating CDN URLs."""
        ts = datetime(2023, 6, 15, 12, 30, 0)

        # Test GOES-16
        url = S3KeyGenerator.to_cdn_url(ts, SatellitePattern.GOES_16)
        self.assertIn("cdn.star.nesdis.noaa.gov/GOES16", url)
        self.assertIn("2023166", url)  # Year + DOY

        # Test with custom resolution
        url = S3KeyGenerator.to_cdn_url(ts, SatellitePattern.GOES_18, "1808x1808")
        self.assertIn("1808x1808", url)

    def test_to_s3_key(self):
        """Test generating S3 keys."""
        ts = datetime(2023, 6, 15, 12, 1, 0)

        # Test RadC (CONUS)
        key = S3KeyGenerator.to_s3_key(ts, SatellitePattern.GOES_16, "RadC")
        self.assertIn("ABI-L1b-RadC/2023/166/12/", key)
        self.assertIn("M6C13_G16", key)

        # Test RadF (Full Disk)
        ts_fd = datetime(2023, 6, 15, 12, 10, 0)
        key = S3KeyGenerator.to_s3_key(ts_fd, SatellitePattern.GOES_16, "RadF")
        self.assertIn("ABI-L1b-RadF/2023/166/12/", key)

    def test_get_s3_bucket(self):
        """Test getting S3 bucket name."""
        self.assertEqual(
            S3KeyGenerator.get_s3_bucket(SatellitePattern.GOES_16), "noaa-goes16"
        )
        self.assertEqual(
            S3KeyGenerator.get_s3_bucket(SatellitePattern.GOES_18), "noaa-goes18"
        )

        with self.assertRaises(ValueError):
            S3KeyGenerator.get_s3_bucket(SatellitePattern.GENERIC)

    def test_generate_local_path(self):
        """Test generating local paths."""
        ts = datetime(2023, 6, 15, 12, 30)
        base_dir = Path("/data")

        path = S3KeyGenerator.generate_local_path(
            ts, SatellitePattern.GOES_16, base_dir
        )
        expected = (
            base_dir
            / "GOES16"
            / "FD"
            / "13"
            / "2023"
            / "166"
            / "20231661230_GOES16-ABI-FD-13-5424x5424.png"
        )
        self.assertEqual(path, expected)

    def test_to_local_path(self):
        """Test generating simplified local paths."""
        ts = datetime(2023, 6, 15, 12, 30, 0)
        path = S3KeyGenerator.to_local_path(ts, SatellitePattern.GOES_16)
        expected = Path("2023/06/15/goes16_20230615_123000_band13.png")
        self.assertEqual(path, expected)

    def test_find_nearest_goes_intervals(self):
        """Test finding nearest GOES intervals."""
        # Test RadF (10-minute intervals)
        ts = datetime(2023, 6, 15, 12, 5, 0)
        intervals = S3KeyGenerator.find_nearest_goes_intervals(ts, "RadF")
        expected = [
            datetime(2023, 6, 15, 12, 0, 0),
            datetime(2023, 6, 15, 12, 10, 0),
        ]
        self.assertEqual(intervals, expected)

        # Test RadC (5-minute intervals)
        ts = datetime(2023, 6, 15, 12, 3, 0)
        intervals = S3KeyGenerator.find_nearest_goes_intervals(ts, "RadC")
        expected = [
            datetime(2023, 6, 15, 12, 1, 0),
            datetime(2023, 6, 15, 12, 6, 0),
        ]
        self.assertEqual(intervals, expected)


class TestFilterS3Keys(unittest.TestCase):
    """Test the filter_s3_keys_by_band function."""

    def test_filter_s3_keys_by_band(self):
        """Test filtering S3 keys by band number."""
        keys = [
            "OR_ABI-L1b-RadF-M6C01_G16_s20230101200000_e20230101205959_c20230101210030.nc",
            "OR_ABI-L1b-RadF-M6C13_G16_s20230101200000_e20230101205959_c20230101210030.nc",
            "OR_ABI-L1b-RadF-M6C15_G16_s20230101200000_e20230101205959_c20230101210030.nc",
        ]

        # Filter for band 13
        filtered = filter_s3_keys_by_band(keys, 13)
        self.assertEqual(len(filtered), 1)
        self.assertIn("C13", filtered[0])

        # Filter for band 1
        filtered = filter_s3_keys_by_band(keys, 1)
        self.assertEqual(len(filtered), 1)
        self.assertIn("C01", filtered[0])

        # Invalid band
        filtered = filter_s3_keys_by_band(keys, 99)
        self.assertEqual(filtered, [])


class TestDirectoryScanner(unittest.TestCase):
    """Test the DirectoryScanner class."""

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.is_dir")
    @patch("pathlib.Path.glob")
    def test_scan_directory_for_timestamps(self, mock_glob, mock_is_dir, mock_exists):
        """Test scanning directory for timestamps."""
        # Setup mocks
        mock_exists.return_value = True
        mock_is_dir.return_value = True

        # Create mock PNG files
        mock_files = [
            MagicMock(name="image_G16_20230615T120000Z.png"),
            MagicMock(name="image_G16_20230615T123000Z.png"),
            MagicMock(name="image_G16_20230615T130000Z.png"),
        ]
        for i, mock_file in enumerate(mock_files):
            mock_file.name = mock_file._mock_name

        mock_glob.return_value = mock_files

        # Test scanning
        directory = Path("/test")
        timestamps = DirectoryScanner.scan_directory_for_timestamps(
            directory, SatellitePattern.GOES_16
        )

        self.assertEqual(len(timestamps), 3)
        self.assertEqual(timestamps[0], datetime(2023, 6, 15, 12, 0, 0))
        self.assertEqual(timestamps[1], datetime(2023, 6, 15, 12, 30, 0))
        self.assertEqual(timestamps[2], datetime(2023, 6, 15, 13, 0, 0))

    def test_find_date_range_in_directory(self):
        """Test finding date range in directory."""
        with patch.object(
            DirectoryScanner, "scan_directory_for_timestamps"
        ) as mock_scan:
            mock_scan.return_value = [
                datetime(2023, 6, 15, 12, 0, 0),
                datetime(2023, 6, 15, 13, 0, 0),
                datetime(2023, 6, 15, 14, 0, 0),
            ]

            directory = Path("/test")
            start, end = DirectoryScanner.find_date_range_in_directory(
                directory, SatellitePattern.GOES_16
            )

            self.assertEqual(start, datetime(2023, 6, 15, 12, 0, 0))
            self.assertEqual(end, datetime(2023, 6, 15, 14, 0, 0))


class TestTimeIndex(unittest.TestCase):
    """Test the main TimeIndex class."""

    def test_constants(self):
        """Test that constants are properly exposed."""
        self.assertEqual(TimeIndex.BAND, BAND)
        self.assertEqual(TimeIndex.CDN_RES, DEFAULT_CDN_RESOLUTION)
        self.assertIn("RadF", TimeIndex.STANDARD_INTERVALS)
        self.assertEqual(TimeIndex.STANDARD_INTERVALS["RadF"], RADF_MINUTES)
        self.assertEqual(TimeIndex.STANDARD_INTERVALS["RadC"], RADC_MINUTES)

    def test_delegated_methods(self):
        """Test that TimeIndex properly delegates to other classes."""
        ts = datetime(2023, 6, 15, 12, 30, 0)

        # Test CDN URL generation
        url = TimeIndex.to_cdn_url(ts, SatellitePattern.GOES_16)
        self.assertIsInstance(url, str)
        self.assertIn("cdn.star.nesdis.noaa.gov", url)

        # Test S3 key generation
        key = TimeIndex.to_s3_key(ts, SatellitePattern.GOES_16)
        self.assertIsInstance(key, str)
        self.assertIn("ABI-L1b", key)

        # Test S3 bucket
        bucket = TimeIndex.get_s3_bucket(SatellitePattern.GOES_16)
        self.assertEqual(bucket, "noaa-goes16")


if __name__ == "__main__":
    unittest.main()
