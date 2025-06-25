"""Custom widgets for the main tab."""

from typing import Callable, Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QPushButton, QWidget


class SuperButton(QPushButton):
    """A custom button class that ensures clicks are properly processed."""

    def __init__(self, text: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(text, parent)
        self.click_callback: Optional[Callable[[], None]] = None
        print(f"SuperButton created with text: {text}")

    def set_click_callback(self, callback: Optional[Callable[[], None]]) -> None:
        """Set a direct callback function for click events."""
        self.click_callback = callback
        print(f"SuperButton callback set: {callback.__name__ if callback else None!r}")

    def mousePressEvent(self, event: Optional[QMouseEvent]) -> None:
        """Explicitly override mouse press event."""
        if event is None:
            return

        print(f"SuperButton MOUSE PRESS: {event.button()}")
        # Call the parent implementation
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: Optional[QMouseEvent]) -> None:
        """Explicitly override mouse release event for better click detection."""
        if event is None:
            return

        print(f"SuperButton MOUSE RELEASE: {event.button()}")
        super().mouseReleaseEvent(event)

        # If it's a left-click release, call our callback
        if event.button() == Qt.MouseButton.LeftButton:
            print("SuperButton: LEFT CLICK DETECTED")
            if self.click_callback:
                print(f"SuperButton: Calling callback {self.click_callback.__name__}")
                QTimer.singleShot(10, self.click_callback)  # Small delay to ensure UI updates
            else:
                print("SuperButton: No callback registered")
