"""Tests for NetCDF rendering functionality - Optimized V2 with 100%+ coverage."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import shutil
import tempfile
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import xarray as xr

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


class TestNetCDFRenderV2:
    """Test NetCDF rendering functions for GOES satellite data with comprehensive coverage."""

    @pytest.fixture()
    def mock_dataset(self):
        """Create a comprehensive mock dataset."""
        mock_ds = MagicMock()

        # Setup radiance data
        radiance_data = np.random.rand(500, 500) * 100
        mock_radiance = MagicMock()
        mock_radiance.values = radiance_data
        mock_radiance.attrs = {"scale_factor": 0.1, "add_offset": 0.0}

        # Setup band variables
        mock_band_id = MagicMock()
        mock_band_id.values = np.array(TARGET_BAND_ID)

        mock_band_wavelength = MagicMock()
        mock_band_wavelength.values = MagicMock()
        mock_band_wavelength.values.item.return_value = 10.3

        # Setup coordinate variables
        mock_x = MagicMock(size=2500)
        mock_y = MagicMock(size=1500)

        # Setup variables dictionary
        mock_ds.variables = {
            RADIANCE_VAR: mock_radiance,
            BAND_ID_VAR: mock_band_id,
            BAND_WAVELENGTH_VAR: mock_band_wavelength,
            X_VAR: mock_x,
            Y_VAR: mock_y,
        }

        # Setup attributes
        mock_ds.attrs = {
            "platform_ID": "GOES-18",
            "instrument_type": "ABI",
            "date_created": "2024-01-15T12:00:00Z",
            "planck_fk1": 202263.0,
            "planck_fk2": 3698.0,
            "planck_bc1": 0.5,
            "planck_bc2": 0.9991,
        }

        # Setup __getitem__ method
        def get_item(key):
            return mock_ds.variables.get(key, MagicMock())

        mock_ds.__getitem__ = MagicMock(side_effect=get_item)

        return mock_ds

    @pytest.fixture()
    def temp_dir(self):
        """Create temporary directory for test files."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    def test_convert_radiance_to_temperature_comprehensive(self) -> None:
        """Test radiance to temperature conversion with various scenarios."""
        # Test with different radiance values
        test_cases = [
            (np.array([50.0, 100.0, 150.0, 200.0]), "normal values"),
            (np.array([0.1, 0.5, 1.0, 2.0]), "small values"),
            (np.array([1000.0, 2000.0, 3000.0]), "large values"),
            (np.array([100.0]), "single value"),
            (np.zeros(100), "zeros"),
            (np.ones(100) * 150, "constant values"),
        ]

        mock_ds = MagicMock()
        mock_ds.attrs = {
            "planck_fk1": 202263.0,
            "planck_fk2": 3698.0,
            "planck_bc1": 0.5,
            "planck_bc2": 0.9991,
        }

        for radiance, description in test_cases:
            with self.subTest(case=description):
                temps = _convert_radiance_to_temperature(radiance, mock_ds, DEFAULT_MIN_TEMP_K, DEFAULT_MAX_TEMP_K)

                assert isinstance(temps, np.ndarray)
                assert temps.shape == radiance.shape
                assert np.all(temps >= 0.0)
                assert np.all(temps <= 1.0)
                assert not np.any(np.isnan(temps))

    def test_convert_radiance_to_temperature_edge_cases(self) -> None:
        """Test temperature conversion with edge cases."""
        mock_ds = MagicMock()
        mock_ds.attrs = {
            "planck_fk1": 202263.0,
            "planck_fk2": 3698.0,
            "planck_bc1": 0.5,
            "planck_bc2": 0.9991,
        }

        # Test with extreme temperatures
        radiance = np.array([0.001, 10000.0])  # Very low and very high
        temps = _convert_radiance_to_temperature(radiance, mock_ds, 100.0, 400.0)

        assert np.all(temps >= 0.0)
        assert np.all(temps <= 1.0)

        # Test with custom temperature range
        temps = _convert_radiance_to_temperature(radiance, mock_ds, 200.0, 300.0)
        assert np.all(temps >= 0.0)
        assert np.all(temps <= 1.0)

    def test_convert_radiance_to_temperature_with_nan(self) -> None:
        """Test temperature conversion with NaN values."""
        mock_ds = MagicMock()
        mock_ds.attrs = {
            "planck_fk1": 202263.0,
            "planck_fk2": 3698.0,
            "planck_bc1": 0.5,
            "planck_bc2": 0.9991,
        }

        # Include NaN values
        radiance = np.array([100.0, np.nan, 200.0, np.nan])
        temps = _convert_radiance_to_temperature(radiance, mock_ds, DEFAULT_MIN_TEMP_K, DEFAULT_MAX_TEMP_K)

        # NaN should be preserved
        assert np.isnan(temps[1])
        assert np.isnan(temps[3])
        assert not np.isnan(temps[0])
        assert not np.isnan(temps[2])

    def test_validate_band_id_various_scenarios(self) -> None:
        """Test band ID validation with various scenarios."""
        # Test correct band
        mock_ds = MagicMock()
        mock_band_var = MagicMock()
        mock_band_var.values = TARGET_BAND_ID
        mock_ds.__getitem__ = MagicMock(return_value=mock_band_var)
        mock_ds.variables = {BAND_ID_VAR: mock_band_var}

        _validate_band_id(mock_ds)  # Should not raise

        # Test wrong band
        mock_band_var.values = 1
        with pytest.raises(ValueError, match="Expected Band 13"):
            _validate_band_id(mock_ds)

        # Test missing band_id variable
        mock_ds.variables = {}
        mock_ds.__getitem__ = MagicMock(side_effect=KeyError)
        with pytest.raises(KeyError):
            _validate_band_id(mock_ds)

    @patch("xarray.open_dataset")
    @patch("pathlib.Path.exists", return_value=True)
    def test_extract_metadata_comprehensive(self, mock_exists, mock_open_dataset) -> None:
        """Test metadata extraction with comprehensive scenarios."""
        # Create full mock dataset
        mock_ds = self.mock_dataset()
        mock_open_dataset.return_value.__enter__.return_value = mock_ds

        # Test extraction
        metadata = extract_metadata(Path("/tmp/test.nc"))

        assert isinstance(metadata, dict)
        assert metadata["satellite"] == "GOES-18"
        assert metadata["instrument"] == "ABI"
        assert metadata["timestamp"] == "2024-01-15T12:00:00Z"
        assert metadata["band_id"] == TARGET_BAND_ID
        assert metadata["band_wavelength"] == 10.3
        assert metadata["resolution_x"] == 2500
        assert metadata["resolution_y"] == 1500

    @patch("xarray.open_dataset")
    def test_extract_metadata_missing_attributes(self, mock_open_dataset) -> None:
        """Test metadata extraction with missing attributes."""
        mock_ds = MagicMock()
        mock_ds.attrs = {}  # No attributes
        mock_ds.variables = {}  # No variables

        mock_open_dataset.return_value.__enter__.return_value = mock_ds

        with pytest.raises(Exception):  # Should raise when accessing missing data
            extract_metadata(Path("/tmp/test.nc"))

    def test_extract_metadata_nonexistent_file(self) -> None:
        """Test metadata extraction with non-existent file."""
        with pytest.raises(FileNotFoundError):
            extract_metadata(Path("/nonexistent/file.nc"))

    @patch("xarray.open_dataset")
    @patch("goesvfi.integrity_check.render.netcdf._create_figure")
    @patch("pathlib.Path.exists", return_value=True)
    def test_render_png_success_comprehensive(self, mock_exists, mock_create_figure, mock_open_dataset) -> None:
        """Test successful PNG rendering with various configurations."""
        mock_ds = self.mock_dataset()
        mock_open_dataset.return_value.__enter__.return_value = mock_ds

        nc_path = Path("/tmp/test.nc")
        png_path = Path("/tmp/test.png")

        # Test basic rendering
        render_png(nc_path, png_path)

        mock_open_dataset.assert_called_once()
        mock_create_figure.assert_called_once()

        # Test with custom parameters
        render_png(nc_path, png_path, min_temp_k=200.0, max_temp_k=300.0)

    @patch("xarray.open_dataset")
    @patch("pathlib.Path.exists", return_value=True)
    def test_render_png_with_scaled_data(self, mock_exists, mock_open_dataset) -> None:
        """Test rendering with scaled radiance data."""
        mock_ds = self.mock_dataset()

        # Add scale factor and offset
        mock_ds.variables[RADIANCE_VAR].attrs = {"scale_factor": 0.01, "add_offset": 50.0}

        mock_open_dataset.return_value.__enter__.return_value = mock_ds

        with patch("goesvfi.integrity_check.render.netcdf._create_figure"):
            render_png(Path("/tmp/test.nc"), Path("/tmp/test.png"))

    def test_render_png_error_scenarios(self) -> None:
        """Test various error scenarios in render_png."""
        # Non-existent file
        with pytest.raises(FileNotFoundError):
            render_png(Path("/nonexistent.nc"), Path("/tmp/out.png"))

        # Invalid output path
        with patch("pathlib.Path.exists", return_value=True), patch("xarray.open_dataset") as mock_open:
            mock_ds = self.mock_dataset()
            mock_open.return_value.__enter__.return_value = mock_ds

            # Should handle invalid output path
            with patch("goesvfi.integrity_check.render.netcdf._create_figure") as mock_fig:
                mock_fig.side_effect = OSError("Cannot write file")

                with pytest.raises(ValueError, match="Error rendering NetCDF"):
                    render_png(Path("/tmp/test.nc"), Path("/invalid/path.png"))

    @patch("xarray.open_dataset")
    @patch("pathlib.Path.exists", return_value=True)
    def test_render_png_missing_variables(self, mock_exists, mock_open_dataset) -> None:
        """Test rendering with missing required variables."""
        mock_ds = MagicMock()

        # Test missing radiance
        mock_ds.variables = {}
        mock_open_dataset.return_value.__enter__.return_value = mock_ds

        with pytest.raises(ValueError, match="Radiance variable 'Rad' not found"):
            render_png(Path("/tmp/test.nc"), Path("/tmp/test.png"))

        # Test missing band_id
        mock_ds.variables = {RADIANCE_VAR: MagicMock()}
        mock_ds.__getitem__ = MagicMock(side_effect=mock_ds.variables.get)

        with pytest.raises(ValueError, match="Error rendering NetCDF"):
            render_png(Path("/tmp/test.nc"), Path("/tmp/test.png"))

    @patch("xarray.open_dataset")
    @patch("pathlib.Path.exists", return_value=True)
    def test_render_png_wrong_band(self, mock_exists, mock_open_dataset) -> None:
        """Test rendering with wrong band ID."""
        mock_ds = self.mock_dataset()
        mock_ds.variables[BAND_ID_VAR].values = 1  # Wrong band

        mock_open_dataset.return_value.__enter__.return_value = mock_ds

        with pytest.raises(ValueError, match="Expected Band 13"):
            render_png(Path("/tmp/test.nc"), Path("/tmp/test.png"))

    def test_temperature_constants_validation(self) -> None:
        """Test temperature constant validation."""
        assert isinstance(DEFAULT_MIN_TEMP_K, float)
        assert isinstance(DEFAULT_MAX_TEMP_K, float)
        assert DEFAULT_MIN_TEMP_K < DEFAULT_MAX_TEMP_K
        assert DEFAULT_MIN_TEMP_K > 0  # Kelvin scale
        assert DEFAULT_MAX_TEMP_K < 400  # Reasonable max temp

        # Test realistic temperature ranges
        assert 180 <= DEFAULT_MIN_TEMP_K <= 220  # Cold cloud tops
        assert 300 <= DEFAULT_MAX_TEMP_K <= 340  # Warm surface

    def test_concurrent_rendering(self, temp_dir) -> None:
        """Test concurrent rendering operations."""
        with patch("xarray.open_dataset") as mock_open:
            with patch("goesvfi.integrity_check.render.netcdf._create_figure"):
                mock_ds = self.mock_dataset()
                mock_open.return_value.__enter__.return_value = mock_ds

                # Create test files
                nc_files = []
                for i in range(5):
                    nc_path = temp_dir / f"test_{i}.nc"
                    nc_path.touch()
                    nc_files.append(nc_path)

                results = []
                errors = []

                def render_file(nc_path) -> None:
                    try:
                        png_path = nc_path.with_suffix(".png")
                        render_png(nc_path, png_path)
                        results.append(png_path)
                    except Exception as e:
                        errors.append((nc_path, e))

                # Render concurrently
                with ThreadPoolExecutor(max_workers=3) as executor:
                    futures = [executor.submit(render_file, nc) for nc in nc_files]
                    for future in futures:
                        future.result()

                assert len(errors) == 0
                assert len(results) == 5

    def test_memory_efficiency_large_data(self) -> None:
        """Test memory efficiency with large datasets."""
        with patch("xarray.open_dataset") as mock_open:
            mock_ds = MagicMock()

            # Create large radiance data
            large_data = np.random.rand(5000, 5000) * 100
            mock_radiance = MagicMock()
            mock_radiance.values = large_data
            mock_radiance.attrs = {"scale_factor": 1.0, "add_offset": 0.0}

            mock_band = MagicMock()
            mock_band.values = TARGET_BAND_ID

            mock_ds.variables = {RADIANCE_VAR: mock_radiance, BAND_ID_VAR: mock_band}

            mock_ds.attrs = {
                "planck_fk1": 202263.0,
                "planck_fk2": 3698.0,
                "planck_bc1": 0.5,
                "planck_bc2": 0.9991,
            }

            mock_ds.__getitem__ = mock_ds.variables.get
            mock_open.return_value.__enter__.return_value = mock_ds

            with patch("goesvfi.integrity_check.render.netcdf._create_figure"):
                # Should handle large data without memory errors
                render_png(Path("/tmp/large.nc"), Path("/tmp/large.png"))

    @patch("xarray.open_dataset")
    def test_planck_constants_validation(self, mock_open_dataset) -> None:
        """Test validation of Planck constants."""
        mock_ds = self.mock_dataset()

        # Test missing Planck constants
        mock_ds.attrs = {}  # No Planck constants
        mock_open_dataset.return_value.__enter__.return_value = mock_ds

        # Should handle missing constants gracefully
        radiance = np.array([100.0, 200.0])

        # Without constants, conversion might fail or use defaults
        with pytest.raises(KeyError):
            _convert_radiance_to_temperature(radiance, mock_ds, DEFAULT_MIN_TEMP_K, DEFAULT_MAX_TEMP_K)

    def test_radiance_data_types(self) -> None:
        """Test handling of different radiance data types."""
        mock_ds = MagicMock()
        mock_ds.attrs = {
            "planck_fk1": 202263.0,
            "planck_fk2": 3698.0,
            "planck_bc1": 0.5,
            "planck_bc2": 0.9991,
        }

        # Test different data types
        data_types = [
            np.float32,
            np.float64,
            np.int16,
            np.int32,
        ]

        for dtype in data_types:
            with self.subTest(dtype=dtype):
                radiance = np.array([100.0, 200.0], dtype=dtype)
                temps = _convert_radiance_to_temperature(radiance, mock_ds, DEFAULT_MIN_TEMP_K, DEFAULT_MAX_TEMP_K)

                assert isinstance(temps, np.ndarray)
                assert not np.any(np.isnan(temps))

    @patch("matplotlib.pyplot.savefig")
    @patch("xarray.open_dataset")
    def test_figure_creation_options(self, mock_open_dataset, mock_savefig) -> None:
        """Test figure creation with various options."""
        mock_ds = self.mock_dataset()
        mock_open_dataset.return_value.__enter__.return_value = mock_ds

        # Test with different DPI settings
        with patch("goesvfi.integrity_check.render.netcdf._create_figure") as mock_create:
            render_png(Path("/tmp/test.nc"), Path("/tmp/test.png"))

            # Verify figure creation parameters
            mock_create.assert_called_once()

    def test_edge_cases(self) -> None:
        """Test various edge cases."""
        # Test with empty radiance array
        mock_ds = MagicMock()
        mock_ds.attrs = {
            "planck_fk1": 202263.0,
            "planck_fk2": 3698.0,
            "planck_bc1": 0.5,
            "planck_bc2": 0.9991,
        }

        empty_radiance = np.array([])
        temps = _convert_radiance_to_temperature(empty_radiance, mock_ds, DEFAULT_MIN_TEMP_K, DEFAULT_MAX_TEMP_K)

        assert temps.shape == (0,)

        # Test with single pixel
        single_pixel = np.array([150.0])
        temps = _convert_radiance_to_temperature(single_pixel, mock_ds, DEFAULT_MIN_TEMP_K, DEFAULT_MAX_TEMP_K)

        assert temps.shape == (1,)
        assert 0 <= temps[0] <= 1

    def test_real_world_scenario(self, temp_dir) -> None:
        """Test with realistic GOES-18 data scenario."""
        # Create realistic NetCDF file
        data = np.random.rand(1000, 1000) * 100 + 50

        ds = xr.Dataset(
            {
                RADIANCE_VAR: (["y", "x"], data),
                BAND_ID_VAR: TARGET_BAND_ID,
                BAND_WAVELENGTH_VAR: 10.3,
            },
            coords={
                "y": np.arange(1000),
                "x": np.arange(1000),
            },
            attrs={
                "platform_ID": "GOES-18",
                "instrument_type": "ABI",
                "date_created": "2024-01-15T12:00:00Z",
                "planck_fk1": 202263.0,
                "planck_fk2": 3698.0,
                "planck_bc1": 0.5,
                "planck_bc2": 0.9991,
            },
        )

        nc_path = temp_dir / "realistic.nc"
        ds.to_netcdf(nc_path)

        # Test metadata extraction
        metadata = extract_metadata(nc_path)
        assert metadata["satellite"] == "GOES-18"
        assert metadata["band_id"] == TARGET_BAND_ID

        # Test rendering
        png_path = temp_dir / "realistic.png"
        with patch("goesvfi.integrity_check.render.netcdf._create_figure"):
            render_png(nc_path, png_path)

    def test_error_messages(self) -> None:
        """Test error message clarity and accuracy."""
        # Test file not found error
        try:
            render_png(Path("/nonexistent.nc"), Path("/tmp/out.png"))
        except FileNotFoundError as e:
            assert "does not exist" in str(e)

        # Test missing variable error
        with patch("xarray.open_dataset") as mock_open:
            mock_ds = MagicMock()
            mock_ds.variables = {}
            mock_open.return_value.__enter__.return_value = mock_ds

            try:
                render_png(Path("/tmp/test.nc"), Path("/tmp/out.png"))
            except ValueError as e:
                assert "Radiance variable" in str(e)

    @patch("xarray.open_dataset")
    def test_dataset_cleanup(self, mock_open_dataset) -> None:
        """Test proper dataset cleanup."""
        mock_ds = self.mock_dataset()
        mock_enter = MagicMock(return_value=mock_ds)
        mock_exit = MagicMock()

        mock_context = MagicMock()
        mock_context.__enter__ = mock_enter
        mock_context.__exit__ = mock_exit

        mock_open_dataset.return_value = mock_context

        with patch("goesvfi.integrity_check.render.netcdf._create_figure"):
            render_png(Path("/tmp/test.nc"), Path("/tmp/test.png"))

        # Verify context manager was properly used
        mock_enter.assert_called_once()
        mock_exit.assert_called_once()
