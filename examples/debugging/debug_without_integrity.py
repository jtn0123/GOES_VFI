#!/usr/bin/env python
"""Debug launcher for GOES-VFI application without integrity check tab."""

import logging
import sys
import traceback

try:
    from PyQt6.QtWidgets import QApplication

    # Set up logging to capture more details
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        filename="debug_without_integrity.log",
    )

    # Create a wrapper class to disable the integrity check tab
    from goesvfi.gui import MainWindow as OriginalMainWindow

    class MainWindowWithoutIntegrityTab(OriginalMainWindow):
        """MainWindow with integrity check tab disabled."""

        def __init__(self, *args, **kwargs):
            print("Initializing MainWindow with integrity check tab disabled")

            # Initialize the parent class
            super().__init__(*args, **kwargs)

            # Skip adding the integrity check tab if it exists
            try:
                # If the tab was added, try to remove it
                if hasattr(self, "integrity_check_tab") and hasattr(self, "tab_widget"):
                    idx = self.tab_widget.indexOf(self.integrity_check_tab)
                    if idx >= 0:
                        print(f"Removing integrity check tab at index {idx}")
                        self.tab_widget.removeTab(idx)
                    else:
                        print("Integrity check tab not found in tab widget")
                else:
                    print("Integrity check tab or tab widget not found")
            except Exception as e:
                print(f"Error removing integrity check tab: {e}")
                traceback.print_exc()

    print("Starting GOES-VFI without integrity check tab...")

    app = QApplication(sys.argv)
    window = MainWindowWithoutIntegrityTab(debug_mode=True)
    window.show()
    sys.exit(app.exec())

except Exception as e:
    print(f"ERROR: {str(e)}")
    traceback.print_exc()
    sys.exit(1)
