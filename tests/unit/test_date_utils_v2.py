"""
Optimized tests for date_utils module with 100% coverage maintained.

This version maintains ALL original test methods while optimizing performance.
"""

import datetime
import pathlib

import pytest

from goesvfi.utils.date_utils import (
    date_to_doy,
    doy_to_date,
    format_satellite_path,
    get_all_date_formats,
    parse_satellite_path,
)


class TestDateToDoyV2:
    """Optimized tests for date_to_doy function maintaining all original tests."""

    def test_start_of_year(self) -> None:  # noqa: PLR6301
        """Test conversion for January 1st."""
        date = datetime.date(2023, 1, 1)
        doy = date_to_doy(date)
        assert doy == 1

    def test_end_of_year(self) -> None:  # noqa: PLR6301
        """Test conversion for December 31st in a non-leap year."""
        date = datetime.date(2023, 12, 31)
        doy = date_to_doy(date)
        assert doy == 365

    def test_leap_year(self) -> None:  # noqa: PLR6301
        """Test conversion for December 31st in a leap year."""
        date = datetime.date(2024, 12, 31)
        doy = date_to_doy(date)
        assert doy == 366

    def test_date_to_doy_additional_cases(self) -> None:  # noqa: PLR6301
        """Test additional date_to_doy cases for better coverage."""
        test_cases = [
            (datetime.date(2023, 2, 28), 59, "last day of Feb non-leap"),
            (datetime.date(2024, 2, 29), 60, "leap day"),
            (datetime.date(2023, 7, 4), 185, "mid-year"),
            (datetime.date(2023, 10, 1), 274, "start of Q4"),
        ]

        for date, expected_doy, description in test_cases:
            doy = date_to_doy(date)
            assert doy == expected_doy, f"Failed for {description}: {date}"


class TestDoyToDateV2:
    """Optimized tests for doy_to_date function maintaining all original tests."""

    def test_start_of_year(self) -> None:  # noqa: PLR6301
        """Test conversion for day 1."""
        date = doy_to_date(2023, 1)
        assert date == datetime.date(2023, 1, 1)

    def test_end_of_year(self) -> None:  # noqa: PLR6301
        """Test conversion for day 365 in a non-leap year."""
        date = doy_to_date(2023, 365)
        assert date == datetime.date(2023, 12, 31)

    def test_leap_year(self) -> None:  # noqa: PLR6301
        """Test conversion for day 366 in a leap year."""
        date = doy_to_date(2024, 366)
        assert date == datetime.date(2024, 12, 31)

    def test_invalid_doy_too_small(self) -> None:  # noqa: PLR6301
        """Test validation for day of year < 1."""
        with pytest.raises(ValueError, match="Day of year must be between 1 and 366, got 0"):
            doy_to_date(2023, 0)

    def test_invalid_doy_too_large(self) -> None:  # noqa: PLR6301
        """Test validation for day of year > 366."""
        with pytest.raises(ValueError, match="Day of year must be between 1 and 366, got 367"):
            doy_to_date(2023, 367)

    def test_invalid_doy_leap_year(self) -> None:  # noqa: PLR6301
        """Test validation for day 366 in a non-leap year."""
        with pytest.raises(ValueError, match="Day of year 366 is invalid for non-leap year 2023"):
            doy_to_date(2023, 366)

    def test_doy_to_date_additional_cases(self) -> None:  # noqa: PLR6301
        """Test additional doy_to_date cases."""
        test_cases = [
            (2023, 59, datetime.date(2023, 2, 28)),
            (2024, 60, datetime.date(2024, 2, 29)),
            (2023, 185, datetime.date(2023, 7, 4)),
        ]

        for year, doy, expected_date in test_cases:
            date = doy_to_date(year, doy)
            assert date == expected_date


class TestParseSatellitePathV2:
    """Optimized tests for parse_satellite_path function with all parameterized tests."""

    @pytest.mark.parametrize(
        "path_str,expected_date",
        [
            # Satellite filename pattern: goes18_YYYYMMDD_HHMMSS_bandXX.png
            ("goes18_20231027_120000_band13.png", datetime.date(2023, 10, 27)),
            ("goes19_20240215_000000_band.jpeg", datetime.date(2024, 2, 15)),
            # Year/DOY pattern: YYYY/DDD
            ("2023/123", datetime.date(2023, 5, 3)),
            ("/data/2024/366", datetime.date(2024, 12, 31)),
            # Compact DOY pattern: YYYYDDD
            ("2023123", datetime.date(2023, 5, 3)),
            ("path/to/2024366/file", datetime.date(2024, 12, 31)),
            # YYYY-MM-DD pattern
            ("2023-10-27", datetime.date(2023, 10, 27)),
            ("/path/to/2024-02-29/file.txt", datetime.date(2024, 2, 29)),
            # YYYY_MM_DD pattern
            ("2023_10_27", datetime.date(2023, 10, 27)),
            ("/data/2024_02_29/image.png", datetime.date(2024, 2, 29)),
            # Timestamp pattern: YYYYMMDDTHHMMSSZ
            ("20231027T120000Z", datetime.date(2023, 10, 27)),
            ("/path/20240229T235959Z.nc", datetime.date(2024, 2, 29)),
            # YYYYMMDD pattern (most general)
            ("20231027", datetime.date(2023, 10, 27)),
            ("/path/to/20240229.txt", datetime.date(2024, 2, 29)),
        ],
    )
    def test_parse_satellite_path_patterns(self, path_str: str, expected_date: str) -> None:  # noqa: PLR6301
        """Test parsing various date patterns from paths."""
        path = pathlib.Path(path_str)
        parsed_date = parse_satellite_path(path)
        assert parsed_date == expected_date

    def test_parse_satellite_path_no_match(self) -> None:  # noqa: PLR6301
        """Test parse_satellite_path when no date pattern matches."""
        no_date_paths = [
            "random_file.txt",
            "/path/to/nowhere",
            "12345",
            "202",
            "",
        ]

        for path_str in no_date_paths:
            path = pathlib.Path(path_str)
            result = parse_satellite_path(path)
            assert result is None

    def test_parse_satellite_path_edge_cases(self) -> None:  # noqa: PLR6301
        """Test edge cases for parse_satellite_path."""
        # Test with string input
        date = parse_satellite_path("2023-10-15")
        assert date == datetime.date(2023, 10, 15)

        # Test with complex nested paths
        complex_path = "/very/long/path/with/many/dirs/2023/123/goes18_data.nc"
        date = parse_satellite_path(complex_path)
        assert date == datetime.date(2023, 5, 3)


class TestFormatSatellitePathV2:
    """Optimized tests for format_satellite_path function."""

    def test_format_satellite_path(self) -> None:  # noqa: PLR6301
        """Test basic format_satellite_path functionality."""
        date = datetime.date(2023, 10, 27)
        
        # Test default format (calendar)
        result = format_satellite_path(date)
        assert isinstance(result, str)
        assert result == "2023-10-27"
        
        # Test doy format
        result_doy = format_satellite_path(date, "doy")
        assert result_doy == "2023/300"  # Day 300

    def test_format_satellite_path_default_values(self) -> None:  # noqa: PLR6301
        """Test format_satellite_path with default parameters."""
        date = datetime.date(2023, 6, 15)
        
        # Test with invalid format_type
        with pytest.raises(ValueError, match="Invalid format_type: invalid"):
            format_satellite_path(date, "invalid")
            
        # Test compact_doy format
        result = format_satellite_path(date, "compact_doy")
        assert result == "2023166"  # Day 166

    def test_format_satellite_path_string_base(self) -> None:  # noqa: PLR6301
        """Test format_satellite_path with different format types."""
        date = datetime.date(2023, 7, 4)
        
        # Test all format types
        calendar_result = format_satellite_path(date, "calendar")
        assert calendar_result == "2023-07-04"
        
        doy_result = format_satellite_path(date, "doy")
        assert doy_result == "2023/185"  # Day 185
        
        compact_result = format_satellite_path(date, "compact_doy")
        assert compact_result == "2023185"

    def test_format_satellite_path_leap_year(self) -> None:  # noqa: PLR6301
        """Test format_satellite_path with leap year dates."""
        date = datetime.date(2024, 2, 29)
        
        # Test leap year date formatting
        calendar_result = format_satellite_path(date)
        assert calendar_result == "2024-02-29"
        
        doy_result = format_satellite_path(date, "doy")
        assert doy_result == "2024/060"  # Day 60 in leap year
        
        compact_result = format_satellite_path(date, "compact_doy")
        assert compact_result == "2024060"

    def test_format_satellite_path_end_of_year(self) -> None:  # noqa: PLR6301
        """Test format_satellite_path with end of year date."""
        date = datetime.date(2023, 12, 31)
        
        # Test end of year date formatting
        calendar_result = format_satellite_path(date)
        assert calendar_result == "2023-12-31"
        
        doy_result = format_satellite_path(date, "doy")
        assert doy_result == "2023/365"  # Day 365
        
        compact_result = format_satellite_path(date, "compact_doy")
        assert compact_result == "2023365"


class TestGetAllDateFormatsV2:
    """Optimized tests for get_all_date_formats function."""

    def test_get_all_date_formats(self) -> None:  # noqa: PLR6301
        """Test get_all_date_formats returns expected formats."""
        date = datetime.date(2023, 10, 27)
        formats = get_all_date_formats(date)

        # Verify it returns a tuple of 3 strings
        assert isinstance(formats, tuple)
        assert len(formats) == 3
        
        calendar_format, doy_format, compact_doy_format = formats
        
        # Verify the expected format values
        assert calendar_format == "2023-10-27"
        assert doy_format == "2023/300"  # Day 300
        assert compact_doy_format == "2023300"

    def test_get_all_date_formats_usage(self) -> None:  # noqa: PLR6301
        """Test get_all_date_formats with different dates."""
        # Test with different dates
        test_dates = [
            datetime.date(2023, 1, 1),   # Start of year
            datetime.date(2023, 12, 31), # End of year
            datetime.date(2024, 2, 29),  # Leap year
        ]
        
        for test_date in test_dates:
            formats = get_all_date_formats(test_date)
            
            # Verify all formats are strings
            assert all(isinstance(fmt, str) for fmt in formats)
            
            # Verify they contain the year
            year_str = str(test_date.year)
            assert all(year_str in fmt for fmt in formats)
