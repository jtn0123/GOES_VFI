# Unified Interface Guide for GOES Imagery and Integrity Check

This guide explains the new unified interface components and integrations between the GOES Imagery and Integrity Check tabs.

## Overview

The unified interface introduces several key improvements:

1. **Shared Preview System** - A common preview panel that both tabs can use to display and cache imagery
2. **Sidebar Settings Panel** - A space-efficient panel for settings with collapsible sections
3. **Split View Mode** - Side-by-side viewing of both tabs simultaneously
4. **Cross-Tab Workflows** - Actions that connect tasks between tabs
5. **Context-Aware Settings** - Settings that adjust based on the active tab

## Shared Components

### SharedPreviewPanel

The `SharedPreviewPanel` provides a unified interface for previewing satellite imagery across different tabs.

**Key Features:**
- Caches previews to prevent redundant downloads
- Provides bookmarking capability for important imagery
- Displays metadata alongside the preview
- Supports zoom controls

**Usage Example:**
```python
# Create panel instance
preview_panel = SharedPreviewPanel()

# Add a preview
preview_panel.addPreview(
    key="channel_13_20230501_120000",
    image=pixmap,
    metadata=PreviewMetadata(
        channel=13,
        product_type=ProductType.FULL_DISK,
        date_time=datetime(2023, 5, 1, 12, 0, 0),
        source="AWS S3"
    )
)

# Connect signals
preview_panel.previewSelected.connect(on_preview_selected)
preview_panel.previewBookmarked.connect(on_preview_bookmarked)
```

### SidebarSettingsPanel

The `SidebarSettingsPanel` replaces the bottom settings area with a more space-efficient sidebar.

**Key Features:**
- Organizes settings into collapsible sections
- Conserves vertical space for imagery display
- Provides context-specific settings based on active tab
- Includes preset buttons for common operations

**Usage Example:**
```python
# Create panel instance
settings_panel = SidebarSettingsPanel()

# Get values from settings
selected_datetime = settings_panel.get_date_time()
satellite = settings_panel.get_satellite()
product_type = settings_panel.get_product_type()

# Show/hide sections based on context
settings_panel.show_section("visualization", True)
settings_panel.show_section("advanced", False)
```

### CollapsibleSettingsGroup

The `CollapsibleSettingsGroup` provides a collapsible container for organizing settings.

**Key Features:**
- Toggle header to expand/collapse content
- Reduces visual clutter
- Groups related settings together

**Usage Example:**
```python
# Create a collapsible group
group = CollapsibleSettingsGroup("Processing Options")

# Add widgets to the group
group.addWidget(resolution_combo)
group.addWidget(format_combo)

# Add to a layout
layout.addWidget(group)
```

## Integration Features

### Cross-Tab Workflows

The unified interface enables seamless workflows between tabs:

1. **Verify Imagery** - In the GOES Imagery tab, verify the integrity of selected imagery
2. **Visualize Verified Files** - In the Integrity Check tab, visualize files that have passed verification

### Split View Mode

Toggle split view to see both tabs simultaneously:

```python
# Enable split view
self.split_view_button.setChecked(True)
self.stacked_widget.setCurrentIndex(2)  # Index of the split view

# Adjust splitter sizes (50/50 split)
self.view_splitter.setSizes([100, 100])
```

### Shared Date/Time Selection

Changes to date/time settings in one tab affect both tabs:

```python
# Connect settings signals
settings_panel.date_edit.dateChanged.connect(update_both_tabs)
settings_panel.time_edit.timeChanged.connect(update_both_tabs)

def update_both_tabs(new_value):
    """Update both tabs when settings change."""
    integrity_tab.update_date_time(new_value)
    imagery_tab.update_date_time(new_value)
```

## Context-Aware Settings

The settings panel adapts based on the active tab:

- **Integrity Tab** - Shows verification-focused settings
- **Imagery Tab** - Shows visualization-focused settings
- **Split View** - Shows comprehensive settings for both tabs

## Usage Tips

1. **Use bookmarks** for important imagery to keep track of specific dates/times
2. **Try split view** to compare verification status with imagery visualization
3. **Use preset buttons** for quick access to common operations
4. **Collapse settings sections** you're not currently using to save space

## Integration with Existing Code

To use these components in the existing codebase:

1. Import shared components:
   ```python
   from goesvfi.integrity_check.shared_components import (
       SharedPreviewPanel, SidebarSettingsPanel, 
       CollapsibleSettingsGroup, PreviewMetadata
   )
   ```

2. Create component instances and add to layout:
   ```python
   # Create component instances
   self.preview_panel = SharedPreviewPanel()
   self.settings_panel = SidebarSettingsPanel()
   
   # Add to layout with splitter
   self.splitter.addWidget(self.content_widget)
   self.splitter.addWidget(self.preview_panel)
   self.splitter.addWidget(self.settings_panel)
   ```

3. Connect signals between components:
   ```python
   # Connect preview signals
   self.preview_panel.previewSelected.connect(self.on_preview_selected)
   
   # Connect settings signals
   self.settings_panel.date_edit.dateChanged.connect(self.on_date_changed)
   ```

## Testing the Unified Interface

A test script is provided to demonstrate the unified interface:

```bash
python test_unified_interface.py
```

This script showcases:
- Shared preview panel with bookmarking
- Settings sidebar with collapsible sections
- Tab switching with context-aware settings
- Cross-tab workflows
- Sample satellite imagery visualization

## Future Enhancements

Future versions may include:
- Drag-and-drop between tabs
- Collections feature for grouping related images
- Keyboard shortcuts for navigating the interface
- Further optimization of space usage