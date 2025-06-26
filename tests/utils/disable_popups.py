"""
Test utility to disable all GUI popups and user interactions.
Import this at the start of any test that uses GUI components.
"""

import os
from typing import Any, List
from unittest.mock import patch

# Set Qt to use offscreen platform
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


# Store the original QDateTimeEdit class before patching
_original_QDateTimeEdit = None


def NoPopupQDateTimeEdit(*args, **kwargs):
    """Factory function that returns a QDateTimeEdit with calendar popup disabled."""
    # Use the stored original class to avoid recursion
    global _original_QDateTimeEdit
    if _original_QDateTimeEdit is None:
        # This should never happen if patches are applied correctly
        from PyQt6.QtWidgets import QDateTimeEdit

        _original_QDateTimeEdit = QDateTimeEdit

    # Create the real widget
    widget = _original_QDateTimeEdit(*args, **kwargs)
    # Disable calendar popup and override setCalendarPopup
    widget.setCalendarPopup(False)

    # Override setCalendarPopup to always keep it disabled
    original_setCalendarPopup = widget.setCalendarPopup

    def no_popup_setCalendarPopup(enable: bool) -> None:
        original_setCalendarPopup(False)

    # Use setattr to avoid mypy method assignment error
    widget.setCalendarPopup = no_popup_setCalendarPopup  # type: ignore[method-assign]

    return widget


class NoPopupQFileDialog:
    """QFileDialog that returns mock values instead of opening dialogs."""

    @staticmethod
    def getExistingDirectory(*args, **kwargs):
        return "/test/mock/directory"

    @staticmethod
    def getSaveFileName(*args, **kwargs):
        return ("/test/mock/file.txt", "All Files (*)")

    @staticmethod
    def getOpenFileName(*args, **kwargs):
        return ("/test/mock/file.txt", "All Files (*)")


class NoPopupQMessageBox:
    """QMessageBox that returns mock values instead of showing dialogs."""

    class StandardButton:
        Yes = 1
        No = 2
        Ok = 3
        Cancel = 4

    @staticmethod
    def information(*args, **kwargs):
        return NoPopupQMessageBox.StandardButton.Ok

    @staticmethod
    def warning(*args, **kwargs):
        return NoPopupQMessageBox.StandardButton.Ok

    @staticmethod
    def critical(*args, **kwargs):
        return NoPopupQMessageBox.StandardButton.Ok

    @staticmethod
    def question(*args, **kwargs):
        return NoPopupQMessageBox.StandardButton.Yes


def apply_gui_patches() -> List[Any]:
    """Apply patches to prevent GUI popups."""
    patches: List[Any] = []

    # Store the original QDateTimeEdit class before patching
    global _original_QDateTimeEdit
    if _original_QDateTimeEdit is None:
        from PyQt6.QtWidgets import QDateTimeEdit

        _original_QDateTimeEdit = QDateTimeEdit

    # Patch QFileDialog - only patch PyQt6 directly to avoid import issues
    patches.extend(
        [
            patch("PyQt6.QtWidgets.QFileDialog", NoPopupQFileDialog),
        ]
    )

    # Patch QMessageBox
    patches.extend(
        [
            patch("PyQt6.QtWidgets.QMessageBox", NoPopupQMessageBox),
            patch(
                "goesvfi.integrity_check.enhanced_gui_tab.QMessageBox",
                NoPopupQMessageBox,
            ),
            patch("goesvfi.integrity_check.gui_tab.QMessageBox", NoPopupQMessageBox),
            patch("goesvfi.gui_tabs.batch_processing_tab.QMessageBox", NoPopupQMessageBox),
        ]
    )

    # Patch QDateTimeEdit to disable calendar popups
    patches.extend(
        [
            patch("PyQt6.QtWidgets.QDateTimeEdit", NoPopupQDateTimeEdit),
        ]
    )

    # Start all patches
    for p in patches:
        p.start()

    return patches


# Global list to track active patches
_active_patches: List[Any] = []


def disable_all_gui_popups():
    """Main function to disable all GUI popups."""
    global _active_patches
    if not _active_patches:  # Only apply once
        _active_patches = apply_gui_patches()


def restore_gui_popups():
    """Restore normal GUI behavior."""
    global _active_patches
    for p in _active_patches:
        try:
            p.stop()
        except Exception:
            pass
    _active_patches = []


# Don't auto-apply - tests should call disable_all_gui_popups() explicitly
# disable_all_gui_popups()
