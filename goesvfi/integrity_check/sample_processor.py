"""
GOES Satellite Imagery Sample Processor

This module provides functionality for downloading and processing sample GOES satellite imagery,
allowing users to preview and compare different processing options before committing to full processing.
"""

import os
import logging
import tempfile
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Union, Any, cast
import numpy as np
from numpy.typing import NDArray
from PIL import Image, ImageDraw, ImageFont
import requests
import boto3
import botocore
import xarray as xr

from .goes_imagery import ChannelType, ProductType, ProcessingMode, ImageryMode
from .visualization_manager import VisualizationManager, ExtendedChannelType

# Configure logging
logger = logging.getLogger(__name__)

class SampleProcessor:
    """Processor for creating sample visualizations for preview and comparison."""
    
    def __init__(self, 
                 visualization_manager: Optional['VisualizationManager'] = None, 
                 satellite: str = "G16", 
                 sample_size: Tuple[int, int] = (500, 500)):
        """
        Initialize the sample processor.
        
        Args:
            visualization_manager: VisualizationManager instance
            satellite: Satellite identifier (G16 for GOES-16, G18 for GOES-18)
            sample_size: Size of sample visualization images
        """
        self.satellite = satellite
        self.sample_size = sample_size
        self.temp_dir = Path(tempfile.mkdtemp(prefix="goes_samples_"))
        
        # Create visualization manager if not provided
        self.viz_manager = visualization_manager or VisualizationManager(
            base_dir=self.temp_dir,
            satellite=satellite
        )
        
        # Create S3 client for raw data access
        self.s3_client = boto3.client(
            's3',
            config=boto3.session.Config(
                signature_version=botocore.UNSIGNED,
                retries={'max_attempts': 3}
            )
        )
        
        # S3 bucket names
        self.s3_buckets = {
            "G16": "noaa-goes16",
            "G18": "noaa-goes18" 
        }
    
    def download_sample_data(self, 
                          channel: Union[ChannelType, int], 
                          product_type: ProductType, 
                          date: Optional[datetime] = None) -> Optional[Path]:
        """
        Download a sample of raw data for a specific channel.
        
        Args:
            channel: Channel type or number
            product_type: Product type
            date: Optional date to use
            
        Returns:
            Path to downloaded sample file or None if failed
        """
        # Determine S3 bucket
        bucket = self.s3_buckets.get(self.satellite)
        if not bucket:
            logger.error(f"Unknown satellite: {self.satellite}")
            return None
            
        # Use current date if not specified
        if date is None:
            date = datetime.utcnow()
            logger.info(f"Using current date: {date.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        else:
            logger.info(f"Using specified date: {date.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        
        # Get day of year
        year = date.year
        doy = date.timetuple().tm_yday
        hour = date.hour
        minute = date.minute
        
        # Log date details for debugging
        logger.info(f"Search parameters - Year: {year}, Day of Year: {doy}, Hour: {hour}, Minute: {minute}")
        
        # Determine channel pattern
        if isinstance(channel, ChannelType):
            channel_num = channel.number
        else:
            channel_num = channel
        
        # Handle special case for composite channels
        if channel_num > 16:
            # Composites require multiple files, currently not implemented in sample
            logger.warning(f"Composite channel {channel_num} not supported in sample processor - would require multiple base files")
            return None
            
        # Create pattern for the file search
        pattern = f"C{channel_num:02d}_"
        
        # Try a series of fallback options if needed
        file_path = None
        
        # 1. Try searching within the specified day, with various hours
        if file_path is None:
            logger.info(f"SEARCH STRATEGY 1: Searching in original date with different hours")
            file_path = self._search_day_hours(bucket, year, doy, channel_num, product_type, pattern)
            
        # 2. If no data found, try previous day
        if file_path is None:
            prev_date = date - timedelta(days=1)
            prev_year = prev_date.year
            prev_doy = prev_date.timetuple().tm_yday
            logger.info(f"SEARCH STRATEGY 2: Searching in previous day {prev_date.strftime('%Y-%m-%d')}")
            file_path = self._search_day_hours(bucket, prev_year, prev_doy, channel_num, product_type, pattern)
        
        # 3. Try with known good fallback dates that usually have data (static dates)
        if file_path is None:
            logger.info(f"SEARCH STRATEGY 3: Trying known good fallback dates")
            
            # List of dates that typically have good GOES data coverage
            fallback_dates = [
                datetime(2023, 5, 1, 19, 0),   # May 2023
                datetime(2023, 8, 15, 18, 0),  # August 2023
                datetime(2023, 11, 1, 20, 0),  # November 2023
                datetime(2024, 1, 15, 17, 0),  # January 2024
                datetime(2024, 3, 1, 16, 0),   # March 2024
            ]
            
            # Try each fallback date until we find data
            for fallback_date in fallback_dates:
                logger.info(f"Trying fallback date: {fallback_date.strftime('%Y-%m-%d %H:%M:%S UTC')}")
                fb_year = fallback_date.year
                fb_doy = fallback_date.timetuple().tm_yday
                fb_hour = fallback_date.hour
                
                file_path = self._search_day_hours(bucket, fb_year, fb_doy, channel_num, product_type, pattern)
                if file_path:
                    logger.info(f"Found data using fallback date: {fallback_date.strftime('%Y-%m-%d')}")
                    break
            
        # 4. Final fallback - try a completely different product if necessary
        if file_path is None and product_type != ProductType.FULL_DISK:
            logger.info(f"SEARCH STRATEGY 4: Trying with FULL_DISK product type as final fallback")
            for fallback_date in fallback_dates:
                logger.info(f"Trying FULL_DISK for date: {fallback_date.strftime('%Y-%m-%d %H:%M:%S UTC')}")
                fb_year = fallback_date.year
                fb_doy = fallback_date.timetuple().tm_yday
                
                # Force FULL_DISK product type as it has most reliable coverage
                file_path = self._search_day_hours(bucket, fb_year, fb_doy, channel_num, ProductType.FULL_DISK, pattern)
                if file_path:
                    logger.info(f"Found FULL_DISK data using fallback date: {fallback_date.strftime('%Y-%m-%d')}")
                    break
        
        # Final result
        if file_path:
            logger.info(f"Successfully found and downloaded sample data to {file_path}")
        else:
            logger.error(f"Failed to find any sample data for channel {channel_num} after all fallback attempts")
        
        return file_path
        
    def _search_day_hours(self, 
                      bucket: str, 
                      year: int, 
                      doy: int, 
                      channel_num: int, 
                      product_type: ProductType, 
                      pattern: str) -> Optional[Path]:
        """
        Search for data within a specific day, trying multiple hours.
        
        Args:
            bucket: S3 bucket name
            year: Year to search
            doy: Day of year to search
            channel_num: Channel number
            product_type: Product type
            pattern: File pattern to match
            
        Returns:
            Path to downloaded file or None if not found
        """
        # Determine product path component
        if product_type == ProductType.FULL_DISK:
            product_path = "ABI-L2-CMIPF"
        elif product_type == ProductType.MESO1:
            product_path = "ABI-L2-CMIPM1"
        elif product_type == ProductType.MESO2:
            product_path = "ABI-L2-CMIPM2"
        elif product_type == ProductType.CMIP:
            product_path = "ABI-L2-CMIPC"
        else:
            logger.error(f"Unsupported product type: {product_type}")
            return None
            
        # Try a range of hours (prioritize afternoon/evening hours when imagery is often best)
        # Start with afternoon hours (more likely to have good imagery), then try morning
        hours_to_try = [18, 19, 20, 17, 16, 15, 21, 14, 13, 12, 22, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0, 23]
        
        logger.info(f"Searching for data in {year}/{doy:03d} for channel {channel_num} in product {product_path}")
        
        for try_hour in hours_to_try:
            current_prefix = f"{product_path}/{year}/{doy:03d}/{try_hour:02d}/"
            logger.info(f"Searching in hour {try_hour:02d} at {current_prefix}")
            
            try:
                # List objects in the bucket with timeout handling
                try:
                    response = self.s3_client.list_objects_v2(
                        Bucket=bucket, 
                        Prefix=current_prefix,
                        MaxKeys=20  # Increased to get more options
                    )
                except Exception as e:
                    logger.warning(f"S3 listing error for {current_prefix}: {str(e)}")
                    continue
                
                if 'Contents' not in response:
                    logger.info(f"No files found in {current_prefix}")
                    continue
                    
                # Filter by pattern
                matches = [obj for obj in response['Contents'] 
                          if pattern in obj['Key'] and obj['Key'].endswith('.nc')]
                
                if not matches:
                    logger.info(f"No matching files found for pattern {pattern} in {current_prefix}")
                    continue
                    
                # Get the most recent file
                matches.sort(key=lambda x: x['LastModified'], reverse=True)
                file_key = matches[0]['Key']
                
                # Create output filename
                filename = os.path.basename(file_key)
                output_path = self.temp_dir / filename
                
                # Download the file with retry logic
                logger.info(f"Found match, downloading sample file: {file_key}")
                
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        self.s3_client.download_file(
                            Bucket=bucket,
                            Key=file_key,
                            Filename=str(output_path)
                        )
                        logger.info(f"Successfully downloaded sample file to {output_path}")
                        return Path(str(output_path))
                    except Exception as e:
                        if attempt < max_retries - 1:
                            retry_delay = 2 ** attempt  # Exponential backoff
                            logger.warning(f"Download attempt {attempt+1} failed: {str(e)}. Retrying in {retry_delay}s...")
                            time.sleep(retry_delay)
                        else:
                            logger.error(f"All {max_retries} download attempts failed for {file_key}: {str(e)}")
                            # Continue to next hour if all download attempts fail
                            break
                
            except Exception as e:
                logger.warning(f"Error during search/download from {current_prefix}: {str(e)}")
                continue
        
        # If we got here, no data was found in any hour
        logger.warning(f"No suitable data found in {year}/{doy:03d} for channel {channel_num}")
        return None
    
    def process_sample_netcdf(self, 
                           file_path: Path, 
                           channel: Union[ChannelType, int]) -> Optional[Tuple[NDArray[np.float64], Image.Image, Image.Image]]:
        """
        Process a sample NetCDF file into sample visualizations.
        
        Args:
            file_path: Path to NetCDF file
            channel: Channel type or number
            
        Returns:
            Tuple of (data, standard_img, colorized_img) or None if processing failed
        """
        try:
            # Open the NetCDF file
            with xr.open_dataset(file_path) as ds:
                # Extract CMI (Cloud and Moisture Imagery) data
                if 'CMI' not in ds:
                    logger.error(f"No CMI data found in {file_path}")
                    return None
                    
                data = ds['CMI'].values
                
                # Create sample visualizations
                std_img, color_img = self.viz_manager.create_sample_visualization(
                    data, channel, self.sample_size
                )
                
                return data, std_img, color_img
                
        except Exception as e:
            logger.error(f"Error processing sample NetCDF file: {e}")
            return None
    
    def download_web_sample(self, 
                         channel: Union[ChannelType, int], 
                         product_type: ProductType, 
                         size: str = "600x600") -> Optional[Image.Image]:
        """
        Download a sample pre-processed image from NOAA website.
        
        Args:
            channel: Channel type or number
            product_type: Product type
            size: Image size (600x600, 1200x1200, etc.)
            
        Returns:
            PIL Image object or None if download failed
        """
        # Convert channel to number if needed
        if isinstance(channel, ChannelType):
            channel_num = channel.number
        else:
            channel_num = channel
        
        logger.info(f"Attempting to download web sample for channel {channel_num} from NOAA CDN")
        
        # Try multiple strategies to obtain imagery from web sources
        return self._try_all_web_sources(channel_num, product_type, size)
    
    def _try_all_web_sources(self, 
                           channel_num: int, 
                           product_type: ProductType, 
                           size: str = "600x600") -> Optional[Image.Image]:
        """
        Try multiple web sources for obtaining imagery.
        
        Args:
            channel_num: Channel number
            product_type: Product type
            size: Image size
            
        Returns:
            PIL Image or None if all sources failed
        """
        # STRATEGY 1: Try NOAA CDN with primary satellite
        img = self._try_noaa_cdn(channel_num, product_type, "GOES16", size)
        if img:
            return img
            
        # STRATEGY 2: Try alternate satellite
        alternate_satellite = "GOES18" if self.satellite == "G16" else "GOES16"
        logger.info(f"Trying alternate satellite {alternate_satellite}")
        img = self._try_noaa_cdn(channel_num, product_type, alternate_satellite, size)
        if img:
            return img
            
        # STRATEGY 3: Try alternate product types
        logger.info(f"Trying alternate product types")
        for alt_product in [p for p in ProductType if p != product_type]:
            img = self._try_noaa_cdn(channel_num, alt_product, "GOES16", size)
            if img:
                return img
                
        # STRATEGY 4: Try NOAA RAMMB site as a completely different source
        logger.info(f"Trying RAMMB SLIDER as alternative source")
        img = self._try_rammb_slider(channel_num)
        if img:
            return img
            
        # STRATEGY 5: Last resort - use archive images
        logger.info(f"Trying archived/static imagery")
        img = self._try_archived_imagery(channel_num)
        if img:
            return img
            
        # If all strategies failed
        logger.error(f"All web imagery sources failed for channel {channel_num}")
        return None
        
    def _try_noaa_cdn(self, 
                      channel_num: int, 
                      product_type: ProductType, 
                      satellite: str, 
                      size: str = "600x600") -> Optional[Image.Image]:
        """
        Try downloading from NOAA CDN with specific parameters.
        
        Args:
            channel_num: Channel number
            product_type: Product type
            satellite: Satellite name (GOES16 or GOES18)
            size: Image size
            
        Returns:
            PIL Image or None if failed
        """
        # Determine web path based on product type
        if product_type == ProductType.FULL_DISK:
            web_path = "FD"
        elif product_type == ProductType.MESO1:
            web_path = "M1"
        elif product_type == ProductType.MESO2:
            web_path = "M2"
        elif product_type == ProductType.CMIP:
            web_path = "CONUS"  # Use CONUS for CMIP
        else:
            logger.info(f"Unsupported product type for web sample: {product_type}, trying FULL_DISK instead")
            web_path = "FD"
            
        base_url = f"https://cdn.star.nesdis.noaa.gov/{satellite}/ABI/{web_path}/latest"
        
        # Different size options to try, starting with requested size
        size_options = [size, "1200x1200", "1000x1000", "600x600", "1280x720", "678x678"]
        
        # NOAA CDN URLs
        urls_to_try = []
        
        # Generate URLs for different sizes
        for sz in size_options:
            # Standard channels
            if channel_num <= 16:
                urls_to_try.append(f"{base_url}/{channel_num:02d}_{sz}.jpg")
            
            # RGB composite options
            elif channel_num == 100:  # True color
                urls_to_try.append(f"{base_url}/GEOCOLOR_{sz}.jpg")
            elif channel_num == 103:  # Airmass RGB
                urls_to_try.append(f"{base_url}/AirMass_{sz}.jpg")
            elif channel_num == 104:  # Fire RGB
                urls_to_try.append(f"{base_url}/HotSpot_{sz}.jpg")
            elif channel_num == 105:  # Day Cloud Phase
                urls_to_try.append(f"{base_url}/DayCloudPhase_{sz}.jpg")
            elif channel_num == 106:  # Dust RGB
                urls_to_try.append(f"{base_url}/Dust_{sz}.jpg")
        
        # Add some alternative URLs for specific bands
        # IR band alternatives
        if channel_num in [13, 14, 15, 16]:
            alt_base = f"https://cdn.star.nesdis.noaa.gov/{satellite}/ABI/FD/IRCL"
            urls_to_try.append(f"{alt_base}/{channel_num:02d}_{size}.jpg")
        
        # Water vapor bands alternatives
        if channel_num in [8, 9, 10]:
            alt_base = f"https://cdn.star.nesdis.noaa.gov/{satellite}/ABI/FD/WVCL"
            urls_to_try.append(f"{alt_base}/{channel_num:02d}_{size}.jpg")
            
        logger.info(f"Trying {len(urls_to_try)} URLs from NOAA CDN")
        
        # Try each URL in sequence until one works
        for url in urls_to_try:
            logger.info(f"Trying URL: {url}")
            img = self._download_image(url)
            if img:
                return img
                
        return None
    
    def _try_rammb_slider(self, channel_num: int) -> Optional[Image.Image]:
        """
        Try downloading from RAMMB SLIDER as an alternative source.
        
        Args:
            channel_num: Channel number
            
        Returns:
            PIL Image or None if failed
        """
        # RAMMB SLIDER uses different URL structure
        rammb_base = "https://rammb-slider.cira.colostate.edu/data/imagery"
        
        # Define URLs to try based on channel
        urls_to_try = []
        
        if channel_num <= 16:
            # Standard ABI channels
            urls_to_try.append(f"{rammb_base}/goes-16/full_disk/band_{channel_num:02d}/latest/1200/1200.jpg")
            urls_to_try.append(f"{rammb_base}/goes-18/full_disk/band_{channel_num:02d}/latest/1200/1200.jpg")
        elif channel_num == 100:
            # True color
            urls_to_try.append(f"{rammb_base}/goes-16/full_disk/geocolor/latest/1200/1200.jpg")
            urls_to_try.append(f"{rammb_base}/goes-18/full_disk/geocolor/latest/1200/1200.jpg")
        elif channel_num == 103:
            # Airmass RGB
            urls_to_try.append(f"{rammb_base}/goes-16/full_disk/air_mass/latest/1200/1200.jpg")
            urls_to_try.append(f"{rammb_base}/goes-18/full_disk/air_mass/latest/1200/1200.jpg")
        elif channel_num == 104:
            # Fire Temperature
            urls_to_try.append(f"{rammb_base}/goes-16/full_disk/fire_temperature/latest/1200/1200.jpg")
            urls_to_try.append(f"{rammb_base}/goes-18/full_disk/fire_temperature/latest/1200/1200.jpg")
        
        logger.info(f"Trying {len(urls_to_try)} URLs from RAMMB SLIDER")
        
        # Try each URL in sequence
        for url in urls_to_try:
            logger.info(f"Trying RAMMB URL: {url}")
            img = self._download_image(url)
            if img:
                return img
                
        return None
        
    def _try_archived_imagery(self, channel_num: int) -> Optional[Image.Image]:
        """
        Try to load static archived imagery as last resort.
        
        Args:
            channel_num: Channel number
            
        Returns:
            PIL Image or None if failed
        """
        # Build archive URL for this channel - use NCEI archive for consistent URLs
        archive_base = "https://www.ncei.noaa.gov/data/goes-r-products/access"
        
        # Known dates with good imagery
        dates_to_try = [
            "20230501/18", 
            "20230701/19", 
            "20230901/20",
            "20240101/17"
        ]
        
        urls_to_try = []
        
        # GOES ABI full disk usually has the most reliable archive
        if channel_num <= 16:
            for date_hour in dates_to_try:
                urls_to_try.append(f"{archive_base}/ABI-L2-CMIPF/{date_hour}/OR_ABI-L2-CMIPF-M6C{channel_num:02d}_G16.jpg")
                
        logger.info(f"Trying {len(urls_to_try)} archive URLs")
        
        # Try each URL in sequence
        for url in urls_to_try:
            logger.info(f"Trying archive URL: {url}")
            img = self._download_image(url)
            if img:
                return img
                
        return None
    
    def _download_image(self, 
                       url: str, 
                       max_retries: int = 3, 
                       timeout: int = 30) -> Optional[Image.Image]:
        """
        Download an image from a URL with retry logic.
        
        Args:
            url: URL to download from
            max_retries: Maximum number of retry attempts
            timeout: Request timeout in seconds
            
        Returns:
            PIL Image or None if download failed
        """
        for attempt in range(max_retries):
            try:
                # Progressive backoff
                current_timeout = timeout * (1 + 0.5 * attempt)
                
                logger.info(f"Download attempt {attempt+1}/{max_retries} for {url}")
                response = requests.get(url, timeout=current_timeout)
                response.raise_for_status()
                
                # Create a temporary file for the image
                with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                    tmp.write(response.content)
                    tmp_path = tmp.name
                
                try:
                    # Attempt to open the image
                    img = Image.open(tmp_path)
                    
                    # Validate image is not corrupt or empty
                    img.verify()  # Verify it's a valid image
                    img = Image.open(tmp_path)  # Reopen after verify
                    
                    # Check image dimensions
                    if img.width < 10 or img.height < 10:
                        logger.warning(f"Image too small ({img.width}x{img.height}), might be invalid")
                        os.unlink(tmp_path)
                        continue
                        
                    # Resize if needed
                    if img.width > self.sample_size[0] or img.height > self.sample_size[1]:
                        scale = min(self.sample_size[0] / img.width, self.sample_size[1] / img.height)
                        new_size = (int(img.width * scale), int(img.height * scale))
                        img = img.resize(new_size, Image.LANCZOS)
                    
                    # Clean up temp file
                    os.unlink(tmp_path)
                    
                    logger.info(f"Successfully downloaded image ({img.width}x{img.height}) from {url}")
                    return img
                    
                except Exception as img_error:
                    logger.warning(f"Downloaded file is not a valid image: {img_error}")
                    os.unlink(tmp_path)
                    continue
                    
            except requests.exceptions.Timeout:
                logger.warning(f"Timeout on attempt {attempt+1}/{max_retries} for {url}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                continue
                
            except requests.exceptions.ConnectionError as e:
                logger.warning(f"Connection error on attempt {attempt+1}/{max_retries} for {url}: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                continue
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"Request error on attempt {attempt+1}/{max_retries} for {url}: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(1)  # Wait before retry
                continue
                
        logger.error(f"All {max_retries} download attempts failed for {url}")
        return None
    
    def create_sample_comparison(self, 
                             channel: Union[ChannelType, int], 
                             product_type: ProductType, 
                             date: Optional[datetime] = None) -> Optional[Image.Image]:
        """
        Create a sample comparison of different processing options.
        
        Args:
            channel: Channel type or number
            product_type: Product type
            date: Optional date to use
            
        Returns:
            PIL Image with comparison or None if creation failed
        """
        # Get channel info
        channel_name = ExtendedChannelType.get_display_name(channel)
        
        # Initialize result components
        images = []
        titles = []
        
        # Get raw data sample
        try:
            # Step 1: Get raw NetCDF sample
            netcdf_path = self.download_sample_data(channel, product_type, date)
            
            if netcdf_path:
                # Process the sample
                result = self.process_sample_netcdf(netcdf_path, channel)
                
                if result:
                    data, std_img, color_img = result
                    
                    # Add standard grayscale image
                    images.append(std_img)
                    titles.append(f"{channel_name} (Standard)")
                    
                    # Add colorized image
                    images.append(color_img)
                    titles.append(f"{channel_name} (Enhanced)")
            
            # Step 2: Get web sample
            web_img = self.download_web_sample(channel, product_type)
            
            if web_img:
                images.append(web_img)
                titles.append(f"{channel_name} (NOAA)")
                
        except Exception as e:
            logger.error(f"Error creating sample comparison: {e}")
            
        # Create comparison image if we have at least one sample
        if images:
            # Create output filename
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            output_name = f"sample_comparison_{channel}_{timestamp}.png"
            output_path = self.temp_dir / output_name
            
            # Create comparison image
            comparison = self.viz_manager.create_comparison_image(
                images, titles, output_path
            )
            
            if isinstance(comparison, Path):
                return Image.open(comparison)
            else:
                return comparison
            
        return None

    def get_estimated_processing_time(self, 
                                 channel: Union[ChannelType, int], 
                                 product_type: ProductType, 
                                 full_resolution: bool = False) -> float:
        """
        Estimate processing time for full imagery based on channel and product.
        
        Args:
            channel: Channel type or number
            product_type: Product type
            full_resolution: Whether to process at full resolution
            
        Returns:
            Estimated processing time in seconds
        """
        # Convert channel to number if needed
        if isinstance(channel, ChannelType):
            channel_num = channel.number
        else:
            channel_num = channel
            
        # Base processing times (in seconds)
        if product_type == ProductType.FULL_DISK:
            base_time = 20.0  # Full disk takes longer
        else:
            base_time = 10.0  # Mesoscale and CONUS are faster
            
        # Adjust based on channel
        if channel_num == 2:  # Band 2 has 2x resolution
            base_time *= 2.5
        elif channel_num > 16:  # Composite channels require multiple bands
            base_time *= 3
            
        # Adjust based on resolution
        if full_resolution:
            base_time *= 2
            
        return base_time
        
    def cleanup(self) -> None:
        """Clean up temporary files."""
        try:
            import shutil
            shutil.rmtree(self.temp_dir)
        except Exception as e:
            logger.error(f"Error cleaning up temporary files: {e}")