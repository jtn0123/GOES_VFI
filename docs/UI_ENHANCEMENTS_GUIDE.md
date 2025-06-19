# UI/UX Enhancements Guide

This guide explains how to use and integrate the UI/UX enhancements into the GOES VFI application.

## Overview

The UI enhancements module provides a comprehensive set of components to improve user experience:

1. **Contextual Tooltips** - Helpful explanations for all settings
2. **Help Buttons** - Detailed help dialogs for complex settings
3. **Progress Tracking** - Real-time speed and ETA calculations
4. **Loading Animations** - Visual feedback during operations
5. **Drag-and-Drop** - Easy file/folder selection
6. **Keyboard Shortcuts** - Quick access to common operations
7. **Notifications** - Non-intrusive status messages

## Components

### TooltipHelper

Manages contextual tooltips with predefined messages for common settings.

```python
from goesvfi.utils.ui_enhancements import TooltipHelper

# Add tooltip to a widget
TooltipHelper.add_tooltip(fps_spinbox, 'fps')

# Add custom tooltip
TooltipHelper.add_tooltip(widget, 'custom', "Your custom tooltip text")
```

Predefined tooltips include:
- `fps` - Frames per second explanation
- `mid_count` - Intermediate frames explanation
- `max_workers` - Worker threads explanation
- `encoder` - Video encoder explanation
- `crf` - Quality factor explanation
- And many more...

### HelpButton

Small "?" buttons that show detailed help when clicked.

```python
from goesvfi.utils.ui_enhancements import HelpButton

# Create help button
help_btn = HelpButton('fps', parent_widget)
help_btn.help_requested.connect(show_help_handler)

# Add to layout next to a setting
layout.addWidget(fps_label, 0, 0)
layout.addWidget(fps_spinbox, 0, 1)
layout.addWidget(help_btn, 0, 2)
```

### ProgressTracker

Tracks operation progress with automatic speed and ETA calculation.

```python
from goesvfi.utils.ui_enhancements import ProgressTracker

# Create tracker
tracker = ProgressTracker()
tracker.stats_updated.connect(update_ui_stats)

# Start tracking
tracker.start(total_items=100)  # or total_bytes=file_size

# Update progress
tracker.update_progress(items=1, bytes_transferred=1024)

# Stats dictionary includes:
# - elapsed: seconds elapsed
# - eta_seconds: estimated time remaining
# - speed_bps: bytes per second
# - speed_human: formatted speed (e.g., "1.5 MB/s")
# - eta_human: formatted ETA (e.g., "2:35")
# - progress_percent: completion percentage
```

### LoadingSpinner

Animated loading indicator for long operations.

```python
from goesvfi.utils.ui_enhancements import LoadingSpinner

# Create spinner
spinner = LoadingSpinner(parent_widget)
spinner.move(10, 10)  # Position in parent

# Show during operation
spinner.start()
# ... do work ...
spinner.stop()
```

### DragDropWidget

Adds drag-and-drop file support to any widget.

```python
from goesvfi.utils.ui_enhancements import DragDropWidget

# Make widget accept drops
drag_handler = DragDropWidget()
drag_handler.files_dropped.connect(handle_dropped_files)

# Override widget's drag/drop events
widget.setAcceptDrops(True)
widget.dragEnterEvent = drag_handler.dragEnterEvent
widget.dragLeaveEvent = drag_handler.dragLeaveEvent
widget.dropEvent = drag_handler.dropEvent

def handle_dropped_files(file_paths):
    for path in file_paths:
        print(f"Dropped: {path}")
```

### ShortcutManager

Centralized keyboard shortcut management.

```python
from goesvfi.utils.ui_enhancements import ShortcutManager

# Create manager
shortcuts = ShortcutManager(main_window)

# Add custom shortcut
shortcuts.add_shortcut(
    name="open",
    key_sequence="Ctrl+O",
    callback=open_file_handler,
    description="Open file"
)

# Setup standard shortcuts
callbacks = {
    'open_file': open_handler,
    'save_file': save_handler,
    'start_processing': start_handler,
    # ... etc
}
shortcuts.setup_standard_shortcuts(callbacks)

# Show all shortcuts
shortcuts.show_shortcuts()
```

Standard shortcuts include:
- `Ctrl+O` - Open file
- `Ctrl+S` - Save file
- `Ctrl+Q` - Quit application
- `Ctrl+R` - Start processing
- `Ctrl+X` - Stop processing
- `Ctrl+P` - Toggle preview
- `F1` - Show help
- `Ctrl+,` - Show settings

### AnimatedProgressBar

Progress bar with smooth animations and state colors.

```python
from goesvfi.utils.ui_enhancements import AnimatedProgressBar

# Create progress bar
progress = AnimatedProgressBar()

# Update with animation
progress.setValue(50)  # Animates to 50%

# Change visual state
progress.set_state("normal")   # Blue
progress.set_state("success")  # Green
progress.set_state("error")    # Red
```

### FadeInNotification

Non-intrusive notification popups.

```python
from goesvfi.utils.ui_enhancements import FadeInNotification

# Create notification
notif = FadeInNotification(parent_widget)

# Show message
notif.show_message("Operation completed!", duration=2000)
```

## Integration Options

### Option 1: Full Enhancement (Recommended)

Use the `UIEnhancer` class to enhance an existing MainWindow:

```python
from goesvfi.gui_enhancements_integration import enhance_existing_gui

# In MainWindow.__init__ after UI setup:
self._ui_enhancer = enhance_existing_gui(self)

# Use enhancer features
self._ui_enhancer.start_operation('processing')
self._ui_enhancer.update_progress(current, total)
self._ui_enhancer.notification.show_message("Done!")
```

### Option 2: Enhanced Tabs

Replace existing tabs with enhanced versions:

```python
from goesvfi.gui_tabs.main_tab_enhanced import EnhancedMainTab
from goesvfi.gui_tabs.ffmpeg_settings_tab_enhanced import EnhancedFFmpegSettingsTab

# Use EnhancedMainTab instead of MainTab
self.main_tab = EnhancedMainTab(...)

# Use EnhancedFFmpegSettingsTab instead of FFmpegSettingsTab
self.ffmpeg_tab = EnhancedFFmpegSettingsTab(...)
```

### Option 3: Minimal Integration

Just add tooltips without changing behavior:

```python
from goesvfi.gui_integration_patch import integrate_enhancements_minimal

# After UI setup
integrate_enhancements_minimal(self)
```

### Option 4: Monkey Patching

Patch the MainWindow class before instantiation:

```python
from goesvfi.gui_integration_patch import patch_main_window
from goesvfi.gui import MainWindow

# Patch the class
patch_main_window(MainWindow)

# Now all MainWindow instances have enhancements
window = MainWindow()
```

## Testing

Run the test script to see all enhancements in action:

```bash
python examples/debugging/test_ui_enhancements.py
```

This demonstrates:
- All UI components
- Keyboard shortcuts
- Drag and drop
- Progress tracking
- Animations and notifications

## Customization

### Adding New Tooltips

Edit `TooltipHelper.TOOLTIPS` dictionary:

```python
TooltipHelper.TOOLTIPS['my_setting'] = 'Explanation of my setting'
```

### Custom Help Content

Override `HelpButton._get_help_text()`:

```python
def custom_help_text(topic):
    if topic == 'my_topic':
        return "<b>My Topic</b><br>Detailed explanation..."
    return original_get_help_text(topic)

HelpButton._get_help_text = custom_help_text
```

### Custom Progress Formatting

Override formatting methods in ProgressTracker:

```python
def custom_format_speed(bps):
    # Your custom formatting
    return f"{bps / 1e6:.2f} MB/s"

ProgressTracker._format_speed = staticmethod(custom_format_speed)
```

## Best Practices

1. **Tooltips**: Keep them concise (1-2 sentences). Use help buttons for detailed explanations.

2. **Help Buttons**: Place them consistently (usually to the right of controls).

3. **Progress Tracking**: Always call `start()` before operations and `stop()` when done.

4. **Notifications**: Use sparingly for important status changes. Keep messages brief.

5. **Keyboard Shortcuts**: Follow platform conventions. Document all shortcuts.

6. **Drag and Drop**: Provide visual feedback during drag. Handle multiple file types gracefully.

7. **Loading Indicators**: Show for any operation over 1 second. Hide immediately when done.

## Troubleshooting

### Tooltips not showing
- Ensure widget has focus policy set
- Check tooltip duration (default 5000ms)
- Verify tooltip text is not empty

### Progress not updating
- Ensure `update_progress()` is called regularly
- Check that total_items or total_bytes is set
- Verify stats_updated signal is connected

### Drag and drop not working
- Ensure `setAcceptDrops(True)` is called
- Check mime types in drag events
- Verify event handlers are properly overridden

### Shortcuts not working
- Check for conflicts with existing shortcuts
- Ensure actions are added to widget
- Verify focus is on correct widget
