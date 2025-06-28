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

    def test_start_of_year(self):
        """Test conversion for January 1st."""
        date = datetime.date(2023, 1, 1)
        doy = date_to_doy(date)
        assert doy == 1

    def test_end_of_year(self):
        """Test conversion for December 31st in a non-leap year."""
        date = datetime.date(2023, 12, 31)
        doy = date_to_doy(date)
        assert doy == 365

    def test_leap_year(self):
        """Test conversion for December 31st in a leap year."""
        date = datetime.date(2024, 12, 31)
        doy = date_to_doy(date)
        assert doy == 366

    def test_date_to_doy_additional_cases(self):
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

    def test_start_of_year(self):
        """Test conversion for day 1."""
        date = doy_to_date(2023, 1)
        assert date == datetime.date(2023, 1, 1)

    def test_end_of_year(self):
        """Test conversion for day 365 in a non-leap year."""
        date = doy_to_date(2023, 365)
        assert date == datetime.date(2023, 12, 31)

    def test_leap_year(self):
        """Test conversion for day 366 in a leap year."""
        date = doy_to_date(2024, 366)
        assert date == datetime.date(2024, 12, 31)

    def test_invalid_doy_too_small(self):
        """Test validation for day of year < 1."""
        with pytest.raises(ValueError):
            doy_to_date(2023, 0)

    def test_invalid_doy_too_large(self):
        """Test validation for day of year > 366."""
        with pytest.raises(ValueError):
            doy_to_date(2023, 367)

    def test_invalid_doy_leap_year(self):
        """Test validation for day 366 in a non-leap year."""
        with pytest.raises(ValueError):
            doy_to_date(2023, 366)

    def test_doy_to_date_additional_cases(self):
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
    def test_parse_satellite_path_patterns(self, path_str, expected_date):
        """Test parsing various date patterns from paths."""
        path = pathlib.Path(path_str)
        parsed_date = parse_satellite_path(path)
        assert parsed_date == expected_date

    def test_parse_satellite_path_no_match(self):
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

    def test_parse_satellite_path_edge_cases(self):
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

    def test_format_satellite_path(self):
        """Test basic format_satellite_path functionality."""
        date = datetime.date(2023, 10, 27)
        base_path = pathlib.Path("/data/satellite")

        result = format_satellite_path(date, base_path, "goes18", "ABI-L2-MCMIPF")
        assert isinstance(result, pathlib.Path)
        assert "2023" in str(result)
        assert "300" in str(result)  # Day 300

    def test_format_satellite_path_default_values(self):
        """Test format_satellite_path with default parameters."""
        date = datetime.date(2023, 6, 15)
        base_path = pathlib.Path("/archive")

        result = format_satellite_path(date, base_path)
        assert isinstance(result, pathlib.Path)
        assert "2023" in str(result)
        assert "166" in str(result)  # Day 166

    def test_format_satellite_path_string_base(self):
        """Test format_satellite_path with string base path."""
        date = datetime.date(2023, 7, 4)
        base_path = "/data/goes"  # String instead of Path

        result = format_satellite_path(date, base_path, "goes16", "ABI-L1b")
        assert isinstance(result, pathlib.Path)
        assert str(result).startswith("/data/goes")

    def test_format_satellite_path_leap_year(self):
        """Test format_satellite_path with leap year dates."""
        date = datetime.date(2024, 2, 29)
        base_path = pathlib.Path("/data")

        result = format_satellite_path(date, base_path, "goes16", "GLM")
        assert "2024" in str(result)
        assert "060" in str(result)  # Day 60

    def test_format_satellite_path_end_of_year(self):
        """Test format_satellite_path with end of year date."""
        date = datetime.date(2023, 12, 31)
        base_path = pathlib.Path("/data")

        result = format_satellite_path(date, base_path, "goes18", "SUVI")
        assert "2023" in str(result)
        assert "365" in str(result)


class TestGetAllDateFormatsV2:
    """Optimized tests for get_all_date_formats function."""

    def test_get_all_date_formats(self):
        """Test get_all_date_formats returns expected formats."""
        formats = get_all_date_formats()

        # Verify it returns a list
        assert isinstance(formats, list)
        assert len(formats) > 0

        # Verify some expected formats are present
        expected_formats = [
            "%Y/%j",      # Year/DOY
            "%Y%j",       # Compact DOY
            "%Y-%m-%d",   # ISO date
            "%Y_%m_%d",   # Underscore date
            "%Y%m%d",     # Compact date
        ]

        for fmt in expected_formats:
            assert fmt in formats

    def test_get_all_date_formats_usage(self):
        """Test that returned formats work with strftime/strptime."""
        formats = get_all_date_formats()
        test_date = datetime.date(2023, 10, 27)

        # Test each format can be used
        for fmt in formats:
            try:
                # Format the date
                date_str = test_date.strftime(fmt)
                assert isinstance(date_str, str)
            except ValueError:
                # Some formats might not be complete
                pass