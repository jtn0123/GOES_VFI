"""
GOES Satellite Imagery Visualization Manager

This module manages the organization, processing, and visualization of GOES satellite imagery,
with support for time-based folder structures and consistent file naming conventions.
"""

import logging
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union, cast

import numpy as np
from matplotlib import cm
from numpy.typing import NDArray
from PIL import Image

from .goes_imagery import ChannelType, ProcessingMode, ProductType

# Configure logging
logger = logging.getLogger(__name__)


class VisualizationManager:
    """Manager for organizing and processing GOES imagery visualizations."""

    def __init__(
        self, base_dir: Optional[Union[str, Path]] = None, satellite: str = "G16"
    ) -> None:
        """
        Initialize the visualization manager.

        Args:
            base_dir: Base directory for storing visualizations
            satellite: Satellite identifier (G16 for GOES-16, G18 for GOES-18)
        """
        self.base_dir = (
            Path(base_dir) if base_dir else Path.home() / "Downloads" / "goes_imagery"
        )
        self.satellite = satellite

        # Create base directory if it doesn't exist
        self.base_dir.mkdir(parents=True, exist_ok=True)

        # Define standard colormaps for different band types
        self.colormaps = {
            "ir": "gray",  # Standard IR grayscale
            "ir_enhanced": "turbo",  # Enhanced IR colormap
            "water_vapor": "jet",  # Water vapor bands
            "visible": "gray",  # Visible bands
            "fire": "inferno",  # Fire detection (band 7)
            "vegetation": "viridis",  # Vegetation (band 3)
            "snow_ice": "cool",  # Snow/ice detection (band 5)
            "airmass": "RdBu_r",  # Airmass RGB
            "dust": "copper",  # Dust detection
            "temperature": "plasma",  # Temperature visualization
        }

    def get_time_directory(self, timestamp: Optional[datetime] = None) -> Path:
        """
        Get or create a time-based directory for storing imagery.

        Args:
            timestamp: Datetime object or None for current time

        Returns:
            Path to the time directory
        """
        if timestamp is None:
            timestamp = datetime.utcnow()

        # Format: YYYY-MM-DD_HH-MM-SS
        time_str = timestamp.strftime("%Y-%m-%d_%H-%M-%S")
        time_dir = self.base_dir / time_str

        # Create directory if it doesn't exist
        time_dir.mkdir(parents=True, exist_ok=True)

        return time_dir

    def get_filename(
        self,
        channel: Union[ChannelType, int],
        is_map: bool = False,
        timestamp: Optional[datetime] = None,
    ) -> str:
        """
        Generate a standardized filename for a processed image.

        Args:
            channel: Channel type or number
            is_map: Whether this is a colorized "map" version
            timestamp: Timestamp for the image or None for the filename

        Returns:
            Standardized filename
        """
        # Convert channel number to ChannelType if needed
        if isinstance(channel, int):
            channel_num = channel
        elif isinstance(channel, ChannelType):
            channel_num = channel.number
        else:
            raise ValueError(f"Invalid channel type: {channel}")

        # Get timestamp
        if timestamp is None:
            timestamp = datetime.utcnow()

        # Format timestamp according to standard
        time_str = timestamp.strftime("%Y%m%dT%H%M%SZ")

        # Create filename with satellite prefix
        if channel_num <= 16:  # Regular bands
            base_name = f"{self.satellite}_{channel_num}_{time_str}.png"
        else:  # Composite products
            if channel_num == 100:  # True color
                base_name = f"abi_rgb_True_Color_{time_str}.png"
            elif channel_num == 101:  # Water vapor composite
                base_name = f"abi_rgb_Water_Vapor_Composite_{time_str}.png"
            elif channel_num == 102:  # IR composite
                base_name = f"abi_rgb_IR_Composite_{time_str}.png"
            elif channel_num == 103:  # Airmass RGB
                base_name = f"abi_rgb_Airmass_{time_str}.png"
            elif channel_num == 104:  # Fire temperature RGB
                base_name = f"abi_rgb_Fire_Temperature_{time_str}.png"
            elif channel_num == 105:  # Day cloud phase RGB
                base_name = f"abi_rgb_Day_Cloud_Phase_{time_str}.png"
            elif channel_num == 106:  # Dust RGB
                base_name = f"abi_rgb_Dust_{time_str}.png"
            else:
                base_name = f"abi_rgb_Custom_{channel_num}_{time_str}.png"

        # Add _map suffix for colorized versions
        if is_map and channel_num <= 16:  # Only regular bands get _map suffix
            base_name = base_name.replace(".png", "_map.png")

        return base_name

    def get_band_colormap(self, channel: Union[ChannelType, int]) -> str:
        """
        Get appropriate colormap for a given channel.

        Args:
            channel: Channel type or number

        Returns:
            Colormap name suitable for the channel
        """
        # Convert to channel number if needed
        if isinstance(channel, ChannelType):
            channel_num = channel.number
        else:
            channel_num = channel

        # Determine appropriate colormap
        if channel_num <= 3:  # Visible bands
            return self.colormaps["visible"]
        elif channel_num in [4, 5, 6]:  # Near-IR bands
            if channel_num == 5:  # Snow/Ice
                return self.colormaps["snow_ice"]
            return self.colormaps["visible"]
        elif channel_num == 7:  # Fire detection
            return self.colormaps["fire"]
        elif channel_num in [8, 9, 10]:  # Water vapor
            return self.colormaps["water_vapor"]
        elif channel_num in [11, 12, 13, 14, 15, 16]:  # IR bands
            return self.colormaps["ir_enhanced"]

        # Default for other channels
        return self.colormaps["visible"]

    def process_band_image(
        self,
        data: NDArray[np.float64],
        channel: Union[ChannelType, int],
        colorized: bool = False,
    ) -> Image.Image:
        """
        Process raw band data into a visualization.

        Args:
            data: NumPy array with band data
            channel: Channel type or number
            colorized: Whether to apply colorization

        Returns:
            PIL Image object with the processed visualization
        """
        # Convert to channel number if needed
        if isinstance(channel, ChannelType):
            channel_num = channel.number
        else:
            channel_num = channel

        # Handle NaN values
        data_clean = np.nan_to_num(data)

        # Normalize data to 0-1 range
        if channel_num <= 6:  # Reflective bands (visible, near-IR)
            # These are already in reflectance values (0-1)
            # Just clip to valid range
            data_norm = np.clip(data_clean, 0, 1)

            # For visible bands, apply gamma correction
            if channel_num <= 3:
                gamma = 2.2
                data_norm = np.power(data_norm, 1 / gamma)
        else:  # Emissive bands (IR)
            # These are in brightness temperature (K)
            # Determine min/max temperature based on band
            if channel_num == 7:  # Fire detection band
                min_temp, max_temp = 200, 380
            elif channel_num in [8, 9, 10]:  # Water vapor
                min_temp, max_temp = 190, 260
            else:  # Regular IR
                min_temp, max_temp = 180, 320

            # Normalize and invert (cold=white, hot=black for standard IR)
            data_norm = 1.0 - np.clip(
                (data_clean - min_temp) / (max_temp - min_temp), 0, 1
            )

        # Create image based on colorization option
        if colorized:
            # Apply colormap
            cmap_name = self.get_band_colormap(channel_num)
            cmap = cm.get_cmap(cmap_name)
            colored_data = cmap(data_norm)

            # Convert to 8-bit RGB
            rgb_uint8 = (colored_data[:, :, :3] * 255).astype(np.uint8)
            img = Image.fromarray(rgb_uint8, "RGB")
        else:
            # Grayscale image
            gray_uint8 = (data_norm * 255).astype(np.uint8)
            img = Image.fromarray(gray_uint8, "L")

        return img

    def process_rgb_composite(
        self,
        red_data: NDArray[np.float64],
        green_data: NDArray[np.float64],
        blue_data: NDArray[np.float64],
        composite_type: str,
    ) -> Image.Image:
        """
        Process data into an RGB composite image.

        Args:
            red_data: Data for red channel
            green_data: Data for green channel
            blue_data: Data for blue channel
            composite_type: Type of composite (true_color, airmass, etc.)

        Returns:
            PIL Image with the RGB composite
        """
        # Create normalized RGB arrays
        r_norm = np.clip(red_data, 0, 1)
        g_norm = np.clip(green_data, 0, 1)
        b_norm = np.clip(blue_data, 0, 1)

        # Apply type-specific processing
        if composite_type == "true_color":
            # Apply gamma correction
            gamma = 2.2
            r = np.power(r_norm, 1 / gamma)
            g = np.power(g_norm, 1 / gamma)
            b = np.power(b_norm, 1 / gamma)

            # Apply contrast enhancement
            contrast = 1.3
            r = np.clip(r * contrast, 0, 1)
            g = np.clip(g * contrast, 0, 1)
            b = np.clip(b * contrast, 0, 1)
        elif composite_type == "airmass":
            # Airmass RGB typically uses the raw data
            r, g, b = r_norm, g_norm, b_norm
        else:
            # Default processing for other composites
            r, g, b = r_norm, g_norm, b_norm

        # Stack into RGB array
        rgb = np.dstack([r, g, b])

        # Convert to 8-bit
        rgb_uint8 = (rgb * 255).astype(np.uint8)

        # Replace NaN with black
        rgb_uint8 = np.nan_to_num(rgb_uint8, nan=0)

        # Create PIL image
        img = Image.fromarray(rgb_uint8, "RGB")

        return img

    def save_visualization(
        self,
        img: Image.Image,
        channel: Union[ChannelType, int],
        timestamp: Optional[datetime] = None,
        colorized: bool = False,
    ) -> Path:
        """
        Save a processed visualization to the appropriate location.

        Args:
            img: PIL Image object
            channel: Channel type or number
            timestamp: Datetime for the image or None for current time
            colorized: Whether this is a colorized version

        Returns:
            Path to the saved file
        """
        # Get time directory
        time_dir = self.get_time_directory(timestamp)

        # Generate filename
        filename = self.get_filename(channel, is_map=colorized, timestamp=timestamp)

        # Create full path
        file_path = time_dir / filename

        # Save the image
        img.save(file_path)
        logger.info(f"Saved visualization to {file_path}")

        return file_path

    def list_available_visualizations(
        self,
        channel: Optional[Union[int, str]] = None,
        date_range: Optional[Tuple[datetime, datetime]] = None,
    ) -> List[Path]:
        """
        List available visualizations matching criteria.

        Args:
            channel: Filter by channel (optional)
            date_range: Filter by date range (optional)

        Returns:
            List of visualization file paths
        """
        # Start with all time directories
        time_dirs = [d for d in self.base_dir.iterdir() if d.is_dir()]

        # Filter by date range if specified
        if date_range:
            start_date, end_date = date_range
            filtered_dirs = []

            for d in time_dirs:
                try:
                    dir_date = datetime.strptime(d.name, "%Y-%m-%d_%H-%M-%S")
                    if start_date <= dir_date <= end_date:
                        filtered_dirs.append(d)
                except ValueError:
                    # Skip directories with invalid format
                    continue

            time_dirs = filtered_dirs

        # Collect all matching files
        result_files = []

        for time_dir in time_dirs:
            # Get all PNG files in the directory
            png_files = list(time_dir.glob("*.png"))

            # Filter by channel if specified
            if channel is not None:
                if isinstance(channel, int):
                    channel_str = f"_{channel}_"
                    channel_files = [f for f in png_files if channel_str in f.name]
                elif isinstance(channel, str):
                    channel_files = [f for f in png_files if channel in f.name]
                else:
                    channel_files = png_files

                result_files.extend(channel_files)
            else:
                result_files.extend(png_files)

        return sorted(result_files)

    def get_latest_visualization(
        self, channel: Union[int, str], colorized: bool = False
    ) -> Optional[Path]:
        """
        Get the latest visualization for a given channel.

        Args:
            channel: Channel to find
            colorized: Whether to get colorized version

        Returns:
            Path to the latest visualization or None if not found
        """
        # List all visualizations for this channel
        all_visuals = self.list_available_visualizations(channel)

        # Filter by colorized status
        if colorized:
            filtered = [v for v in all_visuals if "_map.png" in v.name]
        else:
            filtered = [v for v in all_visuals if "_map.png" not in v.name]

        # Return latest if available
        if filtered:
            return sorted(filtered)[-1]

        return None

    def create_sample_visualization(
        self,
        data: NDArray[np.float64],
        channel: Union[ChannelType, int],
        size: Tuple[int, int] = (400, 400),
    ) -> Tuple[Image.Image, Image.Image]:
        """
        Create a sample visualization for preview purposes.

        Args:
            data: Raw band data
            channel: Channel type or number
            size: Output image size

        Returns:
            Tuple of (standard_image, colorized_image) as PIL Images
        """
        # Resize data if needed
        h, w = data.shape
        scale = min(size[0] / w, size[1] / h)
        new_w, new_h = int(w * scale), int(h * scale)

        # Process standard grayscale version
        std_img = self.process_band_image(data, channel, colorized=False)
        std_img = std_img.resize((new_w, new_h), Image.LANCZOS)

        # Process colorized version
        color_img = self.process_band_image(data, channel, colorized=True)
        color_img = color_img.resize((new_w, new_h), Image.LANCZOS)

        return std_img, color_img

    def create_comparison_image(
        self,
        images: List[Image.Image],
        titles: List[str],
        output_path: Optional[Path] = None,
    ) -> Optional[Union[Image.Image, Path]]:
        """
        Create a side-by-side comparison of multiple images.

        Args:
            images: List of PIL Image objects
            titles: List of titles for each image
            output_path: Optional path to save the comparison

        Returns:
            PIL Image with the comparison
        """
        if not images:
            return None

        # Determine layout (2xN grid)
        n = len(images)
        cols = min(n, 3)
        rows = (n + cols - 1) // cols

        # Get maximum dimensions
        max_width = max(img.width for img in images)
        max_height = max(img.height for img in images)

        # Create blank comparison image
        title_height = 30  # Space for title
        comp_width = max_width * cols + 20 * (cols - 1)
        comp_height = (max_height + title_height) * rows + 20 * (rows - 1)
        comp_img = Image.new("RGB", (comp_width, comp_height), (30, 30, 30))

        # Paste images into grid
        for i, (img, title) in enumerate(zip(images, titles)):
            row = i // cols
            col = i % cols

            # Calculate position
            x = col * (max_width + 20)
            y = row * (max_height + title_height + 20)

            # Paste image
            comp_img.paste(img, (x, y + title_height))

            # TODO: Add title text
            # This would require drawing on the image, which we'll skip for now

        # Save if requested
        if output_path:
            comp_img.save(output_path)
            return output_path

        return comp_img

    def cleanup_old_visualizations(self, max_age_days: int = 30) -> int:
        """
        Clean up old visualization directories.

        Args:
            max_age_days: Maximum age in days to keep

        Returns:
            Number of directories removed
        """
        cutoff_date = datetime.utcnow() - timedelta(days=max_age_days)
        count = 0

        for time_dir in self.base_dir.iterdir():
            if not time_dir.is_dir():
                continue

            try:
                dir_date = datetime.strptime(time_dir.name, "%Y-%m-%d_%H-%M-%S")
                if dir_date < cutoff_date:
                    shutil.rmtree(time_dir)
                    count += 1
            except (ValueError, OSError) as e:
                logger.error(f"Error processing directory {time_dir}: {e}")

        return count


# Extended ChannelType with additional composites
class ExtendedChannelType:
    """Utility class for extended channel types including additional RGB composites."""

    # Add new composite types
    AIRMASS_RGB = (
        103,
        "Airmass RGB",
        "RGB",
        "Air mass analysis using water vapor and ozone bands",
    )
    FIRE_RGB = (
        104,
        "Fire Temperature RGB",
        "RGB",
        "Fire detection using thermal bands",
    )
    CLOUD_PHASE_RGB = (
        105,
        "Day Cloud Phase RGB",
        "RGB",
        "Cloud type and phase analysis",
    )
    DUST_RGB = (106, "Dust RGB", "RGB", "Dust and sand detection")

    @staticmethod
    def get_description(channel: Union[ChannelType, int, Any]) -> str:
        """
        Get the description for a channel.

        Args:
            channel: The channel to get the description for, can be a ChannelType enum
                    or an integer channel number.

        Returns:
            The description for the channel
        """
        # Handle original ChannelType enum
        if isinstance(channel, ChannelType):
            return str(channel.description)

        # Handle extended channel types
        extended_types = {
            103: ExtendedChannelType.AIRMASS_RGB[3],
            104: ExtendedChannelType.FIRE_RGB[3],
            105: ExtendedChannelType.CLOUD_PHASE_RGB[3],
            106: ExtendedChannelType.DUST_RGB[3],
        }

        if isinstance(channel, int) and channel in extended_types:
            return str(extended_types[channel])

        # Try original channel types
        for ch in ChannelType:
            if isinstance(channel, int) and ch.number == channel:
                return str(ch.description)

        return "Unknown channel"

    @staticmethod
    def get_display_name(channel: Union[ChannelType, int, Any]) -> str:
        """
        Get the display name for a channel.

        Args:
            channel: The channel to get the display name for, can be a ChannelType enum
                    or an integer channel number.

        Returns:
            The display name for the channel
        """
        # Handle original ChannelType enum
        if isinstance(channel, ChannelType):
            return str(channel.display_name)

        # Handle extended channel types
        extended_types = {
            103: ExtendedChannelType.AIRMASS_RGB[1],
            104: ExtendedChannelType.FIRE_RGB[1],
            105: ExtendedChannelType.CLOUD_PHASE_RGB[1],
            106: ExtendedChannelType.DUST_RGB[1],
        }

        if isinstance(channel, int) and channel in extended_types:
            return str(extended_types[channel])

        # Try original channel types
        for ch in ChannelType:
            if isinstance(channel, int) and ch.number == channel:
                return str(ch.display_name)

        # Fallback case, convert to string for any type
        return f"Channel {channel}"
