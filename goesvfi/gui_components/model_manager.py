"""Model management functionality for the main GUI window."""

from pathlib import Path
from typing import cast

from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QComboBox, QMessageBox, QWidget

from goesvfi.utils.gui_helpers import RifeCapabilityDetector, RifeCapabilityManager
from goesvfi.utils.log import get_logger

LOGGER = get_logger(__name__)


class ModelManager:
    """Manages RIFE model functionality for the main window."""

    def __init__(self, settings: QSettings) -> None:
        """Initialize the model manager.

        Args:
            settings: The QSettings instance to use for persistence
        """
        self.settings = settings
        self.capability_manager = RifeCapabilityManager()
        self.current_model_path: Path | None = None
        self.available_models: dict[str, Path] = {}
        self.model_capabilities: dict[str, dict[str, bool]] = {}

    def refresh_models(self, model_location: str) -> None:
        """Refresh available models and detect their capabilities."""
        self.available_models.clear()
        self.model_capabilities.clear()

        model_path = Path(model_location)
        if not model_path.exists():
            LOGGER.warning("Model location does not exist: %s", model_location)
            return

        for model_dir in sorted([d for d in model_path.iterdir() if d.is_dir()]):
            model_name = model_dir.name
            self.available_models[model_name] = model_dir

            exe_path = model_dir / "rife-cli"
            if exe_path.suffix == "" and exe_path.with_suffix(".exe").exists():
                exe_path = exe_path.with_suffix(".exe")

            capabilities: dict[str, bool] = {}
            if exe_path.exists():
                try:
                    detector = RifeCapabilityDetector(exe_path)
                    capabilities = {
                        "hd": detector.supports_uhd(),
                        "ensemble": detector.supports_tta_spatial() or detector.supports_tta_temporal(),
                        "fastmode": detector.supports_thread_spec(),
                        "tiling": detector.supports_tiling(),
                    }
                except Exception:  # pylint: disable=broad-except
                    LOGGER.exception(
                        "Failed to analyze model %s capabilities",
                        model_name,
                    )
            else:
                LOGGER.warning("RIFE executable not found in model directory: %s", model_dir)

            self.model_capabilities[model_name] = capabilities

    def populate_models(self, model_combo: QComboBox, model_location: str) -> None:
        """Populate the model combo box with available RIFE models.

        Args:
            model_combo: The combo box to populate
            model_location: Path to the models directory
        """
        model_combo.clear()

        try:
            self.refresh_models(model_location)
            for model_name in self.available_models:
                model_combo.addItem(model_name)

            LOGGER.info("Found %s RIFE models", len(self.available_models))

            if model_combo.count() > 0:
                model_combo.setCurrentIndex(0)

        except Exception as e:  # pylint: disable=broad-except
            LOGGER.exception("Error populating models")
            parent_widget = cast("QWidget", model_combo.parent()) if model_combo.parent() else model_combo
            QMessageBox.critical(
                parent_widget,
                "Model Loading Error",
                f"Failed to load RIFE models: {e!s}",
            )

    def get_model_path(self, model_name: str) -> Path | None:
        """Get the path for a model by name.

        Args:
            model_name: The name of the model

        Returns:
            Path to the model directory, or None if not found
        """
        return self.available_models.get(model_name)

    def get_model_capabilities(self, model_name: str) -> dict[str, bool]:
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

    def get_model_info(self, model_name: str) -> tuple[Path | None, dict[str, bool]]:
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
        except Exception:
            LOGGER.exception("Error saving selected model")

    def load_selected_model(self) -> str | None:
        """Load the previously selected model from settings.

        Returns:
            The name of the previously selected model, or None
        """
        try:
            model_name = self.settings.value("selected_model", "", type=str)
            return cast("str | None", model_name or None)
        except Exception:
            LOGGER.exception("Error loading selected model")
            return None
