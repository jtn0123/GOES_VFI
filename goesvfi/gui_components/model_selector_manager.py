"""Model selection management for MainWindow."""

import re
from typing import Any

from PyQt6.QtCore import Qt

from goesvfi.utils import config, log

LOGGER = log.get_logger(__name__)


class ModelSelectorManager:
    """Manages model selection and validation."""

    @staticmethod
    def populate_models(main_window: Any) -> None:
        """Populate the RIFE model combo box.

        Args:
            main_window: The MainWindow instance
        """
        LOGGER.debug("Entering populate_models...")
        available_models = config.get_available_rife_models()

        # Use alias self.model_combo which points to self.main_tab.rife_model_combo
        main_window.model_combo.clear()

        if available_models:
            main_window.model_combo.addItems(available_models)

            # Set the current text to the loaded setting or default
            loaded_model = main_window.settings.value("rife_model_key", "rife-v4.6", type=str)
            if loaded_model in available_models:
                main_window.model_combo.setCurrentText(loaded_model)
            else:
                main_window.model_combo.setCurrentIndex(0)  # Select the first available model

            # Set model key on main_tab since current_model_key is a property in MainWindow
            if hasattr(main_window.main_tab, "current_model_key"):
                main_window.main_tab.current_model_key = main_window.model_combo.currentText()
        else:
            main_window.model_combo.addItem(main_window.tr("No RIFE models found"))
            main_window.model_combo.setEnabled(False)
            # Set empty model key on main_tab since current_model_key is a property in MainWindow
            if hasattr(main_window.main_tab, "current_model_key"):
                main_window.main_tab.current_model_key = ""
            LOGGER.warning("No RIFE models found.")

    @staticmethod
    def on_model_changed(main_window: Any, model_key: str) -> None:
        """Handle RIFE model selection change.

        Args:
            main_window: The MainWindow instance
            model_key: The selected model key
        """
        LOGGER.debug("Entering on_model_changed... model_key=%s", model_key)
        # Set the model key on main_tab since current_model_key is a property in MainWindow
        if hasattr(main_window.main_tab, "current_model_key"):
            main_window.main_tab.current_model_key = model_key
        main_window._update_rife_ui_elements()  # noqa: SLF001
        main_window._update_start_button_state()  # noqa: SLF001

    @staticmethod
    def validate_thread_spec(main_window: Any, text: str) -> None:
        """Validate the RIFE thread specification format.

        Args:
            main_window: The MainWindow instance
            text: The thread specification text to validate
        """
        LOGGER.debug("Entering validate_thread_spec... text=%s", text)

        # Simple regex check for format like "1:2:2"
        if not re.fullmatch(r"\d+:\d+:\d+", text):
            main_window.main_tab.rife_thread_spec_edit.setProperty("class", "ValidationError")
            main_window.main_tab.start_button.setEnabled(False)
            LOGGER.warning("Invalid RIFE thread specification format: %s", text)
        else:
            main_window.main_tab.rife_thread_spec_edit.setProperty("class", "")
            main_window._update_start_button_state()  # noqa: SLF001

    @staticmethod
    def toggle_sanchez_res_enabled(main_window: Any, state: Qt.CheckState) -> None:
        """Enable or disable the Sanchez resolution combo box based on checkbox state.

        Args:
            main_window: The MainWindow instance
            state: The checkbox state
        """
        # Use the combo box alias defined in __init__
        main_window.sanchez_res_km_combo.setEnabled(state == Qt.CheckState.Checked)

    def connect_model_combo(self, main_window: Any) -> None:
        """Connect the model combo box signal.

        Args:
            main_window: The MainWindow instance
        """
        main_window.model_combo.currentTextChanged.connect(
            lambda model_key: self.on_model_changed(main_window, model_key)
        )
