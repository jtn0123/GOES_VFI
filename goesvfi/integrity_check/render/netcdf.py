"""NetCDF renderer for GOES satellite imagery.

This module provides functions to render PNG images from GOES NetCDF files,
specifically for Band 13 (Clean IR, 10.3 µm) data.
"""

from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt
from PIL import Image
import xarray as xr

from goesvfi.integrity_check.time_index import SatellitePattern
from goesvfi.utils.log import get_logger

LOGGER = get_logger(__name__)

# GOES-16/18 Band 13 (Clean IR, 10.3 µm) rendering constants
# Temperature ranges (Kelvin) for IR visualization
DEFAULT_MIN_TEMP_K = 180.0  # Very cold cloud tops
DEFAULT_MAX_TEMP_K = 320.0  # Warm surface
DEFAULT_COLORMAP = "gray"  # Default grayscale

# Band 13 variable names in NetCDF files
RADIANCE_VAR = "Rad"
BAND_ID_VAR = "band_id"
BAND_WAVELENGTH_VAR = "band_wavelength"
Y_VAR = "y"
X_VAR = "x"

# Target band information
TARGET_BAND_ID = 13  # Clean IR (10.3 µm)


def _validate_band_id(ds: xr.Dataset) -> None:
    """Validate that the dataset contains the target band.

    Args:
        ds: xarray Dataset to validate

    Raises:
        ValueError: If the target band is not found in the dataset
    """
    if BAND_ID_VAR not in ds.variables:
        return  # Skip validation if band_id variable is not present

    band_id_raw = ds[BAND_ID_VAR].values
    # Cast to Any to avoid type inference issues
    band_id: Any = band_id_raw

    if np.isscalar(band_id):
        if band_id != TARGET_BAND_ID:
            # Convert to string safely, regardless of type
            band_str = band_id.decode("utf-8") if isinstance(band_id, bytes) else str(band_id)
            msg = f"Expected Band {TARGET_BAND_ID}, found Band {band_str}"
            raise ValueError(msg)
    elif TARGET_BAND_ID not in band_id:
        msg = f"Band {TARGET_BAND_ID} not found in dataset"
        raise ValueError(msg)


def _convert_radiance_to_temperature(
    data: npt.NDArray[np.float64], ds: xr.Dataset, min_temp_k: float, max_temp_k: float
) -> npt.NDArray[np.float64]:
    """Convert radiance data to brightness temperature and normalize.

    Args:
        data: Raw radiance data from the NetCDF file
        ds: xarray Dataset containing the Planck constants
        min_temp_k: Minimum temperature for scaling
        max_temp_k: Maximum temperature for scaling

    Returns:
        Normalized temperature data (0-1 range, inverted for IR)
    """
    # Convert radiance to brightness temperature if Planck constants are available
    if all(k in ds.attrs for k in ["planck_fk1", "planck_fk2", "planck_bc1", "planck_bc2"]):
        fk1 = ds.attrs["planck_fk1"]
        fk2 = ds.attrs["planck_fk2"]
        bc1 = ds.attrs["planck_bc1"]
        bc2 = ds.attrs["planck_bc2"]

        # Apply Planck function to convert radiance to brightness temperature
        data = (fk2 / np.log((fk1 / data) + 1) - bc1) / bc2

    # Mask invalid data
    data = np.ma.masked_less_equal(data, 0)  # type: ignore[no-untyped-call]
    # Clip data to the specified temperature range
    data = np.clip(data, min_temp_k, max_temp_k)

    # Normalize to 0-1 range
    normalized_data = (data - min_temp_k) / (max_temp_k - min_temp_k)

    # Inverse for IR (cold = bright, warm = dark)
    return 1 - normalized_data


def _get_colormap(colormap_name: str) -> Any:
    """Get a matplotlib colormap based on name.

    Args:
        colormap_name: Name of the colormap

    Returns:
        LinearSegmentedColormap instance
    """
    from matplotlib.colors import LinearSegmentedColormap
    import matplotlib.pyplot as plt

    if colormap_name == "gray":
        # Custom grayscale with enhanced contrast
        return LinearSegmentedColormap.from_list("enhanced_gray", [(0, 0, 0), (1, 1, 1)], N=256)
    # Get the colormap - we just need a Colormap,
    # not specifically LinearSegmentedColormap
    _cmap = plt.get_cmap(colormap_name)
    # Create a new LinearSegmentedColormap with the data from _cmap
    # This ensures type safety while maintaining the colormap
    return LinearSegmentedColormap.from_list(colormap_name, _cmap(np.linspace(0, 1, 256)), N=256)


def _create_figure(data: npt.NDArray[np.float64], colormap_name: str, output_path: Path) -> None:
    """Create a matplotlib figure and save it to a file.

    Args:
        data: Normalized data to visualize
        colormap_name: Name of the colormap to use
        output_path: Path to save the figure

    Returns:
        None
    """
    import matplotlib.pyplot as plt

    # Get appropriate colormap
    cmap = _get_colormap(colormap_name)

    # Create a figure
    dpi = 100
    fig_width = data.shape[1] / dpi
    fig_height = data.shape[0] / dpi

    fig = plt.figure(figsize=(fig_width, fig_height), dpi=dpi)
    ax = fig.add_axes((0, 0, 1, 1))  # Use tuple instead of list for rect parameter
    ax.axis("off")

    # Plot the image
    ax.imshow(data, cmap=cmap, aspect="auto")

    # Save to file
    plt.savefig(output_path, dpi=dpi, bbox_inches="tight", pad_inches=0)
    plt.close(fig)


def _resize_image(image_path: Path, resolution: tuple[int, int]) -> None:
    """Resize an image to the specified resolution.

    Args:
        image_path: Path to the image
        resolution: Target resolution (width, height)

    Returns:
        None
    """
    img = Image.open(image_path)
    img = img.resize(resolution, Image.LANCZOS)
    img.save(image_path)


def _prepare_output_path(netcdf_path: Path, output_path: str | Path | None) -> Path:
    """Prepare the output path for the rendered image.

    Args:
        netcdf_path: Path to the input NetCDF file
        output_path: Optional path to save the image

    Returns:
        Path: The prepared output path
    """
    if output_path is None:
        return netcdf_path.with_suffix(".png")
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    return output_path


def render_png(
    netcdf_path: str | Path,
    output_path: str | Path | None = None,
    min_temp_k: float = DEFAULT_MIN_TEMP_K,
    max_temp_k: float = DEFAULT_MAX_TEMP_K,
    colormap: str = DEFAULT_COLORMAP,
    satellite: SatellitePattern | None = None,
    resolution: tuple[int, int] | None = None,
) -> Path:
    """Render a PNG image from a GOES NetCDF file.

    Args:
        netcdf_path: Path to the NetCDF file
        output_path: Path to save the PNG image (if None, create alongside NetCDF)
        min_temp_k: Minimum temperature in Kelvin for scaling
        max_temp_k: Maximum temperature in Kelvin for scaling
        colormap: Colormap name (from matplotlib)  # type: ignore[import-not-found]
        satellite: Satellite pattern enum (used for metadata)
        resolution: Optional output resolution (width, height)

    Returns:
        Path to the rendered PNG image

    Raises:
        FileNotFoundError: If the NetCDF file doesn't exist
        ValueError: If the NetCDF file doesn't contain Band 13 data
        IOError: If there's an error during rendering
    """
    # Convert to Path and validate existence
    netcdf_path = Path(netcdf_path)
    if not netcdf_path.exists():
        msg = f"NetCDF file not found: {netcdf_path}"
        raise FileNotFoundError(msg)

    # Prepare output path
    final_output_path = _prepare_output_path(netcdf_path, output_path)

    LOGGER.debug("Rendering %s to %s", netcdf_path, final_output_path)

    try:
        # Open the NetCDF dataset
        with xr.open_dataset(netcdf_path) as ds:
            # 1. Validate that this dataset contains the target band
            _validate_band_id(ds)

            # 2. Extract the radiance data
            if RADIANCE_VAR not in ds.variables:
                msg = f"Radiance variable {RADIANCE_VAR!r} not found in dataset"
                raise ValueError(msg)

            data = ds[RADIANCE_VAR].values

            # 3. Convert radiance to brightness temperature and normalize
            normalized_data = _convert_radiance_to_temperature(data, ds, min_temp_k, max_temp_k)

            # 4. Create figure and save to file
            _create_figure(normalized_data, colormap, final_output_path)

            # 5. Optional resize
            if resolution is not None:
                _resize_image(final_output_path, resolution)

            LOGGER.debug("Rendered %s", final_output_path)
            return final_output_path

    except KeyError as e:
        LOGGER.exception("Error occurred")
        msg = f"Error rendering NetCDF file: {e}"
        raise KeyError(msg) from e
    except RuntimeError as e:
        LOGGER.exception("Error occurred")
        msg = f"Error rendering NetCDF file: {e}"
        raise RuntimeError(msg) from e
    except ValueError as e:
        LOGGER.exception("Error occurred")
        msg = f"Error rendering NetCDF file: {e}"
        raise ValueError(msg) from e


def extract_metadata(netcdf_path: str | Path) -> dict[str, Any]:
    """Extract metadata from a GOES NetCDF file.

    Args:
        netcdf_path: Path to the NetCDF file

    Returns:
        Dictionary of metadata

    Raises:
        FileNotFoundError: If the NetCDF file doesn't exist
        ValueError: If the NetCDF file doesn't contain valid metadata
    """
    netcdf_path = Path(netcdf_path)
    if not netcdf_path.exists():
        msg = f"NetCDF file not found: {netcdf_path}"
        raise FileNotFoundError(msg)

    try:
        with xr.open_dataset(netcdf_path) as ds:
            return {
                "satellite": ds.attrs.get("platform_ID", None),
                "instrument": ds.attrs.get("instrument_type", None),
                "timestamp": ds.attrs.get("date_created", None),
                "band_id": (ds[BAND_ID_VAR].values.item() if BAND_ID_VAR in ds.variables else None),
                "band_wavelength": (
                    ds[BAND_WAVELENGTH_VAR].values.item() if BAND_WAVELENGTH_VAR in ds.variables else None
                ),
                "resolution_x": ds[X_VAR].size if X_VAR in ds.variables else None,
                "resolution_y": ds[Y_VAR].size if Y_VAR in ds.variables else None,
            }
    except KeyError as e:
        LOGGER.exception("Error occurred")
        msg = f"Error extracting metadata: {e}"
        raise KeyError(msg) from e
    except RuntimeError as e:
        LOGGER.exception("Error occurred")
        msg = f"Error extracting metadata: {e}"
        raise RuntimeError(msg) from e
    except ValueError as e:
        LOGGER.exception("Error occurred")
        msg = f"Error extracting metadata: {e}"
        raise ValueError(msg) from e
