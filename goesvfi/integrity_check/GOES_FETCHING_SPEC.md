# GOES-16/18 Band 13 Fetch Specification

This document provides detailed specifications for implementing the hybrid CDN/S3 fetching mechanism for GOES-16 and GOES-18 Band 13 imagery within the Integrity Check module.

## 1. Data Sources and Path Patterns

### CDN Source (Recent 7 Days)
- **Service**: NOAA STAR CDN
- **Base URLs**:
  - GOES-16: `https://cdn.star.nesdis.noaa.gov/GOES16/ABI/FD/13/`
  - GOES-18: `https://cdn.star.nesdis.noaa.gov/GOES18/ABI/FD/13/`
- **Path Patterns**:
  - GOES-16: `{YYYY}{DDD}{HH}{MM}_GOES16-ABI-FD-13-{RESOLUTION}.jpg`
  - GOES-18: `{YYYY}{DDD}{HH}{MM}_GOES18-ABI-FD-13-{RESOLUTION}.jpg`
- **Example URLs**:
  - GOES-16: `https://cdn.star.nesdis.noaa.gov/GOES16/ABI/FD/13/20251150420_GOES16-ABI-FD-13-5424x5424.jpg`
  - GOES-18: `https://cdn.star.nesdis.noaa.gov/GOES18/ABI/FD/13/20251150420_GOES18-ABI-FD-13-5424x5424.jpg`
- **Resolution Options**: 339×339, 678×678, 1808×1808, 5424×5424, 10848×10848
- **Default Resolution**: 5424×5424 (matches existing PNG size)
- **Retention**: Approximately 15 days (but we use only 7 days for reliability)

### AWS S3 Source (Historical Data)
- **Service**: NOAA Open Data AWS Bucket
- **Bucket Names**:
  - GOES-16: `noaa-goes16`
  - GOES-18: `noaa-goes18`
- **Key Patterns**:
  - GOES-16: `ABI-L1b-RadF/{YYYY}/{DDD}/{HH}/OR_ABI-L1b-RadF-M6C13_G16_s{YYYY}{DDD}{HH}{MM}{SEQ}_e{YYYY}{DDD}{HH}{MM}{SEQ}_c{YYYY}{DDD}{HH}{MM}{SEQ}.nc`
  - GOES-18: `ABI-L1b-RadF/{YYYY}/{DDD}/{HH}/OR_ABI-L1b-RadF-M6C13_G18_s{YYYY}{DDD}{HH}{MM}{SEQ}_e{YYYY}{DDD}{HH}{MM}{SEQ}_c{YYYY}{DDD}{HH}{MM}{SEQ}.nc`
- **Example Keys**:
  - GOES-16: `ABI-L1b-RadF/2025/115/04/OR_ABI-L1b-RadF-M6C13_G16_s20251150420365_e20251150426132_c20251150426171.nc`
  - GOES-18: `ABI-L1b-RadF/2025/115/04/OR_ABI-L1b-RadF-M6C13_G18_s20251150420365_e20251150426132_c20251150426171.nc`
- **File Type**: NetCDF4 (Level-1b Radiance full disk)
- **File Size**: Approximately 70 MB per file
- **Access Method**: No-sign-request S3 bucket (public read)

## 2. Class Interfaces and Responsibilities

### TimeIndex (Enhanced Version)
Handles all timestamp pattern conversion and filename generation.

```python
class TimeIndex:
    """Enhanced utilities for GOES-16/18 Band 13 timestamp management."""

    # Constants
    BAND = 13                        # Hard-coded for Band 13
    CDN_RES = "5424x5424"            # Default resolution
    RECENT_WINDOW_DAYS = 7           # Window for CDN vs S3 decision

    # Satellite-specific constants - keys are SatellitePattern enum values
    SATELLITE_CODES = {
        SatellitePattern.GOES_16: "G16",
        SatellitePattern.GOES_18: "G18"
    }

    SATELLITE_NAMES = {
        SatellitePattern.GOES_16: "GOES16",
        SatellitePattern.GOES_18: "GOES18"
    }

    S3_BUCKETS = {
        SatellitePattern.GOES_16: "noaa-goes16",
        SatellitePattern.GOES_18: "noaa-goes18"
    }

    @staticmethod
    def to_cdn_url(ts: datetime, satellite: SatellitePattern, resolution: str = None) -> str:
        """
        Generate a CDN URL for the given timestamp and satellite.

        Args:
            ts: Datetime object for the image
            satellite: Satellite pattern (GOES_16 or GOES_18)
            resolution: Optional override for resolution (default is CDN_RES)

        Returns:
            Full CDN URL string
        """
        res = resolution or TimeIndex.CDN_RES
        year = ts.year
        doy = ts.strftime("%j")  # Day of year as string (001-366)
        hour = ts.strftime("%H")
        minute = ts.strftime("%M")

        # Get satellite name
        sat_name = TimeIndex.SATELLITE_NAMES.get(satellite)
        if not sat_name:
            raise ValueError(f"Unsupported satellite pattern: {satellite}")

        # Format: YYYYDDDHHMM_GOES16-ABI-FD-13-RESxRES.jpg or YYYYDDDHHMM_GOES18-ABI-FD-13-RESxRES.jpg
        filename = f"{year}{doy}{hour}{minute}_{sat_name}-ABI-FD-13-{res}.jpg"
        url = f"https://cdn.star.nesdis.noaa.gov/{sat_name}/ABI/FD/13/{filename}"
        return url

    @staticmethod
    def to_s3_key(ts: datetime, satellite: SatellitePattern) -> str:
        """
        Generate an S3 key for the given timestamp and satellite.

        Args:
            ts: Datetime object for the image
            satellite: Satellite pattern (GOES_16 or GOES_18)

        Returns:
            S3 key string (not including bucket name)
        """
        year = ts.year
        doy = ts.strftime("%j")  # Day of year
        hour = ts.strftime("%H")
        minute = ts.strftime("%M")

        # Get satellite code
        sat_code = TimeIndex.SATELLITE_CODES.get(satellite)
        if not sat_code:
            raise ValueError(f"Unsupported satellite pattern: {satellite}")

        # Format example:
        # ABI-L1b-RadF/2025/115/04/OR_ABI-L1b-RadF-M6C13_G16_s20251150420365_e20251150426132_c20251150426171.nc
        # Note: We use a wildcard pattern for the seconds part (SEQ) as it varies
        # and isn't needed for 10-minute-interval uniqueness
        base_key = f"ABI-L1b-RadF/{year}/{doy}/{hour}/"
        pattern = f"OR_ABI-L1b-RadF-M6C13_{sat_code}_s{year}{doy}{hour}{minute}*.nc"

        return base_key + pattern

    @staticmethod
    def get_s3_bucket(satellite: SatellitePattern) -> str:
        """
        Get the S3 bucket name for the given satellite.

        Args:
            satellite: Satellite pattern (GOES_16 or GOES_18)

        Returns:
            S3 bucket name
        """
        bucket = TimeIndex.S3_BUCKETS.get(satellite)
        if not bucket:
            raise ValueError(f"Unsupported satellite pattern: {satellite}")
        return bucket

    @staticmethod
    def generate_local_path(ts: datetime, satellite: SatellitePattern, base_dir: Path) -> Path:
        """
        Generate a local path for storing the image.

        Args:
            ts: Datetime object for the image
            satellite: Satellite pattern (GOES_16 or GOES_18)
            base_dir: Base directory for storage

        Returns:
            Path object for the local file
        """
        year = ts.year
        doy = ts.strftime("%j")  # Day of year
        hour = ts.strftime("%H")
        minute = ts.strftime("%M")

        # Get satellite name
        sat_name = TimeIndex.SATELLITE_NAMES.get(satellite)
        if not sat_name:
            raise ValueError(f"Unsupported satellite pattern: {satellite}")

        # Matches your current SatDump layout
        # {root}/{satellite}/FD/13/{YYYY}/{DDD}/
        dir_path = base_dir / sat_name / "FD" / "13" / str(year) / doy

        # Filename: YYYYDDDHHMM_GOES16-ABI-FD-13-5424x5424.png or YYYYDDDHHMM_GOES18-ABI-FD-13-5424x5424.png
        filename = f"{year}{doy}{hour}{minute}_{sat_name}-ABI-FD-13-5424x5424.png"

        return dir_path / filename

    @staticmethod
    def ts_from_filename(filename: str) -> Tuple[Optional[datetime], Optional[SatellitePattern]]:
        """
        Extract a timestamp and satellite from a filename.

        Args:
            filename: Filename to parse

        Returns:
            Tuple of (datetime object, satellite pattern) if successful, (None, None) otherwise
        """
        # Match pattern for GOES-16: YYYYDDDHHMM_GOES16-ABI-FD-13-*
        goes16_match = re.search(r"(\d{4})(\d{3})(\d{2})(\d{2})_GOES16-ABI-FD-13", filename)
        if goes16_match:
            year = int(goes16_match.group(1))
            doy = int(goes16_match.group(2))
            hour = int(goes16_match.group(3))
            minute = int(goes16_match.group(4))

            # Convert day of year to datetime
            jan1 = datetime(year, 1, 1)
            ts = jan1 + timedelta(days=doy-1, hours=hour, minutes=minute)

            return ts, SatellitePattern.GOES_16

        # Match pattern for GOES-18: YYYYDDDHHMM_GOES18-ABI-FD-13-*
        goes18_match = re.search(r"(\d{4})(\d{3})(\d{2})(\d{2})_GOES18-ABI-FD-13", filename)
        if goes18_match:
            year = int(goes18_match.group(1))
            doy = int(goes18_match.group(2))
            hour = int(goes18_match.group(3))
            minute = int(goes18_match.group(4))

            # Convert day of year to datetime
            jan1 = datetime(year, 1, 1)
            ts = jan1 + timedelta(days=doy-1, hours=hour, minutes=minute)

            return ts, SatellitePattern.GOES_18

        return None, None

    @staticmethod
    def is_recent(ts: datetime) -> bool:
        """
        Check if a timestamp is within the recent window (for CDN).

        Args:
            ts: Datetime object to check

        Returns:
            True if within recent window, False otherwise
        """
        now = datetime.now(ts.tzinfo or timezone.utc)
        delta = now - ts
        return delta.days < TimeIndex.RECENT_WINDOW_DAYS
```

### RemoteStore Base Interface

```python
class RemoteStore(ABC):
    """Abstract base class for remote data stores."""

    @abstractmethod
    async def exists(self, ts: datetime, satellite: SatellitePattern) -> bool:
        """
        Check if a file exists for the given timestamp and satellite.

        Args:
            ts: Datetime to check
            satellite: Satellite pattern (GOES_16 or GOES_18)

        Returns:
            True if the file exists, False otherwise
        """
        pass

    @abstractmethod
    async def download(self, ts: datetime, satellite: SatellitePattern, dest_path: Path) -> Path:
        """
        Download a file for the given timestamp and satellite.

        Args:
            ts: Datetime to download
            satellite: Satellite pattern (GOES_16 or GOES_18)
            dest_path: Destination path

        Returns:
            Path to the downloaded file
        """
        pass
```

### CDNStore Implementation

```python
class CDNStore(RemoteStore):
    """Store implementation for the NOAA STAR CDN."""

    def __init__(self, resolution: str = None, timeout: int = 10):
        """
        Initialize the CDN store.

        Args:
            resolution: Resolution to use (default from TimeIndex.CDN_RES)
            timeout: Request timeout in seconds
        """
        self.resolution = resolution or TimeIndex.CDN_RES
        self.timeout = timeout
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout))

    async def exists(self, ts: datetime, satellite: SatellitePattern) -> bool:
        """
        Check if a file exists in the CDN for the timestamp and satellite.

        Args:
            ts: Datetime to check
            satellite: Satellite pattern (GOES_16 or GOES_18)
        """
        url = TimeIndex.to_cdn_url(ts, satellite, self.resolution)

        try:
            async with self.session.head(url, allow_redirects=True) as response:
                return response.status == 200
        except Exception as e:
            LOGGER.error(f"Error checking CDN file existence: {e}")
            return False

    async def download(self, ts: datetime, satellite: SatellitePattern, dest_path: Path) -> Path:
        """
        Download a file from the CDN.

        Args:
            ts: Datetime to download
            satellite: Satellite pattern (GOES_16 or GOES_18)
            dest_path: Destination path
        """
        url = TimeIndex.to_cdn_url(ts, satellite, self.resolution)

        # Ensure parent directory exists
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            # Download with progress tracking
            async with self.session.get(url, allow_redirects=True) as response:
                if response.status != 200:
                    raise Exception(f"CDN returned status {response.status}")

                # Create temporary file with .jpg extension
                temp_path = dest_path.with_suffix('.jpg.tmp')

                # Get content length for progress calculation
                total_size = int(response.headers.get('Content-Length', 0))
                downloaded = 0

                with open(temp_path, 'wb') as f:
                    async for chunk in response.content.iter_chunked(8192):
                        f.write(chunk)
                        downloaded += len(chunk)
                        # Progress could be reported here

                # Rename to final path with .png extension if needed
                if dest_path.suffix.lower() == '.png' and temp_path.suffix.lower() != '.png':
                    # Convert JPG to PNG (optional)
                    from PIL import Image
                    img = Image.open(temp_path)
                    img.save(dest_path)
                    temp_path.unlink()  # Remove temp file
                else:
                    # Just rename
                    temp_path.rename(dest_path)

                return dest_path

        except Exception as e:
            LOGGER.error(f"Error downloading from CDN: {e}")
            raise
```

### S3Store Implementation

```python
class S3Store(RemoteStore):
    """Store implementation for the NOAA GOES AWS S3 bucket."""

    def __init__(self, timeout: int = 60):
        """
        Initialize the S3 store.

        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout

        # Configure S3 client with unsigned requests (public bucket)
        self.s3_config = aioboto3.Session().get_config_resolver().get_configs()
        self.s3_config['signature_version'] = botocore.UNSIGNED

    async def exists(self, ts: datetime, satellite: SatellitePattern) -> bool:
        """
        Check if a file exists in S3 for the timestamp and satellite.

        Args:
            ts: Datetime to check
            satellite: Satellite pattern (GOES_16 or GOES_18)
        """
        key_pattern = TimeIndex.to_s3_key(ts, satellite)
        bucket_name = TimeIndex.get_s3_bucket(satellite)

        try:
            async with aioboto3.Session().resource('s3', config=self.s3_config) as s3:
                bucket = await s3.Bucket(bucket_name)

                # List objects with the key prefix to find matching files
                key_prefix = "/".join(key_pattern.split("/")[:-1]) + "/"

                objects = []
                async for obj in bucket.objects.filter(Prefix=key_prefix):
                    if fnmatch.fnmatch(obj.key, key_pattern):
                        return True

                return False

        except Exception as e:
            LOGGER.error(f"Error checking S3 file existence: {e}")
            return False

    async def download(self, ts: datetime, satellite: SatellitePattern, dest_path: Path) -> Path:
        """
        Download a NetCDF file from S3.

        Args:
            ts: Datetime to download
            satellite: Satellite pattern (GOES_16 or GOES_18)
            dest_path: Destination path
        """
        key_pattern = TimeIndex.to_s3_key(ts, satellite)
        bucket_name = TimeIndex.get_s3_bucket(satellite)

        # Ensure parent directory exists
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        # Create temp directory for NetCDF file
        temp_dir = Path(tempfile.mkdtemp(prefix="goes_nc_"))

        try:
            # Find the exact key
            async with aioboto3.Session().resource('s3', config=self.s3_config) as s3:
                bucket = await s3.Bucket(bucket_name)

                # List objects with the key prefix to find matching files
                key_prefix = "/".join(key_pattern.split("/")[:-1]) + "/"

                target_key = None
                async for obj in bucket.objects.filter(Prefix=key_prefix):
                    if fnmatch.fnmatch(obj.key, key_pattern):
                        target_key = obj.key
                        break

                if not target_key:
                    raise FileNotFoundError(f"No S3 object found matching {key_pattern}")

                # Download the NetCDF file
                nc_path = temp_dir / "temp.nc"
                object = await s3.Object(bucket_name, target_key)
                await object.download_file(str(nc_path))

                # Convert NetCDF to PNG
                from .render import netcdf_renderer
                await netcdf_renderer.render_png(nc_path, dest_path)

                # Clean up
                nc_path.unlink()
                temp_dir.rmdir()

                return dest_path

        except Exception as e:
            LOGGER.error(f"Error downloading from S3: {e}")
            # Clean up on error
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise
```

### NetCDF Renderer Implementation

```python
async def render_png(nc_path: Path, dest_png: Path) -> Path:
    """
    Extract Band-13 radiance from NetCDF, normalize, and save as PNG.

    Args:
        nc_path: Path to NetCDF file
        dest_png: Path to save PNG file

    Returns:
        Path to the saved PNG file
    """
    import xarray as xr
    import numpy as np
    from PIL import Image

    # Ensure output directory exists
    dest_png.parent.mkdir(parents=True, exist_ok=True)

    # Run in thread pool to avoid blocking event loop
    def _render():
        with xr.open_dataset(nc_path, chunks={}) as ds:
            # Extract the Rad variable (radiance data)
            rad = ds["Rad"].data

            # Convert to numpy array if it's a dask array
            rad = np.asarray(rad, dtype=np.float32)

            # Normalize to 0-255 range
            if rad.max() > 0:
                img8 = np.clip(rad / rad.max() * 255.0, 0, 255).astype(np.uint8)
            else:
                img8 = np.zeros_like(rad, dtype=np.uint8)

            # Save as PNG
            Image.fromarray(img8).save(dest_png, optimize=True)

            return dest_png

    # Run the CPU-intensive work in a thread pool
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _render)
```

## 3. Reconciler Enhancements

### Timestamp Partitioning

The enhanced Reconciler needs to partition missing timestamps into CDN and S3 categories:

```python
class Reconciler:
    """Enhanced Reconciler with hybrid fetching strategy."""

    async def reconcile(self, missing_timestamps: List[Tuple[datetime, SatellitePattern]]) -> Dict[str, Any]:
        """
        Process missing timestamps using the appropriate store.

        Args:
            missing_timestamps: List of (timestamp, satellite) tuples

        Returns:
            Dictionary with results
        """
        # Partition timestamps into recent (CDN) and historical (S3)
        recent_items = []
        historical_items = []

        for ts, satellite in missing_timestamps:
            if TimeIndex.is_recent(ts):
                recent_items.append((ts, satellite))
            else:
                historical_items.append((ts, satellite))

        # Create stores
        cdn_store = CDNStore(resolution=self.settings.get("cdn_resolution", TimeIndex.CDN_RES))
        s3_store = S3Store()

        # Process each group
        cdn_results = await self._process_batch(
            recent_items,
            cdn_store,
            max_concurrent=self.settings.get("cdn_max_threads", 8)
        )

        s3_results = await self._process_batch(
            historical_items,
            s3_store,
            max_concurrent=self.settings.get("s3_max_threads", 4)
        )

        # Combine results
        return {
            "cdn": cdn_results,
            "s3": s3_results,
            "total_fetched": cdn_results["success_count"] + s3_results["success_count"],
            "total_failed": cdn_results["failure_count"] + s3_results["failure_count"]
        }

    async def _process_batch(self,
                           items: List[Tuple[datetime, SatellitePattern]],
                           store: RemoteStore,
                           max_concurrent: int) -> Dict[str, Any]:
        """
        Process a batch of timestamp-satellite pairs with the given store.

        Args:
            items: List of (timestamp, satellite) tuples
            store: RemoteStore to use for downloads
            max_concurrent: Maximum concurrent downloads
        """
        if not items:
            return {"success_count": 0, "failure_count": 0, "results": []}

        # Check disk space if needed (especially for S3 store)
        if isinstance(store, S3Store):
            free_space = self._get_free_disk_space()
            required_space = len(items) * 100 * 1024 * 1024  # 100 MB per file

            if free_space < required_space:
                LOGGER.warning(f"Low disk space: {free_space/1024/1024:.1f} MB free, need ~{required_space/1024/1024:.1f} MB")
                # Could raise an exception or return early with an error

        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(max_concurrent)

        async def _download_with_limit(ts, satellite):
            async with semaphore:
                try:
                    # Generate the destination path
                    dest_path = TimeIndex.generate_local_path(ts, satellite, self.base_directory)

                    # Check if file already exists
                    if dest_path.exists():
                        return {
                            "timestamp": ts,
                            "satellite": satellite,
                            "success": True,
                            "path": dest_path,
                            "already_exists": True
                        }

                    # Download the file
                    await store.download(ts, satellite, dest_path)
                    return {
                        "timestamp": ts,
                        "satellite": satellite,
                        "success": True,
                        "path": dest_path,
                        "already_exists": False
                    }
                except Exception as e:
                    LOGGER.error(f"Error downloading {ts} for {satellite}: {e}")
                    return {
                        "timestamp": ts,
                        "satellite": satellite,
                        "success": False,
                        "error": str(e)
                    }

        # Process all timestamp-satellite pairs concurrently
        tasks = [_download_with_limit(ts, sat) for ts, sat in items]
        results = await asyncio.gather(*tasks)

        # Count successes and failures
        success_count = sum(1 for r in results if r["success"])
        failure_count = len(results) - success_count

        return {
            "success_count": success_count,
            "failure_count": failure_count,
            "results": results
        }
```

## 4. UI Enhancements

The Integrity Check tab UI should be enhanced with additional settings for the hybrid fetching functionality:

1. **CDN/S3 Settings Group**:
   - Recent window days (QSpinBox, default: 7)
   - CDN resolution (QComboBox, options: "339×339", "678×678", "1808×1808", "5424×5424", "10848×10848")
   - Keep NetCDF copies (QCheckBox, default: unchecked)

2. **Advanced Settings Dialog**:
   - CDN thread pool size (QSpinBox, default: 8)
   - S3 thread pool size (QSpinBox, default: 4)
   - Disk space warning threshold (QSpinBox, default: 1000 MB)

3. **Download Strategy Visualization**:
   - Add visual indicators in the Missing Timestamps table to show which source (CDN or S3) will be used

## 5. Dependencies

New dependencies required for the enhanced fetching functionality:

- **xarray**: For NetCDF file handling
- **netCDF4**: Backend for xarray
- **boto3** and **aioboto3**: AWS S3 access
- **aiohttp**: Asynchronous HTTP requests
- **pillow**: Image processing and conversion
- **qasync**: For integrating asyncio with Qt

These dependencies should be added to `pyproject.toml`.

## 6. Implementation Timeline

1. **Week 1**: Implement core TimeIndex enhancements and store interfaces
2. **Week 2**: Implement NetCDF renderer and S3Store
3. **Week 3**: Update Reconciler with partitioning logic and UI enhancements
4. **Week 4**: Testing, optimization, and documentation

## 7. Testing Methodology

1. **Unit Tests**:
   - TimeIndex URL/path generation
   - Timestamp extraction from filenames
   - Partitioning logic

2. **Integration Tests**:
   - CDN connectivity and download
   - S3 object discovery
   - NetCDF rendering

3. **End-to-End Tests**:
   - Full pipeline from scan to download
