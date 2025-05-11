#!/usr/bin/env python
"""Debug launcher for GOES-VFI application."""

import sys
import traceback

try:
    from PyQt6.QtWidgets import QApplication

    from goesvfi.gui import MainWindow

    print("Starting GOES-VFI with debug tracing...")

    app = QApplication(sys.argv)
    window = MainWindow(debug_mode=True)
    window.show()
    sys.exit(app.exec())

except Exception as e:
    print(f"ERROR: {str(e)}")
    traceback.print_exc()
    sys.exit(1)
