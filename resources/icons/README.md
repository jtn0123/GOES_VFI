# Icon Resources

This directory is for storing application icon resources to replace emoji icons throughout the GUI.

## Icon Requirements

### Formats
- **Preferred**: SVG (scalable vector graphics)
- **Alternative**: PNG with multiple sizes

### Standard Sizes
- 16x16 - Small icons
- 24x24 - Medium icons (default)
- 32x32 - Large icons
- 48x48 - Extra large icons

### Naming Convention
Icons should be named according to their function, matching the mappings in `icon_manager.py`:

```
video.svg         # Main tab (video processing)
settings.svg      # Settings tabs
book.svg          # Model library
folder.svg        # File sorter
calendar.svg      # Date sorter
satellite.svg     # Satellite integrity
search.svg        # Search functions
document.svg      # Documentation
save.svg          # Save actions
plus.svg          # Add/create actions
etc.
```

## Adding New Icons

1. Place icon files in this directory
2. Use descriptive names matching the icon mappings
3. The IconManager will automatically find and use them
4. No code changes needed - icons are loaded dynamically

## Icon Sources

Recommended open-source icon sets:
- [Feather Icons](https://feathericons.com/)
- [Font Awesome](https://fontawesome.com/) (free icons)
- [Material Design Icons](https://materialdesignicons.com/)
- [Lucide Icons](https://lucide.dev/)

## Current Status

The IconManager system is fully implemented and ready to use proper icon files. Currently, it falls back to emoji rendering when icon files are not present. Add icon files to this directory to automatically upgrade the UI appearance.