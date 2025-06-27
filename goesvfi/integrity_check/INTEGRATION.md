# Integration Guide for the Enhanced Integrity Check Tab

This document explains how to integrate the enhanced Integrity Check tab with CDN/S3 hybrid fetching support into the main GOES-VFI application.

## Step 1: Modify imports in `goesvfi/gui.py`

Add these imports to the top of the file:

```python
# For basic implementation
from goesvfi.integrity_check import IntegrityCheckTab, IntegrityCheckViewModel, Reconciler

# For enhanced implementation with CDN/S3 support
from goesvfi.integrity_check.enhanced_view_model import EnhancedIntegrityCheckViewModel
from goesvfi.integrity_check.enhanced_gui_tab import EnhancedIntegrityCheckTab
from goesvfi.integrity_check.time_index import SatellitePattern
```

## Step 2: Choose Your Implementation

### Basic Implementation

For the basic implementation (local scanning only):

```python
# Create Integrity Check ViewModel (Basic)
self.integrity_check_view_model = IntegrityCheckViewModel(Reconciler())
LOGGER.info("IntegrityCheckViewModel instantiated.")

# Instantiate the Integrity Check tab (Basic)
self.integrity_check_tab = IntegrityCheckTab(
    view_model=self.integrity_check_view_model,
    parent=self
)
```

### Enhanced Implementation (Recommended)

For the enhanced implementation with CDN/S3 hybrid fetching:

```python
# Create Enhanced Integrity Check ViewModel
self.integrity_check_view_model = EnhancedIntegrityCheckViewModel()
LOGGER.info("EnhancedIntegrityCheckViewModel instantiated.")

# Instantiate the Enhanced Integrity Check tab
self.integrity_check_tab = EnhancedIntegrityCheckTab(
    view_model=self.integrity_check_view_model,
    parent=self
)
```

## Step 3: Add the tab to the tab widget in `MainWindow.__init__`

Add this code where the other tabs are added:

```python
self.tab_widget.addTab(
    self.integrity_check_tab, "Integrity Check"
)  # Add Integrity Check tab
```

## Step 4: Connect directory selection signal (optional)

To allow the Integrity Check tab to set the input directory for other tabs:

```python
self.integrity_check_tab.directory_selected.connect(self._set_in_dir_from_sorter)
```

## Step 5: Add cleanup in `closeEvent` (Important)

Add this code to your `closeEvent` method to ensure proper cleanup:

```python
def closeEvent(self, event):
    # Existing cleanup code...

    # Cleanup integrity check resources
    if hasattr(self, 'integrity_check_view_model'):
        if isinstance(self.integrity_check_view_model, EnhancedIntegrityCheckViewModel):
            self.integrity_check_view_model.cleanup()
        else:
            self.integrity_check_view_model._reconciler.close()

    # Continue with event.accept() or other cleanup logic
    event.accept()
```

## Step 6: Save and load settings (optional)

### Basic Implementation Settings

For the basic implementation:

```python
# Save Integrity Check settings
self.settings.beginGroup("integrity_check")
self.settings.setValue("base_directory", str(self.integrity_check_view_model.base_directory))
self.settings.setValue("selected_pattern", self.integrity_check_view_model.selected_pattern.value)
self.settings.setValue("interval_minutes", self.integrity_check_view_model.interval_minutes)
self.settings.setValue("auto_download", self.integrity_check_view_model.auto_download)
self.settings.setValue("remote_base_url", self.integrity_check_view_model.remote_base_url)
self.settings.endGroup()
```

### Enhanced Implementation Settings

For the enhanced implementation:

```python
# Save Enhanced Integrity Check settings
self.settings.beginGroup("integrity_check")
self.settings.setValue("base_directory", str(self.integrity_check_view_model.base_directory))
self.settings.setValue("satellite", self.integrity_check_view_model.satellite.value)
self.settings.setValue("fetch_source", self.integrity_check_view_model.fetch_source.value)
self.settings.setValue("interval_minutes", self.integrity_check_view_model.interval_minutes)
self.settings.setValue("auto_download", self.integrity_check_view_model.auto_download)
self.settings.setValue("force_rescan", self.integrity_check_view_model.force_rescan)
self.settings.setValue("cdn_resolution", self.integrity_check_view_model.cdn_resolution)
self.settings.setValue("aws_profile", self.integrity_check_view_model.aws_profile or "")
self.settings.setValue("max_concurrent_downloads", self.integrity_check_view_model.max_concurrent_downloads)
self.settings.endGroup()
```

And load them:

```python
# Load Enhanced Integrity Check settings
self.settings.beginGroup("integrity_check")
if self.settings.contains("base_directory"):
    dir_path = self.settings.value("base_directory")
    if dir_path and Path(dir_path).exists():
        self.integrity_check_view_model.base_directory = dir_path
if self.settings.contains("satellite"):
    satellite_value = int(self.settings.value("satellite"))
    self.integrity_check_view_model.satellite = SatellitePattern(satellite_value)
if self.settings.contains("fetch_source"):
    from goesvfi.integrity_check.enhanced_view_model import FetchSource
    fetch_source_value = int(self.settings.value("fetch_source"))
    self.integrity_check_view_model.fetch_source = FetchSource(fetch_source_value)
if self.settings.contains("interval_minutes"):
    self.integrity_check_view_model.interval_minutes = int(self.settings.value("interval_minutes", 10))
if self.settings.contains("auto_download"):
    self.integrity_check_view_model.auto_download = self.settings.value("auto_download") == "true"
if self.settings.contains("force_rescan"):
    self.integrity_check_view_model.force_rescan = self.settings.value("force_rescan") == "true"
if self.settings.contains("cdn_resolution"):
    self.integrity_check_view_model.cdn_resolution = self.settings.value("cdn_resolution")
if self.settings.contains("aws_profile"):
    profile = self.settings.value("aws_profile")
    self.integrity_check_view_model.aws_profile = profile if profile else None
if self.settings.contains("max_concurrent_downloads"):
    self.integrity_check_view_model.max_concurrent_downloads = int(self.settings.value("max_concurrent_downloads", 5))
self.settings.endGroup()
```

## Step 7: Complete Integration

### Requirements

Make sure your environment has the following dependencies installed for the enhanced implementation:

- PyQt6 or PySide6
- aiohttp (for CDN fetching)
- aioboto3 (for S3 fetching)
- xarray and netCDF4 (for processing NetCDF files)
- Pillow (for image processing)
- numpy (for numerical operations)
- matplotlib (for rendering NetCDF data)

These dependencies are included in the project's `pyproject.toml` file:

```
PyQt6>=6.0
aiohttp>=3.8.0
aioboto3>=11.0.0
xarray>=2022.3.0
netCDF4>=1.6.0
pillow>=9.0.0
numpy>=1.22.0
matplotlib>=3.5.0
```

### Testing

After making these changes, test the application to ensure:

1. The Integrity Check tab appears in the GUI
2. The tab functions correctly
3. CDN and S3 fetching works as expected
4. Settings are saved and loaded properly
5. Any directory selections in the Integrity Check tab update other tabs correctly

If all tests pass, you can submit a pull request to integrate the new feature into the main codebase.
