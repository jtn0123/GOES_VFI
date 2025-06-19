"""Tests for NetCDF rendering functionality."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from goesvfi.integrity_check.render.netcdf import (
    BAND_ID_VAR,
    BAND_WAVELENGTH_VAR,
    DEFAULT_MAX_TEMP_K,
    DEFAULT_MIN_TEMP_K,
    RADIANCE_VAR,
    TARGET_BAND_ID,
    X_VAR,
    Y_VAR,
    _convert_radiance_to_temperature,
    _validate_band_id,
    extract_metadata,
    render_png,
)


class TestNetCDFRender:
    """Test NetCDF rendering functions for GOES satellite data."""

    def test_convert_radiance_to_temperature(self):
        """Test conversion from radiance to brightness temperature."""
        # Test with realistic radiance values
        radiance = np.array([100.0, 150.0, 200.0])  # More realistic values

        # Create mock dataset with planck constants
        mock_ds = MagicMock()
        mock_ds.attrs = {
            "planck_fk1": 202263.0,
            "planck_fk2": 3698.0,
            "planck_bc1": 0.5,
            "planck_bc2": 0.9991,
        }

        temps = _convert_radiance_to_temperature(
            radiance, mock_ds, DEFAULT_MIN_TEMP_K, DEFAULT_MAX_TEMP_K
        )

        assert isinstance(temps, np.ndarray)
        assert temps.shape == radiance.shape
        # Check that values are normalized between 0 and 1 (inverted for IR)
        assert np.all(temps >= 0.0)
        assert np.all(temps <= 1.0)

    def test_validate_band_id(self):
        """Test band ID validation."""
        # Create mock dataset with correct band
        mock_ds = MagicMock()
        mock_band_var = MagicMock()
        mock_band_var.values = TARGET_BAND_ID
        mock_ds.__getitem__ = MagicMock(return_value=mock_band_var)
        mock_ds.variables = {BAND_ID_VAR: mock_band_var}

        # Should not raise
        _validate_band_id(mock_ds)

        # Test with wrong band
        mock_band_var.values = 1  # Wrong band
        with pytest.raises(ValueError, match="Expected Band 13"):
            _validate_band_id(mock_ds)

    @patch("xarray.open_dataset")
    @patch("pathlib.Path.exists", return_value=True)
    def test_extract_metadata(self, mock_exists, mock_open_dataset):
        """Test metadata extraction from NetCDF."""
        # Create mock dataset
        mock_ds = MagicMock()
        mock_ds.attrs = {
            "platform_ID": "GOES-16",
            "instrument_type": "ABI",
            "date_created": "2023-01-15T12:00:00Z",
        }

        # Mock band variables
        mock_band_id = MagicMock()
        mock_band_id.values.item.return_value = 13

        mock_band_wavelength = MagicMock()
        mock_band_wavelength.values.item.return_value = 10.3

        # Mock x and y variables
        mock_x = MagicMock(size=2500)
        mock_y = MagicMock(size=1500)

        mock_ds.variables = {
            BAND_ID_VAR: mock_band_id,
            BAND_WAVELENGTH_VAR: mock_band_wavelength,
            X_VAR: mock_x,
            Y_VAR: mock_y,
        }

        # Mock __getitem__ to return the mocked variables
        def get_item(key):
            if key == BAND_ID_VAR:
                return mock_band_id
            elif key == BAND_WAVELENGTH_VAR:
                return mock_band_wavelength
            elif key == X_VAR:
                return mock_x
            elif key == Y_VAR:
                return mock_y
            return MagicMock()

        mock_ds.__getitem__ = MagicMock(side_effect=get_item)

        mock_open_dataset.return_value.__enter__.return_value = mock_ds

        # Test extraction
        metadata = extract_metadata(Path("/tmp/test.nc"))

        assert isinstance(metadata, dict)
        assert metadata["satellite"] == "GOES-16"
        assert metadata["instrument"] == "ABI"
        assert metadata["timestamp"] == "2023-01-15T12:00:00Z"
        assert metadata["band_id"] == 13
        assert metadata["band_wavelength"] == 10.3
        assert metadata["resolution_x"] == 2500
        assert metadata["resolution_y"] == 1500

    @patch("xarray.open_dataset")
    @patch("goesvfi.integrity_check.render.netcdf._create_figure")
    @patch("pathlib.Path.exists", return_value=True)
    def test_render_png_success(
        self, mock_exists, mock_create_figure, mock_open_dataset
    ):
        """Test successful rendering to PNG."""
        # Create mock dataset
        mock_ds = MagicMock()

        # Mock radiance data
        radiance_data = np.random.rand(500, 500) * 100
        mock_radiance = MagicMock()
        mock_radiance.values = radiance_data

        # Mock band attributes
        mock_radiance.attrs = {"scale_factor": 0.1, "add_offset": 0.0}

        # Mock band_id variable properly
        mock_band_var = MagicMock()
        mock_band_var.values = np.array(TARGET_BAND_ID)  # Scalar numpy array

        mock_ds.variables = {RADIANCE_VAR: mock_radiance, BAND_ID_VAR: mock_band_var}

        # Mock __getitem__ to return appropriate variable
        def get_item(key):
            if key == BAND_ID_VAR:
                return mock_band_var
            elif key == RADIANCE_VAR:
                return mock_radiance
            return MagicMock()

        mock_ds.__getitem__ = MagicMock(side_effect=get_item)

        # Mock band info attributes
        mock_ds.attrs = {
            "planck_fk1": 202263.0,
            "planck_fk2": 3698.0,
            "planck_bc1": 0.5,
            "planck_bc2": 0.9991,
        }

        mock_open_dataset.return_value.__enter__.return_value = mock_ds

        # Test rendering
        nc_path = Path("/tmp/test.nc")
        png_path = Path("/tmp/test.png")

        with patch("pathlib.Path.exists", return_value=True):
            render_png(nc_path, png_path)

        # Verify dataset was opened
        mock_open_dataset.assert_called_once()

        # Verify figure creation was called
        mock_create_figure.assert_called_once()

    def test_render_png_nonexistent_file(self):
        """Test error handling for non-existent NetCDF file."""
        nc_path = Path("/tmp/nonexistent.nc")
        png_path = Path("/tmp/output.png")

        with pytest.raises(FileNotFoundError):
            render_png(nc_path, png_path)

    @patch("xarray.open_dataset")
    @patch("pathlib.Path.exists", return_value=True)
    def test_render_png_missing_radiance(self, mock_exists, mock_open_dataset):
        """Test error handling for NetCDF without radiance data."""
        # Create mock dataset without radiance variable
        mock_ds = MagicMock()
        mock_ds.variables = {}  # No RADIANCE_VAR

        mock_open_dataset.return_value.__enter__.return_value = mock_ds

        nc_path = Path("/tmp/test.nc")
        png_path = Path("/tmp/test.png")

        with pytest.raises(
            IOError,
            match="Error rendering NetCDF file.*Radiance variable 'Rad' not found",
        ):
            render_png(nc_path, png_path)

    def test_default_temperature_constants(self):
        """Test default temperature constants."""
        assert isinstance(DEFAULT_MIN_TEMP_K, float)
        assert isinstance(DEFAULT_MAX_TEMP_K, float)
        assert DEFAULT_MIN_TEMP_K < DEFAULT_MAX_TEMP_K
        assert DEFAULT_MIN_TEMP_K > 0  # Kelvin scale
        assert DEFAULT_MAX_TEMP_K < 400  # Reasonable max temp
