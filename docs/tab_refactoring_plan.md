# Refactoring Plan for Tab Implementations

This document outlines the plan for refactoring the `enhanced_gui_tab.py` and `enhanced_imagery_tab.py` to utilize the new shared components.

## Current State

Currently, both tab implementations have:
- Their own preview display logic
- Separate settings sections
- Duplicated date/time selection
- No shared state between tabs

## Refactoring Goals

1. Use the shared `SharedPreviewPanel` for all preview displays
2. Replace bottom settings with the `SidebarSettingsPanel`
3. Implement cross-tab workflows
4. Support split view mode

## Implementation Plan for enhanced_gui_tab.py

### Phase 1: Preview Integration

1. Identify all places where previews are created/displayed
2. Replace with calls to the shared preview panel:
   ```python
   # Before:
   self.preview_label.setPixmap(pixmap)

   # After:
   self.shared_preview_panel.addPreview(
       key=key,
       image=pixmap,
       metadata=PreviewMetadata(...)
   )
   ```

3. Remove redundant preview UI components

### Phase 2: Settings Integration

1. Remove bottom settings area
2. Create a method to update the shared settings panel:
   ```python
   def update_shared_settings(self, settings_panel):
       """Update shared settings panel with integrity-specific settings."""
       # Update date/time
       settings_panel.set_date_time(self.view_model.selected_date)

       # Show/hide sections
       settings_panel.show_section("visualization", False)
       settings_panel.show_section("advanced", False)

       # Update settings values
       # ...
   ```

3. Add method to retrieve settings values:
   ```python
   def apply_shared_settings(self, settings_panel):
       """Apply settings from shared panel to this tab."""
       # Get date/time
       date_time = settings_panel.get_date_time()
       self.view_model.set_date_time(date_time)

       # Get other settings
       # ...
   ```

### Phase 3: Cross-Tab Actions

1. Add methods for handling actions from the imagery tab:
   ```python
   def verify_imagery(self, file_path, metadata):
       """Verify imagery specified by another tab."""
       # Implementation...
   ```

2. Add signals for triggering actions in the imagery tab:
   ```python
   # Define signal
   imagery_requested = pyqtSignal(str, object)  # file_path, metadata

   # Emit signal when needed
   self.imagery_requested.emit(file_path, metadata)
   ```

## Implementation Plan for enhanced_imagery_tab.py

### Phase 1: Preview Integration

1. Replace the preview system with the shared panel:
   ```python
   # Before:
   self.view_panel.showImage(image_path)

   # After:
   self.shared_preview_panel.addPreview(
       key=key,
       image=QPixmap(image_path),
       metadata=PreviewMetadata(...)
   )
   ```

2. Modify SamplePreviewDialog to use the shared preview panel

### Phase 2: Settings Integration

1. Remove the EnhancedImageSelectionPanel
2. Create a method to update the shared settings panel:
   ```python
   def update_shared_settings(self, settings_panel):
       """Update shared settings panel with imagery-specific settings."""
       # Update date/time
       settings_panel.set_date_time(self.current_date_time)

       # Show/hide sections
       settings_panel.show_section("visualization", True)
       settings_panel.show_section("advanced", True)

       # Update settings values
       # ...
   ```

3. Add method to retrieve settings values:
   ```python
   def apply_shared_settings(self, settings_panel):
       """Apply settings from shared panel to this tab."""
       # Get date/time
       date_time = settings_panel.get_date_time()
       self.current_date_time = date_time

       # Get other settings
       # ...
   ```

### Phase 3: Cross-Tab Actions

1. Add methods for handling actions from the integrity tab:
   ```python
   def visualize_file(self, file_path, metadata):
       """Visualize file specified by another tab."""
       # Implementation...
   ```

2. Add signals for triggering actions in the integrity tab:
   ```python
   # Define signal
   verification_requested = pyqtSignal(str, object)  # file_path, metadata

   # Emit signal when needed
   self.verification_requested.emit(file_path, metadata)
   ```

## Integration in Combined Tab

1. Create instances of shared components:
   ```python
   self.preview_panel = SharedPreviewPanel()
   self.settings_panel = SidebarSettingsPanel()
   ```

2. Pass shared components to both tabs:
   ```python
   self.integrity_tab = EnhancedIntegrityCheckTab(
       view_model,
       shared_preview=self.preview_panel,
       shared_settings=self.settings_panel,
       parent=self
   )

   self.imagery_tab = EnhancedGOESImageryTab(
       shared_preview=self.preview_panel,
       shared_settings=self.settings_panel,
       parent=self
   )
   ```

3. Connect signals between tabs:
   ```python
   # Connect integrity tab signals to imagery tab actions
   self.integrity_tab.imagery_requested.connect(
       self.imagery_tab.visualize_file
   )

   # Connect imagery tab signals to integrity tab actions
   self.imagery_tab.verification_requested.connect(
       self.integrity_tab.verify_imagery
   )
   ```

4. Handle tab switching:
   ```python
   def _switch_tab(self, index):
       """Switch to tab at specified index."""
       self.stacked_widget.setCurrentIndex(index)

       # Update settings based on active tab
       if index == 0:
           self.integrity_tab.update_shared_settings(self.settings_panel)
       elif index == 1:
           self.imagery_tab.update_shared_settings(self.settings_panel)
   ```

## Testing Strategy

1. Create tests for each component individually
2. Create integrated tests for tab interactions
3. Test data sharing between tabs
4. Test UI layout and appearance

## Implementation Order

1. First implement the shared components (already completed)
2. Refactor the combined tab to use shared components (already completed)
3. Refactor the integrity tab
4. Refactor the imagery tab
5. Connect signals between tabs
6. Test and refine the integration
