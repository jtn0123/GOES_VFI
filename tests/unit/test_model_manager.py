"""Unit tests for the ModelManager component."""

from pathlib import Path
import tempfile
from typing import ClassVar
import unittest
from unittest.mock import MagicMock, patch

from PyQt6.QtCore import QCoreApplication, QSettings
from PyQt6.QtWidgets import QApplication, QComboBox

from goesvfi.gui_components.model_manager import ModelManager


class TestModelManager(unittest.TestCase):
    """Test cases for ModelManager."""

    app: ClassVar[QCoreApplication | None] = None

    @classmethod
    def setUpClass(cls) -> None:
        """Set up QApplication for all tests."""
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QCoreApplication.instance()

    def setUp(self) -> None:
        """Set up test fixtures."""
        # Create temporary settings file
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".ini")
        self.temp_file.close()

        # Create QSettings with test file
        self.settings = QSettings(self.temp_file.name, QSettings.Format.IniFormat)

        # Create ModelManager instance
        self.model_manager = ModelManager(self.settings)

        # Create temporary model directory
        self.temp_dir = tempfile.TemporaryDirectory()
        self.model_dir = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        """Clean up test fixtures."""
        # Clean up temporary file and directory
        Path(self.temp_file.name).unlink(missing_ok=True)
        self.temp_dir.cleanup()

    def test_initialization(self) -> None:
        """Test ModelManager initialization."""
        assert self.model_manager.settings == self.settings
        assert self.model_manager.current_model_path is None
        assert len(self.model_manager.available_models) == 0
        assert len(self.model_manager.model_capabilities) == 0

    def test_populate_models_valid_directory(self) -> None:
        """Test populating models with valid directory containing models."""
        # Create mock model directories
        model1_dir = self.model_dir / "rife-v4.6"
        model2_dir = self.model_dir / "rife-v4.7"
        model1_dir.mkdir()
        model2_dir.mkdir()

        # Create combo box
        combo_box = QComboBox()

        # Populate models
        self.model_manager.populate_models(combo_box, str(self.model_dir))

        # Verify combo box was populated
        assert combo_box.count() == 2

        # Get all model names (order might vary)
        model_names = [combo_box.itemText(i) for i in range(combo_box.count())]
        assert "rife-v4.6" in model_names
        assert "rife-v4.7" in model_names

        # Verify internal state
        assert len(self.model_manager.available_models) == 2
        assert "rife-v4.6" in self.model_manager.available_models
        assert "rife-v4.7" in self.model_manager.available_models

    def test_populate_models_empty_directory(self) -> None:
        """Test populating models with empty directory."""
        combo_box = QComboBox()

        # Populate with empty directory
        self.model_manager.populate_models(combo_box, str(self.model_dir))

        # Verify combo box is empty
        assert combo_box.count() == 0
        assert len(self.model_manager.available_models) == 0

    def test_populate_models_invalid_directory(self) -> None:
        """Test populating models with non-existent directory."""
        combo_box = QComboBox()
        non_existent = str(self.model_dir / "non_existent")

        # Should not crash
        self.model_manager.populate_models(combo_box, non_existent)

        # Verify combo box is empty
        assert combo_box.count() == 0

    def test_get_model_path(self) -> None:
        """Test getting model path by name."""
        # Set up some models
        model_path = self.model_dir / "rife-v4.6"
        self.model_manager.available_models["rife-v4.6"] = model_path

        # Test getting existing model
        retrieved_path = self.model_manager.get_model_path("rife-v4.6")
        assert retrieved_path == model_path

        # Test getting non-existent model
        retrieved_path = self.model_manager.get_model_path("non-existent")
        assert retrieved_path is None

    def test_get_model_capabilities(self) -> None:
        """Test getting model capabilities."""
        # Set up capabilities
        capabilities = {"ensemble": True, "fastmode": False, "hd": True}
        self.model_manager.model_capabilities["rife-v4.6"] = capabilities

        # Test getting capabilities
        retrieved = self.model_manager.get_model_capabilities("rife-v4.6")
        assert retrieved == capabilities

        # Test non-existent model
        retrieved = self.model_manager.get_model_capabilities("non-existent")
        assert retrieved == {}

    def test_supports_methods(self) -> None:
        """Test the various supports_* methods."""
        # Set up capabilities
        self.model_manager.model_capabilities["model1"] = {
            "ensemble": True,
            "fastmode": False,
            "hd": True,
        }
        self.model_manager.model_capabilities["model2"] = {
            "ensemble": False,
            "fastmode": True,
            "hd": False,
        }

        # Test model1
        assert self.model_manager.supports_ensemble("model1")
        assert not self.model_manager.supports_fastmode("model1")
        assert self.model_manager.supports_hd_mode("model1")

        # Test model2
        assert not self.model_manager.supports_ensemble("model2")
        assert self.model_manager.supports_fastmode("model2")
        assert not self.model_manager.supports_hd_mode("model2")

        # Test non-existent model
        assert not self.model_manager.supports_ensemble("non-existent")

    def test_save_and_load_selected_model(self) -> None:
        """Test saving and loading selected model."""
        model_name = "rife-v4.7"

        # Save model
        self.model_manager.save_selected_model(model_name)

        # Load model
        loaded = self.model_manager.load_selected_model()
        assert loaded == model_name

        # Verify it's in settings
        saved_value = self.settings.value("selected_model", "", type=str)
        assert saved_value == model_name

    def test_load_selected_model_not_exists(self) -> None:
        """Test loading when no model is saved."""
        loaded = self.model_manager.load_selected_model()
        assert loaded is None

    def test_get_model_info(self) -> None:
        """Test getting both path and capabilities for a model."""
        # Set up model
        model_path = self.model_dir / "rife-v4.6"
        capabilities = {"ensemble": True, "fastmode": False, "hd": True}
        self.model_manager.available_models["rife-v4.6"] = model_path
        self.model_manager.model_capabilities["rife-v4.6"] = capabilities

        # Get info
        path, caps = self.model_manager.get_model_info("rife-v4.6")
        assert path == model_path
        assert caps == capabilities

    @patch("goesvfi.gui_components.model_manager.QMessageBox")
    def test_populate_models_with_error(self, mock_messagebox) -> None:
        """Test error handling during model population."""
        combo_box = QComboBox()

        # Create a path that will cause an error when iterating
        with patch.object(Path, "iterdir", side_effect=PermissionError("Access denied")):
            self.model_manager.populate_models(combo_box, str(self.model_dir))

        # Verify error dialog was shown
        mock_messagebox.critical.assert_called_once()

        # Combo box should still be empty
        assert combo_box.count() == 0

    @patch("goesvfi.gui_components.model_manager.RifeCapabilityDetector")
    def test_refresh_models_detects_capabilities(self, mock_detector) -> None:
        """refresh_models should populate capability flags from detector."""

        model1 = self.model_dir / "model1"
        model2 = self.model_dir / "model2"
        model1.mkdir()
        model2.mkdir()
        (model1 / "rife-cli").touch()
        (model2 / "rife-cli").touch()

        det1 = MagicMock()
        det1.supports_uhd.return_value = True
        det1.supports_tta_spatial.return_value = False
        det1.supports_tta_temporal.return_value = True
        det1.supports_thread_spec.return_value = False
        det1.supports_tiling.return_value = True

        det2 = MagicMock()
        det2.supports_uhd.return_value = False
        det2.supports_tta_spatial.return_value = False
        det2.supports_tta_temporal.return_value = False
        det2.supports_thread_spec.return_value = True
        det2.supports_tiling.return_value = False

        mock_detector.side_effect = [det1, det2]

        self.model_manager.refresh_models(str(self.model_dir))

        caps1 = self.model_manager.get_model_capabilities("model1")
        caps2 = self.model_manager.get_model_capabilities("model2")

        assert caps1 == {"hd": True, "ensemble": True, "fastmode": False, "tiling": True}
        assert caps2 == {"hd": False, "ensemble": False, "fastmode": True, "tiling": False}

    def test_refresh_models_missing_executable(self) -> None:
        """Models without an executable should have empty capabilities."""

        model_dir = self.model_dir / "modelX"
        model_dir.mkdir()

        self.model_manager.refresh_models(str(self.model_dir))

        assert self.model_manager.get_model_capabilities("modelX") == {}


if __name__ == "__main__":
    unittest.main()
