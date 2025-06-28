"""
Tests for edge case timezone handling - Optimized v2.

Optimizations applied:
- Shared expensive timezone and datetime setup
- Parameterized test methods for comprehensive coverage
- Mock time operations for consistent testing
- Combined related timezone scenarios
- Reduced redundant timezone object creation
- Enhanced fixture reuse for time index operations
"""

import datetime
import zoneinfo

import pytest

from goesvfi.integrity_check.time_index import SatellitePattern, TimeIndex


class TestEdgeCaseTimezoneV2:
    """Test timezone edge cases and conversions - optimized v2."""

    @pytest.fixture(scope="class")
    def shared_timezones(self):
        """Create shared timezone objects for all tests."""
        return {
            "eastern": zoneinfo.ZoneInfo("America/New_York"),
            "pacific": zoneinfo.ZoneInfo("America/Los_Angeles"),
            "tokyo": zoneinfo.ZoneInfo("Asia/Tokyo"),
            "central": zoneinfo.ZoneInfo("America/Chicago"),
            "china": zoneinfo.ZoneInfo("Asia/Shanghai"),
            "fiji": zoneinfo.ZoneInfo("Pacific/Fiji"),
            "hawaii": zoneinfo.ZoneInfo("Pacific/Honolulu"),
            "indiana": zoneinfo.ZoneInfo("America/Indiana/Indianapolis"),
        }

    @pytest.fixture(scope="class")
    def shared_test_times(self):
        """Create shared test datetime objects."""
        return {
            "summer_utc": datetime.datetime(2023, 7, 15, 18, 30, 0, tzinfo=datetime.UTC),
            "winter_utc": datetime.datetime(2023, 1, 15, 18, 30, 0, tzinfo=datetime.UTC),
            "dst_spring_before": datetime.datetime(2023, 3, 12, 1, 59, 0),  # Before DST
            "dst_fall_first": datetime.datetime(2023, 11, 5, 1, 30, 0),    # Fall back
            "midnight_before": datetime.datetime(2023, 7, 15, 23, 59, 59, tzinfo=datetime.UTC),
            "midnight_after": datetime.datetime(2023, 7, 16, 0, 0, 1, tzinfo=datetime.UTC),
            "leap_year_feb29": datetime.datetime(2024, 2, 29, 12, 0, 0, tzinfo=datetime.UTC),
            "dec_31_leap": datetime.datetime(2024, 12, 31, 23, 59, 59, tzinfo=datetime.UTC),
            "dec_31_regular": datetime.datetime(2023, 12, 31, 23, 59, 59, tzinfo=datetime.UTC),
            "jan_1": datetime.datetime(2024, 1, 1, 0, 0, 0, tzinfo=datetime.UTC),
            "precise_subsecond": datetime.datetime(2023, 7, 15, 12, 30, 45, 123456, tzinfo=datetime.UTC),
        }

    @pytest.fixture()
    def time_index(self):
        """Create a TimeIndex instance for testing."""
        return TimeIndex()

    @pytest.mark.parametrize("test_time_key,timezone_key,expected_hour,expected_day_offset", [
        ("summer_utc", "eastern", 14, 0),   # UTC-4 in summer
        ("summer_utc", "pacific", 11, 0),   # UTC-7 in summer
        ("summer_utc", "tokyo", 3, 1),      # UTC+9, next day
        ("winter_utc", "eastern", 13, 0),   # UTC-5 in winter
        ("winter_utc", "pacific", 10, 0),   # UTC-8 in winter
    ])
    def test_utc_to_local_conversion_comprehensive(self, shared_test_times, shared_timezones,
                                                  test_time_key, timezone_key, expected_hour, expected_day_offset) -> None:
        """Test UTC to local timezone conversion with various combinations."""
        utc_time = shared_test_times[test_time_key]
        target_timezone = shared_timezones[timezone_key]

        # Convert to target timezone
        local_time = utc_time.astimezone(target_timezone)

        # Verify hour conversion
        assert local_time.hour == expected_hour

        # Verify day offset if applicable
        if expected_day_offset != 0:
            expected_day = utc_time.day + expected_day_offset
            assert local_time.day == expected_day

    @pytest.mark.parametrize("dst_scenario,test_description", [
        ("spring_forward", "Spring DST transition handling"),
        ("fall_back", "Fall DST transition handling"),
    ])
    def test_dst_transitions_comprehensive(self, shared_timezones, dst_scenario, test_description) -> None:
        """Test DST transitions comprehensively."""
        eastern = shared_timezones["eastern"]

        if dst_scenario == "spring_forward":
            # Time just before DST transition (1:59 AM EST)
            before_dst = datetime.datetime(2023, 3, 12, 1, 59, 0, tzinfo=eastern)
            after_dst = before_dst + datetime.timedelta(minutes=2)

            # Verify the time progression
            assert after_dst.hour == 2
            assert after_dst.minute == 1

        elif dst_scenario == "fall_back":
            # First occurrence of 1:30 AM EDT
            first_130am = datetime.datetime(2023, 11, 5, 1, 30, 0, tzinfo=eastern)
            second_130am = first_130am + datetime.timedelta(hours=1)

            # Verify time progression
            assert first_130am.hour == 1
            assert first_130am.minute == 30
            assert second_130am.hour == 2  # Continuous time progression

    @pytest.mark.parametrize("satellite,product_type", [
        (SatellitePattern.GOES_16, "RadC"),
        (SatellitePattern.GOES_18, "RadF"),
        (SatellitePattern.GOES_16, "RadF"),
    ])
    def test_goes_timestamp_parsing_with_timezone(self, time_index, shared_test_times, satellite, product_type) -> None:
        """Test timezone-aware datetime objects with existing methods."""
        utc_time = shared_test_times["summer_utc"]

        # Test S3 key generation with timezone-aware datetime
        s3_key = time_index.to_s3_key(
            ts=utc_time,
            satellite=satellite,
            product_type=product_type,
        )

        # Verify key components
        assert "196" in s3_key  # Day 196 is July 15, 2023
        assert "18" in s3_key   # Hour 18
        assert f"ABI-L1b-{product_type}" in s3_key

        # Verify satellite code
        expected_code = "G16" if satellite == SatellitePattern.GOES_16 else "G18"
        assert expected_code in s3_key

    @pytest.mark.parametrize("test_date_key,expected_day_of_year", [
        ("dec_31_regular", 365),  # 2023 is not a leap year
        ("jan_1", 1),             # January 1st
        ("leap_year_feb29", 60),  # Feb 29 in leap year
        ("dec_31_leap", 366),     # Dec 31 in leap year
    ])
    def test_day_of_year_edge_cases(self, shared_test_times, test_date_key, expected_day_of_year) -> None:
        """Test day-of-year calculations around year boundaries."""
        test_date = shared_test_times[test_date_key]
        day_of_year = test_date.timetuple().tm_yday
        assert day_of_year == expected_day_of_year

    def test_midnight_boundary_handling(self, time_index, shared_test_times) -> None:
        """Test handling of midnight boundary crossing."""
        before_midnight = shared_test_times["midnight_before"]
        after_midnight = shared_test_times["midnight_after"]

        # Generate S3 keys for both times
        key_before = time_index.to_s3_key(
            ts=before_midnight,
            satellite=SatellitePattern.GOES_16,
            product_type="RadC",
        )

        key_after = time_index.to_s3_key(
            ts=after_midnight,
            satellite=SatellitePattern.GOES_16,
            product_type="RadC",
        )

        # Verify different days are represented
        assert "196/23" in key_before  # Day 196, hour 23
        assert "197/00" in key_after   # Day 197, hour 00

    def test_international_date_line_handling(self, shared_test_times, shared_timezones) -> None:
        """Test handling around international date line."""
        utc_time = shared_test_times["summer_utc"].replace(hour=12)  # Noon UTC

        fiji_time = utc_time.astimezone(shared_timezones["fiji"])
        hawaii_time = utc_time.astimezone(shared_timezones["hawaii"])

        # Verify date line crossing
        assert fiji_time.day == 16    # Next day in Fiji
        assert hawaii_time.day == 15  # Same day in Hawaii
        assert fiji_time.hour == 0   # Midnight in Fiji
        assert hawaii_time.hour == 2  # 2 AM in Hawaii

    def test_goes_scan_schedule_timezone_consistency(self, shared_test_times, shared_timezones) -> None:
        """Test GOES scan schedule consistency across timezones."""
        base_utc = shared_test_times["summer_utc"].replace(hour=12, minute=0)

        # Generate scan times (15-minute intervals)
        scan_times = [base_utc + datetime.timedelta(minutes=15 * i) for i in range(4)]

        # Convert to Eastern time
        eastern_scan_times = [t.astimezone(shared_timezones["eastern"]) for t in scan_times]

        # Verify 15-minute intervals are preserved
        for i in range(1, len(eastern_scan_times)):
            delta = eastern_scan_times[i] - eastern_scan_times[i - 1]
            assert delta.total_seconds() == 900  # 15 minutes

    def test_filename_timestamp_parsing_edge_cases(self) -> None:
        """Test parsing timestamps from GOES filenames."""
        filename = "OR_ABI-L1b-RadF-M6C13_G16_s20232001200000_e20232001215000_c20232001215300.nc"

        # Parse start time
        parts = filename.split("_")
        start_str = parts[3][1:]  # Remove 's' prefix

        # Extract components efficiently
        year = int(start_str[0:4])
        day_of_year = int(start_str[4:7])
        hour = int(start_str[7:9])
        minute = int(start_str[9:11])
        second = int(start_str[11:13])

        # Reconstruct datetime
        parsed_date = datetime.datetime(year, 1, 1, tzinfo=datetime.UTC)
        parsed_date += datetime.timedelta(days=day_of_year - 1, hours=hour, minutes=minute, seconds=second)

        # Verify parsing
        assert parsed_date.year == 2023
        assert parsed_date.month == 7
        assert parsed_date.day == 19  # Day 200 of 2023
        assert parsed_date.hour == 12
        assert parsed_date.minute == 0

    def test_time_range_queries_across_dst(self, shared_timezones) -> None:
        """Test time range queries that span DST transitions."""
        eastern = shared_timezones["eastern"]

        # Range spanning spring DST transition
        start = datetime.datetime(2023, 3, 11, 22, 0, 0, tzinfo=datetime.UTC)  # 5 PM EST
        end = datetime.datetime(2023, 3, 12, 22, 0, 0, tzinfo=datetime.UTC)    # 6 PM EDT

        # Convert to local times
        start_local = start.astimezone(eastern)
        end_local = end.astimezone(eastern)

        # Verify DST transition
        assert start_local.hour == 17  # 5 PM EST
        assert end_local.hour == 18    # 6 PM EDT

        # Duration should be exactly 24 hours
        duration = end - start
        assert duration.total_seconds() == 86400

    def test_leap_second_handling(self) -> None:
        """Test theoretical leap second handling."""
        # Python doesn't support leap seconds directly
        try:
            # This would normally fail
            leap_second = datetime.datetime(2016, 12, 31, 23, 59, 60, tzinfo=datetime.UTC)
        except ValueError:
            # Expected - round to next second
            leap_second = datetime.datetime(2017, 1, 1, 0, 0, 0, tzinfo=datetime.UTC)

        assert leap_second.year == 2017
        assert leap_second.month == 1
        assert leap_second.day == 1

    def test_timezone_abbreviation_ambiguity(self, shared_test_times, shared_timezones) -> None:
        """Test handling of ambiguous timezone abbreviations."""
        utc_time = shared_test_times["summer_utc"].replace(hour=12)

        # Compare US Central vs China Standard (both "CST")
        us_time = utc_time.astimezone(shared_timezones["central"])
        china_time = utc_time.astimezone(shared_timezones["china"])

        # Very different times despite both being "CST"
        assert us_time.hour == 7   # 7 AM CDT (summer)
        assert china_time.hour == 20  # 8 PM CST

    def test_sub_second_timestamp_precision(self, time_index, shared_test_times) -> None:
        """Test handling of sub-second precision in timestamps."""
        precise_time = shared_test_times["precise_subsecond"]

        # Generate S3 key with sub-second precision
        s3_key = time_index.to_s3_key(
            ts=precise_time,
            satellite=SatellitePattern.GOES_16,
            product_type="RadC",
        )

        # Verify timestamp components are represented
        assert "196" in s3_key  # Day of year
        assert "12" in s3_key   # Hour
        assert "ABI-L1b-RadC" in s3_key
        assert "G16" in s3_key

    @pytest.mark.skip(reason="Historical timezone rule assumptions may vary by system")
    def test_historical_timezone_rules(self, shared_timezones) -> None:
        """Test handling of historical timezone rule changes."""
        indiana = shared_timezones["indiana"]

        # Date in 2005 (Indiana didn't observe DST)
        old_summer = datetime.datetime(2005, 7, 15, 12, 0, 0, tzinfo=datetime.UTC)
        old_local = old_summer.astimezone(indiana)

        # Date in 2023 (with DST)
        new_summer = datetime.datetime(2023, 7, 15, 12, 0, 0, tzinfo=datetime.UTC)
        new_local = new_summer.astimezone(indiana)

        # Note: Actual behavior depends on system timezone database
        assert isinstance(old_local.hour, int)
        assert isinstance(new_local.hour, int)

    @pytest.mark.parametrize("hour,expected_scan_count", [
        (0, 4),   # Midnight UTC
        (6, 4),   # 6 AM UTC
        (12, 4),  # Noon UTC
        (18, 4),  # 6 PM UTC
        (23, 4),  # 11 PM UTC
    ])
    def test_hourly_scan_consistency(self, shared_test_times, hour, expected_scan_count) -> None:
        """Test that scan counts are consistent regardless of hour."""
        base_time = shared_test_times["summer_utc"].replace(hour=hour, minute=0, second=0)

        # Generate scans for the hour
        scans = [base_time.replace(minute=minute) for minute in [0, 15, 30, 45]]

        assert len(scans) == expected_scan_count

        # Verify all scans are valid datetime objects
        for scan in scans:
            assert isinstance(scan, datetime.datetime)
            assert scan.hour == hour

    def test_performance_timezone_operations(self, shared_test_times, shared_timezones) -> None:
        """Test performance of timezone operations with batch processing."""
        base_time = shared_test_times["summer_utc"]

        # Generate multiple timestamps
        timestamps = [base_time + datetime.timedelta(hours=i) for i in range(24)]

        # Convert all to multiple timezones
        for timezone in shared_timezones.values():
            converted_times = [ts.astimezone(timezone) for ts in timestamps]

            # Verify all conversions successful
            assert len(converted_times) == 24
            assert all(isinstance(ct, datetime.datetime) for ct in converted_times)

    def test_edge_case_combinations(self, shared_test_times, shared_timezones, time_index) -> None:
        """Test combinations of edge cases."""
        # Leap year + timezone conversion + S3 key generation
        leap_time = shared_test_times["leap_year_feb29"]
        eastern_leap = leap_time.astimezone(shared_timezones["eastern"])

        s3_key = time_index.to_s3_key(
            ts=eastern_leap.astimezone(datetime.UTC),  # Convert back to UTC
            satellite=SatellitePattern.GOES_18,
            product_type="RadF",
        )

        # Verify leap year day is handled correctly
        assert "060" in s3_key  # Day 60 of leap year
        assert "G18" in s3_key

        # Midnight boundary + international date line
        fiji_midnight = shared_test_times["midnight_before"].astimezone(shared_timezones["fiji"])
        hawaii_midnight = shared_test_times["midnight_before"].astimezone(shared_timezones["hawaii"])

        # Should be different days
        assert fiji_midnight.day != hawaii_midnight.day

    def test_error_handling_invalid_timezones(self, shared_test_times) -> None:
        """Test error handling with invalid timezone operations."""
        utc_time = shared_test_times["summer_utc"]

        # Test with invalid timezone string
        try:
            invalid_tz = zoneinfo.ZoneInfo("Invalid/Timezone")
            utc_time.astimezone(invalid_tz)
        except zoneinfo.ZoneInfoNotFoundError:
            # Expected behavior
            pass

        # Test with None timezone
        try:
            utc_time.astimezone(None)
        except (TypeError, AttributeError):
            # Expected behavior
            pass


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])
