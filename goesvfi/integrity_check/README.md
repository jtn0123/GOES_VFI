# Enhanced Integrity Check Module for GOES-VFI

This module provides functionality to verify the completeness of satellite imagery sequences by detecting missing timestamps within a date range, and fetching missing images using a hybrid CDN/S3 strategy.

## Features

### Basic Features
- **Timestamp Verification**: Scan directories to identify missing files in a time sequence
- **Automatic Interval Detection**: Detect the time interval between images 
- **Caching**: Cache scan results for fast retrieval during subsequent scans
- **Download Integration**: Download missing files from remote repositories
- **Progress Reporting**: Show real-time progress during scanning and downloading
- **Report Generation**: Export missing timestamp information as CSV reports

### Enhanced Features
- **Hybrid Fetching Strategy**: Fetch recent data from CDN and historical data from S3
- **Multi-Satellite Support**: Dedicated support for both GOES-16 and GOES-18 satellites
- **Band 13 Focus**: Specialized for Clean IR (10.3 µm) imagery
- **NetCDF Processing**: Automatic conversion of NetCDF files to PNG images
- **Async Processing**: Non-blocking UI with background threading for all operations
- **Disk Space Monitoring**: Real-time monitoring of available disk space
- **Enhanced Progress Tracking**: Per-file download progress reporting
- **AWS Integration**: Direct access to NOAA S3 buckets for historical data

## Architecture

The module follows the MVVM (Model-View-ViewModel) pattern used throughout the GOES-VFI application:

### Basic Implementation

1. **Model Layer**:
   - `reconciler.py`: Core logic for scanning directories and identifying missing timestamps
   - `time_index.py`: Utilities for timestamp pattern recognition and interval generation
   - `cache_db.py`: SQLite-based caching system for scan results
   - `remote_store.py`: Abstract interface and implementations for remote file access

2. **ViewModel Layer**:
   - `view_model.py`: Coordinates between the UI and model layer, manages state and threading

3. **View Layer**:
   - `gui_tab.py`: PyQt6 widget implementing the Integrity Check tab

4. **Threading**:
   - `tasks.py`: QRunnable implementations for background processing

### Enhanced Implementation

1. **Model Layer**:
   - `time_index.py`: Enhanced with CDN/S3 URL generation for GOES-16/18
   - `cache_db.py`: Updated for asynchronous operation
   - `reconcile_manager.py`: New manager for hybrid CDN/S3 fetching
   - `remote/base.py`: Abstract base class for remote stores
   - `remote/cdn_store.py`: Implementation for NOAA STAR CDN
   - `remote/s3_store.py`: Implementation for AWS S3 buckets
   - `render/netcdf.py`: NetCDF to PNG rendering utilities

2. **ViewModel Layer**:
   - `enhanced_view_model.py`: Enhanced ViewModel with hybrid fetching support

3. **View Layer**:
   - `enhanced_gui_tab.py`: Enhanced PyQt6 widget with CDN/S3 configuration

## Hybrid Fetching Strategy

This module implements a hybrid fetching strategy:

1. Recent data (≤7 days old by default) is fetched from the NOAA STAR CDN in JPG format
2. Older data is fetched from AWS S3 buckets in NetCDF format and rendered to PNG

This approach offers several advantages:
- Faster access to recent data via CDN
- Access to historical data via S3 buckets
- Consistent PNG output regardless of source

## Remote Sources

### CDN Source

- NOAA STAR CDN: https://cdn.star.nesdis.noaa.gov
- Provides recent imagery (typically 7 days)
- JPG format, various resolutions (100m, 250m, 500m, 1000m)
- Example URL: https://cdn.star.nesdis.noaa.gov/GOES16/ABI/CONUS/13/20230615123000_GOES16-ABI-CONUS-13-1000m.jpg

### S3 Source

- AWS S3 buckets: `noaa-goes16` and `noaa-goes18`
- Provides full historical archive
- NetCDF format, requires rendering to PNG
- Example key: `ABI-L1b-RadC/2022/001/00/OR_ABI-L1b-RadC-M6C13_G16_s20220101000000_e20220101000999_c*.nc`

## Usage

### Basic Usage

The main interface is the `IntegrityCheckTab` class which can be added to the GOES-VFI application's tab widget. See `INTEGRATION.md` for instructions on adding the tab to the main application.

For programmatic usage, the `Reconciler` class can be used directly:

```python
from goesvfi.integrity_check import Reconciler
from goesvfi.integrity_check.time_index import SatellitePattern
from datetime import datetime
from pathlib import Path

# Create a reconciler instance
reconciler = Reconciler()

# Scan a directory for missing timestamps
result = reconciler.scan_date_range(
    start_date=datetime(2023, 5, 1),
    end_date=datetime(2023, 5, 2),
    satellite_pattern=SatellitePattern.GOES_16,
    base_directory=Path("/path/to/images"),
    interval_minutes=30  # 0 for auto-detect
)

# Print missing timestamps
for dt in result["missing"]:
    print(f"Missing: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
```

### Enhanced Usage

For the enhanced implementation with hybrid fetching:

```python
import asyncio
from goesvfi.integrity_check.reconcile_manager import ReconcileManager
from goesvfi.integrity_check.cache_db import CacheDB
from goesvfi.integrity_check.time_index import SatellitePattern
from datetime import datetime
from pathlib import Path

async def main():
    # Create dependencies
    cache_db = CacheDB()
    base_dir = Path("/path/to/images")
    
    # Create reconcile manager
    manager = ReconcileManager(
        cache_db=cache_db,
        base_dir=base_dir
    )
    
    # Scan and fetch
    total, existing, fetched = await manager.reconcile(
        directory=base_dir,
        satellite=SatellitePattern.GOES_18,
        start_time=datetime(2023, 5, 1),
        end_time=datetime(2023, 5, 2),
        interval_minutes=10,
        progress_callback=lambda c, t, m: print(f"Progress: {c}/{t} - {m}")
    )
    
    print(f"Total: {total}, Existing: {existing}, Fetched: {fetched}")
    
    # Clean up
    await cache_db.close()

# Run the async function
asyncio.run(main())
```

## Integration with GOES-VFI

The Enhanced Integrity Check tab is designed to integrate seamlessly with the rest of the GOES-VFI application. It uses the same logging system, configuration utilities, and UI styling conventions.

When a directory is selected in the Integrity Check tab, it emits a signal that can update other tabs, making it easy to switch between integrity checking and other operations on the same dataset.

See `INTEGRATION.md` for detailed instructions on integrating the enhanced tab.

## Requirements

For the enhanced implementation, you'll need:

- Python 3.13+
- PyQt6 or PySide6
- aiohttp (for CDN fetching)
- aioboto3 (for S3 fetching)
- xarray and netCDF4 (for processing NetCDF files)
- Pillow (for image processing)
- numpy (for numerical operations)
- matplotlib (for rendering NetCDF data)

## Future Enhancements

- Desktop notifications for long-running operations
- Visual timeline display of missing timestamps
- More detailed analytics for gap patterns
- Scheduled background scanning and fetching
- Alternative rendering options for NetCDF files
- Support for additional GOES bands beyond Band 13