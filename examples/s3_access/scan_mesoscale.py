#!/usr/bin/env python3
"""
Scan specifically for Mesoscale imagery availability.
This script is designed to find when and where mesoscale data exists.
"""
import argparse
import re
from datetime import datetime, timedelta

import boto3
from botocore import UNSIGNED
from botocore.config import Config

# Configure boto3 for anonymous access
s3_config = Config(signature_version=UNSIGNED, region_name="us-east-1")

s3 = boto3.client("s3", config=s3_config)


def check_path_exists(bucket, prefix, pattern=None):
    """Check if files exist matching a given prefix and pattern."""
    print(f"Checking {bucket}/{prefix}")

    try:
        # List objects with the given prefix
        paginator = s3.get_paginator("list_objects_v2")
        page_iterator = paginator.paginate(Bucket=bucket, Prefix=prefix, MaxKeys=10)

        # Check if any objects exist
        for page in page_iterator:
            if "Contents" in page:
                if pattern is None:
                    return True, [obj["Key"] for obj in page["Contents"][:5]]

                # If pattern provided, filter by it
                matching = [
                    obj["Key"] for obj in page["Contents"] if pattern in obj["Key"]
                ]

                if matching:
                    return True, matching[:5]

        return False, []

    except Exception as e:
        print(f"  Error checking {bucket}/{prefix}: {e}")
        return False, []


def scan_day_hours(satellite, sector, band, year, doy, hours=None):
    """Scan a specific day and hours for mesoscale imagery."""
    if hours is None:
        hours = range(0, 24)  # Default to all hours

    bucket = f"noaa-{satellite.lower()}"

    # Convert satellite to number
    satellite_num = satellite[-2:]

    # Pattern to match specific band
    pattern = f"OR_ABI-L2-CMIPM{sector}-M6C{band:02d}_G{satellite_num}"

    found_files = {}

    for hour in hours:
        # Format hour as 2-digit string
        hour_str = f"{hour:02d}"

        # Build prefix
        prefix = f"ABI-L2-CMIPM{sector}/{year}/{doy:03d}/{hour_str}/"

        # Check if this path exists and has files
        exists, files = check_path_exists(bucket, prefix, pattern)

        if exists:
            print(f"✓ Found {len(files)} Band {band} files in {bucket}/{prefix}")
            print(f"  Examples:")
            for file in files:
                print(f"  - {file}")

            found_files[hour] = files
        else:
            print(f"✗ No Band {band} files found in {bucket}/{prefix}")

    return found_files


def main():
    parser = argparse.ArgumentParser(
        description="Scan for GOES Mesoscale imagery availability"
    )
    parser.add_argument(
        "--satellite",
        choices=["GOES16", "GOES18"],
        default="GOES16",
        help="Satellite to scan (default: GOES16)",
    )
    parser.add_argument(
        "--sector",
        choices=["1", "2"],
        default="1",
        help="Mesoscale sector (1 or 2) (default: 1)",
    )
    parser.add_argument(
        "--band", type=int, default=13, help="Band number to search for (default: 13)"
    )
    parser.add_argument(
        "--year",
        type=int,
        default=datetime.now().year,
        help=f"Year to scan (default: {datetime.now().year})",
    )
    parser.add_argument(
        "--day",
        type=int,
        default=datetime.now().timetuple().tm_yday,
        help=f"Day of year to scan (default: {datetime.now().timetuple().tm_yday} - today)",
    )
    parser.add_argument(
        "--hour-start", type=int, default=0, help="Starting hour (0-23) (default: 0)"
    )
    parser.add_argument(
        "--hour-end", type=int, default=23, help="Ending hour (0-23) (default: 23)"
    )
    args = parser.parse_args()

    # Get hours to scan
    hours = range(args.hour_start, args.hour_end + 1)

    print(f"Scanning for Mesoscale {args.sector} imagery from {args.satellite}")
    print(f"Date: {args.year}/{args.day:03d}, Hours: {args.hour_start}-{args.hour_end}")
    print(f"Band: {args.band}")
    print("-" * 70)

    found_files = scan_day_hours(
        args.satellite, args.sector, args.band, args.year, args.day, hours
    )

    if found_files:
        print("\nSummary:")
        print(
            f"Found Mesoscale {args.sector} Band {args.band} imagery in {len(found_files)} hours"
        )
        hours_with_data = sorted(found_files.keys())
        print(f"Hours with data: {', '.join(str(h) for h in hours_with_data)}")

        # Get example command to download
        example_hour = hours_with_data[0]
        print("\nExample command to download:")
        print(
            f"python download_ir_simple.py --date {args.year}-MM-DD --hour {example_hour} "
            + f"--satellite {args.satellite} --sector M{args.sector}"
        )
    else:
        print("\nNo Mesoscale imagery found for the specified parameters")

        # Try some other suggestions
        print("\nSuggestions to try:")
        print(
            f"1. Try a different day - mesoscale sectors move based on weather events"
        )
        print(f"2. Try scanning both M1 and M2 sectors")
        print(f"3. Try a date range within the last year for better availability")


if __name__ == "__main__":
    main()
