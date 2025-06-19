"""Model management functionality for the main GUI window."""

from pathlib import Path
from typing import Dict, Optional, Tuple

from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QComboBox, QMessageBox

from goesvfi.utils.gui_helpers import RifeCapabilityManager
from goesvfi.utils.log import get_logger

LOGGER = get_logger(__name__)


class ModelManager:
    """Manages RIFE model functionality for the main window."""

    def __init__(self, settings: QSettings):
        """Initialize the model manager.

        Args:
            settings: The QSettings instance to use for persistence
        """
        self.settings = settings
        self.capability_manager = RifeCapabilityManager()
        self.current_model_path: Optional[Path] = None
        self.available_models: Dict[str, Path] = {}
        self.model_capabilities: Dict[str, Dict[str, bool]] = {}

    def populate_models(self, model_combo: QComboBox, model_location: str) -> None:
        """Populate the model combo box with available RIFE models.

        Args:
            model_combo: The combo box to populate
            model_location: Path to the models directory
        """
        model_combo.clear()

        try:
            model_path = Path(model_location)
            if not model_path.exists():
                LOGGER.warning("Model location does not exist: %s", model_location)
                return

            # Find all model directories
            model_dirs = [d for d in model_path.iterdir() if d.is_dir()]

            if not model_dirs:
                LOGGER.warning("No model directories found in: %s", model_location)
                return

            # Clear and rebuild model collections
            self.available_models.clear()
            self.model_capabilities.clear()

            for model_dir in model_dirs:
                model_name = model_dir.name
                self.available_models[model_name] = model_dir

                # Check model capabilities
                # For now, just set default capabilities
                # TODO: Implement actual capability checking based on model
                capabilities = {"ensemble": False, "fastmode": False, "hd": False}
                self.model_capabilities[model_name] = capabilities

                # Add to combo box
                model_combo.addItem(model_name)

            LOGGER.info("Found %s RIFE models", len(self.available_models))

            # Select the first model by default
            if model_combo.count() > 0:
                model_combo.setCurrentIndex(0)

        except Exception as e:
            LOGGER.error("Error populating models: %s", e)
            QMessageBox.critical(
                None, "Model Loading Error", f"Failed to load RIFE models: {str(e)}"
            )

    def get_model_path(self, model_name: str) -> Optional[Path]:
        """Get the path for a model by name.

        Args:
            model_name: The name of the model

        Returns:
            Path to the model directory, or None if not found
        """
        return self.available_models.get(model_name)

    def get_model_capabilities(self, model_name: str) -> Dict[str, bool]:
        """Get the capabilities for a model by name.

        Args:
            model_name: The name of the model

        Returns:
            Dictionary of model capabilities
        """
        return self.model_capabilities.get(model_name, {})

    def supports_ensemble(self, model_name: str) -> bool:
        """Check if a model supports ensemble mode.

        Args:
            model_name: The name of the model

        Returns:
            True if the model supports ensemble mode
        """
        capabilities = self.get_model_capabilities(model_name)
        return capabilities.get("ensemble", False)

    def supports_fastmode(self, model_name: str) -> bool:
        """Check if a model supports fast mode.

        Args:
            model_name: The name of the model

        Returns:
            True if the model supports fast mode
        """
        capabilities = self.get_model_capabilities(model_name)
        return capabilities.get("fastmode", False)

    def supports_hd_mode(self, model_name: str) -> bool:
        """Check if a model supports HD mode.

        Args:
            model_name: The name of the model

        Returns:
            True if the model supports HD mode
        """
        capabilities = self.get_model_capabilities(model_name)
        return capabilities.get("hd", False)

    def get_model_info(self, model_name: str) -> Tuple[Optional[Path], Dict[str, bool]]:
        """Get both path and capabilities for a model.

        Args:
            model_name: The name of the model

        Returns:
            Tuple of (model path, capabilities dict)
        """
        path = self.get_model_path(model_name)
        capabilities = self.get_model_capabilities(model_name)
        return path, capabilities

    def save_selected_model(self, model_name: str) -> None:
        """Save the selected model to settings.

        Args:
            model_name: The name of the selected model
        """
        try:
            self.settings.setValue("selected_model", model_name)
            self.settings.sync()
            LOGGER.debug("Saved selected model: %s", model_name)
        except Exception as e:
            LOGGER.error("Error saving selected model: %s", e)

    def load_selected_model(self) -> Optional[str]:
        """Load the previously selected model from settings.

        Returns:
            The name of the previously selected model, or None
        """
        try:
            model_name = self.settings.value("selected_model", "", type=str)
            return model_name if model_name else None
        except Exception as e:
            LOGGER.error("Error loading selected model: %s", e)
            return None
