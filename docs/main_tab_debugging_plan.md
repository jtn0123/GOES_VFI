# Main Tab Debugging Plan

This document outlines a systematic approach to debug several issues in the Main Tab of the GOES-VFI application.

## 1. Cropping Functionality Debugging

### Critical Debug Points:
- Crop Selection Dialog Initialization
  - Add enhanced logging in `_on_crop_clicked()` to track proper image loading
  - Verify QImage creation from both original and Sanchez-processed images
  - Check memory leaks with multiple dialog creations

### Implementation Issues:
- Coordinate Mapping: Verify scaling calculations between display and original image coordinates
- Event Propagation: Ensure click and drag events are properly captured in CropSelectionDialog
- Error Handling: Validate crop rectangle dimensions before applying to images

## 2. Sanchez Integration with Cropping

### Debug Areas:
- Sanchez Preview Caching:
  - Add cache size monitoring to prevent memory issues
  - Add timestamps to track cache staleness
  - Log cache hits/misses statistics

### Performance Issues:
- Processing Timeline: Profile time spent in Sanchez processing vs. UI updates
- Memory Consumption: Monitor RAM usage during consecutive Sanchez preview operations

## 3. Settings Persistence and State Restoration

### Key Debug Areas:
- QSettings Storage and Retrieval:
  - Add detailed logging in `load_settings()` and `save_settings()`
  - Verify each setting is properly saved and retrieved
  - Check data type consistency between save and load operations

### Common Issues:
- Checkbox State Persistence:
  - Verify `QSettings.value()` type casting for boolean values
  - Add explicit type conversion for all checkbox states
- Path Restoration: Ensure file and directory paths are validated before usage
- Silent Failures: Check for exceptions during settings loading that might be suppressed

## 4. Start Interpolation Button Functionality

### Debug Points:
- Signal Connection:
  - Verify `processing_started` signal is properly connected
  - Add direct debugging in `_start()` function to trace signal emission
- Argument Preparation:
  - Add validation for all arguments in `get_processing_args()`
  - Log complete argument dictionary before emission

### Implementation Issues:
- Worker Creation: Check worker thread instantiation and exception handling
- UI State Transition: Verify UI state changes correctly when processing starts
- Error Propagation: Ensure errors are properly reported to the user

## 5. FFmpeg Integration with Cropped Images

### Debug Points:
- Parameter Passing: Verify that crop parameters are correctly passed to FFmpeg commands
- Resolution Handling: Test that FFmpeg properly respects crop dimensions for output
- Performance Impact: Profile encoding time difference between cropped vs. full-frame processing

## 6. MainTab and MainWindow Integration

### State Management:
- State Synchronization:
  - Add sanity checks when state is passed between components
  - Verify signals are connected between MainTab and MainWindow
  - Track state changes with detailed logging

## 7. General Debugging Tools

### Recommended Debug Methods:
- Add Visual Debug Indicators:
  - Show crop rectangle dimensions in UI
  - Display scaling factors and coordinate mappings
- Add Performance Metrics:
  - Track and display processing time for key operations
  - Add memory consumption metrics for large operations

## 8. Preview Functionality Improvements

### Potential Enhancements:
- Real-time Crop Updates:
  - Implement progressive rendering during crop operation
  - Add mini-view of full image during cropping
- Zoom/Pan Controls:
  - Add explicit controls for navigation during cropping
  - Implement keyboard shortcuts for precision adjustments

## Implementation Approach

1. Add logging first, focusing on component interfaces
2. Add debug UI indicators for state visualization
3. Implement step-by-step verification of signal paths
4. Create isolated test cases for components with issues
5. Document all findings and solutions systematically
