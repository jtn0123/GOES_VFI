from typing import Optional, import, requests  # Base URL for NOAA's CDN

CDN_BASE_URL = "https://cdn.star.nesdis.noaa.gov" # Satellites SATELLITES = ["GOES16", "GOES18"] # Product types / sectors SECTORS = { "FD": "Full Disk", "C": "CONUS (Continental US)", "M1": "Mesoscale 1", "M2": "Mesoscale 2", } # Image types IMAGE_TYPES = { "GEOCOLOR": "GeoColor (true color day, multispectral IR night)", "TRUECOLOR": "True Color RGB", "13": "Clean IR (Band 13)", "09": "Water Vapor (Band 9)", "07": "Shortwave IR (Band 7)", "FIRE": "Fire Temperature RGB", } # Available resolutions by sector RESOLUTIONS = { "FD": [ "339x339", "678x678", "1808x1808", "5424x5424", "10848x10848", "21696x21696", ], "C": ["600x600", "1200x1200", "2400x2400", "5000x5000", "10000x10000"], "M1": ["300x300", "500x500", "1000x1000", "2000x2000"], "M2": ["300x300", "500x500", "1000x1000", "2000x2000"], } def download_image(url: str, output_path: Path) -> bool: """ Download an image from a URL and save it to the specified path. Args: url: The URL to download from output_path: The path to save the image to Returns: bool: True if successful, False otherwise """ print(f"Downloading {url}...") try: # Create parent directories if they don't exist output_path.parent.mkdir(parents=True, exist_ok=True) # Make the request response = requests.get(url, stream=True, timeout=10) # Check if the request was successful if response.status_code == 200: # Save the image with open(output_path, "wb") as f: for chunk in response.iter_content(1024 * 1024): # 1MB chunks f.write(chunk) print(f"Downloaded to {output_path}") return True else: print(f"Failed to download: HTTP {response.status_code}") return False except Exception as e: print(f"Error downloading {url}: {e}") return False def build_url( satellite: str, sector: str, image_type: str, timestamp: datetime.datetime, resolution: str, ) -> str: """ Build the URL for a GOES image on NOAA's CDN. Args: satellite: Satellite name (e.g. "GOES16") sector: Sector code (e.g. "FD", "C", "M1", "M2") image_type: Image type code (e.g. "GEOCOLOR", "13") timestamp: Datetime object for the image timestamp resolution: Resolution string (e.g. "1808x1808") Returns: str: The complete URL """ # Format timestamp as YYYYMMDD_HHMMSS timestamp_str = timestamp.strftime("%Y % m % d_ % H % M % S") # Build and return the URL return f"{CDN_BASE_URL}/{satellite}/ABI/{sector}/{image_type}/{timestamp_str}_{satellite}-ABI-{sector}-{image_type}-{resolution}.jpg" def try_recent_timestamps( satellite: str, sector: str, image_type: str, resolution: str, hours_back: int = 24 ) -> Optional[str]: """ Try recent timestamps to find an available image. Args: satellite: Satellite name sector: Sector code image_type: Image type code resolution: Resolution string hours_back: How many hours to look back Returns: Optional[str]: URL if found, None otherwise """ print( f"Looking for {satellite} {SECTORS[sector]} {IMAGE_TYPES[image_type]} images..." ) # Get current time (UTC) now = datetime.datetime.now(datetime.UTC) # Try timestamps in 10 - minute intervals going back for h in range(1, hours_back + 1): for m in range(0, 60, 10): # Every 10 minutes # Calculate timestamp timestamp = now - datetime.timedelta(hours=h, minutes=m) # Build URL url = build_url(satellite, sector, image_type, timestamp, resolution) # Use HEAD request to check if the image exists try: response = requests.head(url, timeout=5) if response.status_code == 200: print( f"Found image from {timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}" ) return url, timestamp except Exception: # Continue to next timestamp if there's an error continue print(f"No images found in the last {hours_back} hours") return None, None def main(): """Main function to download GOES images.""" parser = argparse.ArgumentParser( description="Download GOES satellite images from NOAA's CDN"'
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
help="Sector to download (default: FD - Full Disk)",
)
parser.add_argument(
"--type",
choices=list(IMAGE_TYPES.keys()),
default="GEOCOLOR",
help="Image type to download (default: GEOCOLOR)",
)
parser.add_argument(
"--resolution",
help="Resolution to download (default: medium resolution for sector)",
)
parser.add_argument(
"--output - dir",
default="~/Downloads / goes_cdn",
help="Directory to save images (default: ~/Downloads / goes_cdn)",
)
parser.add_argument(
"--hours - back",
type=int,
default=24,
help="How many hours to look back (default: 24)",
)
args = parser.parse_args()

# Set default resolution if not specified
if not args.resolution:
     pass
# Choose a medium resolution for better download speeds
available_resolutions = RESOLUTIONS[args.sector]
args.resolution = available_resolutions[len(available_resolutions) // 2]

# Create output directory
output_dir = Path(os.path.expanduser(args.output_dir))
output_dir.mkdir(parents=True, exist_ok=True)

print(
f"Downloading {args.satellite} {SECTORS[args.sector]} {IMAGE_TYPES[args.type]}"
)
print(f"Resolution: {args.resolution}")
print(f"Output directory: {output_dir}")
print("-" * 70)

# Try to find and download the most recent image
url, timestamp = try_recent_timestamps(
args.satellite, args.sector, args.type, args.resolution, args.hours_back
)

if url and timestamp:
     pass
# Create output filename
output_filename = f"{args.satellite}_{args.sector}_{args.type}_{timestamp.strftime('%Y % m % d_ % H % M % S')}.jpg"
output_path = output_dir / output_filename

# Download the image
success = download_image(url, output_path)

if success:
     pass
print("\nDownload successful!")
print(f"Image saved to: {output_path}")
else:
     print("\nDownload failed.")
sys.exit(1)
else:
     print(
"\nNo images found. Try increasing --hours - back or check your parameters."
)
sys.exit(1)


if __name__ == "__main__":
    pass
main()
