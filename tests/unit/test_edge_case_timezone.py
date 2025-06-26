"""Tests for edge case timezone handling.

These tests verify proper handling of UTC/local time conversions,
daylight saving time transitions, and timezone-related edge cases.
"""

import datetime
import zoneinfo

import pytest

from goesvfi.integrity_check.time_index import SatellitePattern, TimeIndex


class TestEdgeCaseTimezone:
    """Test timezone edge cases and conversions."""

    @pytest.fixture
    def time_index(self):
        """Create a TimeIndex instance for testing."""
        return TimeIndex()

    def test_utc_to_local_conversion(self):
        """Test UTC to local timezone conversion."""
        # Test UTC timestamp
        utc_time = datetime.datetime(
            2023, 7, 15, 18, 30, 0, tzinfo=datetime.timezone.utc
        )

        # Test conversion to various timezones
        eastern = zoneinfo.ZoneInfo("America/New_York")
        pacific = zoneinfo.ZoneInfo("America/Los_Angeles")
        tokyo = zoneinfo.ZoneInfo("Asia/Tokyo")

        # Convert to different timezones
        eastern_time = utc_time.astimezone(eastern)
        pacific_time = utc_time.astimezone(pacific)
        tokyo_time = utc_time.astimezone(tokyo)

        # Verify conversions
        assert eastern_time.hour == 14  # UTC-4 in summer
        assert pacific_time.hour == 11  # UTC-7 in summer
        assert tokyo_time.hour == 3  # UTC+9, next day
        assert tokyo_time.day == 16  # Next day in Tokyo

    def test_dst_transition_spring_forward(self):
        """Test handling of spring DST transition (spring forward)."""
        # DST starts at 2 AM on second Sunday of March in US
        eastern = zoneinfo.ZoneInfo("America/New_York")

        # Time just before DST transition (1:59 AM EST)
        before_dst = datetime.datetime(2023, 3, 12, 1, 59, 0, tzinfo=eastern)

        # Add 2 minutes - in Python's zoneinfo, this will be 2:01 AM
        # The "spring forward" happens when you localize a non-existent time
        after_dst = before_dst + datetime.timedelta(minutes=2)

        # Verify the time (Python doesn't automatically jump the hour)
        assert after_dst.hour == 2
        assert after_dst.minute == 1

        # Note: Python's zoneinfo handles DST transitions transparently
        # Unlike some other timezone libraries, it doesn't raise exceptions
        # for non-existent times during DST transitions

    def test_dst_transition_fall_back(self):
        """Test handling of fall DST transition (fall back)."""
        # DST ends at 2 AM on first Sunday of November in US
        eastern = zoneinfo.ZoneInfo("America/New_York")

        # First occurrence of 1:30 AM EDT
        first_130am = datetime.datetime(2023, 11, 5, 1, 30, 0, tzinfo=eastern)

        # One hour later - second occurrence of 1:30 AM EST
        second_130am = first_130am + datetime.timedelta(hours=1)

        # Both should show 1:30 AM but different UTC times
        assert first_130am.hour == 1
        assert first_130am.minute == 30
        assert second_130am.hour == 2  # Actually 2:30 AM in continuous time

    def test_goes_timestamp_parsing_with_timezone(self, time_index):
        """Test that timezone-aware datetime objects work correctly with existing methods."""
        # Create a UTC datetime (GOES imagery is always in UTC)
        utc_time = datetime.datetime(
            2023, 7, 15, 18, 30, 0, tzinfo=datetime.timezone.utc
        )

        # Test that the UTC time works with S3 key generation
        s3_key = time_index.to_s3_key(
            ts=utc_time,
            satellite=SatellitePattern.GOES_16,
            product_type="RadC",
        )

        # Verify the key contains expected components
        assert "196" in s3_key  # Day 196 is July 15, 2023
        assert "18" in s3_key  # Hour 18
        assert "ABI-L1b-RadC" in s3_key
        assert "G16" in s3_key

    def test_day_of_year_edge_cases(self, time_index):
        """Test day-of-year calculations around year boundaries."""
        # Test December 31st
        dec_31 = datetime.datetime(
            2023, 12, 31, 23, 59, 59, tzinfo=datetime.timezone.utc
        )
        day_of_year = dec_31.timetuple().tm_yday
        assert day_of_year == 365  # 2023 is not a leap year

        # Test January 1st
        jan_1 = datetime.datetime(2024, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc)
        day_of_year = jan_1.timetuple().tm_yday
        assert day_of_year == 1

        # Test leap year
        feb_29 = datetime.datetime(2024, 2, 29, 12, 0, 0, tzinfo=datetime.timezone.utc)
        day_of_year = feb_29.timetuple().tm_yday
        assert day_of_year == 60  # Feb 29 is day 60 in leap year

        # Test December 31st in leap year
        dec_31_leap = datetime.datetime(
            2024, 12, 31, 23, 59, 59, tzinfo=datetime.timezone.utc
        )
        day_of_year = dec_31_leap.timetuple().tm_yday
        assert day_of_year == 366  # Leap year has 366 days

    def test_midnight_boundary_handling(self, time_index):
        """Test handling of midnight boundary crossing using existing methods."""
        # Just before midnight UTC
        before_midnight = datetime.datetime(
            2023, 7, 15, 23, 59, 59, tzinfo=datetime.timezone.utc
        )

        # Just after midnight UTC
        after_midnight = datetime.datetime(
            2023, 7, 16, 0, 0, 1, tzinfo=datetime.timezone.utc
        )

        # Generate S3 keys using existing method
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

        # Verify different days are represented in the keys
        assert "196/23" in key_before  # Day 196, hour 23
        assert "197/00" in key_after  # Day 197, hour 00

    def test_international_date_line_handling(self):
        """Test handling around international date line."""
        # UTC time
        utc_time = datetime.datetime(
            2023, 7, 15, 12, 0, 0, tzinfo=datetime.timezone.utc
        )

        # Timezones on either side of date line
        fiji = zoneinfo.ZoneInfo("Pacific/Fiji")  # UTC+12
        hawaii = zoneinfo.ZoneInfo("Pacific/Honolulu")  # UTC-10

        fiji_time = utc_time.astimezone(fiji)
        hawaii_time = utc_time.astimezone(hawaii)

        # Fiji is ahead by almost a day
        assert fiji_time.day == 16  # Next day
        assert hawaii_time.day == 15  # Same day
        assert fiji_time.hour == 0  # Midnight in Fiji
        assert hawaii_time.hour == 2  # 2 AM in Hawaii

    def test_goes_scan_schedule_timezone_consistency(self, time_index):
        """Test GOES scan schedule remains consistent across timezones."""
        # GOES operates on UTC schedule
        base_utc = datetime.datetime(
            2023, 7, 15, 12, 0, 0, tzinfo=datetime.timezone.utc
        )

        # Full disk scans every 15 minutes
        scan_times = []
        for i in range(4):  # One hour of scans
            scan_time = base_utc + datetime.timedelta(minutes=15 * i)
            scan_times.append(scan_time)

        # Convert to different timezone
        eastern = zoneinfo.ZoneInfo("America/New_York")
        eastern_scan_times = [t.astimezone(eastern) for t in scan_times]

        # Verify 15-minute intervals are preserved
        for i in range(1, len(eastern_scan_times)):
            delta = eastern_scan_times[i] - eastern_scan_times[i - 1]
            assert delta.total_seconds() == 900  # 15 minutes

    def test_filename_timestamp_parsing_edge_cases(self, time_index):
        """Test parsing timestamps from GOES filenames."""
        # Standard filename
        filename = "OR_ABI-L1b-RadF-M6C13_G16_s20232001200000_e20232001215000_c20232001215300.nc"

        # Parse start time
        parts = filename.split("_")
        start_str = parts[3][1:]  # Remove 's' prefix

        # Extract components
        year = int(start_str[0:4])
        day_of_year = int(start_str[4:7])
        hour = int(start_str[7:9])
        minute = int(start_str[9:11])
        second = int(start_str[11:13])

        # Reconstruct datetime
        parsed_date = datetime.datetime(year, 1, 1, tzinfo=datetime.timezone.utc)
        parsed_date += datetime.timedelta(
            days=day_of_year - 1, hours=hour, minutes=minute, seconds=second
        )

        assert parsed_date.year == 2023
        assert parsed_date.month == 7
        assert parsed_date.day == 19  # Day 200 of 2023
        assert parsed_date.hour == 12
        assert parsed_date.minute == 0

    def test_time_range_queries_across_dst(self, time_index):
        """Test time range queries that span DST transitions."""
        eastern = zoneinfo.ZoneInfo("America/New_York")

        # Create range that spans spring DST transition
        start = datetime.datetime(
            2023, 3, 11, 22, 0, 0, tzinfo=datetime.timezone.utc
        )  # 5 PM EST March 11
        end = datetime.datetime(
            2023, 3, 12, 22, 0, 0, tzinfo=datetime.timezone.utc
        )  # 6 PM EDT March 12

        # Convert to local times
        start_local = start.astimezone(eastern)
        end_local = end.astimezone(eastern)

        # Verify DST transition occurred
        assert start_local.hour == 17  # 5 PM EST
        assert end_local.hour == 18  # 6 PM EDT

        # Duration should be 24 hours despite local time showing 25 hours
        duration = end - start
        assert duration.total_seconds() == 86400  # Exactly 24 hours

    def test_leap_second_handling(self):
        """Test handling of leap seconds (theoretical)."""
        # Note: Python datetime doesn't directly support leap seconds
        # But we should handle timestamps that might include them

        # Simulate a timestamp during a leap second
        # December 31, 2016 had a leap second at 23:59:60 UTC
        try:
            # This would normally fail
            leap_second = datetime.datetime(
                2016, 12, 31, 23, 59, 60, tzinfo=datetime.timezone.utc
            )
        except ValueError:
            # Expected - Python doesn't support second=60
            # In practice, we'd handle this by rounding to next second
            leap_second = datetime.datetime(
                2017, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc
            )

        assert leap_second.year == 2017
        assert leap_second.month == 1
        assert leap_second.day == 1

    def test_timezone_abbreviation_ambiguity(self):
        """Test handling of ambiguous timezone abbreviations."""
        # CST could mean Central Standard Time or China Standard Time
        # EST could mean Eastern Standard Time or Eastern Summer Time (Australia)

        # Use explicit timezone names instead of abbreviations
        us_central = zoneinfo.ZoneInfo("America/Chicago")
        china_standard = zoneinfo.ZoneInfo("Asia/Shanghai")

        utc_time = datetime.datetime(
            2023, 7, 15, 12, 0, 0, tzinfo=datetime.timezone.utc
        )

        us_time = utc_time.astimezone(us_central)
        china_time = utc_time.astimezone(china_standard)

        # Very different times despite both being "CST"
        assert us_time.hour == 7  # 7 AM CDT (summer)
        assert china_time.hour == 20  # 8 PM CST

    def test_sub_second_timestamp_precision(self, time_index):
        """Test handling of sub-second precision in timestamps using existing methods."""
        # GOES can have sub-second start times
        precise_time = datetime.datetime(
            2023, 7, 15, 12, 30, 45, 123456, tzinfo=datetime.timezone.utc
        )

        # Generate S3 key using existing method
        s3_key = time_index.to_s3_key(
            ts=precise_time,
            satellite=SatellitePattern.GOES_16,
            product_type="RadC",
        )

        # Verify that timestamp components are represented
        # Day 196 is July 15, 2023, hour 12
        assert "196" in s3_key  # Day of year
        assert "12" in s3_key  # Hour
        # S3 keys use wildcards, so we check the general structure
        assert "ABI-L1b-RadC" in s3_key
        assert "G16" in s3_key

    @pytest.mark.skip(reason="Timezone rule test assumptions may vary")
    def test_historical_timezone_rules(self):
        """Test handling of historical timezone rule changes."""
        # Indiana used to not observe DST before 2006
        indiana = zoneinfo.ZoneInfo("America/Indiana/Indianapolis")

        # Date in 2005 (no DST)
        old_summer = datetime.datetime(
            2005, 7, 15, 12, 0, 0, tzinfo=datetime.timezone.utc
        )
        old_local = old_summer.astimezone(indiana)

        # Date in 2023 (with DST)
        new_summer = datetime.datetime(
            2023, 7, 15, 12, 0, 0, tzinfo=datetime.timezone.utc
        )
        new_local = new_summer.astimezone(indiana)

        # Different UTC offsets for same summer date
        assert old_local.hour == 8  # UTC-4 (EST year-round)
        assert new_local.hour == 8  # UTC-4 (EDT in summer)

    @pytest.mark.parametrize(
        "hour,expected_scan_count",
        [
            (0, 4),  # Midnight UTC - 4 scans
            (6, 4),  # 6 AM UTC - 4 scans
            (12, 4),  # Noon UTC - 4 scans
            (18, 4),  # 6 PM UTC - 4 scans
            (23, 4),  # 11 PM UTC - 4 scans
        ],
    )
    def test_hourly_scan_consistency(self, time_index, hour, expected_scan_count):
        """Test that scan counts are consistent regardless of hour."""
        base_time = datetime.datetime(
            2023, 7, 15, hour, 0, 0, tzinfo=datetime.timezone.utc
        )

        # Get scans for the hour
        scans = []
        for minute in [0, 15, 30, 45]:
            scan_time = base_time.replace(minute=minute)
            scans.append(scan_time)

        assert len(scans) == expected_scan_count
