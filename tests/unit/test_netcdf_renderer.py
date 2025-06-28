"""Unit tests for the integrity_check NetCDF renderer functionality."""

from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from goesvfi.integrity_check.render.netcdf import extract_metadata, render_png

# Mock optional dependencies to avoid import errors during module import
sys.modules.setdefault("aioboto3", MagicMock())
sys.modules.setdefault("botocore", MagicMock())
sys.modules.setdefault("botocore.config", MagicMock())
sys.modules.setdefault("botocore.exceptions", MagicMock())
sys.modules.setdefault("requests", MagicMock())


# Create a mock xarray Dataset similar to a GOES NetCDF file
def create_mock_dataset():
    mock_ds = MagicMock()

    # Add variables
    mock_ds.variables = {
        "Rad": MagicMock(),
        "band_id": MagicMock(),
        "band_wavelength": MagicMock(),
        "y": MagicMock(),
        "x": MagicMock(),
    }

    # Add attributes
    mock_ds.attrs = {
        "platform_ID": "G16",
        "instrument_type": "ABI",
        "date_created": "2023-06-15T12:30:00Z",
        "planck_fk1": 13530.2,
        "planck_fk2": 1306.56,
        "planck_bc1": 0.09929,
        "planck_bc2": 0.99944,
    }

    # Add methods
    mock_ds.__getitem__ = lambda self, key: mock_ds.variables[key]

    # Configure variable values
    mock_ds.variables["Rad"].values = np.ones((100, 100)) * 10
    mock_ds.variables["band_id"].values = np.array(13)
    mock_ds.variables["band_wavelength"].values = np.array(10.3)
    mock_ds.variables["y"].size = 100
    mock_ds.variables["x"].size = 100

    # Setup values accessor
    for var_name in mock_ds.variables:
        mock_ds.variables[var_name].values = mock_ds.variables[var_name].values

    # Make values accessible via ds[var_name].values
    for var_name, var in mock_ds.variables.items():
        var_mock = MagicMock()
        var_mock.values = var.values
        mock_ds[var_name] = var_mock

    return mock_ds


class TestNetCDFRenderer(unittest.TestCase):
    """Test cases for the NetCDF renderer."""

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

    def test_render_png(self) -> None:
        """Test rendering a NetCDF file to PNG."""
        # Setup mock dataset
        mock_ds = create_mock_dataset()

        # Create dummy figure and axes for mocking
        mock_figure = MagicMock()
        mock_ax = MagicMock()

        # Create mock for linearSegmentedColormap
        mock_cmap = MagicMock()

        # Output path
        output_path = self.base_dir / "output.png"

        with patch("xarray.open_dataset") as mock_open_dataset:
            with patch("matplotlib.pyplot.figure", return_value=mock_figure):
                with patch("matplotlib.pyplot.savefig"):
                    with patch("matplotlib.pyplot.close"):
                        with patch("matplotlib.pyplot.get_cmap", return_value=mock_cmap):
                            # Mock figure.add_axes
                            mock_figure.add_axes.return_value = mock_ax

                            # Configure mock dataset
                            mock_open_dataset.return_value.__enter__.return_value = mock_ds

                            # Test basic rendering
                            result = render_png(netcdf_path=self.netcdf_path, output_path=output_path)

                            # Verify
                            assert result == output_path
                            mock_open_dataset.assert_called_with(self.netcdf_path)
                            mock_figure.add_axes.assert_called_once()
                            mock_ax.imshow.assert_called_once()

    def test_render_png_with_custom_colormap(self) -> None:
        """Test rendering with a custom colormap."""
        # Setup mock dataset
        mock_ds = create_mock_dataset()

        # Create dummy figure and axes for mocking
        mock_figure = MagicMock()
        mock_ax = MagicMock()

        # Create mock for linearSegmentedColormap
        mock_lsc = MagicMock()

        # Output path
        output_path = self.base_dir / "output_gray.png"

        with patch("xarray.open_dataset") as mock_open_dataset:
            with patch("matplotlib.pyplot.figure", return_value=mock_figure):
                with patch("matplotlib.pyplot.savefig"):
                    with patch("matplotlib.pyplot.close"):
                        with patch(
                            "matplotlib.colors.LinearSegmentedColormap.from_list",
                            return_value=mock_lsc,
                        ):
                            # Mock figure.add_axes
                            mock_figure.add_axes.return_value = mock_ax

                            # Configure mock dataset
                            mock_open_dataset.return_value.__enter__.return_value = mock_ds

                            # Test gray colormap
                            result = render_png(
                                netcdf_path=self.netcdf_path,
                                output_path=output_path,
                                colormap="gray",
                            )

                            # Verify
                            assert result == output_path
                            mock_ax.imshow.assert_called_once()

    @patch("xarray.open_dataset")
    def test_render_png_file_not_found(self, mock_open_dataset) -> None:
        """Test error handling when NetCDF file is not found."""
        # Setup
        nonexistent_path = self.base_dir / "nonexistent.nc"
        mock_open_dataset.side_effect = FileNotFoundError("File not found")

        # Test
        with pytest.raises(FileNotFoundError):
            render_png(nonexistent_path)

    @patch("xarray.open_dataset")
    def test_render_png_invalid_band(self, mock_open_dataset) -> None:
        """Test error handling when band ID is incorrect."""
        # Setup
        mock_ds = create_mock_dataset()
        mock_ds["band_id"].values = np.array(7)  # Wrong band
        mock_open_dataset.return_value.__enter__.return_value = mock_ds

        # Output path
        output_path = self.base_dir / "output.png"

        # Test - should raise a ValueError for wrong band
        with pytest.raises(ValueError) as context:
            render_png(self.netcdf_path, output_path)

        # Verify the error message
        assert "Band 13 not found" in str(context.value)

    @patch("xarray.open_dataset")
    def test_render_png_missing_variable(self, mock_open_dataset) -> None:
        """Test error handling when required variable is missing."""
        # Setup
        mock_ds = create_mock_dataset()
        # Remove Rad variable
        del mock_ds.variables["Rad"]
        mock_ds.__getitem__ = lambda self, key: (mock_ds.variables.get(key, None))
        mock_open_dataset.return_value.__enter__.return_value = mock_ds

        # Output path
        output_path = self.base_dir / "output.png"

        # Test - should raise a ValueError when variable missing
        with pytest.raises(ValueError) as context:
            render_png(self.netcdf_path, output_path)

        # Verify the error message
        assert "Radiance variable 'Rad' not found" in str(context.value)

    @patch("xarray.open_dataset")
    def test_extract_metadata(self, mock_open_dataset) -> None:
        """Test extracting metadata from a NetCDF file."""
        # Setup
        mock_ds = create_mock_dataset()
        mock_open_dataset.return_value.__enter__.return_value = mock_ds

        # Test
        metadata = extract_metadata(self.netcdf_path)

        # Verify
        assert metadata["satellite"] == "G16"
        assert metadata["instrument"] == "ABI"
        assert metadata["timestamp"] == "2023-06-15T12:30:00Z"
        assert metadata["band_id"] == 13
        assert metadata["band_wavelength"] == 10.3
        assert metadata["resolution_x"] == 100
        assert metadata["resolution_y"] == 100

    @patch("xarray.open_dataset")
    def test_extract_metadata_file_not_found(self, mock_open_dataset) -> None:
        """Test error handling when NetCDF file is not found during metadata extraction."""
        # Setup
        nonexistent_path = self.base_dir / "nonexistent.nc"
        mock_open_dataset.side_effect = FileNotFoundError("File not found")

        # Test
        with pytest.raises(FileNotFoundError):
            extract_metadata(nonexistent_path)

    @patch("xarray.open_dataset")
    def test_extract_metadata_error(self, mock_open_dataset) -> None:
        """Test error handling during metadata extraction."""
        # Setup
        mock_open_dataset.side_effect = KeyError("Generic error")

        # Test
        with pytest.raises(KeyError):
            extract_metadata(self.netcdf_path)


if __name__ == "__main__":
    unittest.main()
