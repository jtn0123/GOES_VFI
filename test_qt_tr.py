"""Test file to verify flake8-qt-tr plugin."""

from PyQt6.QtWidgets import QLabel, QWidget

class TestWidget(QWidget):
    """Test widget with an untranslated string."""
    
    def __init__(self) -> None:
        """Initialize with a label that should be translated."""
        super().__init__()
        
        # This should trigger a QTR error - string needs tr()
        self.label = QLabel("This is an untranslated string")