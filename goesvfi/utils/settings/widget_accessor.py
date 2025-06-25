"""
Safe widget access utilities.

Provides safe widget access patterns that eliminate the repetitive defensive
programming patterns found in complex settings functions.
"""

import logging
from typing import Any, Callable, Optional, Type, Union, cast

from PyQt6.QtWidgets import QCheckBox, QComboBox, QLineEdit, QSpinBox, QWidget

from goesvfi.utils.errors import ErrorClassifier
from goesvfi.utils.validation import ValidationResult, ValidatorBase

LOGGER = logging.getLogger(__name__)


class WidgetSafetyValidator(ValidatorBase):
    """Validator for Qt widget safety checks."""

    def __init__(
        self,
        field_name: Optional[str] = None,
        expected_type: Optional[Type[QWidget]] = None,
        allow_none: bool = False,
    ) -> None:
        super().__init__(field_name)
        self.expected_type = expected_type
        self.allow_none = allow_none

    def validate(self, value: Any, context: Optional[dict] = None) -> ValidationResult:
        """Validate widget safety."""
        if value is None:
            if self.allow_none:
                return ValidationResult.success()
            else:
                return ValidationResult.failure(self._create_error("Widget is None", value))

        # Check if object still exists (not deleted)
        try:
            # Accessing any property will raise RuntimeError if object is deleted
            _ = value.objectName()
        except RuntimeError:
            return ValidationResult.failure(self._create_error("Widget has been deleted", value))
        except AttributeError:
            return ValidationResult.failure(self._create_error("Value is not a widget", value))

        # Check type if specified
        if self.expected_type and not isinstance(value, self.expected_type):
            return ValidationResult.failure(
                self._create_error(
                    f"Widget is not of expected type {self.expected_type.__name__}",
                    value,
                )
            )

        return ValidationResult.success()


class SafeWidgetAccessor:
    """
    Provides safe access to Qt widgets with automatic error handling.

    Eliminates the repetitive hasattr/isinstance/None checking patterns
    that create complexity in settings functions.
    """

    def __init__(self, classifier: Optional[ErrorClassifier] = None) -> None:
        self.classifier = classifier or ErrorClassifier()

    def safe_get_widget(
        self,
        parent: Any,
        widget_name: str,
        expected_type: Optional[Type[QWidget]] = None,
        default: Any = None,
    ) -> Optional[QWidget]:
        """
        Safely get a widget from a parent object.

        Args:
            parent: Parent object containing the widget
            widget_name: Name of the widget attribute
            expected_type: Expected widget type for validation
            default: Default value if widget not found/invalid

        Returns:
            Widget if found and valid, default otherwise
        """
        try:
            # Check if parent has the attribute
            if not hasattr(parent, widget_name):
                return cast(Optional[QWidget], default)

            # Get the widget
            widget = getattr(parent, widget_name)

            # Validate the widget
            validator = WidgetSafetyValidator(
                field_name=widget_name,
                expected_type=expected_type,
                allow_none=(default is None),
            )

            result = validator.validate(widget)
            if result.is_valid:
                # Type checking passed, safe to return
                return widget if isinstance(widget, (type(None), QWidget)) else cast(Optional[QWidget], default)
            else:
                if result.errors:
                    LOGGER.debug(f"Widget {widget_name} validation failed: {result.errors[0].message}")
                return cast(Optional[QWidget], default)

        except Exception as e:
            error = self.classifier.create_structured_error(e, f"get_widget_{widget_name}", "widget_accessor")
            LOGGER.debug(f"Failed to get widget {widget_name}: {error.user_message}")
            return cast(Optional[QWidget], default)

    def safe_get_value(
        self,
        parent: Any,
        widget_name: str,
        value_getter: Union[str, Callable],
        expected_type: Optional[Type[QWidget]] = None,
        default: Any = None,
    ) -> Any:
        """
        Safely get a value from a widget.

        Args:
            parent: Parent object containing the widget
            widget_name: Name of the widget attribute
            value_getter: Method name (str) or callable to get value
            expected_type: Expected widget type
            default: Default value if operation fails

        Returns:
            Widget value if successful, default otherwise
        """
        widget = self.safe_get_widget(parent, widget_name, expected_type, None)
        if widget is None:
            return default

        try:
            if isinstance(value_getter, str):
                # Method name string
                if hasattr(widget, value_getter):
                    method = getattr(widget, value_getter)
                    return method()
                else:
                    LOGGER.debug(f"Widget {widget_name} has no method {value_getter}")
                    return default
            else:
                # Callable
                return value_getter(widget)

        except Exception as e:
            error = self.classifier.create_structured_error(e, f"get_value_{widget_name}", "widget_accessor")
            LOGGER.debug(f"Failed to get value from {widget_name}: {error.user_message}")
            return default

    def safe_set_value(
        self,
        parent: Any,
        widget_name: str,
        value: Any,
        value_setter: Union[str, Callable],
        expected_type: Optional[Type[QWidget]] = None,
    ) -> bool:
        """
        Safely set a value on a widget.

        Args:
            parent: Parent object containing the widget
            widget_name: Name of the widget attribute
            value: Value to set
            value_setter: Method name (str) or callable to set value
            expected_type: Expected widget type

        Returns:
            True if successful, False otherwise
        """
        widget = self.safe_get_widget(parent, widget_name, expected_type, None)
        if widget is None:
            return False

        try:
            if isinstance(value_setter, str):
                # Method name string
                if hasattr(widget, value_setter):
                    method = getattr(widget, value_setter)
                    method(value)
                    return True
                else:
                    LOGGER.debug(f"Widget {widget_name} has no method {value_setter}")
                    return False
            else:
                # Callable
                value_setter(widget, value)
                return True

        except Exception as e:
            error = self.classifier.create_structured_error(e, f"set_value_{widget_name}", "widget_accessor")
            LOGGER.debug(f"Failed to set value on {widget_name}: {error.user_message}")
            return False

    # Convenience methods for common widget types
    def get_spinbox_value(self, parent: Any, widget_name: str, default: int = 0) -> int:
        """Get value from a QSpinBox."""
        result = self.safe_get_value(parent, widget_name, "value", QSpinBox, default)
        return int(result) if result is not None else default

    def get_combobox_text(self, parent: Any, widget_name: str, default: str = "") -> str:
        """Get current text from a QComboBox."""
        result = self.safe_get_value(parent, widget_name, "currentText", QComboBox, default)
        return str(result) if result is not None else default

    def get_checkbox_checked(self, parent: Any, widget_name: str, default: bool = False) -> bool:
        """Get checked state from a QCheckBox."""
        result = self.safe_get_value(parent, widget_name, "isChecked", QCheckBox, default)
        return bool(result) if result is not None else default

    def get_lineedit_text(self, parent: Any, widget_name: str, default: str = "") -> str:
        """Get text from a QLineEdit."""
        result = self.safe_get_value(parent, widget_name, "text", QLineEdit, default)
        return str(result) if result is not None else default

    def set_spinbox_value(self, parent: Any, widget_name: str, value: int) -> bool:
        """Set value on a QSpinBox."""
        return self.safe_set_value(parent, widget_name, value, "setValue", QSpinBox)

    def set_combobox_text(self, parent: Any, widget_name: str, text: str) -> bool:
        """Set current text on a QComboBox."""
        return self.safe_set_value(parent, widget_name, text, "setCurrentText", QComboBox)

    def set_checkbox_checked(self, parent: Any, widget_name: str, checked: bool) -> bool:
        """Set checked state on a QCheckBox."""
        return self.safe_set_value(parent, widget_name, checked, "setChecked", QCheckBox)

    def set_lineedit_text(self, parent: Any, widget_name: str, text: str) -> bool:
        """Set text on a QLineEdit."""
        return self.safe_set_value(parent, widget_name, text, "setText", QLineEdit)
