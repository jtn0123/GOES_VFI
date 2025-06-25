#!/bin/bash
# Launch GUI and bring to foreground

echo "🚀 Launching GOES-VFI GUI..."
source .venv/bin/activate

# Launch in foreground with explicit display
python -c "
import sys
from PyQt6.QtWidgets import QApplication
from goesvfi.gui import MainWindow

app = QApplication(sys.argv)
window = MainWindow()
window.show()
window.raise_()  # Bring to front
window.activateWindow()  # Make active
app.exec()
"
