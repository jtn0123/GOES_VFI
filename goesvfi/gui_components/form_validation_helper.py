"""
Form validation helper utilities for consistent theme-based validation feedback.

This module provides helper functions for applying validation state theme classes
to form elements, ensuring consistent visual feedback across the application.
"""

from typing import Optional

from PyQt6.QtWidgets import QWidget


def apply_validation_state(widget: QWidget, is_valid: bool, error_message: str | None = None) -> None:
    """
    Apply validation theme classes to a widget based on validation result.

    Args:
        widget: The widget to apply validation styling to
        is_valid: Whether the validation passed
        error_message: Optional error message to show in tooltip
    """
    if not is_valid:
        widget.setProperty("class", "ValidationError")
        if error_message:
            widget.setToolTip(error_message)
    else:
        # Clear validation error class
        widget.setProperty("class", "")
        widget.setToolTip("")

    # Force style refresh to apply new theme class
    style = widget.style()
    if style:
        style.unpolish(widget)
        style.polish(widget)


def clear_validation_state(widget: QWidget) -> None:
    """
    Clear validation state from a widget.

    Args:
        widget: The widget to clear validation styling from
    """
    apply_validation_state(widget, is_valid=True)


def apply_form_label_theme(widget: QWidget, theme_class: str = "FFmpegLabel") -> None:
    """
    Apply consistent form label theme class to a widget.

    Args:
        widget: The widget to apply theme class to
        theme_class: The theme class to apply (default: FFmpegLabel)
    """
    widget.setProperty("class", theme_class)
    style = widget.style()
    if style:
        style.unpolish(widget)
        style.polish(widget)
