#!/usr/bin/env python3
"""
Demo script to test the improved enhanced integrity check tab UI.

This script launches a window with just the improved enhanced integrity check tab
for testing the UI improvements independently of the full application.
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add the repository root to the Python path
repo_root = str(Path(__file__).parent.parent.parent)
sys.path.insert(0, repo_root)

from enum import Enum, auto

from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget

from goesvfi.integrity_check.enhanced_gui_tab_improved import (
    ImprovedEnhancedIntegrityCheckTab,
)
from goesvfi.integrity_check.enhanced_view_model import EnhancedIntegrityCheckViewModel
from goesvfi.integrity_check.thread_cache_db import ThreadLocalCacheDB
from goesvfi.integrity_check.view_model import MissingTimestamp
from goesvfi.utils import log


# Define a simple Satellite enum for demonstration
class Satellite(Enum):
    GOES16 = auto()
GOES18 = auto()


# Configure logging
LOGGER = log.get_logger(__name__)


class TestWindow(QMainWindow):
    """Test window for the improved enhanced integrity check tab."""

def __init__(self):
     super().__init__()

self.setWindowTitle("Improved Enhanced Integrity Check Tab Demo")
self.resize(900, 700)

# Create central widget
central_widget = QWidget()
self.setCentralWidget(central_widget)

# Create layout
layout = QVBoxLayout(central_widget)

# Create thread - safe cache DB for demo
thread_safe_cache = ThreadLocalCacheDB()

# Create view model with thread - safe components
downloads_dir = os.path.expanduser("~/Downloads")
self.view_model = EnhancedIntegrityCheckViewModel(cache_db=thread_safe_cache)
self.view_model.base_directory = (
downloads_dir # Set directory after initialization
)

# Add attributes that might be missing for demo purposes
# Import needed classes from the improved tab
from goesvfi.integrity_check.enhanced_gui_tab_improved import (
    FetchSource,  # Set missing attributes if needed if not hasattr(self.view_model, "preferred_source"): self.view_model.preferred_source = FetchSource.AUTO # Set other missing attributes if not hasattr(self.view_model, "can_start_scan"): self.view_model.can_start_scan = True if not hasattr(self.view_model, "total_expected"): self.view_model.total_expected = 0 if not hasattr(self.view_model, "missing_count"): self.view_model.missing_count = 0 if not hasattr(self.view_model, "is_scanning"): self.view_model.is_scanning = False if not hasattr(self.view_model, "is_downloading"): self.view_model.is_downloading = False if not hasattr(self.view_model, "status_message"): self.view_model.status_message = "Ready" # Set demo data for testing self._set_demo_data() # Create the improved tab self.tab = ImprovedEnhancedIntegrityCheckTab(self.view_model) layout.addWidget(self.tab) # Connect to signals for demonstration self.view_model.status_updated.connect(self._log_status) self.view_model.scan_completed.connect(self._log_scan_completed) LOGGER.info("Test window initialized") def _set_demo_data(self): """Set demo data for testing the UI.""" # Set date range to last week self.view_model.start_date = datetime.now() - timedelta(days=7) self.view_model.end_date = datetime.now() # Generate some demo missing items for the table missing_items = [] # Create timestamps from yesterday going back, one per hour base_time = datetime.now().replace( hour=0, minute=0, second=0, microsecond=0 ) - timedelta(days=1) for i in range(24): timestamp = base_time - timedelta(hours=i) # Create missing timestamp with different statuses expected_filename = ( f"OR_ABI - L1b - RadF - M6C13_G16_{timestamp.strftime('%Y % j % H % M % S')}.nc" ) if i % 6 == 0: # Downloaded item = MissingTimestamp(timestamp, expected_filename) item.is_downloaded = True item.local_path = f"/tmp / GOES / OR_ABI - L1b - RadF - M6C13_G16_{timestamp.strftime('%Y % j % H % M % S')}.nc" elif i % 6 == 1: # Downloading item = MissingTimestamp(timestamp, expected_filename) item.is_downloading = True if hasattr(item, "progress"): item.progress = 35 elif i % 6 == 2: # Error item = MissingTimestamp(timestamp, expected_filename) item.download_error = ( "Connection timeout while downloading from S3 bucket"
)

elif i % 6 == 3:
     pass
# Missing
item = MissingTimestamp(timestamp, expected_filename)
elif i % 6 == 4:
     pass
# Different error
item = MissingTimestamp(timestamp, expected_filename)
item.download_error = (
"404 Not Found: The specified key does not exist [Error 404]"
)
else:
     pass
# Another error
item = MissingTimestamp(timestamp, expected_filename)
item.download_error = "S3 permissions error: Access denied [Error 403]"

# Set satellite for enhanced items
try:
     item.satellite = Satellite.GOES16 if i % 2 == 0 else Satellite.GOES18
except AttributeError:
     pass
pass
pass # Skip if not an enhanced item

# Set source for enhanced items
try:
     pass
item.source = "s3" if i % 3 == 0 else "cdn"
except AttributeError:
     pass
pass
pass # Skip if not an enhanced item

# Set progress for downloading items
if getattr(item, "is_downloading", False):
     pass
try:
     item.progress = 35 + (i * 5) % 60 # Different progress values
except AttributeError:
     pass
pass
pass # Skip if not an enhanced item

missing_items.append(item)

# Set properties that would normally be set during a scan
self.view_model._missing_items = missing_items
self.view_model._missing_count = len(missing_items)
self.view_model._total_expected = 60 # 24 hours * 2.5 per hour
self.view_model._has_missing_items = True

# Emit signal to update the UI
self.view_model.missing_items_updated.emit(missing_items)

def _log_status(self, message: str):
     """Log status messages."""
LOGGER.info(f"Status: {message}")

def _log_scan_completed(self, success: bool, message: str):
     """Log scan completion."""
if success:
     pass
LOGGER.info(f"Scan completed successfully: {message}")
else:
     LOGGER.error(f"Scan failed: {message}")


def main():
    """Main entry point for the demo application."""
# Create application (Qt6 has high DPI scaling enabled by default)
app = QApplication(sys.argv)

# Create and show the main window
window = TestWindow()
window.show()

sys.exit(app.exec())


if __name__ == "__main__":
    pass
main()
