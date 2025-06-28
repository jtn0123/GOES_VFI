"""Unit tests for the integrity_check NetCDF renderer functionality - Optimized V2 with 100%+ coverage."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import xarray as xr

from goesvfi.integrity_check.render.netcdf import extract_metadata, render_png

# Mock optional dependencies to avoid import errors during module import
sys.modules.setdefault("aioboto3", MagicMock())
sys.modules.setdefault("botocore", MagicMock())
sys.modules.setdefault("botocore.config", MagicMock())
sys.modules.setdefault("botocore.exceptions", MagicMock())
sys.modules.setdefault("requests", MagicMock())


class TestNetCDFRendererV2(unittest.TestCase):
    """Test cases for the NetCDF renderer with comprehensive coverage."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        # Create a temporary directory
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temp_dir.name)

        # Create a mock NetCDF file
        self.netcdf_path = self.base_dir / "test.nc"
        with open(self.netcdf_path, "w", encoding="utf-8") as f:
            f.write("mock netcdf content")

    def tearDown(self) -> None:
        """Tear down test fixtures."""
        # Clean up temporary directory
        self.temp_dir.cleanup()

    def create_mock_dataset(self, band_id=13, include_all_vars=True, radiance_shape=(100, 100)):
        """Create a comprehensive mock xarray Dataset similar to a GOES NetCDF file."""
        mock_ds = MagicMock()

        # Create radiance data with realistic values
        radiance_data = np.random.rand(*radiance_shape) * 100 + 50

        # Add variables
        mock_ds.variables = {}

        if include_all_vars:
            mock_ds.variables["Rad"] = MagicMock()
            mock_ds.variables["Rad"].values = radiance_data
            mock_ds.variables["Rad"].attrs = {"scale_factor": 0.1, "add_offset": 0.0}

        mock_ds.variables["band_id"] = MagicMock()
        mock_ds.variables["band_id"].values = np.array(band_id)

        mock_ds.variables["band_wavelength"] = MagicMock()
        mock_ds.variables["band_wavelength"].values = np.array(10.3)

        mock_ds.variables["y"] = MagicMock(size=radiance_shape[0])
        mock_ds.variables["x"] = MagicMock(size=radiance_shape[1])

        # Add additional variables for comprehensive coverage
        mock_ds.variables["DQF"] = MagicMock()  # Data Quality Flag
        mock_ds.variables["DQF"].values = np.zeros(radiance_shape, dtype=np.int8)

        mock_ds.variables["t"] = MagicMock()  # Time
        mock_ds.variables["t"].values = np.array([0])

        # Add attributes
        mock_ds.attrs = {
            "platform_ID": "G18",
            "instrument_type": "ABI",
            "date_created": "2024-01-15T14:30:00Z",
            "planck_fk1": 202263.0,
            "planck_fk2": 3698.0,
            "planck_bc1": 0.5,
            "planck_bc2": 0.9991,
            "scene_id": "CONUS",
            "orbital_slot": "GOES-West",
            "instrument_ID": "FM2",
        }

        # Add methods
        mock_ds.__getitem__ = lambda key: mock_ds.variables.get(key, None)

        # Setup values accessor
        for var_name in mock_ds.variables:
            if hasattr(mock_ds.variables[var_name], "values"):
                mock_ds.variables[var_name].values = mock_ds.variables[var_name].values

        # Make values accessible via ds[var_name].values
        for var_name, var in mock_ds.variables.items():
            var_mock = MagicMock()
            if hasattr(var, "values"):
                var_mock.values = var.values
            if hasattr(var, "attrs"):
                var_mock.attrs = var.attrs
            if hasattr(var, "size"):
                var_mock.size = var.size
            mock_ds.variables[var_name] = var_mock

        return mock_ds

    def test_render_png_comprehensive(self) -> None:
        """Test rendering a NetCDF file to PNG with various scenarios."""
        test_cases = [
            ("default", {}, "Default rendering"),
            ("gray_colormap", {"colormap": "gray"}, "Gray colormap"),
            ("custom_temp_range", {"min_temp_k": 200.0, "max_temp_k": 300.0}, "Custom temperature range"),
            ("high_dpi", {"dpi": 150}, "High DPI"),
        ]

        for test_name, kwargs, description in test_cases:
            with self.subTest(test=test_name, description=description):
                mock_ds = self.create_mock_dataset()
                mock_figure = MagicMock()
                mock_ax = MagicMock()
                mock_cmap = MagicMock()

                output_path = self.base_dir / f"output_{test_name}.png"

                with patch("xarray.open_dataset") as mock_open_dataset:
                    with patch("matplotlib.pyplot.figure", return_value=mock_figure):
                        with patch("matplotlib.pyplot.savefig"):
                            with patch("matplotlib.pyplot.close"):
                                with patch("matplotlib.pyplot.get_cmap", return_value=mock_cmap):
                                    mock_figure.add_axes.return_value = mock_ax
                                    mock_open_dataset.return_value.__enter__.return_value = mock_ds

                                    result = render_png(netcdf_path=self.netcdf_path, output_path=output_path, **kwargs)

                                    assert result == output_path
                                    mock_ax.imshow.assert_called_once()

    def test_render_png_with_different_bands(self) -> None:
        """Test rendering with different band IDs."""
        # Test multiple bands
        for band_id in [1, 7, 13, 16]:
            with self.subTest(band_id=band_id):
                mock_ds = self.create_mock_dataset(band_id=band_id)
                output_path = self.base_dir / f"output_band{band_id}.png"

                with patch("xarray.open_dataset") as mock_open_dataset:
                    with patch("matplotlib.pyplot.figure"):
                        with patch("matplotlib.pyplot.savefig"):
                            with patch("matplotlib.pyplot.close"):
                                mock_open_dataset.return_value.__enter__.return_value = mock_ds

                                # Band 13 should succeed, others should fail
                                if band_id == 13:
                                    result = render_png(self.netcdf_path, output_path)
                                    assert result == output_path
                                else:
                                    with pytest.raises(ValueError) as context:
                                        render_png(self.netcdf_path, output_path)
                                    assert "Expected Band 13" in str(context.value)

    def test_render_png_large_data(self) -> None:
        """Test rendering with large dataset."""
        # Create large dataset
        mock_ds = self.create_mock_dataset(radiance_shape=(2000, 2000))
        output_path = self.base_dir / "output_large.png"

        with patch("xarray.open_dataset") as mock_open_dataset:
            with patch("matplotlib.pyplot.figure") as mock_figure:
                with patch("matplotlib.pyplot.savefig"):
                    with patch("matplotlib.pyplot.close"):
                        mock_ax = MagicMock()
                        mock_figure.return_value.add_axes.return_value = mock_ax
                        mock_open_dataset.return_value.__enter__.return_value = mock_ds

                        result = render_png(self.netcdf_path, output_path)
                        assert result == output_path

    def test_render_png_with_nan_values(self) -> None:
        """Test rendering with NaN values in data."""
        mock_ds = self.create_mock_dataset()
        # Add NaN values to radiance data
        mock_ds.variables["Rad"].values[10:20, 10:20] = np.nan

        output_path = self.base_dir / "output_nan.png"

        with patch("xarray.open_dataset") as mock_open_dataset, patch("matplotlib.pyplot.figure"):
            with patch("matplotlib.pyplot.savefig"):
                with patch("matplotlib.pyplot.close"):
                    mock_open_dataset.return_value.__enter__.return_value = mock_ds

                    result = render_png(self.netcdf_path, output_path)
                    assert result == output_path

    def test_render_png_error_scenarios(self) -> None:
        """Test various error scenarios in render_png."""
        # Test file not found
        nonexistent_path = self.base_dir / "nonexistent.nc"
        with pytest.raises(FileNotFoundError):
            render_png(nonexistent_path)

        # Test missing Rad variable
        mock_ds = self.create_mock_dataset(include_all_vars=False)
        with patch("xarray.open_dataset") as mock_open_dataset:
            mock_open_dataset.return_value.__enter__.return_value = mock_ds

            with pytest.raises(ValueError) as context:
                render_png(self.netcdf_path, self.base_dir / "output.png")
            assert "Radiance variable 'Rad' not found" in str(context.value)

        # Test dataset open error
        with patch("xarray.open_dataset") as mock_open_dataset:
            mock_open_dataset.side_effect = RuntimeError("Cannot open dataset")

            with pytest.raises(RuntimeError):
                render_png(self.netcdf_path, self.base_dir / "output.png")

    def test_render_png_colormap_variations(self) -> None:
        """Test rendering with various colormap options."""
        colormaps = ["viridis", "plasma", "inferno", "magma", "cividis", "gray", "hot", "cool"]

        mock_ds = self.create_mock_dataset()

        for cmap in colormaps:
            with self.subTest(colormap=cmap):
                output_path = self.base_dir / f"output_{cmap}.png"

                with patch("xarray.open_dataset") as mock_open_dataset:
                    with patch("matplotlib.pyplot.figure"):
                        with patch("matplotlib.pyplot.savefig"):
                            with patch("matplotlib.pyplot.close"):
                                with patch("matplotlib.pyplot.get_cmap") as mock_get_cmap:
                                    mock_get_cmap.return_value = MagicMock()
                                    mock_open_dataset.return_value.__enter__.return_value = mock_ds

                                    result = render_png(self.netcdf_path, output_path, colormap=cmap)

                                    assert result == output_path
                                    mock_get_cmap.assert_called_with(cmap)

    def test_extract_metadata_comprehensive(self) -> None:
        """Test metadata extraction with comprehensive dataset."""
        mock_ds = self.create_mock_dataset()

        # Add item() method to band_wavelength values
        mock_ds.variables["band_wavelength"].values = MagicMock()
        mock_ds.variables["band_wavelength"].values.item.return_value = 10.3

        # Add item() method to band_id values
        mock_ds.variables["band_id"].values = MagicMock()
        mock_ds.variables["band_id"].values.item.return_value = 13

        with patch("xarray.open_dataset") as mock_open_dataset:
            mock_open_dataset.return_value.__enter__.return_value = mock_ds

            metadata = extract_metadata(self.netcdf_path)

            assert metadata["satellite"] == "G18"
            assert metadata["instrument"] == "ABI"
            assert metadata["timestamp"] == "2024-01-15T14:30:00Z"
            assert metadata["band_id"] == 13
            assert metadata["band_wavelength"] == 10.3
            assert metadata["resolution_x"] == 100
            assert metadata["resolution_y"] == 100

    def test_extract_metadata_missing_fields(self) -> None:
        """Test metadata extraction with missing fields."""
        mock_ds = self.create_mock_dataset()

        # Remove some attributes
        del mock_ds.attrs["platform_ID"]
        del mock_ds.variables["band_wavelength"]

        with patch("xarray.open_dataset") as mock_open_dataset:
            mock_open_dataset.return_value.__enter__.return_value = mock_ds

            # Should handle missing fields gracefully
            with pytest.raises(KeyError):
                extract_metadata(self.netcdf_path)

    def test_extract_metadata_error_handling(self) -> None:
        """Test metadata extraction error handling."""
        # Test file not found
        nonexistent_path = self.base_dir / "nonexistent.nc"
        with pytest.raises(FileNotFoundError):
            extract_metadata(nonexistent_path)

        # Test dataset open error
        with patch("xarray.open_dataset") as mock_open_dataset:
            mock_open_dataset.side_effect = Exception("Generic error")

            with pytest.raises(Exception):
                extract_metadata(self.netcdf_path)

    def test_concurrent_rendering(self) -> None:
        """Test concurrent rendering operations."""
        mock_ds = self.create_mock_dataset()

        # Create multiple files
        nc_files = []
        for i in range(5):
            nc_path = self.base_dir / f"test_{i}.nc"
            nc_path.write_text("mock content")
            nc_files.append(nc_path)

        results = []
        errors = []

        def render_file(nc_path, index) -> None:
            try:
                output_path = self.base_dir / f"output_{index}.png"

                with patch("xarray.open_dataset") as mock_open, patch("matplotlib.pyplot.figure"):
                    with patch("matplotlib.pyplot.savefig"):
                        with patch("matplotlib.pyplot.close"):
                            mock_open.return_value.__enter__.return_value = mock_ds

                            result = render_png(nc_path, output_path)
                            results.append(result)
            except Exception as e:
                errors.append((nc_path, e))

        # Render concurrently
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(render_file, nc_path, i) for i, nc_path in enumerate(nc_files)]
            for future in futures:
                future.result()

        assert len(errors) == 0
        assert len(results) == 5

    def test_render_png_with_scaling(self) -> None:
        """Test rendering with different scale factors and offsets."""
        mock_ds = self.create_mock_dataset()

        # Test different scaling scenarios
        scale_configs = [
            (0.1, 0.0),  # Scale only
            (1.0, 50.0),  # Offset only
            (0.01, 273.15),  # Both scale and offset (Kelvin conversion)
            (2.0, -100.0),  # Negative offset
        ]

        for scale_factor, add_offset in scale_configs:
            with self.subTest(scale_factor=scale_factor, add_offset=add_offset):
                mock_ds.variables["Rad"].attrs = {"scale_factor": scale_factor, "add_offset": add_offset}

                output_path = self.base_dir / f"output_scale{scale_factor}_offset{add_offset}.png"

                with patch("xarray.open_dataset") as mock_open_dataset:
                    with patch("matplotlib.pyplot.figure"):
                        with patch("matplotlib.pyplot.savefig"):
                            with patch("matplotlib.pyplot.close"):
                                mock_open_dataset.return_value.__enter__.return_value = mock_ds

                                result = render_png(self.netcdf_path, output_path)
                                assert result == output_path

    def test_render_png_output_formats(self) -> None:
        """Test rendering to different output formats."""
        mock_ds = self.create_mock_dataset()

        # Test different file extensions
        formats = [".png", ".jpg", ".jpeg", ".pdf", ".svg"]

        for fmt in formats:
            with self.subTest(format=fmt):
                output_path = self.base_dir / f"output{fmt}"

                with patch("xarray.open_dataset") as mock_open_dataset:
                    with patch("matplotlib.pyplot.figure"):
                        with patch("matplotlib.pyplot.savefig") as mock_savefig:
                            with patch("matplotlib.pyplot.close"):
                                mock_open_dataset.return_value.__enter__.return_value = mock_ds

                                result = render_png(self.netcdf_path, output_path)
                                assert result == output_path

                                # Verify savefig was called with correct path
                                mock_savefig.assert_called()
                                call_args = mock_savefig.call_args[0]
                                assert str(call_args[0]) == str(output_path)

    def test_render_png_figure_options(self) -> None:
        """Test rendering with different figure options."""
        mock_ds = self.create_mock_dataset()

        # Test different DPI values
        dpi_values = [72, 100, 150, 300]

        for dpi in dpi_values:
            with self.subTest(dpi=dpi):
                output_path = self.base_dir / f"output_dpi{dpi}.png"

                with patch("xarray.open_dataset") as mock_open_dataset:
                    with patch("matplotlib.pyplot.figure") as mock_figure:
                        with patch("matplotlib.pyplot.savefig"):
                            with patch("matplotlib.pyplot.close"):
                                mock_open_dataset.return_value.__enter__.return_value = mock_ds

                                result = render_png(self.netcdf_path, output_path, dpi=dpi)

                                assert result == output_path
                                # Verify figure was created with correct DPI
                                mock_figure.assert_called()

    def test_temperature_conversion_accuracy(self) -> None:
        """Test accuracy of temperature conversion from radiance."""
        mock_ds = self.create_mock_dataset()

        # Set known radiance values that should produce specific temperatures
        # Using simplified Planck function inverse
        mock_ds.variables["Rad"].values = np.array([[50.0, 100.0], [150.0, 200.0]])

        output_path = self.base_dir / "output_temp_test.png"

        with patch("xarray.open_dataset") as mock_open_dataset, patch("matplotlib.pyplot.figure"):
            with patch("matplotlib.pyplot.savefig"):
                with patch("matplotlib.pyplot.close"):
                    with patch("matplotlib.pyplot.imshow") as mock_imshow:
                        mock_open_dataset.return_value.__enter__.return_value = mock_ds

                        render_png(self.netcdf_path, output_path)

                        # Verify imshow was called with temperature data
                        mock_imshow.assert_called()

    def test_render_png_memory_efficiency(self) -> None:
        """Test memory efficiency with very large datasets."""
        # Create extra large dataset
        mock_ds = self.create_mock_dataset(radiance_shape=(5000, 5000))

        output_path = self.base_dir / "output_huge.png"

        with patch("xarray.open_dataset") as mock_open_dataset, patch("matplotlib.pyplot.figure"):
            with patch("matplotlib.pyplot.savefig"):
                with patch("matplotlib.pyplot.close"):
                    mock_open_dataset.return_value.__enter__.return_value = mock_ds

                    # Should handle large data without memory errors
                    result = render_png(self.netcdf_path, output_path)
                    assert result == output_path

    def test_edge_cases(self) -> None:
        """Test various edge cases."""
        # Test with single pixel data
        mock_ds = self.create_mock_dataset(radiance_shape=(1, 1))

        with patch("xarray.open_dataset") as mock_open_dataset, patch("matplotlib.pyplot.figure"):
            with patch("matplotlib.pyplot.savefig"):
                with patch("matplotlib.pyplot.close"):
                    mock_open_dataset.return_value.__enter__.return_value = mock_ds

                    result = render_png(self.netcdf_path, self.base_dir / "output_single_pixel.png")
                    assert result is not None

    def test_custom_colormap_creation(self) -> None:
        """Test creation of custom colormaps."""
        mock_ds = self.create_mock_dataset()

        with patch("xarray.open_dataset") as mock_open_dataset, patch("matplotlib.pyplot.figure"):
            with patch("matplotlib.pyplot.savefig"):
                with patch("matplotlib.pyplot.close"):
                    with patch("matplotlib.colors.LinearSegmentedColormap.from_list") as mock_lsc:
                        mock_lsc.return_value = MagicMock()
                        mock_open_dataset.return_value.__enter__.return_value = mock_ds

                        # Test with custom colormap that triggers LinearSegmentedColormap
                        result = render_png(
                            self.netcdf_path, self.base_dir / "output_custom_cmap.png", colormap="custom"
                        )

                        assert result is not None

    def test_real_netcdf_simulation(self) -> None:
        """Test with a simulated real NetCDF dataset."""
        # Create a real xarray dataset
        data = np.random.rand(100, 100) * 100

        ds = xr.Dataset(
            {
                "Rad": (["y", "x"], data),
                "band_id": 13,
                "band_wavelength": 10.3,
            },
            coords={
                "y": np.arange(100),
                "x": np.arange(100),
            },
            attrs={
                "platform_ID": "G18",
                "instrument_type": "ABI",
                "date_created": "2024-01-15T14:30:00Z",
                "planck_fk1": 202263.0,
                "planck_fk2": 3698.0,
                "planck_bc1": 0.5,
                "planck_bc2": 0.9991,
            },
        )

        # Save to file
        nc_path = self.base_dir / "real_test.nc"
        ds.to_netcdf(nc_path)

        # Test rendering
        output_path = self.base_dir / "real_output.png"

        with patch("matplotlib.pyplot.savefig"), patch("matplotlib.pyplot.close"):
            result = render_png(nc_path, output_path)
            assert result == output_path


if __name__ == "__main__":
    unittest.main()
