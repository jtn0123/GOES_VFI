"""Unit tests for the ModelManager component."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication, QComboBox

from goesvfi.gui_components.model_manager import ModelManager


class TestModelManager(unittest.TestCase):
    """Test cases for ModelManager."""

    @classmethod
    def setUpClass(cls):
        """Set up QApplication for all tests."""
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QApplication.instance()

    def setUp(self):
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

    def tearDown(self):
        """Clean up test fixtures."""
        # Clean up temporary file and directory
        Path(self.temp_file.name).unlink(missing_ok=True)
        self.temp_dir.cleanup()

    def test_initialization(self):
        """Test ModelManager initialization."""
        self.assertEqual(self.model_manager.settings, self.settings)
        self.assertIsNone(self.model_manager.current_model_path)
        self.assertEqual(len(self.model_manager.available_models), 0)
        self.assertEqual(len(self.model_manager.model_capabilities), 0)

    def test_populate_models_valid_directory(self):
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
        self.assertEqual(combo_box.count(), 2)

        # Get all model names (order might vary)
        model_names = [combo_box.itemText(i) for i in range(combo_box.count())]
        self.assertIn("rife-v4.6", model_names)
        self.assertIn("rife-v4.7", model_names)

        # Verify internal state
        self.assertEqual(len(self.model_manager.available_models), 2)
        self.assertIn("rife-v4.6", self.model_manager.available_models)
        self.assertIn("rife-v4.7", self.model_manager.available_models)

    def test_populate_models_empty_directory(self):
        """Test populating models with empty directory."""
        combo_box = QComboBox()

        # Populate with empty directory
        self.model_manager.populate_models(combo_box, str(self.model_dir))

        # Verify combo box is empty
        self.assertEqual(combo_box.count(), 0)
        self.assertEqual(len(self.model_manager.available_models), 0)

    def test_populate_models_invalid_directory(self):
        """Test populating models with non-existent directory."""
        combo_box = QComboBox()
        non_existent = str(self.model_dir / "non_existent")

        # Should not crash
        self.model_manager.populate_models(combo_box, non_existent)

        # Verify combo box is empty
        self.assertEqual(combo_box.count(), 0)

    def test_get_model_path(self):
        """Test getting model path by name."""
        # Set up some models
        model_path = self.model_dir / "rife-v4.6"
        self.model_manager.available_models["rife-v4.6"] = model_path

        # Test getting existing model
        retrieved_path = self.model_manager.get_model_path("rife-v4.6")
        self.assertEqual(retrieved_path, model_path)

        # Test getting non-existent model
        retrieved_path = self.model_manager.get_model_path("non-existent")
        self.assertIsNone(retrieved_path)

    def test_get_model_capabilities(self):
        """Test getting model capabilities."""
        # Set up capabilities
        capabilities = {"ensemble": True, "fastmode": False, "hd": True}
        self.model_manager.model_capabilities["rife-v4.6"] = capabilities

        # Test getting capabilities
        retrieved = self.model_manager.get_model_capabilities("rife-v4.6")
        self.assertEqual(retrieved, capabilities)

        # Test non-existent model
        retrieved = self.model_manager.get_model_capabilities("non-existent")
        self.assertEqual(retrieved, {})

    def test_supports_methods(self):
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
        self.assertTrue(self.model_manager.supports_ensemble("model1"))
        self.assertFalse(self.model_manager.supports_fastmode("model1"))
        self.assertTrue(self.model_manager.supports_hd_mode("model1"))

        # Test model2
        self.assertFalse(self.model_manager.supports_ensemble("model2"))
        self.assertTrue(self.model_manager.supports_fastmode("model2"))
        self.assertFalse(self.model_manager.supports_hd_mode("model2"))

        # Test non-existent model
        self.assertFalse(self.model_manager.supports_ensemble("non-existent"))

    def test_save_and_load_selected_model(self):
        """Test saving and loading selected model."""
        model_name = "rife-v4.7"

        # Save model
        self.model_manager.save_selected_model(model_name)

        # Load model
        loaded = self.model_manager.load_selected_model()
        self.assertEqual(loaded, model_name)

        # Verify it's in settings
        saved_value = self.settings.value("selected_model", "", type=str)
        self.assertEqual(saved_value, model_name)

    def test_load_selected_model_not_exists(self):
        """Test loading when no model is saved."""
        loaded = self.model_manager.load_selected_model()
        self.assertIsNone(loaded)

    def test_get_model_info(self):
        """Test getting both path and capabilities for a model."""
        # Set up model
        model_path = self.model_dir / "rife-v4.6"
        capabilities = {"ensemble": True, "fastmode": False, "hd": True}
        self.model_manager.available_models["rife-v4.6"] = model_path
        self.model_manager.model_capabilities["rife-v4.6"] = capabilities

        # Get info
        path, caps = self.model_manager.get_model_info("rife-v4.6")
        self.assertEqual(path, model_path)
        self.assertEqual(caps, capabilities)

    @patch("goesvfi.gui_components.model_manager.QMessageBox")
    def test_populate_models_with_error(self, mock_messagebox):
        """Test error handling during model population."""
        combo_box = QComboBox()

        # Create a path that will cause an error when iterating
        with patch.object(Path, "iterdir", side_effect=PermissionError("Access denied")):
            self.model_manager.populate_models(combo_box, str(self.model_dir))

        # Verify error dialog was shown
        mock_messagebox.critical.assert_called_once()

        # Combo box should still be empty
        self.assertEqual(combo_box.count(), 0)


if __name__ == "__main__":
    unittest.main()
