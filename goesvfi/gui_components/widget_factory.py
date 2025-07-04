"""Widget factory for consistent widget creation and styling across the application."""

from collections.abc import Callable
from typing import Any

from PyQt6.QtWidgets import (
    QCalendarWidget,
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QGroupBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QTimeEdit,
    QWidget,
)

from goesvfi.utils import log

LOGGER = log.get_logger(__name__)


class WidgetFactory:
    """Factory class for creating widgets with consistent styling.

    This class provides static methods to create commonly used widgets
    with appropriate style classes automatically applied. All widgets
    are created with consistent styling that follows the design system
    defined in default.qss.
    """

    # Style class mappings for different widget types
    BUTTON_STYLES = {
        "primary": "DialogPrimaryButton",
        "secondary": "DialogButton",
        "start": "StartButton",
        "cancel": "CancelButton",
        "tab": "TabButton",
        "date_picker": "DatePickerButton",
        "date_picker_primary": "DatePickerPrimary",
    }

    LABEL_STYLES = {
        "standard": "StandardLabel",
        "header": "AppHeader",
        "status": "StatusLabel",
        "status_success": "StatusSuccess",
        "status_error": "StatusError",
        "status_warning": "StatusWarning",
        "status_info": "StatusInfo",
        "ffmpeg": "FFmpegLabel",
        "imagery": "ImageryLabel",
        "preview": "ImagePreview",
        "date_range": "DateRangeDisplay",
        "date_picker_title": "DatePickerTitle",
        "date_picker_mono": "DatePickerMonospace",
        "crop_instruction": "CropDialogInstruction",
        "error_message": "ErrorDialogMessage",
        "feedback": "FeedbackStatusLabel",
        "feedback_info": "FeedbackStatusInfo",
        "feedback_success": "FeedbackStatusSuccess",
        "feedback_warning": "FeedbackStatusWarning",
        "feedback_error": "FeedbackStatusError",
        "feedback_debug": "FeedbackStatusDebug",
        "satellite_header": "SatelliteHeader",
        "satellite_description": "SatelliteDescription",
        "date_range_label": "DateRangeLabel",
        "goes_imagery_header": "GOESImageryHeader",
        "crop_preview": "CropPreviewLabel",
        "image_viewer": "ImageViewerLabel",
    }

    FRAME_STYLES = {
        "control": "ControlFrame",
        "satellite": "SatelliteDataFrame",
        "date_picker_group": "DatePickerGroup",
        "date_picker_preview": "DatePickerPreview",
    }

    DIALOG_STYLES = {
        "crop": "CropSelectionDialog",
        "image_viewer": "ImageViewerDialog",
        "auto_detection": "AutoDetectionDialog",
    }

    WIDGET_STYLES = {
        "main_tab": "MainTab",
        "integrity_tab": "IntegrityCheckTab",
        "ffmpeg_tab": "FFmpegSettingsTab",
        "timeline": "TimelineViz",
        "crop_header": "CropDialogHeader",
        "profile_container": "ProfileContainer",
        "results_control_panel": "resultsControlPanel",
        "satellite_tab_widget": "SatelliteTabWidget",
    }

    LIST_STYLES = {
        "feedback": "FeedbackMessageList",
        "auto_detection_log": "AutoDetectionLog",
    }

    @staticmethod
    def create_button(
        text: str = "",
        style: str = "secondary",
        parent: QWidget | None = None,
        tooltip: str = "",
        accessibility_name: str = "",
        **kwargs: Any,
    ) -> QPushButton:
        """Create a styled button with accessibility features.

        Args:
            text: Button text
            style: Style type (primary, secondary, start, cancel, tab, date_picker)
            parent: Parent widget
            tooltip: Tooltip text for accessibility
            accessibility_name: Accessible name for screen readers
            **kwargs: Additional QPushButton properties

        Returns:
            Styled QPushButton instance with accessibility features
        """
        button = QPushButton(text, parent)

        # Apply style class
        style_class = WidgetFactory.BUTTON_STYLES.get(style, "DialogButton")
        button.setProperty("class", style_class)

        # Add accessibility features
        if tooltip:
            button.setToolTip(tooltip)
            button.setStatusTip(tooltip)

        if accessibility_name:
            button.setAccessibleName(accessibility_name)
        elif text:
            button.setAccessibleName(text)

        # Add keyboard accelerator if not present and text is available
        if "&" not in text and text:
            button.setText(f"&{text}")

        # Apply any additional properties
        for key, value in kwargs.items():
            if hasattr(button, key):
                setattr(button, key, value)

        return button

    @staticmethod
    def create_label(
        text: str = "",
        style: str = "standard",
        parent: QWidget | None = None,
        tooltip: str = "",
        accessibility_name: str = "",
        **kwargs: Any,
    ) -> QLabel:
        """Create a styled label with accessibility features.

        Args:
            text: Label text
            style: Style type (standard, header, status, etc.)
            parent: Parent widget
            tooltip: Tooltip text for accessibility
            accessibility_name: Accessible name for screen readers
            **kwargs: Additional QLabel properties

        Returns:
            Styled QLabel instance with accessibility features
        """
        label = QLabel(text, parent)

        # Apply style class
        style_class = WidgetFactory.LABEL_STYLES.get(style, "StandardLabel")
        label.setProperty("class", style_class)

        # Add accessibility features
        if tooltip:
            label.setToolTip(tooltip)

        if accessibility_name:
            label.setAccessibleName(accessibility_name)
        elif text:
            label.setAccessibleName(text)

        # Apply any additional properties
        for key, value in kwargs.items():
            if hasattr(label, key):
                setattr(label, key, value)

        return label

    @staticmethod
    def create_line_edit(
        text: str = "",
        placeholder: str = "",
        parent: QWidget | None = None,
        validation_error: bool = False,
        **kwargs: Any,
    ) -> QLineEdit:
        """Create a styled line edit.

        Args:
            text: Initial text
            placeholder: Placeholder text
            parent: Parent widget
            validation_error: Whether to show validation error style
            **kwargs: Additional QLineEdit properties

        Returns:
            Styled QLineEdit instance
        """
        line_edit = QLineEdit(text, parent)

        if placeholder:
            line_edit.setPlaceholderText(placeholder)

        # Apply validation error style if needed
        if validation_error:
            line_edit.setProperty("class", "ValidationError")
        else:
            line_edit.setProperty("class", "")

        # Apply any additional properties
        for key, value in kwargs.items():
            if hasattr(line_edit, key):
                setattr(line_edit, key, value)

        return line_edit

    @staticmethod
    def create_frame(style: str = "control", parent: QWidget | None = None, **kwargs: Any) -> QFrame:
        """Create a styled frame.

        Args:
            style: Style type (control, satellite, date_picker_group, etc.)
            parent: Parent widget
            **kwargs: Additional QFrame properties

        Returns:
            Styled QFrame instance
        """
        frame = QFrame(parent)

        # Apply style class
        style_class = WidgetFactory.FRAME_STYLES.get(style, "ControlFrame")
        frame.setProperty("class", style_class)

        # Apply any additional properties
        for key, value in kwargs.items():
            if hasattr(frame, key):
                setattr(frame, key, value)

        return frame

    @staticmethod
    def create_group_box(title: str = "", parent: QWidget | None = None, **kwargs: Any) -> QGroupBox:
        """Create a styled group box.

        Args:
            title: Group box title
            parent: Parent widget
            **kwargs: Additional QGroupBox properties

        Returns:
            Styled QGroupBox instance
        """
        group_box = QGroupBox(title, parent)

        # Group box styling is handled by default QSS
        # No need for specific class

        # Apply any additional properties
        for key, value in kwargs.items():
            if hasattr(group_box, key):
                setattr(group_box, key, value)

        return group_box

    @staticmethod
    def create_progress_bar(parent: QWidget | None = None, data_progress: bool = True, **kwargs: Any) -> QProgressBar:
        """Create a styled progress bar.

        Args:
            parent: Parent widget
            data_progress: Whether to use DataProgress style
            **kwargs: Additional QProgressBar properties

        Returns:
            Styled QProgressBar instance
        """
        progress_bar = QProgressBar(parent)

        # Apply style class
        if data_progress:
            progress_bar.setProperty("class", "DataProgress")

        # Apply any additional properties
        for key, value in kwargs.items():
            if hasattr(progress_bar, key):
                setattr(progress_bar, key, value)

        return progress_bar

    @staticmethod
    def create_dialog(style: str = "default", parent: QWidget | None = None, **kwargs: Any) -> QDialog:
        """Create a styled dialog.

        Args:
            style: Style type (crop, image_viewer)
            parent: Parent widget
            **kwargs: Additional QDialog properties

        Returns:
            Styled QDialog instance
        """
        dialog = QDialog(parent)

        # Apply style class
        style_class = WidgetFactory.DIALOG_STYLES.get(style, "")
        if style_class:
            dialog.setProperty("class", style_class)

        # Apply any additional properties
        for key, value in kwargs.items():
            if hasattr(dialog, key):
                setattr(dialog, key, value)

        return dialog

    @staticmethod
    def create_widget(
        widget_class: type[QWidget], style: str | None = None, parent: QWidget | None = None, **kwargs: Any
    ) -> QWidget:
        """Create a generic widget with optional styling.

        Args:
            widget_class: The widget class to instantiate
            style: Optional style class name
            parent: Parent widget
            **kwargs: Additional widget properties

        Returns:
            Styled widget instance
        """
        widget = widget_class(parent)

        # Apply style class if provided
        if style:
            # Check if it's a known widget style
            if style in WidgetFactory.WIDGET_STYLES:
                widget.setProperty("class", WidgetFactory.WIDGET_STYLES[style])
            else:
                widget.setProperty("class", style)

        # Apply any additional properties
        for key, value in kwargs.items():
            if hasattr(widget, key):
                setattr(widget, key, value)

        return widget

    @staticmethod
    def create_list_widget(parent: QWidget | None = None, style: str | None = None, **kwargs: Any) -> QListWidget:
        """Create a styled list widget.

        Args:
            parent: Parent widget
            style: Style type (feedback, auto_detection_log)
            **kwargs: Additional QListWidget properties

        Returns:
            Styled QListWidget instance
        """
        list_widget = QListWidget(parent)

        # Apply style class
        if style and style in WidgetFactory.LIST_STYLES:
            list_widget.setProperty("class", WidgetFactory.LIST_STYLES[style])

        # Apply any additional properties
        for key, value in kwargs.items():
            if hasattr(list_widget, key):
                setattr(list_widget, key, value)

        return list_widget

    @staticmethod
    def create_text_edit(
        parent: QWidget | None = None, error_traceback: bool = False, **kwargs: Any
    ) -> QTextEdit | QPlainTextEdit:
        """Create a styled text edit widget.

        Args:
            parent: Parent widget
            error_traceback: Whether to use ErrorDialogTraceback style
            **kwargs: Additional text edit properties

        Returns:
            Styled QTextEdit or QPlainTextEdit instance
        """
        text_edit: QTextEdit | QPlainTextEdit
        if error_traceback:
            text_edit = QPlainTextEdit(parent)
            text_edit.setProperty("class", "ErrorDialogTraceback")
        else:
            text_edit = QTextEdit(parent)

        # Apply any additional properties
        for key, value in kwargs.items():
            if hasattr(text_edit, key):
                setattr(text_edit, key, value)

        return text_edit

    @staticmethod
    def create_calendar_widget(
        parent: QWidget | None = None, date_picker: bool = True, **kwargs: Any
    ) -> QCalendarWidget:
        """Create a styled calendar widget.

        Args:
            parent: Parent widget
            date_picker: Whether to use DatePickerCalendar style
            **kwargs: Additional QCalendarWidget properties

        Returns:
            Styled QCalendarWidget instance
        """
        calendar = QCalendarWidget(parent)

        # Apply style class
        if date_picker:
            calendar.setProperty("class", "DatePickerCalendar")

        # Apply any additional properties
        for key, value in kwargs.items():
            if hasattr(calendar, key):
                setattr(calendar, key, value)

        return calendar

    @staticmethod
    def create_time_edit(parent: QWidget | None = None, date_picker: bool = True, **kwargs: Any) -> QTimeEdit:
        """Create a styled time edit widget.

        Args:
            parent: Parent widget
            date_picker: Whether to use DatePickerTime style
            **kwargs: Additional QTimeEdit properties

        Returns:
            Styled QTimeEdit instance
        """
        time_edit = QTimeEdit(parent)

        # Apply style class
        if date_picker:
            time_edit.setProperty("class", "DatePickerTime")

        # Apply any additional properties
        for key, value in kwargs.items():
            if hasattr(time_edit, key):
                setattr(time_edit, key, value)

        return time_edit

    @staticmethod
    def update_widget_style(widget: QWidget, style_class: str, refresh: bool = True) -> None:
        """Update the style class of an existing widget.

        Args:
            widget: Widget to update
            style_class: New style class to apply
            refresh: Whether to refresh the widget style
        """
        widget.setProperty("class", style_class)

        if refresh:
            # Force style refresh
            style = widget.style()
            if style:
                style.unpolish(widget)
                style.polish(widget)
            widget.update()

    @staticmethod
    def update_all_widget_styles(parent_widget: QWidget) -> None:
        """Force refresh all widget styles under a parent widget.
        Useful after theme changes to ensure all widgets update properly.

        Args:
            parent_widget: Parent widget to recursively update
        """

        def refresh_widget(widget: QWidget) -> None:
            style = widget.style()
            if style:
                style.unpolish(widget)
                style.polish(widget)
            widget.update()

            # Recursively update child widgets
            for child in widget.findChildren(QWidget):
                refresh_widget(child)

        refresh_widget(parent_widget)

    @staticmethod
    def remove_widget_style(widget: QWidget, refresh: bool = True) -> None:
        """Remove custom style class from a widget.

        Args:
            widget: Widget to update
            refresh: Whether to refresh the widget style
        """
        widget.setProperty("class", "")

        if refresh:
            # Force style refresh
            style = widget.style()
            if style:
                style.unpolish(widget)
                style.polish(widget)
            widget.update()

    @staticmethod
    def create_tab_widget(parent: QWidget | None = None, style: str | None = None, **kwargs: Any) -> QTabWidget:
        """Create a styled tab widget.

        Args:
            parent: Parent widget
            style: Style type (satellite_tab_widget)
            **kwargs: Additional QTabWidget properties

        Returns:
            Styled QTabWidget instance
        """
        tab_widget = QTabWidget(parent)

        # Apply style class
        if style and style == "satellite_tab_widget":
            tab_widget.setProperty("class", WidgetFactory.WIDGET_STYLES.get(style, ""))

        # Apply any additional properties
        for key, value in kwargs.items():
            if hasattr(tab_widget, key):
                setattr(tab_widget, key, value)

        return tab_widget

    @staticmethod
    def create_separator(orientation: str = "horizontal", parent: QWidget | None = None, **kwargs: Any) -> QFrame:
        """Create a separator line.

        Args:
            orientation: Separator orientation (horizontal or vertical)
            parent: Parent widget
            **kwargs: Additional QFrame properties

        Returns:
            Styled QFrame separator
        """
        separator = QFrame(parent)

        if orientation.lower() == "vertical":
            separator.setFrameShape(QFrame.Shape.VLine)
        else:
            separator.setFrameShape(QFrame.Shape.HLine)

        separator.setFrameShadow(QFrame.Shadow.Sunken)

        # Set maximum dimension based on orientation
        if orientation.lower() == "vertical":
            separator.setMaximumWidth(1)
        else:
            separator.setMaximumHeight(1)

        # Apply any additional properties
        for key, value in kwargs.items():
            if hasattr(separator, key):
                setattr(separator, key, value)

        return separator

    @staticmethod
    def create_combo_box(
        items: list[str] | None = None,
        parent: QWidget | None = None,
        tooltip: str | None = None,
        **kwargs: Any,
    ) -> QComboBox:
        """Create a styled combo box.

        Args:
            items: List of items to add to the combo box
            parent: Parent widget
            tooltip: Tooltip text
            **kwargs: Additional QComboBox properties

        Returns:
            Styled QComboBox instance
        """
        combo_box = QComboBox(parent)

        if items:
            combo_box.addItems(items)

        if tooltip:
            combo_box.setToolTip(tooltip)

        # Apply any additional properties
        for key, value in kwargs.items():
            if hasattr(combo_box, key):
                setattr(combo_box, key, value)

        return combo_box

    @staticmethod
    def create_checkbox(
        text: str = "",
        parent: QWidget | None = None,
        tooltip: str | None = None,
        **kwargs: Any,
    ) -> QCheckBox:
        """Create a styled checkbox.

        Args:
            text: Checkbox text
            parent: Parent widget
            tooltip: Tooltip text
            **kwargs: Additional QCheckBox properties

        Returns:
            Styled QCheckBox instance
        """
        checkbox = QCheckBox(text, parent)

        if tooltip:
            checkbox.setToolTip(tooltip)

        # Apply any additional properties
        for key, value in kwargs.items():
            if hasattr(checkbox, key):
                setattr(checkbox, key, value)

        return checkbox

    @staticmethod
    def create_container(style: str = "default", parent: QWidget | None = None, **kwargs: Any) -> QWidget:
        """Create a styled container widget.

        Args:
            style: Container style (profile, etc.)
            parent: Parent widget
            **kwargs: Additional QWidget properties

        Returns:
            Styled QWidget container
        """
        container = QWidget(parent)

        # Apply style class based on style type
        if style == "profile":
            container.setProperty("class", "ProfileContainer")
        elif style in WidgetFactory.WIDGET_STYLES:
            container.setProperty("class", WidgetFactory.WIDGET_STYLES[style])

        # Apply any additional properties
        for key, value in kwargs.items():
            if hasattr(container, key):
                setattr(container, key, value)

        return container


# Convenience functions for common widget creation patterns
def create_form_label(text: str, parent: QWidget | None = None) -> QLabel:
    """Create a label suitable for form layouts."""
    return WidgetFactory.create_label(text, style="standard", parent=parent)


def create_status_label(text: str = "", status_type: str = "info", parent: QWidget | None = None) -> QLabel:
    """Create a status label with appropriate styling."""
    style = f"status_{status_type}" if status_type in {"success", "error", "warning", "info"} else "status"
    return WidgetFactory.create_label(text, style=style, parent=parent)


def create_action_button(
    text: str, action: str = "primary", parent: QWidget | None = None, clicked: Callable | None = None
) -> QPushButton:
    """Create an action button with optional clicked handler."""
    button = WidgetFactory.create_button(text, style=action, parent=parent)
    if clicked:
        button.clicked.connect(clicked)
    return button
