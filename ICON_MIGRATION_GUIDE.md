# Icon Migration Guide

This guide shows how to update all GUI components to use the IconManager system.

## IconManager Usage Pattern

### For Labels with Icons:
```python
# Old way:
header = QLabel("⚙️ Settings")

# New way:
header_widget = QWidget()
header_layout = QHBoxLayout(header_widget)
icon_label = QLabel()
icon_label.setPixmap(get_icon("⚙️").pixmap(24, 24))
header_layout.addWidget(icon_label)
text_label = QLabel("Settings")
header_layout.addWidget(text_label)
```

### For Buttons:
```python
# Old way:
button = QPushButton("💾 Save")

# New way:
button = QPushButton("Save")
button.setIcon(get_icon("💾"))
```

### For Tabs:
```python
# Old way:
tab_widget.addTab(widget, "📁 Files")

# New way:
tab_widget.addTab(widget, "")
index = tab_widget.count() - 1
tab_widget.setTabIcon(index, get_icon("📁"))
tab_widget.setTabText(index, "Files")
```

## Files Requiring Updates

### ✅ Already Updated:
1. **UISetupManager** (`ui_setup_manager.py`) - All main tabs
2. **Settings Tab** (`settings_tab.py`) - Header, tabs, and buttons
3. **LazyTabLoader** (`lazy_tab_loader.py`) - Accepts QIcon objects
4. **Main Tab** (`gui_tabs/main_tab.py`) - Header, group boxes, and buttons ✅
5. **Batch Processing Tab** (`gui_tabs/batch_processing_tab.py`) - Header and all buttons ✅  
6. **Model Library Tab** (`gui_tabs/model_library_tab.py`) - Headers, labels, and status icons ✅

### 🔄 Still Need Updates:

#### Medium Priority:
1. **FFmpeg Settings Tab** (`gui_tabs/ffmpeg_settings_tab.py`)
   - Headers and groups: "⚙️" multiple uses
   - Groups: "🔍 Sharpening", "🎬 Encoding Quality"

5. **File Sorter Tab** (`file_sorter/gui_tab.py`)
   - Multiple uses of: "📁", "📂", "🔍", "💾", "✨", "⚙️", "🚀", "📊"

6. **Date Sorter Tab** (`date_sorter/gui_tab.py`)
   - Similar to File Sorter

7. **Operation History Tab** (`gui_tabs/operation_history_tab.py`)
   - Group: "🔍 Operation Details"

8. **Resource Limits Tab** (`gui_tabs/resource_limits_tab.py`)
   - Header: "⚙️ Resource Limits Configuration"
   - Group: "📊 Current Resource Usage"

#### Lower Priority (Less Visible):
9. **Integrity Check Tabs**
   - Enhanced GUI Tab: "⚡", "🔍"
   - Enhanced Imagery Tab: "📊", "✅", "📁"
   - Combined Tab: "🛰️", "📁"

## Implementation Steps

1. **Import IconManager** in each file:
   ```python
   from goesvfi.gui_components.icon_manager import get_icon
   ```

2. **Update each emoji usage** following the patterns above

3. **Test the changes** to ensure icons display correctly

4. **Add actual icon files** to `resources/icons/` when available

## Benefits of Migration

- **Performance**: Icons cached after first load
- **Consistency**: Unified icon handling
- **Professional**: Easy to add proper icon resources
- **Flexibility**: Graceful fallback system
- **Maintainability**: Centralized icon management

## Adding New Icons

When adding new UI elements with icons:
1. Check if the emoji is already mapped in `icon_manager.py`
2. If not, add to `ICON_MAPPINGS` dictionary
3. Use `get_icon()` consistently
4. Consider adding the actual icon file to `resources/icons/`