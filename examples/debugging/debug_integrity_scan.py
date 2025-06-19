#!/usr/bin/env python3
"""
Debug script for diagnosing issues with the integrity check scan.
This adds additional logging and provides a direct way to test the scan functionality.
"""

import argparse
import asyncio
import logging
import sys
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from typing import Set, Tuple

# Set up logging
log_file = Path("debug_integrity_scan.log")
logging.basicConfig(
level=logging.DEBUG,
format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
handlers=[logging.FileHandler(log_file), logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger("debug_integrity_scan")
logger.info(f"Debug script started at {datetime.now().isoformat()}")
logger.info(f"Python version: {sys.version}")
logger.info(f"Log file: {log_file.absolute()}")

# Import required modules
try:
    from goesvfi.integrity_check.cache_db import CacheDB

from goesvfi.integrity_check.enhanced_view_model import (
    EnhancedIntegrityCheckViewModel,
    FetchSource,
)
from goesvfi.integrity_check.reconcile_manager import ReconcileManager
from goesvfi.integrity_check.time_index import (
    SatellitePattern,
    TimeIndex,
    extract_timestamp_from_directory_name,
    find_date_range_in_directory,
    scan_directory_for_timestamps,
)
from goesvfi.utils.log import get_logger

logger.info("Successfully imported required modules")
except ImportError as e:
    pass
logger.critical(f"Failed to import required modules: {e}")
traceback.print_exc()
sys.exit(1)

# Set up debug logger for goesvfi modules
goesvfi_logger = get_logger("goesvfi")
goesvfi_logger.setLevel(logging.DEBUG)


def test_timestamp_extraction(directory_name: str) -> None:
    """Test timestamp extraction from a directory name."""
logger.info(f"Testing timestamp extraction from directory name: {directory_name}")

# Test direct extraction
timestamp = extract_timestamp_from_directory_name(directory_name)

if timestamp:
     pass
logger.info(f"✅ Successfully extracted timestamp: {timestamp.isoformat()}")
else:
     logger.error("❌ Failed to extract timestamp from directory name")

# Test through TimeIndex class
time_index_timestamp = TimeIndex.ts_from_directory_name(directory_name)

if time_index_timestamp:
     pass
logger.info(
f"✅ TimeIndex extracted timestamp: {time_index_timestamp.isoformat()}"
)
else:
     logger.error("❌ TimeIndex failed to extract timestamp from directory name")


def test_directory_structure(directory_path: str or Path) -> None:
    """Test and display the directory structure to help diagnose issues."""
directory = Path(directory_path)
logger.info(f"Analyzing directory structure: {directory}")

# Check if directory exists
if not directory.exists():
     pass
logger.error(f"❌ Directory does not exist: {directory}")
return

if not directory.is_dir():
     pass
logger.error(f"❌ Path is not a directory: {directory}")
return

# List top - level subdirectories
subdirs = [d for d in directory.iterdir() if d.is_dir()]
logger.info(f"Found {len(subdirs)} subdirectories at top level")

for i, subdir in enumerate(subdirs[:10]): # Show first 10 subdirectories
logger.info(f" 📁 {i + 1}. {subdir.name}")

# Test timestamp extraction from subdirectory name
ts = extract_timestamp_from_directory_name(subdir.name)
if ts:
     pass
logger.info(f" ✅ Timestamp: {ts.isoformat()}")
else:
     logger.info(" ❌ No timestamp found in directory name")

# Count PNG files
png_files = list(subdir.glob("**/*.png"))
logger.info(f" Found {len(png_files)} PNG files")

# Show first few files if any
for j, file in enumerate(png_files[:3]):
     logger.info(f" 📄 {j + 1}. {file.name}")


def test_directory_scanning(
directory_path: str or Path, satellite_pattern: SatellitePattern
) -> None:
    """Test the directory scanning functionality."""
directory = Path(directory_path)

if not directory.exists() or not directory.is_dir():
     pass
logger.error(f"❌ Directory does not exist or is not a directory: {directory}")
return

logger.info(
f"Testing directory scanning for {directory} with pattern {satellite_pattern.name}"
)

# Test directory structure
logger.info("Directory structure:")
for item in directory.glob("*"):
     if item.is_dir():
         pass
     pass
logger.info(
f" DIR: {item.name} - {len(list(item.glob('*.png')))} PNG files"
)

# Test timestamp extraction from directory names
logger.info("Testing timestamp extraction from directory names:")
subdirs = [p for p in directory.iterdir() if p.is_dir()]
found_timestamps = 0
for subdir in subdirs[:20]: # Limit to first 20 to avoid excessive output
ts = extract_timestamp_from_directory_name(subdir.name)
logger.info(f" {subdir.name} -> {ts.isoformat() if ts else 'No match'}")
if ts:
     pass
found_timestamps += 1

logger.info(
f"Found {found_timestamps} timestamps in {len(subdirs)} directory names"
)

# Test full directory scan
logger.info("Testing full directory scan:")
timestamps = scan_directory_for_timestamps(directory, satellite_pattern)
logger.info(f" Found {len(timestamps)} timestamps")
if timestamps:
     pass
logger.info(f" First timestamp: {timestamps[0].isoformat()}")
logger.info(f" Last timestamp: {timestamps[-1].isoformat()}")

# Check intervals
if len(timestamps) > 1:
     pass
intervals_minutes = []
for i in range(len(timestamps) - 1):
     delta = timestamps[i + 1] - timestamps[i]
intervals_minutes.append(delta.total_seconds() / 60)

avg_interval = sum(intervals_minutes) / len(intervals_minutes)
logger.info(f" Average interval: {avg_interval:.1f} minutes")
logger.info(f" Min interval: {min(intervals_minutes):.1f} minutes")
logger.info(f" Max interval: {max(intervals_minutes):.1f} minutes")

# Test date range detection
logger.info("Testing date range detection:")
start_date, end_date = find_date_range_in_directory(directory, satellite_pattern)
if start_date and end_date:
     pass
logger.info(
f" ✅ Date range: {start_date.isoformat()} to {end_date.isoformat()}"
)
days_span = (end_date - start_date).total_seconds() / (86400)
logger.info(f" Spanning approximately {days_span:.1f} days")
else:
     logger.info(" ❌ No date range found")


async def run_reconcile_manager_scan(
directory: Path,
satellite: SatellitePattern,
start_time: datetime,
end_time: datetime,
interval_minutes: int = 30,
) -> Tuple[Set[datetime], Set[datetime]]:
    """Run a scan using ReconcileManager directly."""
logger.info("Running ReconcileManager scan asynchronously")

# Create cache DB and reconcile manager
cache_db = CacheDB()
reconcile_manager = ReconcileManager(cache_db=cache_db, base_dir=directory)

# Progress callback
def progress_callback(current, total, message):
     logger.info(f"Scan progress: {current}/{total} - {message}")

try:
     # Run scan
existing, missing = await reconcile_manager.scan_directory(
directory=directory,
satellite=satellite,
start_time=start_time,
end_time=end_time,
interval_minutes=interval_minutes,
progress_callback=progress_callback,
)

logger.info("ReconcileManager scan completed:")
logger.info(f" Found {len(existing)} existing timestamps")
logger.info(f" Found {len(missing)} missing timestamps")
logger.info(f" Total expected: {len(existing) + len(missing)}")

return existing, missing
except Exception as e:
     pass
logger.error(f"Error in ReconcileManager scan: {e}")
logger.error(traceback.format_exc())
return set(), set()
finally:
     # Clean up
await cache_db.close()


def test_view_model_scan(
directory_path: str or Path, satellite_pattern: SatellitePattern
) -> None:
    """Test the view model scan functionality."""
directory = Path(directory_path)

if not directory.exists() or not directory.is_dir():
     pass
logger.error(f"❌ Directory does not exist or is not a directory: {directory}")
return

logger.info(
f"Testing view model scan for {directory} with pattern {satellite_pattern.name}"
)

# Create view model
view_model = EnhancedIntegrityCheckViewModel()
view_model.base_directory = directory
view_model.satellite = satellite_pattern
view_model.fetch_source = FetchSource.LOCAL # Only scan local files

# Set date range
start_date, end_date = find_date_range_in_directory(directory, satellite_pattern)
if start_date and end_date:
     pass
view_model.start_date = start_date
view_model.end_date = end_date
logger.info(
f"Set date range: {start_date.isoformat()} to {end_date.isoformat()}"
)
else:
     # Use default range (yesterday)
yesterday = datetime.now() - timedelta(days=1)
view_model.start_date = yesterday.replace(
hour=0, minute=0, second=0, microsecond=0
)
view_model.end_date = yesterday.replace(
hour=23, minute=59, second=59, microsecond=0
)
logger.info(
f"Using default date range: {view_model.start_date.isoformat()} to {view_model.end_date.isoformat()}"
)

# Set other parameters
view_model.interval_minutes = 30 # 30 minute interval
view_model.force_rescan = True

# Set up progress callback
def progress_callback(current, total, message):
     logger.info(f"Scan progress: {current}/{total} - {message}")

# Connect progress signal
view_model.progress_updated.connect(
lambda current, total, eta: progress_callback(
current, total, f"ETA: {eta:.1f}s"
)
)

# Connect completion signal
view_model.scan_completed.connect(
lambda success, message: logger.info(f"Scan completed: {success} - {message}")
)

# Run the scan
logger.info("Starting scan...")
view_model.start_enhanced_scan()

# Wait for scan to complete
import time

start_time = time.time()
timeout = 60 # 60 second timeout

while view_model._status.name == "SCANNING" and time.time() - start_time < timeout:
     time.sleep(0.1)

if view_model._status.name == "SCANNING":
     pass
logger.warning(f"❌ Scan timed out after {timeout} seconds")
return

duration = time.time() - start_time
logger.info(f"✅ Scan completed in {duration:.1f} seconds")

# Check results
logger.info(f"Missing timestamps: {len(view_model.missing_items)}")
if view_model.missing_items:
     pass
logger.info(
f"First missing timestamp: {view_model.missing_items[0].timestamp.isoformat()}"
)
logger.info(
f"Last missing timestamp: {view_model.missing_items[-1].timestamp.isoformat()}"
)

# Clean up
view_model.cleanup()


def test_direct_async_scan(
directory_path: str or Path, satellite_pattern: SatellitePattern
) -> None:
    """Test the reconcile manager scan functionality directly using asyncio."""
directory = Path(directory_path)

if not directory.exists() or not directory.is_dir():
     pass
logger.error(f"❌ Directory does not exist or is not a directory: {directory}")
return

logger.info(
f"Testing direct async scan for {directory} with pattern {satellite_pattern.name}"
)

# Set date range
start_date, end_date = find_date_range_in_directory(directory, satellite_pattern)
if not start_date or not end_date:
     pass
# Use default range (yesterday)
yesterday = datetime.now() - timedelta(days=1)
start_date = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
end_date = yesterday.replace(hour=23, minute=59, second=59, microsecond=0)

logger.info(f"Using date range: {start_date.isoformat()} to {end_date.isoformat()}")

# Run the scan
try:
     loop = asyncio.get_event_loop()
except RuntimeError:
     pass
# No event loop in current thread
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

loop.run_until_complete(
run_reconcile_manager_scan(
directory=directory,
satellite=satellite_pattern,
start_time=start_date,
end_time=end_date,
interval_minutes=30,
)
)


if __name__ == "__main__":
    pass
# Set up argument parser
parser = argparse.ArgumentParser(description="Debug GOES integrity scanning")
parser.add_argument("directory", help="Directory to scan")
parser.add_argument(
"--satellite",
choices=["GOES_16", "GOES_18", "GOES_17", "GENERIC"],
default="GOES_18",
help="Satellite pattern to use",
)
parser.add_argument(
"--test",
choices=["extract", "structure", "scan", "model", "direct", "all"],
default="all",
help="Test to run",
)

args = parser.parse_args()

# Convert satellite string to enum
satellite = getattr(SatellitePattern, args.satellite)
directory = args.directory

logger.info(f"Testing with directory: {directory}")
logger.info(f"Testing with satellite: {satellite.name}")

# Run selected test
if args.test == "extract" or args.test == "all":
     pass
# Extract last directory name from path
dir_name = Path(directory).name
test_timestamp_extraction(dir_name)

# Also test first few subdirectories
subdirs = [d for d in Path(directory).iterdir() if d.is_dir()]
for subdir in subdirs[:5]:
     test_timestamp_extraction(subdir.name)

if args.test == "structure" or args.test == "all":
     pass
test_directory_structure(directory)

if args.test == "scan" or args.test == "all":
     pass
test_directory_scanning(directory, satellite)

if args.test == "model" or args.test == "all":
     pass
test_view_model_scan(directory, satellite)

if args.test == "direct" or args.test == "all":
     pass
test_direct_async_scan(directory, satellite)

logger.info("All tests completed")
