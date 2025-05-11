"""Tests for date_utils.py module."""

import datetime
import pathlib
from typing import Optional

import pytest

from goesvfi.utils.date_utils import (
    date_to_doy,
    doy_to_date,
    format_satellite_path,
    get_satellite_path_components,
    parse_satellite_path,
)


class TestDateToDoy:
    """Tests for date_to_doy function."""

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


class TestDoyToDate:
    """Tests for doy_to_date function."""

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


class TestParseSatellitePath:
    """Tests for parse_satellite_path function."""

    @pytest.mark.parametrize(
        "path_str,expected_date",
        [
            # Satellite filename pattern: goes18_20231027_120000_band13.png
            ("goes18_20231027_120000_band13.png", datetime.date(2023, 10, 27)),
            ("goes19_20240215_000000_band.jpeg", datetime.date(2024, 2, 15)),
            # Year/DOY pattern: 2023/123
            ("2023/123", datetime.date(2023, 5, 3)),
            ("/data/2024/366", datetime.date(2024, 12, 31)),
            # Compact DOY pattern: 2023123
            ("2023123", datetime.date(2023, 5, 3)),
            ("path/to/2024366/file", datetime.date(2024, 12, 31)),
            # YYYY-MM-DD pattern
            ("2023-10-27", datetime.date(2023, 10, 27)),
            ("/path/to/2024-02-29/file.txt", datetime.date(2024, 2, 29)),
            # YYYY_MM_DD pattern
            ("2023_10_27", datetime.date(2023, 10, 27)),
            ("/data/2024_02_29/image.png", datetime.date(2024, 2, 29)),
            # Timestamp pattern: 20231027T120000Z
            ("20231027T120000Z", datetime.date(2023, 10, 27)),
            ("/path/20240229T235959Z.nc", datetime.date(2024, 2, 29)),
            # YYYYMMDD pattern (most general)
            ("20231027", datetime.date(2023, 10, 27)),
            ("/path/to/20240229.txt", datetime.date(2024, 2, 29)),
        ],
    )
    def test_parse_various_formats(self, path_str: str, expected_date: datetime.date):
        """Test parsing various date formats from paths."""
        result = parse_satellite_path(path_str)
        assert result == expected_date

    @pytest.mark.parametrize(
        "path_str,expected_date",
        [
            # Test with Path objects
            (pathlib.Path("goes18_20231027_120000_band13.png"), datetime.date(2023, 10, 27)),
            (pathlib.Path("2023/123"), datetime.date(2023, 5, 3)),
            (pathlib.Path("2023-10-27"), datetime.date(2023, 10, 27)),
        ],
    )
    def test_parse_with_path_objects(self, path_str: pathlib.Path, expected_date: datetime.date):
        """Test parsing dates from pathlib.Path objects."""
        result = parse_satellite_path(path_str)
        assert result == expected_date

    @pytest.mark.parametrize(
        "path_str",
        [
            "no_date_here",
            "2023",  # Year only
            "10-27",  # Month-day only
            "123",  # DOY only
            "notadate",
            "20230230",  # Invalid date (February 30)
            "2023999",  # Invalid DOY
            "2023-13-01",  # Invalid month
            "2023-02-31",  # Invalid day for February
        ],
    )
    def test_parse_invalid_paths(self, path_str: str):
        """Test parsing invalid paths returns None."""
        result = parse_satellite_path(path_str)
        assert result is None

    def test_parsing_priority(self):
        """Test that more specific patterns are prioritized over general ones."""
        # This string has multiple valid date patterns:
        # - goes18_20231027_120000 (satellite pattern)
        # - 20231027 (YYYYMMDD pattern)
        path_str = "goes18_20231027_120000_band13.png"
        
        # This will use the satellite pattern parser first, which should correctly
        # extract the date as October 27, 2023
        result = parse_satellite_path(path_str)
        assert result == datetime.date(2023, 10, 27)


class TestFormatSatellitePath:
    """Tests for format_satellite_path function."""

    def test_calendar_format(self):
        """Test calendar date format (YYYY-MM-DD)."""
        date = datetime.date(2023, 10, 27)
        result = format_satellite_path(date, "calendar")
        assert result == "2023-10-27"

    def test_doy_format(self):
        """Test day of year format (YYYY/DDD)."""
        date = datetime.date(2023, 5, 3)  # Day 123 of 2023
        result = format_satellite_path(date, "doy")
        assert result == "2023/123"

    def test_compact_doy_format(self):
        """Test compact day of year format (YYYYDDD)."""
        date = datetime.date(2023, 5, 3)  # Day 123 of 2023
        result = format_satellite_path(date, "compact_doy")
        assert result == "2023123"

    def test_default_format(self):
        """Test default format is calendar."""
        date = datetime.date(2023, 10, 27)
        result = format_satellite_path(date)  # No format specified
        assert result == "2023-10-27"

    def test_invalid_format(self):
        """Test invalid format raises ValueError."""
        date = datetime.date(2023, 10, 27)
        with pytest.raises(ValueError):
            format_satellite_path(date, "invalid_format")


class TestGetSatellitePathComponents:
    """Tests for get_satellite_path_components function."""

    def test_components(self):
        """Test getting all path format components for a date."""
        date = datetime.date(2023, 5, 3)  # Day 123 of 2023
        calendar, doy, compact_doy = get_satellite_path_components(date)
        
        assert calendar == "2023-05-03"
        assert doy == "2023/123"
        assert compact_doy == "2023123"

    def test_components_leap_year(self):
        """Test getting components for a leap year date."""
        date = datetime.date(2024, 12, 31)  # Day 366 of 2024
        calendar, doy, compact_doy = get_satellite_path_components(date)
        
        assert calendar == "2024-12-31"
        assert doy == "2024/366"
        assert compact_doy == "2024366"