#!/usr/bin/env python3
"""
Debug script for diagnosing issues with the directory browsing in the integrity check tab.

This script adds comprehensive logging and exception handling to help diagnose crashes
during directory browsing operations in the integrity check tab.

Usage:
    pass
python debug_integrity_browse.py

The script will run the application with enhanced debugging for directory browsing
operations and output detailed logs to both the console and a log file.
"""

import logging
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path

# Setup logging before imports
log_file = Path("debug_integrity_browse.log")
logging.basicConfig(
level=logging.DEBUG,
format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
handlers=[logging.FileHandler(log_file), logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger("debug_integrity_browse")
logger.info(f"Debug script started at {datetime.now().isoformat()}")
logger.info(f"Python version: {sys.version}")
logger.info(f"Log file: {log_file.absolute()}")

# Import PyQt after logging setup
try:
    from PyQt6.QtCore import Qt, pyqtSignal
    from PyQt6.QtWidgets import (
        QApplication,
        QFileDialog,
        QPushButton,
        QVBoxLayout,
        QWidget,
    )
    logger.info("Successfully imported PyQt6 modules")
except ImportError as e:
    pass
    logger.critical(f"Failed to import PyQt6: {e}")
    sys.exit(1)


# Install exception hook to catch all unhandled exceptions
def exception_hook(exc_type, exc_value, exc_traceback):
    """Global exception hook to log unhandled exceptions."""
    logger.critical(
        "Unhandled exception:", exc_info=(exc_type, exc_value, exc_traceback)
    )
    # Also print to stderr for immediate visibility
    print("CRITICAL ERROR - UNHANDLED EXCEPTION:", file=sys.stderr)
    traceback.print_exception(exc_type, exc_value, exc_traceback, file=sys.stderr)

    # Call the original exception hook
    sys.__excepthook__(exc_type, exc_value, exc_traceback)


sys.excepthook = exception_hook

# Patch QFileDialog to add detailed logging
original_get_existing_directory = QFileDialog.getExistingDirectory


def patched_get_existing_directory(
    parent, caption, directory, options=QFileDialog.Option.ShowDirsOnly
):
    """Patched version of QFileDialog.getExistingDirectory with detailed logging."""
    logger.debug("QFileDialog.getExistingDirectory called with:")
    logger.debug(f" - parent: {parent}")
    logger.debug(f" - caption: {caption}")
    logger.debug(f" - directory: {directory}")
    logger.debug(f" - options: {options}")

    try:
        start_time = datetime.now()
        logger.info(f"Starting directory dialog at {start_time.isoformat()}")

        result = original_get_existing_directory(parent, caption, directory, options)

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info(f"Directory dialog completed in {duration:.2f} seconds")
        logger.info(f"Selected directory: {result}")

        return result
    except Exception as e:
        logger.error(f"Error in getExistingDirectory: {e}")
        logger.exception("Exception details:")
        raise


# Apply the patch
QFileDialog.getExistingDirectory = patched_get_existing_directory
logger.info("Patched QFileDialog.getExistingDirectory for detailed logging")


# Create a simple test application
class DirectoryBrowserTester(QWidget):
    """Simple test widget for directory browsing."""

directory_selected = pyqtSignal(str)

    def __init__(self):
     super().__init__()
        self.setWindowTitle("Directory Browser Test")
        self.setGeometry(100, 100, 500, 200)

        layout = QVBoxLayout(self)

        # Button to test file dialog
        self.browse_button = QPushButton("Browse Directory...")
        self.browse_button.clicked.connect(self.browse_directory)
        layout.addWidget(self.browse_button)

        # Connect signal to log
        self.directory_selected.connect(self.on_directory_selected)

        logger.info("DirectoryBrowserTester initialized")

    def browse_directory(self):
     """Test the directory browsing functionality."""
        logger.info("Browse button clicked")

        try:
        # Set wait cursor
        self.setCursor(Qt.CursorShape.WaitCursor)
        QApplication.processEvents()

        try:
     # Start from home directory
        start_dir = str(Path.home())
        logger.info(f"Starting directory dialog from: {start_dir}")

        # Open directory dialog
        directory = QFileDialog.getExistingDirectory(
        self,
        "Select Test Directory",
        start_dir,
        QFileDialog.Option.ShowDirsOnly,
        )

        logger.info(f"Directory dialog returned: {directory}")

        if directory:
     pass
        # Verify the directory
        path_obj = Path(directory)

        if not path_obj.exists():
     pass
        logger.error(f"Selected directory does not exist: {directory}")
        return

        if not path_obj.is_dir():
     pass
        logger.error(f"Selected path is not a directory: {directory}")
        return

        # Try to read the directory contents
        try:
     next(path_obj.iterdir(), None)
        logger.info(
        f"Successfully read first item in directory: {directory}"
        )
        except PermissionError as e:
     pass
        logger.error(f"Permission denied reading directory: {e}")
        return
        except Exception as e:
     pass
        logger.error(f"Error reading directory: {e}")
        logger.exception("Exception details:")
        return

        # Emit signal
        logger.info(f"Emitting directory_selected signal with: {directory}")
        self.directory_selected.emit(directory)
        except Exception as e:
     pass
        logger.error(f"Error in browse_directory: {e}")
        logger.exception("Exception details:")
        finally:
     # Restore cursor
        self.setCursor(Qt.CursorShape.ArrowCursor)
        QApplication.processEvents()

    def on_directory_selected(self, directory):
     """Handle directory selection."""
        logger.info(f"directory_selected signal received with: {directory}")

        # Try to get disk information
        try:
     stats = os.statvfs(directory)
        total = stats.f_frsize * stats.f_blocks / (1024**3) # Convert to GB
        free = stats.f_frsize * stats.f_bfree / (1024**3)
        used = total - free

        logger.info("Directory disk information:")
        logger.info(f" - Total space: {total:.2f} GB")
        logger.info(f" - Used space: {used:.2f} GB")
        logger.info(f" - Free space: {free:.2f} GB")
        except Exception as e:
     pass
        logger.error(f"Error getting disk information: {e}")
        logger.exception("Exception details:")


    def patch_goesvfi():
        """Patch the GOES - VFI classes for enhanced debugging."""
        try:
     # First, try to import the necessary modules
        from goesvfi.integrity_check.enhanced_gui_tab import EnhancedIntegrityCheckTab
        from goesvfi.integrity_check.remote.s3_store import S3Store

        logger.info("Successfully imported GOES - VFI modules for patching")

        # Patch EnhancedIntegrityCheckTab._browse_directory
        original_browse_directory = EnhancedIntegrityCheckTab._browse_directory

    def patched_browse_directory(self):
     """Patched version of _browse_directory with enhanced logging."""
        logger.info("EnhancedIntegrityCheckTab._browse_directory called")
        logger.info(f"Current base_directory: {self.view_model.base_directory}")

        try:
     result = original_browse_directory(self)
        logger.info("_browse_directory completed successfully")
        return result
        except Exception as e:
     pass
        logger.error(f"Error in _browse_directory: {e}")
        logger.exception("Exception details:")
        raise

        EnhancedIntegrityCheckTab._browse_directory = patched_browse_directory
        logger.info(
        "Patched EnhancedIntegrityCheckTab._browse_directory for detailed logging"
        )

        # Patch S3Store._get_s3_client
        original_get_s3_client = S3Store._get_s3_client

        async def patched_get_s3_client(self):
     """Patched version of _get_s3_client with enhanced logging."""
        logger.info("S3Store._get_s3_client called")
        logger.info(f"AWS region: {self.aws_region}, Profile: {self.aws_profile}")

        try:
     start_time = datetime.now()
        logger.info(f"Starting S3 client creation at {start_time.isoformat()}")

        result = await original_get_s3_client(self)

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info(f"S3 client creation completed in {duration:.2f} seconds")

        return result
        except Exception as e:
     pass
        logger.error(f"Error in _get_s3_client: {e}")
        logger.exception("Exception details:")
        raise

        S3Store._get_s3_client = patched_get_s3_client
        logger.info("Patched S3Store._get_s3_client for detailed logging")

        return True
        except ImportError as e:
     pass
        logger.error(f"Failed to import GOES - VFI modules for patching: {e}")
        return False
        except Exception as e:
     pass
        logger.error(f"Error patching GOES - VFI classes: {e}")
        logger.exception("Exception details:")
        return False


    def run_test_app():
        """Run the test application."""
        app = QApplication([])
        tester = DirectoryBrowserTester()
        tester.show()
        logger.info("Test application started")
        sys.exit(app.exec())


    def run_patched_goesvfi():
        """Run the actual GOES - VFI application with patches."""
        try:
     # Import main application
        from goesvfi import gui

        logger.info("Starting patched GOES - VFI application")
        sys.argv.append("--debug") # Add debug flag
        gui.main()
        except ImportError as e:
     pass
        logger.error(f"Failed to import GOES - VFI GUI: {e}")
        except Exception as e:
     pass
        logger.error(f"Error running GOES - VFI application: {e}")
        logger.exception("Exception details:")


        if __name__ == "__main__":
        pass
        logger.info("Starting debug script")

        # Patch QFileDialog
        logger.info("Applying patches...")

        # Try to patch GOES - VFI classes
        patched = patch_goesvfi()

        if patched:
     pass
        logger.info("Running patched GOES - VFI application")
        run_patched_goesvfi()
        else:
     logger.info("Running test directory browser application")
        run_test_app()
