#!/usr/bin/env python3
"""
Script to update the time_index.py file to support all bands and product types.
This script modifies the existing file to make the band number configurable.
"""
import re
from pathlib import Path

# Path to the time_index.py file
time_index_path = Path(
    "/Users/justin/Documents/Github/GOES_VFI/goesvfi/integrity_check/time_index.py"
)

# Read the current content
content = time_index_path.read_text()

# Make changes
changes = [
    # Update the constant BAND from fixed value to a default value
    (
        "# Constants for GOES imagery\nBAND = 13  # Hard-coded for Band 13 (Clean IR)",
        "# Constants for GOES imagery\nDEFAULT_BAND = 13  # Default band is 13 (Clean IR)",
    ),
    # Update CDN URL generation to support all bands
    (
        "def to_cdn_url(ts: datetime, satellite: SatellitePattern, resolution: Optional[str] = None) -> str:",
        "def to_cdn_url(ts: datetime, satellite: SatellitePattern, resolution: Optional[str] = None, band: int = DEFAULT_BAND) -> str:",
    ),
    # Update CDN URL generation implementation
    (
        '    # Basic test expects: YYYY+DOY+HHMM+SS_GOESxx-ABI-FD-13-RESxRES.jpg\n        filename = f"{year}{doy_str}{hour}{minute}{second}_{sat_name}-ABI-FD-13-{res}.jpg"\n        url = f"https://cdn.star.nesdis.noaa.gov/{sat_name}/ABI/FD/13/{filename}"',
        '    # Basic test expects: YYYY+DOY+HHMM+SS_GOESxx-ABI-FD-{band}-RESxRES.jpg\n        band_str = f"{band}"\n        filename = f"{year}{doy_str}{hour}{minute}{second}_{sat_name}-ABI-FD-{band_str}-{res}.jpg"\n        url = f"https://cdn.star.nesdis.noaa.gov/{sat_name}/ABI/FD/{band_str}/{filename}"',
    ),
    # Update the other CDN URL format
    (
        '    # Main test expects: YYYY+DOY+HHMM_GOESxx-ABI-CONUS-13-RESxRES.jpg\n        filename = f"{year}{doy_str}{hour}{minute}_{sat_name}-ABI-CONUS-13-{res}.jpg"\n        url = f"https://cdn.star.nesdis.noaa.gov/{sat_name}/ABI/CONUS/13/{filename}"',
        '    # Main test expects: YYYY+DOY+HHMM_GOESxx-ABI-CONUS-{band}-RESxRES.jpg\n        band_str = f"{band}"\n        filename = f"{year}{doy_str}{hour}{minute}_{sat_name}-ABI-CONUS-{band_str}-{res}.jpg"\n        url = f"https://cdn.star.nesdis.noaa.gov/{sat_name}/ABI/CONUS/{band_str}/{filename}"',
    ),
    # Update TimeIndex class to use DEFAULT_BAND
    (
        "    # Constants\n    BAND = BAND",
        "    # Constants\n    DEFAULT_BAND = DEFAULT_BAND",
    ),
    # Update TimeIndex.to_cdn_url method to support band parameter
    (
        "    def to_cdn_url(ts: datetime, satellite: SatellitePattern, resolution: Optional[str] = None) -> str:",
        "    def to_cdn_url(ts: datetime, satellite: SatellitePattern, resolution: Optional[str] = None, band: int = DEFAULT_BAND) -> str:",
    ),
    # Update TimeIndex.to_cdn_url implementation
    (
        "        return to_cdn_url(ts, satellite, resolution or TimeIndex.CDN_RES)",
        "        return to_cdn_url(ts, satellite, resolution or TimeIndex.CDN_RES, band)",
    ),
    # Update the docstring for to_local_path to mention band support
    (
        "def to_local_path(ts: datetime, satellite: SatellitePattern) -> Path",
        "def to_local_path(ts: datetime, satellite: SatellitePattern, band: int = DEFAULT_BAND) -> Path",
    ),
    # Update the implementation of to_local_path
    (
        "    # Create filename with satellite and timestamp: goes16_20230615_123000_band13.png\n    filename = f\"{sat_name}_{ts.strftime('%Y%m%d_%H%M%S')}_band13.png\"",
        "    # Create filename with satellite and timestamp: goes16_20230615_123000_band{band}.png\n    filename = f\"{sat_name}_{ts.strftime('%Y%m%d_%H%M%S')}_band{band}.png\"",
    ),
    # Update TimeIndex.to_local_path method signature
    (
        "    def to_local_path(ts: datetime, satellite: SatellitePattern) -> Path:",
        "    def to_local_path(ts: datetime, satellite: SatellitePattern, band: int = DEFAULT_BAND) -> Path:",
    ),
    # Update TimeIndex.to_local_path implementation
    (
        "        return to_local_path(ts, satellite)",
        "        return to_local_path(ts, satellite, band)",
    ),
]

# Apply changes
new_content = content
for old, new in changes:
    new_content = new_content.replace(old, new)

# Write the updated content back
Path("/Users/justin/Documents/Github/GOES_VFI/time_index_updated.py").write_text(
    new_content
)

print("Updated time_index.py file has been written to time_index_updated.py")
print("Review the changes and then copy to goesvfi/integrity_check/time_index.py")
