"""
GOES Satellite Imagery Handler

This module provides functionality for downloading and processing GOES satellite imagery,
with support for both raw NetCDF data and pre-processed images.

Key features:
- Download pre-colorized imagery from NOAA
- Process single-channel data (with focus on IR channels)
- Support different processing modes (none, basic, advanced)
- Handle different product types (Full Disk, Mesoscale, CMIP, etc.)
"""

import logging
import os
from datetime import datetime, timedelta
from enum import Enum

# import numpy as np  # Uncomment when needed
from pathlib import Path
from typing import Optional, Union

import boto3
import botocore
import botocore.config
import requests

# Configure logging
logger = logging.getLogger(__name__)

# Constants
GOES_S3_BUCKET = "noaa-goes16"
GOES_IMAGE_BASE_URL = "https://cdn.star.nesdis.noaa.gov/GOES16/ABI"
DEFAULT_OUTPUT_DIR = Path("goes_imagery")


class ProductType(Enum):
    """GOES satellite product types."""

    FULL_DISK = "FULL_DISK"
    MESO1 = "MESO1"
    MESO2 = "MESO2"
    CMIP = "CMIP"
    RAIN_RATE = "RAIN_RATE"

    @classmethod
    def to_s3_prefix(cls, product_type: "ProductType") -> Optional[str]:
        """Convert product type to S3 bucket prefix."""
        mapping = {
            cls.FULL_DISK: "ABI-L1b-RadF",
            cls.MESO1: "ABI-L1b-RadM1",
            cls.MESO2: "ABI-L1b-RadM2",
            cls.CMIP: "ABI-L2-CMIPF",
            cls.RAIN_RATE: "ABI-L2-RRQPEF",
        }
        return mapping.get(product_type)

    @classmethod
    def to_web_path(cls, product_type: "ProductType") -> Optional[str]:
        """Convert product type to web image path."""
        mapping = {
            cls.FULL_DISK: "FD",
            cls.MESO1: "M1",
            cls.MESO2: "M2",
            cls.CMIP: "CMIPC",
            cls.RAIN_RATE: "RAMMB",  # Different source for rain rate
        }
        return mapping.get(product_type)


class ChannelType(Enum):
    """GOES satellite channel types with metadata."""

    CH01 = (1, "Blue (Visible)", "0.47 μm", "Aerosols, smoke, haze detection")
    CH02 = (2, "Red (Visible)", "0.64 μm", "Cloud, fog, insolation, winds")
    CH03 = (3, "Veggie (Near-IR)", "0.86 μm", "Vegetation, burn scar, aerosol, winds")
    CH04 = (4, "Cirrus (Near-IR)", "1.37 μm", "Cirrus cloud detection")
    CH05 = (
        5,
        "Snow/Ice (Near-IR)",
        "1.6 μm",
        "Cloud-top phase, snow/ice discrimination",
    )
    CH06 = (
        6,
        "Cloud Particle Size (Near-IR)",
        "2.2 μm",
        "Cloud particle size, snow cloud discrimination",
    )
    CH07 = (
        7,
        "Shortwave Window IR",
        "3.9 μm",
        "Fire detection, fog detection, night fog, winds",
    )
    CH08 = (
        8,
        "Upper-Level Water Vapor IR",
        "6.2 μm",
        "High-level moisture, winds, rainfall",
    )
    CH09 = (
        9,
        "Mid-Level Water Vapor IR",
        "6.9 μm",
        "Mid-level moisture, winds, rainfall",
    )
    CH10 = (
        10,
        "Lower-level Water Vapor IR",
        "7.3 μm",
        "Lower-level moisture, winds, rainfall",
    )
    CH11 = (11, "Cloud Top Phase IR", "8.4 μm", "Cloud-top phase, dust, SO2 detection")
    CH12 = (12, "Ozone IR", "9.6 μm", "Atmospheric total column ozone")
    CH13 = (
        13,
        "Clean Longwave Window IR",
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
    CH16 = (16, "CO2 Longwave IR", "13.3 μm", "Air temperature, cloud heights")
    TRUE_COLOR = (
        100,
        "True Color",
        "RGB",
        "Natural color composite of channels 1, 2, 3",
    )
    WATER_VAPOR = (
        101,
        "Water Vapor",
        "6.2/7.3/9.6 μm",
        "Atmospheric moisture at different levels",
    )
    IR_COMPOSITE = (102, "IR Composite", "10.3/11.2 μm", "Enhanced infrared imagery")

    def __init__(
        self, number: int, display_name: str, wavelength: str, description: str
    ) -> None:
        self.number = number
        self.display_name = display_name
        self.wavelength = wavelength
        self.description = description

    @classmethod
    def from_number(cls, number: int) -> Optional["ChannelType"]:
        """Get channel type from channel number."""
        for channel in cls:
            if channel.number == number:
                return channel
        return None

    @property
    def is_visible(self) -> bool:
        """Check if channel is in visible light spectrum."""
        return self.number in [1, 2, 3]

    @property
    def is_infrared(self) -> bool:
        """Check if channel is in infrared spectrum."""
        return self.number in [7, 8, 9, 10, 11, 12, 13, 14, 15, 16]

    @property
    def is_near_ir(self) -> bool:
        """Check if channel is in near-infrared spectrum."""
        return self.number in [4, 5, 6]

    @property
    def is_water_vapor(self) -> bool:
        """Check if channel is water vapor."""
        return self.number in [8, 9, 10]

    @property
    def is_composite(self) -> bool:
        """Check if channel is a composite."""
        # Explicitly cast to bool to fix mypy no-any-return error
        return bool(self.number >= 100)


class ProcessingMode(Enum):
    """Image processing modes."""

    NONE = "none"
    BASIC = "basic"
    ADVANCED = "advanced"


class ImageryMode(Enum):
    """Imagery source modes."""

    RAW_DATA = "raw_data"  # Process from raw NetCDF data
    IMAGE_PRODUCT = "image_product"  # Use pre-processed images


class GOESImageryDownloader:
    """Class for downloading GOES satellite imagery."""

    def __init__(
        self,
        satellite: str = "goes16",
        output_dir: Optional[Union[str, Path]] = None,
        cache: bool = True,
    ):
        """Initialize the downloader."""
        self.satellite = satellite
        self.output_dir = output_dir or DEFAULT_OUTPUT_DIR
        self.cache = cache

        # Create output directory if it doesn't exist
        os.makedirs(self.output_dir, exist_ok=True)

        # Create S3 client for raw data
        self.s3_client = boto3.client(
            "s3",
            config=botocore.config.Config(  # Use botocore.config.Config instead of boto3.session.Config
                signature_version=botocore.UNSIGNED, retries={"max_attempts": 5}
            ),
        )

    def download_precolorized_image(
        self,
        channel: ChannelType,
        product_type: ProductType,
        date: Optional[datetime] = None,
        size: str = "1200",
    ) -> Optional[Path]:
        """
        Download a pre-processed, colorized image from NOAA.

        Args:
            channel: The channel to download
            product_type: The product type (Full Disk, Mesoscale, etc.)
            date: The date to download (defaults to latest)
            size: Image size (600, 1200, 2400, etc.)

        Returns:
            Path to the downloaded image or None if download failed
        """
        # Use current date if not specified
        if date is None:
            date = datetime.utcnow()

        # Determine image URL based on channel and product type
        web_path = ProductType.to_web_path(product_type)

        # Handle composite channels differently
        if channel.is_composite:
            if channel == ChannelType.TRUE_COLOR:
                url_suffix = f"{size}x{size}.jpg"
                url_channel = "GEOCOLOR"
            elif channel == ChannelType.WATER_VAPOR:
                url_suffix = f"{size}x{size}.jpg"
                url_channel = "08"
            elif channel == ChannelType.IR_COMPOSITE:
                url_suffix = f"{size}x{size}.jpg"
                url_channel = "13"
            else:
                logger.error("Unsupported composite channel: %s", channel)
                return None
        else:
            url_suffix = f"{size}x{size}.jpg"
            url_channel = f"{channel.number:02d}"

        # Construct URL
        url = f"{GOES_IMAGE_BASE_URL}/{web_path}/latest/{url_channel}_{url_suffix}"

        logger.info("Downloading pre-colorized image from: %s", url)

        # Create filename
        timestamp = date.strftime("%Y%m%d_%H%M%S")
        filename = f"{product_type.name.lower()}_{channel.display_name.lower().replace(' ', '_')}_{timestamp}.jpg"
        output_path = Path(self.output_dir) / filename

        # Check cache
        if self.cache and output_path.exists():
            logger.info("Using cached image: %s", output_path)
            return output_path

        # Download the image
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            with open(output_path, "wb") as f:
                f.write(response.content)

            logger.info("Downloaded image to: %s", output_path)
            return output_path
        except Exception as e:
            logger.error("Error downloading image: %s", e)
            return None

    def find_raw_data(
        self,
        channel: ChannelType,
        product_type: ProductType,
        date: Optional[datetime] = None,
        hour: Optional[int] = None,
    ) -> Optional[str]:
        """
        Find raw NetCDF data in S3 bucket.

        Args:
            channel: The channel to find
            product_type: The product type
            date: The date to search for
            hour: Specific hour to search

        Returns:
            S3 key for the file or None if not found
        """
        # Use current date if not specified
        if date is None:
            date = datetime.utcnow()

        # Get day of year
        day_of_year = date.timetuple().tm_yday

        # Get S3 prefix
        prefix = ProductType.to_s3_prefix(product_type)
        if not prefix:
            logger.error("Invalid product type: %s", product_type)
            return None

        # Build search prefix
        search_prefix = f"{prefix}/{date.year}/{day_of_year:03d}"
        if hour is not None:
            search_prefix += f"/{hour:02d}"

        logger.info("Searching for raw data in: %s", search_prefix)

        try:
            # List objects with the given prefix
            response = self.s3_client.list_objects_v2(
                Bucket=GOES_S3_BUCKET, Prefix=search_prefix, MaxKeys=100
            )

            if "Contents" not in response:
                logger.warning("No files found for %s", search_prefix)
                return None

            # Filter by channel if needed
            matching_files = []

            for obj in response["Contents"]:
                file_key = obj["Key"]

                # Skip non-NetCDF files
                if not file_key.endswith(".nc"):
                    continue

                # Filter by channel
                if channel.is_composite:
                    # For composites, we need multiple files
                    # This is handled separately
                    continue
                elif channel.number > 0:
                    # Check for channel pattern in filename
                    channel_pattern = f"C{channel.number:02d}_"
                    if channel_pattern not in file_key:
                        continue

                matching_files.append(file_key)

            if not matching_files:
                logger.warning("No matching files found for %s", channel)
                return None

            # Sort by name and return the latest
            matching_files.sort()
            # Explicitly cast to str to fix mypy no-any-return error
            return str(matching_files[-1]) if matching_files else None

        except Exception as e:
            logger.error("Error searching for raw data: %s", e)
            return None

    def download_raw_data(self, file_key: str) -> Optional[Path]:
        """
        Download raw NetCDF data from S3 bucket.

        Args:
            file_key: S3 key for the file

        Returns:
            Path to the downloaded file or None if download failed
        """
        # Create output filename
        filename = os.path.basename(file_key)
        output_path = Path(self.output_dir) / filename

        # Check cache
        if self.cache and output_path.exists():
            logger.info("Using cached file: %s", output_path)
            return output_path

        logger.info("Downloading raw data: %s", file_key)

        try:
            self.s3_client.download_file(
                Bucket=GOES_S3_BUCKET, Key=file_key, Filename=str(output_path)
            )

            logger.info("Downloaded file to: %s", output_path)
            return output_path
        except Exception as e:
            logger.error("Error downloading file: %s", e)
            return None


class GOESImageProcessor:
    """Class for processing GOES satellite imagery."""

    def __init__(
        self,
        mode: ProcessingMode = ProcessingMode.BASIC,
        output_dir: Optional[Union[str, Path]] = None,
    ):
        """Initialize the processor."""
        self.mode = mode
        self.output_dir = output_dir or DEFAULT_OUTPUT_DIR

        # Create output directory if it doesn't exist
        os.makedirs(self.output_dir, exist_ok=True)

    def process_raw_data(
        self, file_path: Path, channel: ChannelType, resolution: Optional[int] = None
    ) -> Optional[Path]:
        """
        Process raw NetCDF data into an image.

        Args:
            file_path: Path to NetCDF file
            channel: Channel type
            resolution: Output resolution (defaults to half of native)

        Returns:
            Path to processed image or None if processing failed
        """
        logger.info("Processing raw data: %s", file_path)

        # Create output filename
        timestamp = self._extract_timestamp_from_filename(file_path.name)
        filename = f"processed_{channel.name.lower().replace(' ', '_')}_{timestamp}.png"
        output_path = Path(self.output_dir) / filename

        # Process data based on mode
        try:
            # For simplicity, we'll use a basic processing approach here
            # In a real implementation, you would use xarray, satpy, etc.
            if self.mode == ProcessingMode.NONE:
                logger.info("No processing requested, skipping")
                return None
            elif self.mode == ProcessingMode.BASIC:
                # Example: call a basic processing function
                success = self._basic_processing(
                    file_path, output_path, channel, resolution
                )
            elif self.mode == ProcessingMode.ADVANCED:
                # Example: call an advanced processing function
                success = self._advanced_processing(
                    file_path, output_path, channel, resolution
                )
            else:
                logger.error("Invalid processing mode: %s", self.mode)
                return None

            if success:
                logger.info("Processed image saved to: %s", output_path)
                return output_path
            else:
                logger.error("Processing failed")
                return None
        except Exception as e:
            logger.error("Error processing raw data: %s", e)
            return None

    def _basic_processing(
        self,
        input_path: Path,
        output_path: Path,
        channel: ChannelType,
        resolution: Optional[int] = None,
    ) -> bool:
        """Basic image processing."""
        logger.info("Applying basic processing to %s", input_path)

        try:
            # In a real implementation, this would use xarray, etc.
            # For now, we'll just log what would happen
            logger.info(
                "Would process %s data at resolution %s", channel.name, resolution
            )
            logger.info("Would save output to %s", output_path)

            # Placeholder - in real implementation, we would:
            # 1. Read NetCDF data
            # 2. Apply basic scaling/normalization
            # 3. Convert to image and save

            # For testing, create a dummy image
            with open(output_path, "w") as f:
                f.write("Placeholder for processed image")

            return True
        except Exception as e:
            logger.error("Error in basic processing: %s", e)
            return False

    def _advanced_processing(
        self,
        input_path: Path,
        output_path: Path,
        channel: ChannelType,
        resolution: Optional[int] = None,
    ) -> bool:
        """Advanced image processing."""
        logger.info("Applying advanced processing to %s", input_path)

        try:
            # In a real implementation, this would use satpy, etc.
            # For now, we'll just log what would happen
            logger.info("Would apply advanced processing to %s data", channel.name)
            logger.info("Would use atmospheric correction, enhancement, etc.")
            logger.info("Would save output to %s", output_path)

            # Placeholder - in real implementation, we would:
            # 1. Use satpy to read and process data
            # 2. Apply advanced corrections and enhancements
            # 3. Save as image

            # For testing, create a dummy image
            with open(output_path, "w") as f:
                f.write("Placeholder for advanced processed image")

            return True
        except Exception as e:
            logger.error("Error in advanced processing: %s", e)
            return False

    def _extract_timestamp_from_filename(self, filename: str) -> str:
        """Extract timestamp from filename."""
        # Example filename: OR_ABI-L1b-RadF-M6C13_G16_s20233001550210_e20233001559530_c20233001559577.nc
        if "_s" in filename:
            timestamp_part = filename.split("_s")[1][:13]  # Format: YYYYDDDHHMMSS
            year_str = timestamp_part[:4]
            doy_str = timestamp_part[4:7]
            hour_str = timestamp_part[7:9]
            min_str = timestamp_part[9:11]
            sec_str = timestamp_part[11:13]

            # Convert to datetime
            base_date = datetime(int(year_str), 1, 1)
            date_time = base_date + timedelta(
                days=int(doy_str) - 1,
                hours=int(hour_str),
                minutes=int(min_str),
                seconds=int(sec_str),
            )
            return date_time.strftime("%Y%m%d_%H%M%S")
        return datetime.now().strftime("%Y%m%d_%H%M%S")


class GOESImageryManager:
    """Manager class for GOES satellite imagery."""

    def __init__(
        self,
        satellite: str = "goes16",
        output_dir: Optional[Path] = None,
        cache: bool = True,
        default_mode: ImageryMode = ImageryMode.IMAGE_PRODUCT,
        default_processing: ProcessingMode = ProcessingMode.BASIC,
    ):
        """
        Initialize the GOES imagery manager.

        Args:
            satellite: Satellite identifier (goes16/goes18)
            output_dir: Directory for storing output files, defaults to user's downloads
            cache: Whether to cache downloaded files
            default_mode: Default imagery mode
            default_processing: Default processing mode
        """
        self.satellite = satellite
        self.output_dir = output_dir or DEFAULT_OUTPUT_DIR
        self.cache = cache
        self.default_mode = default_mode
        self.default_processing = default_processing

        # Create components
        self.downloader = GOESImageryDownloader(
            satellite=satellite, output_dir=output_dir, cache=cache
        )

        self.processor = GOESImageProcessor(
            mode=default_processing, output_dir=output_dir
        )

    def get_imagery(
        self,
        channel: Union[ChannelType, int],
        product_type: ProductType,
        date: Optional[datetime] = None,
        mode: Optional[ImageryMode] = None,
        processing: Optional[ProcessingMode] = None,
        resolution: Optional[int] = None,
        size: str = "1200",
    ) -> Optional[Path]:
        """
        Get satellite imagery based on specified parameters.

        Args:
            channel: Channel to retrieve
            product_type: Product type
            date: Date to retrieve (default: latest)
            mode: Imagery mode (default: from instance)
            processing: Processing mode (default: from instance)
            resolution: Output resolution for raw data processing
            size: Image size for pre-processed images

        Returns:
            Path to the image file or None if retrieval failed
        """
        # Convert channel if needed
        channel_obj: Optional[ChannelType] = (
            channel if isinstance(channel, ChannelType) else None
        )
        if isinstance(channel, int):
            channel_obj = ChannelType.from_number(channel)
            if channel_obj is None:
                logger.error("Invalid channel number: %s", channel)
                return None

        # Ensure we have a valid ChannelType object
        if channel_obj is None:
            logger.error("Invalid channel type: %s", type(channel).__name__)
            return None

        # Use defaults if not specified
        mode = mode or self.default_mode
        processing = processing or self.default_processing

        # Get imagery based on mode
        if mode == ImageryMode.IMAGE_PRODUCT:
            # Use pre-processed imagery
            return self.downloader.download_precolorized_image(
                channel=channel_obj, product_type=product_type, date=date, size=size
            )
        elif mode == ImageryMode.RAW_DATA:
            # Process from raw data
            # First find the data
            file_key = self.downloader.find_raw_data(
                channel=channel_obj, product_type=product_type, date=date
            )

            if not file_key:
                # Handle case where channel_obj might be an int (even though we've tried to convert it)
                channel_name = getattr(channel_obj, "name", f"Channel {channel_obj}")
                logger.error(
                    "No raw data found for %s, %s", channel_name, product_type.name
                )
                return None

            # Download the data
            file_path = self.downloader.download_raw_data(file_key)

            if not file_path:
                logger.error("Failed to download raw data")
                return None

            # Process the data
            return self.processor.process_raw_data(
                file_path=file_path, channel=channel_obj, resolution=resolution
            )
        else:
            logger.error("Invalid imagery mode: %s", mode)
            return None


# Example usage
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(level=logging.INFO)

    # Create manager
    manager = GOESImageryManager()

    # Get pre-processed imagery
    image_path = manager.get_imagery(
        channel=ChannelType.CH13,
        product_type=ProductType.FULL_DISK,
        mode=ImageryMode.IMAGE_PRODUCT,
    )

    print(f"Image downloaded to: {image_path}")
