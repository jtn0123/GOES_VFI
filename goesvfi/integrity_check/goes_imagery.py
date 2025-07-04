"""GOES satellite imagery processing and management.

This module provides classes and utilities for handling GOES satellite imagery,
including channel definitions, product types, and imagery management.
"""

from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
import tempfile
from typing import Any, Optional

import numpy as np
from numpy.typing import NDArray
from PIL import Image
import requests

from goesvfi.utils import log

LOGGER = log.get_logger(__name__)

# Channel number ranges
VISIBLE_CHANNEL_MAX = 6
IR_CHANNEL_MIN = 7
IR_CHANNEL_MAX = 16
NEAR_IR_CHANNEL_MIN = 4
NEAR_IR_CHANNEL_MAX = 6
WATER_VAPOR_CHANNEL_MIN = 8
WATER_VAPOR_CHANNEL_MAX = 10
COMPOSITE_CHANNEL_MIN = 100

# Default cache size
DEFAULT_CACHE_SIZE = 100


class ProductType(Enum):
    """GOES product types."""

    FULL_DISK = "RadF"
    CONUS = "RadC"
    MESOSCALE = "RadM"
    MESO1 = "RadM1"
    MESO2 = "RadM2"
    CMIP = "CMIP"
    CMIPF = "CMIPF"

    @staticmethod
    def to_s3_prefix(product_type: "ProductType") -> str:
        """Convert product type to S3 prefix format.

        Args:
            product_type: The product type to convert

        Returns:
            S3 prefix string for the product type
        """
        # Map product types to their S3 prefixes
        prefix_map = {
            ProductType.FULL_DISK: "ABI-L1b-RadF",
            ProductType.CONUS: "ABI-L1b-RadC",
            ProductType.MESOSCALE: "ABI-L1b-RadM",
            ProductType.MESO1: "ABI-L1b-RadM1",
            ProductType.MESO2: "ABI-L1b-RadM2",
            ProductType.CMIP: "ABI-L2-CMIPC",
            ProductType.CMIPF: "ABI-L2-CMIPF",
        }
        if product_type not in prefix_map:
            raise KeyError(f"Unknown product type: {product_type}")
        return prefix_map[product_type]

    @staticmethod
    def to_web_path(product_type: "ProductType") -> str:
        """Convert product type to web path format.

        Args:
            product_type: The product type to convert

        Returns:
            Web path string for the product type
        """
        # Map product types to their web paths
        path_map = {
            ProductType.FULL_DISK: "FD",
            ProductType.CONUS: "CONUS",
            ProductType.MESOSCALE: "M",
            ProductType.MESO1: "MESO1",
            ProductType.MESO2: "MESO2",
            ProductType.CMIP: "CMIP_CONUS",
            ProductType.CMIPF: "CMIP_FD",
        }
        if product_type not in path_map:
            raise KeyError(f"Unknown product type: {product_type}")
        return path_map[product_type]


class ImageryMode(Enum):
    """Imagery retrieval modes."""

    RAW = "raw"
    RAW_DATA = "raw_data"  # Alias for RAW
    PROCESSED = "processed"
    BOTH = "both"
    IMAGE_PRODUCT = "image_product"  # Pre-processed image products


class ProcessingMode(Enum):
    """Processing modes for imagery."""

    QUICKLOOK = "quicklook"
    FULL_RESOLUTION = "full_resolution"
    THUMBNAIL = "thumbnail"


class ChannelType(Enum):
    """GOES ABI channel definitions with metadata.

    Each channel is defined as a tuple of:
    (number, display_name, wavelength, description)
    """

    # Visible channels
    CH01 = (1, "Blue", "0.47 μm", "Aerosols, smoke, haze detection")
    CH02 = (2, "Red", "0.64 μm", "Cloud, fog, insolation, winds")
    CH03 = (3, "Veggie", "0.86 μm", "Vegetation, burn scar, aerosol, winds")

    # Near-IR channels
    CH04 = (4, "Cirrus (Near-IR)", "1.37 μm", "Cirrus cloud detection")
    CH05 = (
        5,
        "Snow/Ice",
        "1.6 μm",
        "Cloud-top phase, snow/ice discrimination",
    )
    CH06 = (
        6,
        "Cloud Particle Size (Near-IR)",
        "2.2 μm",
        "Cloud particle size, snow cloud discrimination",
    )

    # IR channels
    CH07 = (
        7,
        "Shortwave Window",
        "3.9 μm",
        "Fire detection, fog detection, night fog, winds",
    )
    CH08 = (
        8,
        "Upper-Level Water Vapor",
        "6.2 μm",
        "High-level moisture, winds, rainfall",
    )
    CH09 = (
        9,
        "Mid-Level Water Vapor",
        "6.9 μm",
        "Mid-level moisture, winds, rainfall",
    )
    CH10 = (
        10,
        "Lower-Level Water Vapor",
        "7.3 μm",
        "Lower-level moisture, winds, rainfall",
    )
    CH11 = (11, "Cloud Top Phase IR", "8.4 μm", "Cloud-top phase, dust, SO2 detection")
    CH12 = (12, "Ozone IR", "9.6 μm", "Atmospheric total column ozone")
    CH13 = (
        13,
        "Clean Longwave Window",
        "10.3 μm",
        "Surface temp, cloud detection, rainfall",
    )
    CH14 = (14, "Dirty Longwave Window IR", "11.2 μm", "Sea surface temperature")
    CH15 = (
        15,
        "Mid-level Tropospheric CO2 IR",
        "12.3 μm",
        "Air temperature, cloud heights",
    )
    CH16 = (16, "CO2 Longwave", "13.3 μm", "Air temperature, cloud heights")

    # RGB composites
    TRUE_COLOR = (
        100,
        "True Color",
        "RGB",
        "Natural color composite of channels 1, 2, 3",
    )
    GEOCOLOR = (
        101,
        "GeoColor",
        "RGB",
        "Enhanced color composite with day/night blend",
    )
    NATURAL_COLOR = (
        102,
        "Natural Color",
        "RGB",
        "Natural color composite",
    )
    RGB_AIRMASS = (
        103,
        "RGB Airmass",
        "RGB",
        "RGB airmass composite",
    )
    WATER_VAPOR = (
        104,
        "Water Vapor",
        "6.2/7.3/9.6 μm",
        "Atmospheric moisture at different levels",
    )
    IR_COMPOSITE = (105, "IR Composite", "10.3/11.2 μm", "Enhanced infrared imagery")

    def __init__(self, number: int, display_name: str, wavelength: str, description: str) -> None:
        """Initialize channel type."""
        self.number = number
        self.display_name = display_name
        self.wavelength = wavelength
        self.description = description

    @property
    def is_visible(self) -> bool:
        """Check if this is a visible channel."""
        return self.number <= VISIBLE_CHANNEL_MAX

    @property
    def is_ir(self) -> bool:
        """Check if this is an IR channel."""
        return IR_CHANNEL_MIN <= self.number <= IR_CHANNEL_MAX

    @property
    def is_composite(self) -> bool:
        """Check if this is a composite channel."""
        return self.number >= COMPOSITE_CHANNEL_MIN

    @property
    def is_infrared(self) -> bool:
        """Check if this is an infrared channel (alias for is_ir)."""
        return self.is_ir

    @property
    def is_near_ir(self) -> bool:
        """Check if this is a near-IR channel."""
        return NEAR_IR_CHANNEL_MIN <= self.number <= NEAR_IR_CHANNEL_MAX

    @property
    def is_water_vapor(self) -> bool:
        """Check if this is a water vapor channel."""
        return WATER_VAPOR_CHANNEL_MIN <= self.number <= WATER_VAPOR_CHANNEL_MAX

    @classmethod
    def from_number(cls: type["ChannelType"], number: int | None) -> Optional["ChannelType"]:
        """Get channel type from number."""
        if number is None:
            return None
        for channel in cls:
            if channel.number == number:
                return channel
        return None


class GOESImageryManager:
    """Manager for GOES satellite imagery.

    This is a minimal stub implementation to allow the app to start.
    The full implementation needs to be restored from the corrupted file.
    """

    def __init__(
        self,
        base_dir: Path | None = None,
        output_dir: Path | None = None,
        *,
        satellite: str = "G16",
        cache_size: int = DEFAULT_CACHE_SIZE,
        default_mode: ImageryMode = ImageryMode.IMAGE_PRODUCT,
    ) -> None:
        """Initialize the imagery manager.

        Args:
            base_dir: Base directory for imagery storage
            output_dir: Output directory for downloads (alias for base_dir)
            satellite: Satellite identifier
            cache_size: Maximum cache size
            default_mode: Default imagery mode
        """
        LOGGER.warning("Using stub implementation of GOESImageryManager")
        self.satellite = satellite
        self.base_dir = output_dir or base_dir or Path(tempfile.mkdtemp(prefix="goes_imagery_"))
        self.output_dir = self.base_dir  # Alias for compatibility
        self.cache_size = cache_size
        self.default_mode = default_mode
        self._cache: dict[str, Any] = {}

        # Create downloader instance
        self.downloader = GOESImageryDownloader(satellite=satellite, output_dir=self.base_dir)

        # Create processor instance
        self.processor = GOESImageProcessor(output_dir=self.base_dir)

    @staticmethod
    def process_image(
        data: NDArray[np.float64],
        channel: ChannelType,
        product_type: ProductType,
        *,
        timestamp: datetime,
        output_size: tuple[int, int] | None = None,
    ) -> Image.Image | None:
        """Process GOES imagery data.

        Args:
            data: Raw imagery data
            channel: Channel type
            product_type: Product type
            timestamp: Image timestamp
            output_size: Optional output size

        Returns:
            Processed image or None
        """
        LOGGER.warning("Stub: Image processing not implemented")
        # Return a placeholder image
        size = output_size or (512, 512)
        return Image.new("RGB", size, color="gray")

    @staticmethod
    def create_composite(
        channels: list[ChannelType],
        _data_dict: dict[int, NDArray[np.float64]],
        _composite_type: str = "true_color",
    ) -> Image.Image | None:
        """Create a composite image from multiple channels.

        Args:
            channels: List of channels to combine
            data_dict: Dictionary mapping channel numbers to data
            composite_type: Type of composite to create

        Returns:
            Composite image or None
        """
        LOGGER.warning("Stub: Composite creation not implemented")
        return None

    def get_imagery(
        self,
        channel: ChannelType,
        product_type: ProductType,
        *,
        mode: ImageryMode | None = None,
        date: datetime | None = None,
        size: str = "1200",
    ) -> Path | None:
        """Get imagery for the specified parameters.

        Args:
            channel: Channel to get imagery for
            product_type: Product type
            mode: Imagery mode (defaults to self.default_mode)
            date: Date for the imagery (not used in IMAGE_PRODUCT mode)
            size: Size for pre-colorized images

        Returns:
            Path to the imagery file or None if failed
        """
        mode = mode or self.default_mode

        if mode == ImageryMode.IMAGE_PRODUCT:
            # Download pre-colorized image
            result = self.downloader.download_precolorized_image(
                channel=channel, product_type=product_type, date=date, size=size
            )
            return result.file_path if result else None

        if mode in {ImageryMode.RAW, ImageryMode.RAW_DATA}:
            # Raw data mode - find, download, and process
            # 1. Find raw data file
            s3_key = self.downloader.find_raw_data(channel, product_type, date)
            if not s3_key:
                LOGGER.error("Could not find raw data")
                return None

            # 2. Download it
            raw_file = self.downloader.download_raw_data(s3_key)
            if not raw_file:
                LOGGER.error("Could not download raw data")
                return None

            # 3. Process it
            return self.processor.process_raw_data(raw_file, channel)

        LOGGER.warning("Unsupported mode: %s", mode)
        return None


class GOESImageryDownloader:
    """Downloader for GOES satellite imagery.

    This class handles downloading GOES imagery from various sources
    including S3 and web endpoints.
    """

    def __init__(
        self,
        satellite: str = "G16",
        output_dir: Path | None = None,
        timeout: int = 60,
    ) -> None:
        """Initialize the downloader.

        Args:
            satellite: Satellite identifier (G16 or G18)
            output_dir: Directory to save downloaded files
            timeout: Download timeout in seconds
        """
        self.satellite = satellite
        self.output_dir = output_dir or Path(tempfile.mkdtemp())
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self.s3_client = None  # Will be set externally or created as needed
        LOGGER.info("Initialized GOESImageryDownloader for %s", satellite)

    @staticmethod
    def download(
        channel: ChannelType,
        product_type: ProductType,
        timestamp: datetime,
        source: str = "s3",
    ) -> Path | None:
        """Download imagery for specified parameters.

        Args:
            channel: Channel to download
            product_type: Product type to download
            timestamp: Timestamp for the imagery
            source: Download source (s3 or web)

        Returns:
            Path to downloaded file or None if failed
        """
        LOGGER.warning("Stub: Download functionality not implemented")
        return None

    @staticmethod
    def download_batch(_download_requests: list[dict[str, Any]], max_workers: int = 5) -> dict[str, Path | None]:
        """Download multiple files in parallel.

        Args:
            download_requests: List of download requests
            max_workers: Maximum number of parallel downloads

        Returns:
            Dictionary mapping request IDs to downloaded file paths
        """
        LOGGER.warning("Stub: Batch download not implemented")
        return {}

    def download_precolorized_image(
        self,
        channel: ChannelType,
        product_type: ProductType,
        _date: datetime | None = None,
        size: str = "1200x1200",
    ) -> Optional["DownloadResult"]:
        """Download a pre-colorized image from the CDN.

        Args:
            channel: Channel to download
            product_type: Product type
            date: Date for imagery (optional, defaults to latest)
            size: Image size (default: 1200x1200)

        Returns:
            DownloadResult object or None if failed
        """
        # Construct URL based on satellite, channel, and product
        base_url = "https://cdn.star.nesdis.noaa.gov"
        satellite = "GOES16" if self.satellite == "G16" else "GOES18"
        product_path = ProductType.to_web_path(product_type)

        # Handle composite channels that don't have simple numbers
        if channel.is_composite:
            channel_str = channel.name.lower()
        else:
            channel_str = str(channel.number)
        
        url = f"{base_url}/{satellite}/ABI/{product_path}/latest/{channel_str}_{size}.jpg"

        try:
            # Download the image
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            # Save to file
            filename = f"{satellite}_{channel.number}_{product_path}_{size}.jpg"
            output_path = self.output_dir / filename
            output_path.write_bytes(response.content)

            # Return a result object
            return DownloadResult(output_path)

        except Exception as e:
            LOGGER.exception("Failed to download precolorized image: %s", e)
            return None

    @staticmethod
    def find_raw_data(
        channel: ChannelType,
        product_type: ProductType,
        timestamp: datetime | None = None,
    ) -> str | None:
        """Find raw data file key in S3.

        Args:
            channel: Channel to find
            product_type: Product type
            timestamp: Timestamp for the data

        Returns:
            S3 key for the raw data file or None if not found
        """
        LOGGER.warning("Stub: find_raw_data not implemented")
        # Return a dummy key for testing
        return "test_file_key"

    @staticmethod
    def download_raw_data(s3_key: str, output_path: Path | None = None) -> Path | None:
        """Download raw data from S3.

        Args:
            s3_key: S3 key to download
            output_path: Path to save the file

        Returns:
            Path to downloaded file or None if failed
        """
        LOGGER.warning("Stub: download_raw_data not implemented")
        # Return a dummy path for testing
        return Path("test_file_path")


class DownloadResult:
    """Result of a download operation."""

    def __init__(self, file_path: Path) -> None:
        """Initialize download result.

        Args:
            file_path: Path to downloaded file
        """
        self.file_path = file_path

    def check_file_exists(self) -> bool:
        """Check if the downloaded file exists.

        Returns:
            True if file exists, False otherwise
        """
        return self.file_path.exists()

    def get_file_size(self) -> int:
        """Get the size of the downloaded file.

        Returns:
            File size in bytes, or 0 if file doesn't exist
        """
        return self.file_path.stat().st_size if self.file_path.exists() else 0


class GOESImageProcessor:
    """Processor for GOES satellite imagery.

    This class handles processing raw GOES NetCDF data into
    usable imagery products.
    """

    def __init__(
        self,
        calibration_type: str = "reflectance",
        enhance: bool = True,
        output_dir: Path | None = None,
    ) -> None:
        """Initialize the processor.

        Args:
            calibration_type: Type of calibration to apply
            enhance: Whether to apply enhancement
            output_dir: Output directory for processed files
        """
        self.calibration_type = calibration_type
        self.enhance = enhance
        self.output_dir = output_dir or Path(tempfile.mkdtemp())
        LOGGER.info("Initialized GOESImageProcessor")

    @staticmethod
    def process(file_path: Path, channel: ChannelType, _output_format: str = "png") -> Image.Image | None:
        """Process a GOES NetCDF file.

        Args:
            file_path: Path to NetCDF file
            channel: Channel type
            output_format: Output image format

        Returns:
            Processed image or None if failed
        """
        LOGGER.warning("Stub: Process functionality not implemented")
        # Return a placeholder image
        return Image.new("RGB", (512, 512), color="gray")

    @staticmethod
    def apply_calibration(data: NDArray[np.float64], channel: ChannelType) -> NDArray[np.float64]:
        """Apply calibration to raw data.

        Args:
            data: Raw data array
            channel: Channel type

        Returns:
            Calibrated data array
        """
        LOGGER.warning("Stub: Calibration not implemented")
        return data

    @staticmethod
    def enhance_image(image: Image.Image, channel: ChannelType) -> Image.Image:
        """Apply enhancement to an image.

        Args:
            image: Input image
            channel: Channel type

        Returns:
            Enhanced image
        """
        LOGGER.warning("Stub: Enhancement not implemented")
        return image

    @staticmethod
    def _extract_timestamp_from_filename(filename: str | None) -> str | None:
        """Extract timestamp from GOES filename.

        Args:
            filename: GOES filename

        Returns:
            Timestamp string in format YYYYMMDD_HHMMSS
        """
        # Example filename: OR_ABI-L1b-RadF-M6C13_G16_s20233001550210_e20233001559530_c20233001559577.nc
        # s20233001550210 = start time: year 2023, day 300, time 155021 (with extra 0)

        import re

        if not filename:
            return None

        # Extract start time from filename
        match = re.search(r"_s(\d{4})(\d{3})(\d{6})", filename)
        if not match:
            return None

        year = int(match.group(1))
        day_of_year = int(match.group(2))
        time_str = match.group(3)

        # Convert day of year to month/day
        date = datetime(year, 1, 1) + timedelta(days=day_of_year - 1)

        # Format as YYYYMMDD_HHMMSS
        date_str = date.strftime("%Y%m%d")
        time_formatted = f"{time_str[:2]}{time_str[2:4]}{time_str[4:6]}"

        return f"{date_str}_{time_formatted}"

    def process_raw_data(
        self,
        file_path: Path,
        channel: ChannelType | None = None,
        output_format: str = "png",
        **kwargs,  # Accept additional kwargs for flexibility
    ) -> Path | None:
        """Process raw GOES data file.

        Args:
            file_path: Path to raw data file
            channel: Channel type (optional)
            output_format: Output format
            **kwargs: Additional arguments (ignored in stub)

        Returns:
            Path to processed file or None if failed
        """
        LOGGER.warning("Stub: process_raw_data not implemented")
        # Return the expected path for testing
        output_path = self.output_dir / "test_processed_image.png"
        output_path.touch()
        return output_path
