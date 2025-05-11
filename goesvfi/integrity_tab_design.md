# Integrity Check Tab Design for GOES-VFI

This document outlines the implementation plan for the new "Integrity Check" tab, designed according to the Qt-based MVVM pattern used in the existing codebase.

## Module Structure

```
goesvfi/
│
├─ integrity_check/
│   ├─ __init__.py
│   ├─ gui_tab.py           # IntegrityCheckTab (QWidget subclass - View)
│   ├─ view_model.py        # IntegrityCheckViewModel (manages state & business logic)
│   ├─ reconciler.py        # Reconciler (core logic for scan & verification)
│   ├─ time_index.py        # Utilities for timestamp patterns & calculations
│   ├─ cache_db.py          # SQLite wrapper for caching scan results
│   └─ remote_store.py      # Abstract base + HTTP implementation for fetching
│
├─ utils/
    └─ task_thread.py       # QRunnable subclass for background tasks (if not already present)
```

## Core Classes & Responsibilities

### 1. IntegrityCheckTab (View)

```python
class IntegrityCheckTab(QWidget):
    """QWidget tab for verifying timestamp integrity and finding gaps in GOES imagery."""

    directory_selected = pyqtSignal(str)  # Signal when directory is chosen

    def __init__(self, view_model: IntegrityCheckViewModel, parent: Optional[QWidget] = None):
        # Initialize UI components
        # Connect signals to ViewModel
        # Set up observer pattern with ViewModel
```

### 2. IntegrityCheckViewModel

```python
class IntegrityCheckViewModel(QObject):
    """ViewModel for the Integrity Check tab."""

    # Signals
    status_updated = pyqtSignal(str)
    progress_updated = pyqtSignal(int, int, float)  # current, total, eta
    missing_items_updated = pyqtSignal(list)  # List of missing timestamps
    scan_completed = pyqtSignal(bool, str)  # success, message

    def __init__(self, reconciler: Reconciler, parent: Optional[QObject] = None):
        # Initialize state properties
        # Store reference to model

    def start_scan(self) -> None:
        """Start the integrity scan operation."""
        # Validate inputs
        # Create and start worker thread

    def cancel_scan(self) -> None:
        """Cancel the ongoing scan operation."""

    # Additional methods for handling downloads, cache operations, etc.
```

### 3. Reconciler (Model)

```python
class Reconciler:
    """Core business logic for scanning directories and identifying missing timestamps."""

    def scan_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        satellite_pattern: str,
        interval_minutes: int = 0,  # 0 means auto-detect
        progress_callback: Optional[Callable[[int, int, float], None]] = None,
        should_cancel: Optional[Callable[[], bool]] = None,
        force_rescan: bool = False
    ) -> Dict[str, Any]:
        """
        Scan for missing timestamps within the date range.

        Returns dict with:
        - status: "completed", "cancelled", "error"
        - missing: List of missing timestamps
        - interval: Detected interval in minutes
        - total_expected: Total expected timestamps
        - total_found: Total timestamps found
        """
```

## UI Layout Components

- **Date Range Controls:**
  - From/To date pickers (QDateTimeEdit)
  - Interval spinner (QSpinBox) with auto-detect option
  - Satellite selector (QComboBox)

- **Action Controls:**
  - Verify button
  - Cancel button (enabled during scan)
  - Auto-download checkbox
  - Force rescan checkbox

- **Status & Results:**
  - Progress bar
  - Status text area
  - Missing items table (QTableView + custom model)
  - Cache info label

- **Modal Dialogs:**
  - Cache Inspector dialog
  - Export Report dialog

## Threading Implementation

We'll use QRunnable + QThreadPool for background operations:

```python
class ScanTask(QRunnable):
    """Background task for directory scanning."""

    class Signals(QObject):
        progress = pyqtSignal(int, int, float)  # current, total, eta
        missing = pyqtSignal(list)  # List of missing timestamps
        error = pyqtSignal(str)
        finished = pyqtSignal(dict)  # Results dictionary

    def __init__(self, reconciler, start_date, end_date, satellite, interval, force_rescan):
        self.signals = self.Signals()
        # Store parameters

    def run(self):
        try:
            # Call reconciler.scan_date_range with callbacks
            # Emit signals during processing
        except Exception as e:
            self.signals.error.emit(str(e))
        finally:
            # Always emit finished signal
```

## Cache Implementation

The SQLite cache will store:
- Scan date ranges (start, end, interval)
- Satellite pattern and options used
- Missing timestamps with metadata
- Last scan timestamp

## Signal Flow

1. User sets parameters, clicks "Verify"
2. View calls ViewModel.start_scan()
3. ViewModel creates ScanTask, connects signals
4. ScanTask runs in background, emits progress signals
5. ViewModel receives signals, updates its state, notifies View
6. View updates UI based on ViewModel state changes
7. On completion, ViewModel emits scan_completed
8. View shows results table, enables "Download" functionality

## Workflow Details

1. **Cache Hit Path:**
   - Check DB for previous scan of exact parameters
   - If found and not force_rescan, return cached results immediately

2. **Cache Miss Path:**
   - Generate expected timestamps based on interval
   - Scan local files for matches
   - Calculate missing timestamps
   - Store results in cache
   - Return list of missing items

3. **Download Path:**
   - For each missing timestamp:
     - Construct remote URL based on pattern
     - Download to local path
     - Update status in table

## Key Implementation Considerations

1. **Cache-First Design:**
   - Quick response for repeated scans of the same range
   - "Force Rescan" for refreshing when needed

2. **Responsive UI:**
   - All heavy operations in background threads
   - Progress signals provide frequent updates
   - QApplication.processEvents() in critical sections

3. **Error Handling:**
   - Worker threads catch and propagate exceptions
   - Clear error messages in UI
   - Graceful cancellation support

4. **Testability:**
   - Models isolated from Qt dependencies
   - ViewModels tested with mocked signals
   - End-to-end tests with pytest-qt
