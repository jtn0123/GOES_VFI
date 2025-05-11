#!/usr/bin/env python3
"""
Download pre-processed GOES satellite images from NOAA's CDN server.
These are ready-made images that don't require any additional processing.
"""
import argparse
import os
from datetime import datetime, timedelta
from pathlib import Path

import requests

# Base URL for NOAA's CDN
CDN_BASE_URL = "https://cdn.star.nesdis.noaa.gov"

# Available satellites
SATELLITES = ["GOES16", "GOES18"]

# Available sectors
SECTORS = {"FD": "Full Disk", "C": "CONUS", "M1": "Mesoscale 1", "M2": "Mesoscale 2"}

# Available products
PRODUCTS = {
    "GEOCOLOR": "GeoColor (True Color daytime, multispectral IR at night)",
    "TRUECOLOR": "True Color RGB",
    "13": "Clean IR (Band 13)",
    "09": "Water Vapor (Band 9)",
    "07": "Shortwave IR (Band 7)",
    "FIRE": "Fire Temperature RGB",
}

# Available resolutions by sector
RESOLUTIONS = {
    "FD": [
        "339x339",
        "678x678",
        "1808x1808",
        "5424x5424",
        "10848x10848",
        "21696x21696",
    ],
    "C": ["600x600", "1200x1200", "2400x2400", "5000x5000", "10000x10000"],
    "M1": ["300x300", "500x500", "1000x1000", "2000x2000"],
    "M2": ["300x300", "500x500", "1000x1000", "2000x2000"],
}


def get_recent_timestamps(hours_back=24, interval_minutes=10):
    """Generate timestamps for recent images."""
    now = datetime.utcnow()
    # Round down to the nearest 10 minutes
    now = now.replace(minute=now.minute // 10 * 10, second=0, microsecond=0)

    timestamps = []
    for h in range(hours_back, 0, -1):
        for m in range(0, 60, interval_minutes):
            time = now - timedelta(hours=h, minutes=m)
            timestamps.append(time)

    return timestamps


def build_url(satellite, sector, product, timestamp, resolution):
    """Build the URL for a specific image."""
    date_str = timestamp.strftime("%Y%m%d_%H%M%S")
    return f"{CDN_BASE_URL}/{satellite}/ABI/{sector}/{product}/{date_str}_{satellite}-ABI-{sector}-{product}-{resolution}.jpg"


def download_image(url, output_dir, filename=None):
    """Download an image from the given URL."""
    if filename is None:
        filename = url.split("/")[-1]

    output_path = output_dir / filename

    try:
        print(f"Attempting to download: {url}")
        response = requests.get(url, stream=True, timeout=10)

        if response.status_code == 200:
            with open(output_path, "wb") as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
            print(f"Downloaded: {output_path}")
            return output_path
        else:
            print(f"Failed to download (status {response.status_code}): {url}")
            return None
    except Exception as e:
        print(f"Error downloading {url}: {e}")
        return None


def find_latest_image(satellite, sector, product, resolution, hours_back=24):
    """Find the latest available image by trying recent timestamps."""
    timestamps = get_recent_timestamps(hours_back=hours_back)

    for timestamp in timestamps:
        url = build_url(satellite, sector, product, timestamp, resolution)

        try:
            response = requests.head(url, timeout=5)
            if response.status_code == 200:
                return url, timestamp
        except Exception:
            continue

    return None, None


def main():
    """Main function to download pre-processed GOES images."""
    parser = argparse.ArgumentParser(
        description="Download pre-processed GOES satellite images from NOAA's CDN"
    )
    parser.add_argument(
        "--satellite",
        choices=SATELLITES,
        default="GOES18",
        help="Satellite to use (default: GOES18)",
    )
    parser.add_argument(
        "--sector",
        choices=list(SECTORS.keys()),
        default="FD",
        help="Sector to download (default: FD [Full Disk])",
    )
    parser.add_argument(
        "--product",
        choices=list(PRODUCTS.keys()),
        default="GEOCOLOR",
        help="Product type to download (default: GEOCOLOR)",
    )
    parser.add_argument(
        "--resolution",
        default=None,
        help="Resolution to download (default: medium resolution for the sector)",
    )
    parser.add_argument(
        "--output-dir",
        default="~/Downloads/goes_quicklook",
        help="Directory to save images (default: ~/Downloads/goes_quicklook)",
    )
    parser.add_argument(
        "--hours-back",
        type=int,
        default=24,
        help="How many hours back to search for images (default: 24)",
    )
    parser.add_argument(
        "--latest-only",
        action="store_true",
        help="Download only the latest available image",
    )
    parser.add_argument(
        "--timestamp", help="Specific timestamp to download (format: YYYYMMDD_HHMMSS)"
    )
    args = parser.parse_args()

    # Create output directory
    output_dir = Path(os.path.expanduser(args.output_dir))
    output_dir.mkdir(parents=True, exist_ok=True)

    # Select default resolution if not specified
    if args.resolution is None:
        # Choose a medium resolution for the sector
        available_resolutions = RESOLUTIONS[args.sector]
        args.resolution = available_resolutions[len(available_resolutions) // 2]

    print(
        f"Downloading {args.satellite} {SECTORS[args.sector]} {PRODUCTS[args.product]} images"
    )
    print(f"Resolution: {args.resolution}")
    print(f"Output directory: {output_dir}")
    print("-" * 70)

    if args.timestamp:
        # Download specific timestamp
        try:
            timestamp = datetime.strptime(args.timestamp, "%Y%m%d_%H%M%S")
            url = build_url(
                args.satellite, args.sector, args.product, timestamp, args.resolution
            )
            download_image(url, output_dir)
        except ValueError:
            print(f"Invalid timestamp format. Use YYYYMMDD_HHMMSS format.")
    elif args.latest_only:
        # Find and download latest available image
        print(
            f"Searching for latest available image (up to {args.hours_back} hours back)..."
        )
        url, timestamp = find_latest_image(
            args.satellite, args.sector, args.product, args.resolution, args.hours_back
        )

        if url:
            print(f"Found latest image from {timestamp}")
            download_image(url, output_dir)
        else:
            print(f"No images found in the last {args.hours_back} hours")
    else:
        # Download images from recent timestamps
        print(f"Downloading images from the last {args.hours_back} hours...")
        timestamps = get_recent_timestamps(hours_back=args.hours_back)

        successful_downloads = 0
        for timestamp in timestamps:
            url = build_url(
                args.satellite, args.sector, args.product, timestamp, args.resolution
            )
            if download_image(url, output_dir):
                successful_downloads += 1

        print(f"\nDownloaded {successful_downloads} images to {output_dir}")


if __name__ == "__main__":
    main()
