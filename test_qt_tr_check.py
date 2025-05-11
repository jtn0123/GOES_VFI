"""Test file to verify flake8-qt-tr plugin functionality."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget


class TestWidget(QWidget):
    """Test widget with untranslated strings to verify linter detection."""

    def __init__(self) -> None:
        """Initialize with labels and buttons that should be translated."""
        super().__init__()

        # Set window title - should be translated
        self.setWindowTitle("Untranslated Window Title")

        layout = QVBoxLayout(self)

        # These strings should all trigger translation warnings
        self.label1 = QLabel("This is an untranslated string")
        self.label2 = QLabel("Another untranslated string with punctuation!")

        # Buttons with untranslated text
        self.button1 = QPushButton("OK")
        self.button2 = QPushButton("Cancel")

        # Add widgets to layout
        layout.addWidget(self.label1)
        layout.addWidget(self.label2)
        layout.addWidget(self.button1)
        layout.addWidget(self.button2)

        # Set tooltip - should be translated
        self.setToolTip("This tooltip should be translated")
