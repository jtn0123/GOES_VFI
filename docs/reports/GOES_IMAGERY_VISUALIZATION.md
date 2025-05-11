# GOES Imagery Visualization

This document describes the enhanced GOES satellite imagery visualization features added to the GOES-VFI application.

## Overview

The GOES Imagery Visualization tab provides functionality for viewing, processing, and comparing different types of GOES satellite imagery. It includes features for:

1. Visualizing all 16 ABI channels (from visible to infrared)
2. Creating RGB composite products
3. Previewing and comparing different processing options
4. Organizing imagery in a time-based folder structure
5. Displaying both standard and enhanced colorizations

## Features

### Channel Types

The application supports all ABI instrument channels:

- **Visible/Near-IR Channels (1-6)**: Daytime imagery for land, cloud, and vegetation features
- **Infrared Channels (7-16)**: 24-hour imagery for temperature, water vapor, and atmospheric features
- **RGB Composites**: True Color, Airmass, Fire Temperature, Dust, and Day Cloud Phase

### Processing Options

Each channel can be processed in multiple ways:

- **Standard Processing**: Basic grayscale visualization
- **Enhanced Processing**: Colorized visualization using specialized colormaps
- **Custom Temperature Ranges**: For infrared channels, allowing emphasis on different features

### Preview and Verification

Before committing to full processing, you can:

1. Preview sample images from each channel
2. Compare different processing options side-by-side
3. View NOAA standard visualizations for reference
4. Estimate processing time for full-resolution imagery

### File Organization

Processed images are organized in a consistent structure:

- **Time-based folders**: `YYYY-MM-DD_HH-MM-SS` format
- **Standardized filenames**:
  - Single bands: `G16_[band]_[timestamp].png`
  - Colorized maps: `G16_[band]_[timestamp]_map.png`
  - RGB composites: `abi_rgb_[descriptor]_[timestamp].png`

## Usage

### Running the GOES Imagery Tab

You can run the GOES Imagery visualization in several ways:

1. **As part of the main application**: The tab is integrated into the Integrity Check section
2. **As a standalone component**: Use `test_enhanced_imagery_tab.py` for imagery-only testing
3. **As part of the combined interface**: Use `test_combined_tab.py` to test both integrity and imagery tabs

### Basic Workflow

1. **Select a Channel**: Choose from Infrared, Water Vapor, Visible, or RGB Composite tabs
2. **Choose Product Type**: Select Full Disk, CONUS, or Mesoscale
3. **Set Date/Time**: Specify when to retrieve imagery
4. **Preview**: Click "Preview" to see sample visualizations
5. **Process**: Confirm settings and process the full imagery
6. **View and Save**: View the processed imagery and save if desired

## Implementation Details

The GOES Imagery Visualization is implemented with these key components:

- **VisualizationManager**: Handles file organization and image processing
- **SampleProcessor**: Creates preview and comparison images
- **EnhancedGOESImageryTab**: Provides the user interface for imagery functions
- **CombinedIntegrityAndImageryTab**: Integrates integrity check and imagery functions

## Advanced Usage

### Customizing Colormaps

The default colormaps are optimized for each channel, but can be customized:

```python
# Example: Change water vapor colormap
visualization_manager.colormaps["water_vapor"] = "plasma"  # Instead of jet
```

### Adding New RGB Composites

New RGB composites can be added by extending the ExtendedChannelType enum:

```python
# Example: Add a new RGB composite type
NEW_RGB = (107, "Custom RGB", "RGB", "Custom RGB composite description")
```

## Troubleshooting

- **Missing Images**: Make sure the date/time has available imagery (not all times have all sectors)
- **Processing Errors**: Check for sufficient disk space and valid directory permissions
- **Display Issues**: Try different processing options or temperature ranges
