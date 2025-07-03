"""
Comprehensive tests for the refactored time_utils modules - Optimized v2.

Optimizations applied:
- Shared expensive setup operations across test classes
- Parameterized test methods for comprehensive coverage
- Mock time operations for consistent testing
- Combined related test scenarios
- Reduced redundant object creation
- Enhanced fixture reuse
"""

from datetime import datetime, timedelta
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

import pytest

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


class SharedTimeUtilsTestCase(unittest.TestCase):
    """Shared base class for time utils tests with common optimizations."""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up shared test data for all test methods."""
        # Shared test timestamps
        cls.test_dates = {
            "standard": datetime(2023, 6, 15, 12, 30, 0),
            "midnight": datetime(2023, 6, 15, 0, 0, 0),
            "end_of_day": datetime(2023, 6, 15, 23, 59, 59),
            "new_year": datetime(2023, 1, 1, 0, 0, 0),
            "leap_day": datetime(2024, 2, 29, 12, 0, 0),
            "precise": datetime(2023, 6, 15, 12, 30, 45, 123456),
            "custom_range_start": datetime(2023, 5, 1, 10, 30),
            "custom_range_end": datetime(2023, 5, 15, 16, 45),
        }

        # Shared satellite patterns
        cls.satellites = {
            "goes16": SatellitePattern.GOES_16,
            "goes18": SatellitePattern.GOES_18,
            "generic": SatellitePattern.GENERIC,
        }

        # Pre-computed expected values
        cls.expected_satellite_info = {
            SatellitePattern.GOES_16: {
                "name": "GOES-16 (East)",
                "short_name": "GOES16",
                "s3_bucket": "noaa-goes16",
                "code": "G16",
            },
            SatellitePattern.GOES_18: {
                "name": "GOES-18 (West)",
                "short_name": "GOES18",
                "s3_bucket": "noaa-goes18",
                "code": "G18",
            },
            SatellitePattern.GENERIC: {
                "name": "Generic Pattern",
                "s3_bucket": None,
                "code": None,
            },
        }

        # Test file patterns
        cls.test_filenames = {
            "simple_goes16": "goes16_20230615_123000_band13.png",
            "legacy_goes16": "image_G16_20230615T123000Z.png",
            "cdn_format": "2023166123000_GOES16-ABI-FD-13-5424x5424.jpg",
            "invalid": "invalid_filename.png",
        }

        # Timestamp sequences for testing
        cls.test_sequences = {
            "regular_10min": [
                datetime(2023, 6, 15, 12, 0, 0),
                datetime(2023, 6, 15, 12, 10, 0),
                datetime(2023, 6, 15, 12, 20, 0),
                datetime(2023, 6, 15, 12, 30, 0),
            ],
            "irregular_mixed": [
                datetime(2023, 6, 15, 12, 0, 0),
                datetime(2023, 6, 15, 12, 5, 0),
                datetime(2023, 6, 15, 12, 15, 0),
                datetime(2023, 6, 15, 12, 30, 0),
            ],
        }


class TestPatternsV2(SharedTimeUtilsTestCase):
    """Test the patterns module functionality - optimized v2."""

    def test_get_satellite_info_comprehensive(self) -> None:
        """Test getting satellite information for all satellites."""
        test_cases = [
            (SatellitePattern.GOES_16, SatellitePattern.GOES_16),
            (SatellitePattern.GOES_18, SatellitePattern.GOES_18),
            (SatellitePattern.GENERIC, SatellitePattern.GENERIC),
        ]
        
        for satellite, expected_key in test_cases:
            info = get_satellite_info(satellite)
            expected = self.expected_satellite_info[expected_key]

            for key, expected_value in expected.items():
                assert info[key] == expected_value

    def test_get_satellite_info_all_required_fields(self) -> None:
        """Test that all satellite info contains required fields."""
        required_fields = ["name", "short_name", "s3_bucket", "code"]

        for satellite in [SatellitePattern.GOES_16, SatellitePattern.GOES_18, SatellitePattern.GENERIC]:
            info = get_satellite_info(satellite)
            for field in required_fields:
                assert field in info


class TestTimestampExtractorV2(SharedTimeUtilsTestCase):
    """Test the TimestampExtractor class - optimized v2."""

    def test_extract_timestamp_patterns(self) -> None:
        """Test extracting timestamps from various filename patterns."""
        test_cases = [
            ("simple_goes16", SatellitePattern.GOES_16, datetime(2023, 6, 15, 12, 30, 0)),
            ("legacy_goes16", SatellitePattern.GOES_16, datetime(2023, 6, 15, 12, 30, 0)),
        ]
        
        for filename_key, satellite, expected_datetime in test_cases:
            filename = self.test_filenames[filename_key]
            ts = TimestampExtractor.extract_timestamp(filename, satellite)
            assert ts == expected_datetime

    def test_extract_timestamp_invalid_pattern(self) -> None:
        """Test extracting timestamp with invalid pattern."""
        filename = self.test_filenames["invalid"]
        with pytest.raises(ValueError):
            TimestampExtractor.extract_timestamp(filename, self.satellites["goes16"])

    def test_extract_timestamp_and_satellite(self) -> None:
        """Test extracting both timestamp and satellite."""
        filename = self.test_filenames["cdn_format"]
        ts, sat = TimestampExtractor.extract_timestamp_and_satellite(filename)
        assert ts == datetime(2023, 6, 15, 12, 30)
        assert sat == SatellitePattern.GOES_16

    def test_extract_timestamp_from_directory_name(self) -> None:
        """Test extracting timestamp from directory names."""
        test_cases = [
            ("2024-12-21_18-00-22", datetime(2024, 12, 21, 18, 0, 22)),
            ("20241221_180022", datetime(2024, 12, 21, 18, 0, 22)),
            ("GOES18/FD/13/2023/166", datetime(2023, 6, 15, 0, 0, 0)),
            ("invalid_directory", None),
        ]
        
        for dirname, expected_result in test_cases:
            result = TimestampExtractor.extract_timestamp_from_directory_name(dirname)
            assert result == expected_result

    def test_extract_timestamp_error_handling(self) -> None:
        """Test error handling in timestamp extraction."""
        # Test with None input
        with pytest.raises((TypeError, AttributeError)):
            TimestampExtractor.extract_timestamp(None, self.satellites["goes16"])

        # Test with empty string
        with pytest.raises(ValueError):
            TimestampExtractor.extract_timestamp("", self.satellites["goes16"])


class TestTimestampFormatterV2(SharedTimeUtilsTestCase):
    """Test the TimestampFormatter class - optimized v2."""

    def test_format_timestamp_consistency(self) -> None:
        """Test timestamp formatting consistency."""
        dt = self.test_dates["standard"]
        formatted = TimestampFormatter.format_timestamp(dt)
        assert formatted == "20230615T123000"

    def test_get_filename_pattern(self) -> None:
        """Test getting filename patterns for various satellites."""
        test_cases = [
            (SatellitePattern.GOES_16, None, "image_G16_{timestamp}Z.png"),
            (SatellitePattern.GOES_18, "test", "test_G18_{timestamp}Z.png"),
            (SatellitePattern.GENERIC, None, "image_{timestamp}Z.png"),
        ]
        
        for satellite, base_name, expected_pattern in test_cases:
            if base_name:
                pattern = TimestampFormatter.get_filename_pattern(satellite, base_name)
            else:
                pattern = TimestampFormatter.get_filename_pattern(satellite)
            assert pattern == expected_pattern

    def test_generate_expected_filename(self) -> None:
        """Test generating expected filenames for various satellites."""
        test_cases = [
            (SatellitePattern.GOES_16, "image_G16_20230615T123000Z.png"),
            (SatellitePattern.GOES_18, "image_G18_20230615T123000Z.png"),
            (SatellitePattern.GENERIC, "image_20230615T123000Z.png"),
        ]
        
        dt = self.test_dates["standard"]
        for satellite, expected_filename in test_cases:
            filename = TimestampFormatter.generate_expected_filename(dt, satellite)
            assert filename == expected_filename

    def test_format_timestamp_edge_cases(self) -> None:
        """Test timestamp formatting with edge cases."""
        # Test midnight
        midnight = self.test_dates["midnight"]
        formatted = TimestampFormatter.format_timestamp(midnight)
        assert formatted == "20230615T000000"

        # Test end of day
        end_of_day = self.test_dates["end_of_day"]
        formatted = TimestampFormatter.format_timestamp(end_of_day)
        assert formatted == "20230615T235959"


class TestTimestampGeneratorV2(SharedTimeUtilsTestCase):
    """Test the TimestampGenerator class - optimized v2."""

    def test_generate_timestamp_sequence(self) -> None:
        """Test generating timestamp sequence."""
        start = self.test_dates["standard"].replace(minute=0)
        end = start + timedelta(hours=1)
        sequence = TimestampGenerator.generate_timestamp_sequence(start, end, 30)

        expected = [
            start,
            start + timedelta(minutes=30),
            end,
        ]
        assert sequence == expected

    def test_detect_interval(self) -> None:
        """Test detecting intervals for various timestamp sequences."""
        test_cases = [
            ("regular_10min", 10),
            ("irregular_mixed", 5),  # Most common difference
        ]
        
        for sequence_key, expected_interval in test_cases:
            timestamps = self.test_sequences[sequence_key]
            interval = TimestampGenerator.detect_interval(timestamps)
            assert interval == expected_interval

    def test_is_recent_with_mocked_time(self) -> None:
        """Test is_recent function with mocked datetime."""
        fixed_now = datetime(2023, 6, 20, 0, 0, 0)

        with patch("goesvfi.integrity_check.time_utils.timestamp.datetime") as mock_dt:
            mock_dt.now.return_value = fixed_now
            mock_dt.side_effect = datetime

            # Recent date (3 days ago)
            recent = fixed_now - timedelta(days=3)
            assert TimestampGenerator.is_recent(recent)

            # Old date (10 days ago)
            old = fixed_now - timedelta(days=10)
            assert not TimestampGenerator.is_recent(old)

    def test_generate_sequence_edge_cases(self) -> None:
        """Test timestamp sequence generation with edge cases."""
        start = self.test_dates["standard"]

        # Test same start and end
        sequence = TimestampGenerator.generate_timestamp_sequence(start, start, 30)
        assert sequence == [start]

        # Test very small interval - when interval is larger than time range
        end = start + timedelta(minutes=1)
        sequence = TimestampGenerator.generate_timestamp_sequence(start, end, 30)
        assert len(sequence) == 1  # Only start is included since next interval would exceed end

    def test_detect_interval_error_handling(self) -> None:
        """Test interval detection error handling."""
        # Empty list
        result = TimestampGenerator.detect_interval([])
        assert isinstance(result, int)

        # Single timestamp
        single = [self.test_dates["standard"]]
        result = TimestampGenerator.detect_interval(single)
        assert isinstance(result, int)


class TestS3KeyGeneratorV2(SharedTimeUtilsTestCase):
    """Test the S3KeyGenerator class - optimized v2."""

    def test_to_cdn_url(self) -> None:
        """Test generating CDN URLs with various parameters."""
        test_cases = [
            (SatellitePattern.GOES_16, None, ["cdn.star.nesdis.noaa.gov/GOES16", "2023166"]),
            (SatellitePattern.GOES_18, "1808x1808", ["cdn.star.nesdis.noaa.gov/GOES18", "1808x1808"]),
        ]
        
        ts = self.test_dates["standard"]
        for satellite, resolution, expected_parts in test_cases:
            if resolution:
                url = S3KeyGenerator.to_cdn_url(ts, satellite, resolution)
            else:
                url = S3KeyGenerator.to_cdn_url(ts, satellite)

            for part in expected_parts:
                assert part in url

    def test_to_s3_key(self) -> None:
        """Test generating S3 keys for different product types."""
        test_cases = [
            ("RadC", ["ABI-L1b-RadC/2023/166/12/", "M6C13_G16"]),
            ("RadF", ["ABI-L1b-RadF/2023/166/12/", "M6C13_G16"]),
        ]
        
        ts = self.test_dates["standard"].replace(minute=1)  # Ensure minute=1 for RadC
        for product_type, expected_parts in test_cases:
            key = S3KeyGenerator.to_s3_key(ts, self.satellites["goes16"], product_type)

            for part in expected_parts:
                assert part in key

    def test_get_s3_bucket(self) -> None:
        """Test getting S3 bucket names."""
        test_cases = [
            (SatellitePattern.GOES_16, "noaa-goes16"),
            (SatellitePattern.GOES_18, "noaa-goes18"),
        ]
        
        for satellite, expected_bucket in test_cases:
            bucket = S3KeyGenerator.get_s3_bucket(satellite)
            assert bucket == expected_bucket

    def test_get_s3_bucket_generic_error(self) -> None:
        """Test S3 bucket error for generic satellite."""
        with pytest.raises(ValueError):
            S3KeyGenerator.get_s3_bucket(SatellitePattern.GENERIC)

    def test_generate_local_path(self) -> None:
        """Test generating local paths."""
        ts = self.test_dates["standard"]
        base_dir = Path("/data")

        path = S3KeyGenerator.generate_local_path(ts, self.satellites["goes16"], base_dir)
        expected = base_dir / "GOES16" / "FD" / "13" / "2023" / "166" / "20231661230_GOES16-ABI-FD-13-5424x5424.png"
        assert path == expected

    def test_to_local_path(self) -> None:
        """Test generating simplified local paths."""
        ts = self.test_dates["standard"]
        path = S3KeyGenerator.to_local_path(ts, self.satellites["goes16"])
        expected = Path("2023/06/15/goes16_20230615_123000_band13.png")
        assert path == expected

    def test_find_nearest_goes_intervals(self) -> None:
        """Test finding nearest GOES intervals."""
        test_cases = [
            ("RadF", 2),  # 10-minute intervals: before and after
            ("RadC", 2),  # 5-minute intervals: before and after
        ]
        
        ts = self.test_dates["standard"].replace(minute=5)  # 12:05
        for product_type, expected_count in test_cases:
            intervals = S3KeyGenerator.find_nearest_goes_intervals(ts, product_type)

            assert len(intervals) == expected_count
            assert all(isinstance(interval, datetime) for interval in intervals)

    def test_s3_key_time_components(self) -> None:
        """Test S3 key generation with various time components."""
        # Test midnight
        midnight = self.test_dates["midnight"]
        key = S3KeyGenerator.to_s3_key(midnight, self.satellites["goes16"], "RadF")
        assert "/00/" in key  # Hour should be 00

        # Test end of day
        end_of_day = self.test_dates["end_of_day"]
        key = S3KeyGenerator.to_s3_key(end_of_day, self.satellites["goes16"], "RadF")
        assert "/23/" in key  # Hour should be 23


class TestFilterS3KeysV2(SharedTimeUtilsTestCase):
    """Test the filter_s3_keys_by_band function - optimized v2."""

    @classmethod
    def setUpClass(cls) -> None:
        """Set up shared test data."""
        super().setUpClass()
        cls.test_keys = [
            "OR_ABI-L1b-RadF-M6C01_G16_s20230101200000_e20230101205959_c20230101210030.nc",
            "OR_ABI-L1b-RadF-M6C13_G16_s20230101200000_e20230101205959_c20230101210030.nc",
            "OR_ABI-L1b-RadF-M6C15_G16_s20230101200000_e20230101205959_c20230101210030.nc",
        ]

    def test_filter_s3_keys_by_band(self) -> None:
        """Test filtering S3 keys by band number."""
        test_cases = [
            (13, 1, "C13"),
            (1, 1, "C01"),
            (15, 1, "C15"),
            (99, 0, None),  # Invalid band
        ]
        
        for band, expected_count, expected_content in test_cases:
            filtered = filter_s3_keys_by_band(self.test_keys, band)
            assert len(filtered) == expected_count

            if expected_content and filtered:
                assert expected_content in filtered[0]

    def test_filter_s3_keys_performance(self) -> None:
        """Test filtering performance with larger dataset."""
        # Generate larger test dataset
        large_keys = []
        for band in range(1, 17):  # ABI has 16 bands
            band_str = f"C{band:02d}"
            key = f"OR_ABI-L1b-RadF-M6{band_str}_G16_s20230101200000_e20230101205959_c20230101210030.nc"
            large_keys.append(key)

        # Test filtering each band
        for band in range(1, 17):
            filtered = filter_s3_keys_by_band(large_keys, band)
            assert len(filtered) == 1
            assert f"C{band:02d}" in filtered[0]


class TestDirectoryScannerV2(SharedTimeUtilsTestCase):
    """Test the DirectoryScanner class - optimized v2."""

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.is_dir")
    @patch("pathlib.Path.glob")
    def test_scan_directory_for_timestamps(self, mock_glob, mock_is_dir, mock_exists) -> None:
        """Test scanning directory for timestamps with mocked filesystem."""
        # Setup mocks
        mock_exists.return_value = True
        mock_is_dir.return_value = True

        # Create mock PNG files
        mock_files = []
        expected_timestamps = []

        for _i, time_key in enumerate(["standard", "midnight", "end_of_day"]):
            dt = self.test_dates[time_key]
            filename = f"image_G16_{dt.strftime('%Y%m%dT%H%M%S')}Z.png"

            mock_file = MagicMock()
            mock_file.name = filename
            mock_files.append(mock_file)
            expected_timestamps.append(dt)

        mock_glob.return_value = mock_files

        # Test scanning
        directory = Path("/test")
        timestamps = DirectoryScanner.scan_directory_for_timestamps(directory, self.satellites["goes16"])

        assert len(timestamps) == 3
        # Sort both lists for comparison
        timestamps.sort()
        expected_timestamps.sort()
        assert timestamps == expected_timestamps

    def test_find_date_range_in_directory(self) -> None:
        """Test finding date range in directory."""
        test_timestamps = [
            self.test_dates["standard"],
            self.test_dates["midnight"],
            self.test_dates["end_of_day"],
        ]

        with patch.object(DirectoryScanner, "scan_directory_for_timestamps") as mock_scan:
            # Return sorted timestamps like the real method does
            mock_scan.return_value = sorted(test_timestamps)

            directory = Path("/test")
            start, end = DirectoryScanner.find_date_range_in_directory(directory, self.satellites["goes16"])

            # Verify we get the min and max timestamps
            assert start == min(test_timestamps)
            assert end == max(test_timestamps)

    def test_scan_directory_error_handling(self) -> None:
        """Test error handling in directory scanning."""
        with patch("pathlib.Path.exists", return_value=False):
            # Non-existent directory should be handled gracefully
            directory = Path("/nonexistent")
            timestamps = DirectoryScanner.scan_directory_for_timestamps(directory, self.satellites["goes16"])
            assert timestamps == []


class TestTimeIndexV2(SharedTimeUtilsTestCase):
    """Test the main TimeIndex class - optimized v2."""

    def test_constants_availability(self) -> None:
        """Test that constants are properly exposed."""
        assert TimeIndex.BAND == BAND
        assert TimeIndex.CDN_RES == DEFAULT_CDN_RESOLUTION
        assert "RadF" in TimeIndex.STANDARD_INTERVALS
        assert TimeIndex.STANDARD_INTERVALS["RadF"] == RADF_MINUTES
        assert TimeIndex.STANDARD_INTERVALS["RadC"] == RADC_MINUTES

    def test_delegated_methods(self) -> None:
        """Test that TimeIndex properly delegates to other classes."""
        test_cases = [
            ("to_cdn_url", str),
            ("to_s3_key", str),
            ("get_s3_bucket", str),
        ]
        
        ts = self.test_dates["standard"]
        for method_name, expected_type in test_cases:
            if method_name == "to_cdn_url":
                result = TimeIndex.to_cdn_url(ts, self.satellites["goes16"])
            elif method_name == "to_s3_key":
                result = TimeIndex.to_s3_key(ts, self.satellites["goes16"])
            elif method_name == "get_s3_bucket":
                result = TimeIndex.get_s3_bucket(self.satellites["goes16"])

            assert isinstance(result, expected_type)

    def test_time_index_integration(self) -> None:
        """Test TimeIndex integration with all methods."""
        ts = self.test_dates["standard"]
        satellite = self.satellites["goes16"]

        # Test CDN URL generation
        url = TimeIndex.to_cdn_url(ts, satellite)
        assert "cdn.star.nesdis.noaa.gov" in url

        # Test S3 key generation
        key = TimeIndex.to_s3_key(ts, satellite)
        assert "ABI-L1b" in key

        # Test S3 bucket
        bucket = TimeIndex.get_s3_bucket(satellite)
        assert bucket == "noaa-goes16"

        # Test local path
        path = TimeIndex.to_local_path(ts, satellite)
        assert isinstance(path, Path)

    def test_performance_batch_operations(self) -> None:
        """Test performance with batch operations."""
        # Generate multiple timestamps
        base_time = self.test_dates["standard"]
        timestamps = [base_time + timedelta(hours=i) for i in range(24)]

        # Test batch CDN URL generation
        urls = [TimeIndex.to_cdn_url(ts, self.satellites["goes16"]) for ts in timestamps]
        assert len(urls) == 24
        assert all("cdn.star.nesdis.noaa.gov" in url for url in urls)

        # Test batch S3 key generation
        keys = [TimeIndex.to_s3_key(ts, self.satellites["goes16"]) for ts in timestamps]
        assert len(keys) == 24
        assert all("ABI-L1b" in key for key in keys)

    def test_error_handling_comprehensive(self) -> None:
        """Test comprehensive error handling."""
        # Test with None timestamp
        with pytest.raises((TypeError, AttributeError)):
            TimeIndex.to_cdn_url(None, self.satellites["goes16"])

        # Test with invalid satellite for S3 bucket
        with pytest.raises(ValueError):
            TimeIndex.get_s3_bucket(self.satellites["generic"])

        # Test with invalid timestamp format
        try:
            invalid_ts = "not a datetime"
            TimeIndex.to_s3_key(invalid_ts, self.satellites["goes16"])
        except (AttributeError, TypeError):
            pass  # Expected for invalid timestamp


if __name__ == "__main__":
    unittest.main()
