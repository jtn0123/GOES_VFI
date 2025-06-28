"""Custom widgets for the main tab."""

from collections.abc import Callable

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QPushButton, QWidget


class SuperButton(QPushButton):
    """A custom button class that ensures clicks are properly processed."""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.click_callback: Callable[[], None] | None = None

    def set_click_callback(self, callback: Callable[[], None] | None) -> None:
        """Set a direct callback function for click events."""
        self.click_callback = callback

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        """Explicitly override mouse press event."""
        if event is None:
            return

        # Call the parent implementation
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent | None) -> None:
        """Explicitly override mouse release event for better click detection."""
        if event is None:
            return

        super().mouseReleaseEvent(event)

        # If it's a left-click release, call our callback
        if event.button() == Qt.MouseButton.LeftButton and self.click_callback:
            QTimer.singleShot(10, self.click_callback)  # Small delay to ensure UI updates
