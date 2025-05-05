# Integrity Check Tab Implementation Plan

This document outlines the step-by-step implementation plan for the new "Integrity Check" tab in the GOES-VFI application, following the existing PyQt/MVVM architecture patterns.

## Implementation Checklist

### Phase 1: Infrastructure Setup
- [x] Create directory structure (`integrity_check/`)
- [x] Setup basic imports and module scaffolding
- [x] Define core interfaces and type definitions
- [x] Implement SQLite cache schema

### Phase 2: Core Logic (Model Layer) - Basic Implementation
- [x] Implement `time_index.py` (timestamp pattern recognition)
  - [x] Define timestamp patterns for different satellites
  - [x] Add functions for range generation and interval detection
- [x] Implement `reconciler.py` (core scanning logic)
  - [x] Directory scanning functionality
  - [x] Missing interval calculation
  - [x] Progress reporting mechanism
- [x] Implement `cache_db.py` (SQLite wrapper)
  - [x] Create tables and indexes
  - [x] Query and storage methods for scan results
  - [x] Cache invalidation logic
- [x] Implement `remote_store.py` (abstract + HTTP implementation)
  - [x] Define common interface
  - [x] HTTP implementation for standard URLs
  - [x] Download progress reporting

### Phase 3: ViewModel Implementation
- [x] Create `view_model.py` with `IntegrityCheckViewModel` class
  - [x] Properties for date range, satellite, interval
  - [x] State tracking for scan progress
  - [x] Signal definitions for UI updates
  - [x] Threading integration for background tasks
  - [x] Caching logic integration

### Phase 4: View Implementation
- [x] Create `gui_tab.py` with `IntegrityCheckTab` class
  - [x] Basic layout setup
  - [x] Date range and control widgets
  - [x] Progress and status display
  - [x] Table view for missing timestamps
  - [x] Signal connections to ViewModel

### Phase 5: Threading Implementation
- [x] Create worker classes for background operations
  - [x] `ScanTask` QRunnable implementation
  - [x] `FetchTask` for downloading missing files
  - [x] Signal connections for progress updates
  - [x] Error handling and cancellation support

### Phase 6: Advanced Remote Fetching (GOES-18 Band 13)
- [ ] Create remote subpackage structure
  - [ ] Implement enhanced `TimeIndex` with Band 13 specific methods
  - [ ] Update `to_cdn_url()` method with GOES-18 CDN path pattern
  - [ ] Add `to_s3_key()` for AWS S3 bucket access
  - [ ] Implement `ts_from_filename()` for filename parsing
- [ ] Implement specialized remote stores
  - [ ] Build `CDNStore` using aiohttp with retry logic
  - [ ] Develop `S3Store` using aioboto3 for AWS access
  - [ ] Add concurrency controls and resource management
- [ ] Create render subpackage for NetCDF processing
  - [ ] Implement `render_png()` function using xarray and Pillow
  - [ ] Add normalization and optional LUT application
  - [ ] Implement cleanup of temporary NetCDF files
- [ ] Enhance Reconciler for hybrid fetching
  - [ ] Add timestamp partitioning logic (7-day window)
  - [ ] Implement specialized FetchTask workers
  - [ ] Add disk space verification before batch operations

### Phase 7: Advanced UI Features
- [x] Register tab in main application (integration guide created)
- [x] Connect to existing logging system
- [x] Add cache management UI components
- [x] Implement report export functionality
- [ ] Add CDN/S3 configuration settings to UI
  - [ ] Recent window days setting
  - [ ] CDN resolution selector
  - [ ] NetCDF retention option
  - [ ] Thread pool size controls
- [ ] Add download strategy visualization in UI
- [ ] Add desktop notifications for long operations

### Phase 8: Testing and Documentation
- [ ] Unit tests for core models
  - [ ] TimeIndex URL/path generation tests
  - [ ] Renderer output validation tests 
  - [ ] Reconciler partitioning tests
- [ ] ViewModel tests with mocked signals
- [ ] UI tests with pytest-qt
- [ ] End-to-end smoke tests
- [ ] Update dependency requirements
  - [ ] Add xarray, netCDF4, boto3, aiohttp, pillow

## File Structure

```
goesvfi/
└─ integrity_check/
   ├─ __init__.py                # Package exports
   ├─ IMPLEMENTATION_PLAN.md     # This document
   ├─ gui_tab.py                 # IntegrityCheckTab (View)
   ├─ view_model.py              # IntegrityCheckViewModel
   ├─ reconciler.py              # Reconciler (core logic)
   ├─ time_index.py              # Timestamp utilities
   ├─ cache_db.py                # SQLite cache wrapper
   ├─ remote_store.py            # Basic remote fetching
   ├─ tasks.py                   # QRunnable implementations
   ├─ remote/                    # Advanced remote fetching
   │  ├─ __init__.py
   │  ├─ base.py                 # Abstract RemoteStore interface
   │  ├─ cdn_store.py            # CDN implementation
   │  └─ s3_store.py             # S3 implementation
   └─ render/                    # NetCDF rendering
      ├─ __init__.py
      └─ netcdf_renderer.py      # PNG generation from NetCDF
```

## Key Classes and Responsibilities

### `Reconciler` (Model)
Primary responsibility: Directory scanning and timestamp analysis
- Scan file system for existing timestamps
- Generate expected timestamps for date range
- Calculate missing intervals
- Store/retrieve results from cache

### `IntegrityCheckViewModel` (ViewModel)
Primary responsibility: Coordinating business logic and UI state
- Manage scan parameters and state
- Coordinate background tasks
- Handle signal routing from workers to UI
- Expose data properties for View binding

### `IntegrityCheckTab` (View) 
Primary responsibility: Visual representation and user interaction
- Render UI components according to current state
- Handle user input and actions
- Display progress and results
- Forward commands to ViewModel

### `ScanTask` and `FetchTask` (Worker Threads)
Primary responsibility: Background processing
- Perform CPU-intensive operations off the main thread
- Report progress via signals
- Handle errors and cancellation

## Implementation Notes

1. **Cache Design**:
   - Use SQLite with simple schema for speed
   - Key by date range + satellite + options
   - Store both full ranges and individual timestamps

2. **Threading Approach**:
   - QRunnable + QThreadPool (matches existing code patterns)
   - Clear signal interfaces between threads
   - Proper exception handling

3. **Error States**:
   - Use enum or string constants for error types
   - Propagate errors with context information
   - Show appropriate UI feedback

4. **UI Responsiveness**:
   - Progress updates every ~250ms
   - QApplication.processEvents() in critical sections
   - Cancel button always responsive

## Integration Points

1. **Main Window Integration**:
   - Add tab to main TabWidget
   - Register in view model hierarchy

2. **Logging Integration**:
   - Use existing logger from utils.log
   - Attach console widget to logger

3. **Config Integration**:
   - Use existing config system for defaults
   - Save/restore scan parameters

## Memory and Performance Considerations

1. **Large Dataset Handling**:
   - Paginate table results for large missing sets
   - Use generators for timestamp processing when possible
   - Implement timeouts for remote operations

2. **Cache Management**:
   - Limit cache size with LRU policy
   - Provide UI for manual clean-up
   - Store only essential information

This implementation plan provides a structured approach to building the Integrity Check tab while maintaining consistency with the existing codebase architecture.