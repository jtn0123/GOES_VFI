"""Unit tests for the refactored TimeIndex functionality."""

from datetime import datetime
from pathlib import Path
import unittest
from unittest.mock import patch

import pytest

from goesvfi.integrity_check.time_index_refactored import (
    _filter_timestamp_by_range,
    _find_nearest_valid_scan_minute,
    _scan_files_for_timestamps,
    _scan_subdirectories_for_timestamps,
    _try_extract_time_component,
    _try_primary_datetime_patterns,
    _try_satellite_specific_patterns,
    _validate_directory_and_pattern,
    _validate_product_type_and_band,
    extract_timestamp_from_directory_name,
    scan_directory_for_timestamps,
    to_s3_key,
)


class TestExtractTimestampFromDirectoryName(unittest.TestCase):
    """Test cases for the extract_timestamp_from_directory_name function and its helpers."""

    def test_try_extract_time_component(self) -> None:
        """Test the _try_extract_time_component helper function."""
        # Define test patterns
        patterns = [
            unittest.mock.Mock(**{"search.return_value": None}),  # No match
            unittest.mock.Mock(**{  # Valid match
                "search.return_value": unittest.mock.Mock(**{
                    "group.side_effect": lambda i: {1: "12", 2: "30", 3: "00"}[i]
                })
            }),
            unittest.mock.Mock(**{  # Match but invalid values
                "search.return_value": unittest.mock.Mock(**{"group.side_effect": ValueError("Invalid value")})
            }),
        ]

        # Test with no match
        assert _try_extract_time_component("test_dir", [patterns[0]]) is None

        # Test with valid match
        result = _try_extract_time_component("test_dir", [patterns[1]])
        assert result == (12, 30, 0)

        # Test with exception in group extraction
        assert _try_extract_time_component("test_dir", [patterns[2]]) is None

    def test_try_primary_datetime_patterns(self) -> None:
        """Test the _try_primary_datetime_patterns helper function."""
        # Test valid YYYY-MM-DD_HH-MM-SS format
        result = _try_primary_datetime_patterns("2023-06-15_12-30-00")
        assert result == datetime(2023, 6, 15, 12, 30, 0)

        # Test valid YYYYMMDD_HHMMSS format
        result = _try_primary_datetime_patterns("20230615_123000")
        assert result == datetime(2023, 6, 15, 12, 30, 0)

        # Test valid YYYYMMDDTHHMMSS format
        result = _try_primary_datetime_patterns("20230615T123000")
        assert result == datetime(2023, 6, 15, 12, 30, 0)

        # Test invalid format
        result = _try_primary_datetime_patterns("invalid_format")
        assert result is None

    def test_try_satellite_specific_patterns(self) -> None:
        """Test the _try_satellite_specific_patterns helper function."""
        # Test valid GOES18/FD/13/YYYY/DDD format
        with patch("goesvfi.integrity_check.time_index_refactored.date_utils.doy_to_date") as mock_doy_to_date:
            mock_date = unittest.mock.Mock(year=2023, month=6, day=15)
            mock_doy_to_date.return_value = mock_date

            result = _try_satellite_specific_patterns("GOES18/FD/13/2023/166")
            mock_doy_to_date.assert_called_once_with(2023, 166)
            assert result == datetime(2023, 6, 15, 0, 0, 0)

        # Test valid goes18_YYYYMMDD_HHMMSS format
        result = _try_satellite_specific_patterns("goes18_20230615_123000")
        assert result == datetime(2023, 6, 15, 12, 30, 0)

        # Test invalid format
        result = _try_satellite_specific_patterns("invalid_format")
        assert result is None

    def test_extract_timestamp_from_directory_name(self) -> None:
        """Test the extract_timestamp_from_directory_name function."""
        # Test with date_utils.parse_satellite_path returning a valid date
        with patch("goesvfi.integrity_check.time_index_refactored.date_utils.parse_satellite_path") as mock_parse:
            mock_date = datetime(2023, 6, 15).date()
            mock_parse.return_value = mock_date

            # Test with valid time component
            result = extract_timestamp_from_directory_name("2023-06-15_12-30-00")
            assert result == datetime(2023, 6, 15, 12, 30, 0)

            # Test with no time component (should use midnight)
            result = extract_timestamp_from_directory_name("2023-06-15")
            assert result == datetime(2023, 6, 15, 0, 0, 0)

        # Test with date_utils.parse_satellite_path returning None
        with patch(
            "goesvfi.integrity_check.time_index_refactored.date_utils.parse_satellite_path",
            return_value=None,
        ):
            # Test with valid primary datetime pattern
            with patch("goesvfi.integrity_check.time_index_refactored._try_primary_datetime_patterns") as mock_primary:
                mock_primary.return_value = datetime(2023, 6, 15, 12, 30, 0)
                mock_satellite = unittest.mock.Mock(return_value=None)

                result = extract_timestamp_from_directory_name("2023-06-15_12-30-00")
                assert result == datetime(2023, 6, 15, 12, 30, 0)
                mock_primary.assert_called_once()

            # Test with valid satellite-specific pattern
            with (
                patch(
                    "goesvfi.integrity_check.time_index_refactored._try_primary_datetime_patterns",
                    return_value=None,
                ),
                patch(
                    "goesvfi.integrity_check.time_index_refactored._try_satellite_specific_patterns"
                ) as mock_satellite,
            ):
                mock_satellite.return_value = datetime(2023, 6, 15, 12, 30, 0)

                result = extract_timestamp_from_directory_name("GOES18/FD/13/2023/166")
                assert result == datetime(2023, 6, 15, 12, 30, 0)
                mock_satellite.assert_called_once()

            # Test with no pattern matching
            with (
                patch(
                    "goesvfi.integrity_check.time_index_refactored._try_primary_datetime_patterns",
                    return_value=None,
                ),
                patch(
                    "goesvfi.integrity_check.time_index_refactored._try_satellite_specific_patterns",
                    return_value=None,
                ),
            ):
                result = extract_timestamp_from_directory_name("invalid_format")
                assert result is None


class TestScanDirectoryForTimestamps(unittest.TestCase):
    """Test cases for the scan_directory_for_timestamps function and its helpers."""

    def test_validate_directory_and_pattern(self) -> None:
        """Test the _validate_directory_and_pattern helper function."""
        # Test with non-existent directory
        with patch("pathlib.Path.exists", return_value=False), patch("pathlib.Path.is_dir", return_value=False):
            is_valid, compiled_pattern = _validate_directory_and_pattern(Path("/fake/dir"), "GOES_16")
            assert not is_valid
            assert compiled_pattern is None

        # Test with directory that's not a directory
        with patch("pathlib.Path.exists", return_value=True), patch("pathlib.Path.is_dir", return_value=False):
            is_valid, compiled_pattern = _validate_directory_and_pattern(Path("/fake/file"), "GOES_16")
            assert not is_valid
            assert compiled_pattern is None

        # Test with unknown pattern
        with patch("pathlib.Path.exists", return_value=True), patch("pathlib.Path.is_dir", return_value=True):
            with patch(
                "goesvfi.integrity_check.time_index_refactored.COMPILED_PATTERNS",
                {},  # Empty dict means .get() will return None for any key
            ):
                is_valid, compiled_pattern = _validate_directory_and_pattern(Path("/valid/dir"), "UNKNOWN_PATTERN")
                assert not is_valid
                assert compiled_pattern is None

        # Test with valid directory and pattern
        with patch("pathlib.Path.exists", return_value=True), patch("pathlib.Path.is_dir", return_value=True):
            mock_pattern = unittest.mock.Mock()
            mock_compiled_patterns = {"GOES_16": mock_pattern}
            with patch(
                "goesvfi.integrity_check.time_index_refactored.COMPILED_PATTERNS",
                mock_compiled_patterns,
            ):
                is_valid, compiled_pattern = _validate_directory_and_pattern(Path("/valid/dir"), "GOES_16")
                assert is_valid
                assert compiled_pattern == mock_pattern

    def test_filter_timestamp_by_range(self) -> None:
        """Test the _filter_timestamp_by_range helper function."""
        timestamp = datetime(2023, 6, 15, 12, 30, 0)

        # Test with no range filters
        assert _filter_timestamp_by_range(timestamp, None, None)

        # Test with only start_time
        start_time = datetime(2023, 6, 15, 0, 0, 0)  # Earlier
        assert _filter_timestamp_by_range(timestamp, start_time, None)

        start_time = datetime(2023, 6, 16, 0, 0, 0)  # Later
        assert not _filter_timestamp_by_range(timestamp, start_time, None)

        # Test with only end_time
        end_time = datetime(2023, 6, 16, 0, 0, 0)  # Later
        assert _filter_timestamp_by_range(timestamp, None, end_time)

        end_time = datetime(2023, 6, 14, 0, 0, 0)  # Earlier
        assert not _filter_timestamp_by_range(timestamp, None, end_time)

        # Test with both start_time and end_time
        start_time = datetime(2023, 6, 14, 0, 0, 0)  # Earlier
        end_time = datetime(2023, 6, 16, 0, 0, 0)  # Later
        assert _filter_timestamp_by_range(timestamp, start_time, end_time)

        start_time = datetime(2023, 6, 16, 0, 0, 0)  # Later
        end_time = datetime(2023, 6, 17, 0, 0, 0)  # Later
        assert not _filter_timestamp_by_range(timestamp, start_time, end_time)

    @patch("goesvfi.integrity_check.time_index_refactored._extract_timestamp_from_file")
    @patch("goesvfi.integrity_check.time_index_refactored._filter_timestamp_by_range")
    def test_scan_files_for_timestamps(self, mock_filter, mock_extract, tmp_path) -> None:
        """Test the _scan_files_for_timestamps helper function."""
        # Setup mock files
        mock_files = [tmp_path / f"file{i}.png" for i in range(3)]

        # Mock glob to return our mock files
        with patch("pathlib.Path.glob", return_value=mock_files):
            # Test with no timestamp matches
            mock_extract.side_effect = [None, None, None]

            result = _scan_files_for_timestamps(tmp_path, "GOES_16")
            assert len(result) == 0

            # Test with some timestamp matches that pass filtering
            mock_timestamps = [
                datetime(2023, 6, 15, 12, 0, 0),
                datetime(2023, 6, 15, 12, 30, 0),
                datetime(2023, 6, 15, 13, 0, 0),
            ]
            mock_extract.side_effect = mock_timestamps
            mock_filter.return_value = True

            result = _scan_files_for_timestamps(
                tmp_path,
                "GOES_16",
                start_time=datetime(2023, 6, 15, 0, 0, 0),
                end_time=datetime(2023, 6, 16, 0, 0, 0),
            )
            assert len(result) == 3
            assert result == mock_timestamps

            # Test with some timestamp matches that fail filtering
            mock_extract.side_effect = mock_timestamps
            mock_filter.side_effect = [True, False, True]

            result = _scan_files_for_timestamps(tmp_path, "GOES_16")
            assert len(result) == 2
            assert result == [mock_timestamps[0], mock_timestamps[2]]

    @patch("goesvfi.integrity_check.time_index_refactored.extract_timestamp_from_directory_name")
    @patch("goesvfi.integrity_check.time_index_refactored._filter_timestamp_by_range")
    def test_scan_subdirectories_for_timestamps(self, mock_filter, mock_extract, tmp_path) -> None:
        """Test the _scan_subdirectories_for_timestamps helper function."""
        # Setup mock subdirectories
        mock_subdirs = [tmp_path / f"subdir{i}" for i in range(3)]

        # Mock iterdir to return our mock subdirectories
        with patch("pathlib.Path.iterdir", return_value=mock_subdirs):
            with patch("pathlib.Path.is_dir", return_value=True):
                # Test with no timestamp matches
                mock_extract.side_effect = [None, None, None]

                result = _scan_subdirectories_for_timestamps(tmp_path)
                assert len(result) == 0

                # Test with some timestamp matches that pass filtering
                mock_timestamps = [
                    datetime(2023, 6, 15, 12, 0, 0),
                    datetime(2023, 6, 15, 12, 30, 0),
                    datetime(2023, 6, 15, 13, 0, 0),
                ]
                mock_extract.side_effect = mock_timestamps
                mock_filter.return_value = True

                result = _scan_subdirectories_for_timestamps(
                    Path("/tmp"),
                    start_time=datetime(2023, 6, 15, 0, 0, 0),
                    end_time=datetime(2023, 6, 16, 0, 0, 0),
                )
                assert len(result) == 3
                assert result == mock_timestamps

                # Test with some timestamp matches that fail filtering
                mock_extract.side_effect = mock_timestamps
                mock_filter.side_effect = [True, False, True]

                result = _scan_subdirectories_for_timestamps(tmp_path)
                assert len(result) == 2
                assert result == [mock_timestamps[0], mock_timestamps[2]]

    @patch("goesvfi.integrity_check.time_index_refactored._validate_directory_and_pattern")
    @patch("goesvfi.integrity_check.time_index_refactored._scan_files_for_timestamps")
    @patch("goesvfi.integrity_check.time_index_refactored._scan_subdirectories_for_timestamps")
    def test_scan_directory_for_timestamps(self, mock_scan_subdirs, mock_scan_files, mock_validate) -> None:
        """Test the scan_directory_for_timestamps function."""
        # Test with invalid directory or pattern
        mock_validate.return_value = (False, None)

        result = scan_directory_for_timestamps(Path("/tmp"), "UNKNOWN_PATTERN")
        assert len(result) == 0

        # Test with valid directory and pattern, files have timestamps
        mock_validate.return_value = (True, unittest.mock.Mock())
        mock_timestamps = [
            datetime(2023, 6, 15, 12, 0, 0),
            datetime(2023, 6, 15, 12, 30, 0),
            datetime(2023, 6, 15, 13, 0, 0),
        ]
        mock_scan_files.return_value = mock_timestamps

        result = scan_directory_for_timestamps(Path("/tmp"), "GOES_16")
        assert result == sorted(mock_timestamps)
        mock_scan_subdirs.assert_not_called()  # Shouldn't call scan_subdirectories if files have timestamps

        # Test with valid directory and pattern, no files have timestamps
        mock_scan_files.return_value = []
        mock_scan_subdirs.return_value = mock_timestamps

        result = scan_directory_for_timestamps(Path("/tmp"), "GOES_16")
        assert result == sorted(mock_timestamps)
        mock_scan_subdirs.assert_called_once()


class TestToS3Key(unittest.TestCase):
    """Test cases for the to_s3_key function and its helpers."""

    def test_validate_product_type_and_band(self) -> None:
        """Test the _validate_product_type_and_band helper function."""
        # Test with valid product_type and band
        _validate_product_type_and_band("RadF", 13)  # Should not raise

        # Test with invalid product_type
        with pytest.raises(ValueError):
            _validate_product_type_and_band("InvalidType", 13)

        # Test with invalid band (too low)
        with pytest.raises(ValueError):
            _validate_product_type_and_band("RadF", 0)

        # Test with invalid band (too high)
        with pytest.raises(ValueError):
            _validate_product_type_and_band("RadF", 17)

    def test_find_nearest_valid_scan_minute(self) -> None:
        """Test the _find_nearest_valid_scan_minute helper function."""
        # Test exact match
        assert _find_nearest_valid_scan_minute(15, [0, 15, 30, 45]) == 15

        # Test rounding down
        assert _find_nearest_valid_scan_minute(14, [0, 15, 30, 45]) == 0
        assert _find_nearest_valid_scan_minute(29, [0, 15, 30, 45]) == 15

        # Test with empty scan_minutes (should return original_minute)
        assert _find_nearest_valid_scan_minute(14, []) == 14

        # Test with None scan_minutes (should return original_minute)
        assert _find_nearest_valid_scan_minute(14, None) == 14

    @patch("goesvfi.integrity_check.time_index_refactored._detect_test_environment")
    @patch("goesvfi.integrity_check.time_index_refactored.date_utils.date_to_doy")
    def test_to_s3_key(self, mock_date_to_doy, mock_detect_env) -> None:
        """Test the to_s3_key function."""
        # Setup
        ts = datetime(2023, 6, 15, 12, 30, 0)
        satellite = "GOES_16"
        mock_date_to_doy.return_value = 166  # June 15 is day 166 of 2023
        mock_detect_env.return_value = (False, False, False)  # Not in test env

        # Test with default parameters (RadC, band 13)
        with (
            patch(
                "goesvfi.integrity_check.time_index_refactored._find_nearest_valid_scan_minute",
                return_value=30,
            ) as mock_find,
            patch("goesvfi.integrity_check.time_index_refactored._get_s3_filename_pattern") as mock_pattern,
        ):
            mock_pattern.return_value = "test_pattern.nc"

            result = to_s3_key(ts, satellite)

            # Verify the function calls
            mock_find.assert_called_once()
            mock_pattern.assert_called_once()

            # Verify the result
            assert result == "ABI-L1b-RadC/2023/166/12/test_pattern.nc"

        # Test with custom parameters (RadF, band 2)
        with (
            patch(
                "goesvfi.integrity_check.time_index_refactored._find_nearest_valid_scan_minute",
                return_value=30,
            ) as mock_find,
            patch("goesvfi.integrity_check.time_index_refactored._get_s3_filename_pattern") as mock_pattern,
        ):
            mock_pattern.return_value = "test_pattern.nc"

            result = to_s3_key(ts, satellite, product_type="RadF", band=2)

            # Verify the function calls
            mock_find.assert_called_once()
            mock_pattern.assert_called_once()

            # Verify the result
            assert result == "ABI-L1b-RadF/2023/166/12/test_pattern.nc"

        # Test with exact_match=True
        with (
            patch(
                "goesvfi.integrity_check.time_index_refactored._find_nearest_valid_scan_minute",
                return_value=30,
            ) as mock_find,
            patch("goesvfi.integrity_check.time_index_refactored._get_s3_filename_pattern") as mock_pattern,
        ):
            mock_pattern.return_value = "test_pattern.nc"

            result = to_s3_key(ts, satellite, exact_match=True)

            # Verify the result
            assert result == "ABI-L1b-RadC/2023/166/12/test_pattern.nc"

        # Test with invalid satellite
        with pytest.raises(ValueError):
            to_s3_key(ts, "INVALID_SATELLITE")


if __name__ == "__main__":
    unittest.main()
