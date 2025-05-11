#!/usr/bin/env python3
"""
Scan for available GOES satellite data across multiple dates, hours, and buckets.
This script helps find when and where data is actually available.
"""
import argparse
import concurrent.futures
import sys
from datetime import datetime, timedelta

import boto3
from botocore import UNSIGNED
from botocore.config import Config

# Configure boto3 for anonymous access
s3_config = Config(signature_version=UNSIGNED, region_name="us-east-1")

s3 = boto3.client("s3", config=s3_config)


def check_path_exists(bucket, prefix):
    """Check if a path exists in the bucket by listing objects with the prefix."""
    try:
        response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=1)
        # If the response has contents, the path exists
        return "Contents" in response and len(response["Contents"]) > 0
    except Exception as e:
        print(f"Error checking {bucket}/{prefix}: {e}")
        return False


def check_date_hour(bucket, product, year, doy, hour):
    """Check if data exists for a specific bucket, product, date, and hour."""
    # Format with zero-padded DOY
    date_str = f"{year}/{doy:03d}"
    hour_str = f"{hour:02d}"

    # Check with ABI-L2 prefix (new format)
    prefix_new = f"ABI-L2-{product}/{date_str}/{hour_str}/"
    new_exists = check_path_exists(bucket, prefix_new)

    # Check without ABI-L2 prefix (old format)
    prefix_old = f"{product}/{date_str}/{hour_str}/"
    old_exists = check_path_exists(bucket, prefix_old)

    # Return results
    return {
        "bucket": bucket,
        "product": product,
        "date": date_str,
        "hour": hour_str,
        "new_path": prefix_new,
        "new_exists": new_exists,
        "old_path": prefix_old,
        "old_exists": old_exists,
    }


def scan_range(args):
    """Scan a range of dates and hours for available data."""
    bucket, product, year, doy, hour = args
    result = check_date_hour(bucket, product, year, doy, hour)

    # Only print if we found something
    if result["new_exists"] or result["old_exists"]:
        path_info = []
        if result["new_exists"]:
            path_info.append(f"{result['new_path']} (FOUND)")
        if result["old_exists"]:
            path_info.append(f"{result['old_path']} (FOUND)")

        print(
            f"✓ {result['bucket']} - {result['product']} - {result['date']} - Hour {result['hour']}"
        )
        for path in path_info:
            print(f"  → {path}")

        return result

    # If verbose, print all checked paths
    if VERBOSE:
        print(
            f"✗ {result['bucket']} - {result['product']} - {result['date']} - Hour {result['hour']}"
        )

    return None


def get_day_of_year(date_str):
    """Convert a date string (YYYY-MM-DD) to day of year."""
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        return date_obj.timetuple().tm_yday
    except ValueError:
        print(f"Invalid date format: {date_str}. Expected YYYY-MM-DD.")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Scan for available GOES satellite data"
    )
    parser.add_argument(
        "--buckets",
        nargs="+",
        default=["noaa-goes16", "noaa-goes18"],
        help="S3 bucket names to check (default: noaa-goes16 noaa-goes18)",
    )
    parser.add_argument(
        "--products",
        nargs="+",
        default=["CMIPF", "CMIPC", "CMIPM"],
        help="Product types to check (default: CMIPF CMIPC CMIPM)",
    )
    parser.add_argument(
        "--start-date",
        default="2023-05-05",
        help="Start date in YYYY-MM-DD format (default: 2023-05-05)",
    )
    parser.add_argument(
        "--end-date",
        default="2023-05-05",
        help="End date in YYYY-MM-DD format (default: same as start-date)",
    )
    parser.add_argument(
        "--hours",
        nargs="+",
        type=int,
        default=list(range(0, 24, 4)),
        help="Hours to check (default: 0 4 8 12 16 20)",
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Print all checks, not just found paths"
    )
    args = parser.parse_args()

    global VERBOSE
    VERBOSE = args.verbose

    # Parse dates and convert to day of year
    start_date = datetime.strptime(args.start_date, "%Y-%m-%d")
    if args.end_date:
        end_date = datetime.strptime(args.end_date, "%Y-%m-%d")
    else:
        end_date = start_date

    # Ensure end date is not before start date
    if end_date < start_date:
        print("Error: End date cannot be before start date.")
        sys.exit(1)

    # Generate date range
    current_date = start_date
    date_range = []
    while current_date <= end_date:
        year = current_date.year
        doy = current_date.timetuple().tm_yday
        date_range.append((year, doy))
        current_date += timedelta(days=1)

    # Generate all combinations to check
    scan_args = []
    for bucket in args.buckets:
        for product in args.products:
            for year, doy in date_range:
                for hour in args.hours:
                    scan_args.append((bucket, product, year, doy, hour))

    print(f"Scanning for GOES data across {len(scan_args)} combinations...")
    print(f"Buckets: {args.buckets}")
    print(f"Products: {args.products}")
    print(f"Date range: {args.start_date} to {args.end_date}")
    print(f"Hours: {args.hours}")
    print("-" * 70)

    # Use ThreadPoolExecutor for parallel scanning
    found_paths = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(scan_range, scan_args))
        # Filter out None results (not found)
        found_paths = [r for r in results if r is not None]

    # Print summary
    print("\nScan Complete!")
    print(
        f"Found {len(found_paths)} valid data paths across {len(scan_args)} combinations."
    )

    # If any paths found, provide sample command
    if found_paths:
        sample = found_paths[0]
        bucket = sample["bucket"]
        prefix = sample["new_path"] if sample["new_exists"] else sample["old_path"]

        print("\nExample command to explore one of the found paths:")
        print(f"aws s3 ls --no-sign-request s3://{bucket}/{prefix}")


if __name__ == "__main__":
    main()
