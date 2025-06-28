"""
Optimized unit tests for the ModelManager component.

Key optimizations:
1. Use in-memory file system mocks instead of real temp directories
2. Combine related test scenarios
3. Share QApplication instance across tests
4. Mock file operations directly
"""

from typing import ClassVar
import unittest
from unittest.mock import MagicMock, Mock, patch

from PyQt6.QtCore import QCoreApplication, QSettings
from PyQt6.QtWidgets import QApplication, QComboBox

from goesvfi.gui_components.model_manager import ModelManager


class TestModelManagerOptimized(unittest.TestCase):
    """Optimized test cases for ModelManager."""

    app: ClassVar[QCoreApplication | None] = None
    _mock_fs: ClassVar[dict] = {}  # Shared mock filesystem

    @classmethod
    def setUpClass(cls) -> None:
        """Set up QApplication once for all tests."""
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QCoreApplication.instance()

    def setUp(self) -> None:
        """Set up test fixtures with mocked file system."""
        # Mock settings in memory
        self.settings = MagicMock(spec=QSettings)
        self.settings._data = {}
        self.settings.value.side_effect = lambda key, default=None, type=None: self.settings._data.get(key, default)
        self.settings.setValue.side_effect = lambda key, value: self.settings._data.update({key: value})

        # Create ModelManager instance
        self.model_manager = ModelManager(self.settings)

        # Reset mock filesystem
        self._mock_fs.clear()

        # Mock Path operations
        self.path_patcher = patch("pathlib.Path")
        self.mock_path_class = self.path_patcher.start()

        # Override Path methods to use mock filesystem
        def mock_path_init(self, *args) -> None:
            if args:
                self._path = str(args[0])
            else:
                self._path = ""

        def mock_exists(self):
            return self._path in self._mock_fs

        def mock_is_dir(self):
            return self._mock_fs.get(self._path, {}).get("is_dir", False)

        def mock_iterdir(self):
            if self._path not in self._mock_fs:
                msg = f"Directory not found: {self._path}"
                raise FileNotFoundError(msg)

            if not self._mock_fs[self._path].get("is_dir", False):
                msg = f"Not a directory: {self._path}"
                raise NotADirectoryError(msg)

            children = self._mock_fs[self._path].get("children", [])
            for child_name in children:
                child_path = f"{self._path}/{child_name}"
                mock_child = Mock()
                mock_child._path = child_path
                mock_child.name = child_name
                mock_child.is_dir = lambda: self._mock_fs.get(child_path, {}).get("is_dir", False)
                mock_child.__truediv__ = lambda s, other: mock_path_instance(f"{s._path}/{other}")
                yield mock_child

        def mock_path_instance(path_str):
            instance = Mock()
            instance._path = str(path_str)
            instance.exists = lambda: mock_exists(instance)
            instance.is_dir = lambda: mock_is_dir(instance)
            instance.iterdir = lambda: mock_iterdir(instance)
            instance.name = path_str.split("/")[-1] if "/" in path_str else path_str
            instance.__str__ = lambda: instance._path
            instance.__truediv__ = lambda self, other: mock_path_instance(f"{self._path}/{other}")
            return instance

        self.mock_path_class.side_effect = mock_path_instance

    def tearDown(self) -> None:
        """Clean up test fixtures."""
        self.path_patcher.stop()

    def _create_mock_directory(self, path: str, children: list | None = None) -> None:
        """Helper to create a mock directory in our fake filesystem."""
        self._mock_fs[path] = {"is_dir": True, "children": children or []}
        # Also create child entries
        for child in children or []:
            child_path = f"{path}/{child}"
            if child.startswith("rife-"):  # Model directories
                self._mock_fs[child_path] = {"is_dir": True, "children": []}

    def test_initialization_and_populate_empty(self) -> None:
        """Test initialization and empty directory population together."""
        # Test initialization
        assert self.model_manager.settings == self.settings
        assert self.model_manager.current_model_path is None
        assert len(self.model_manager.available_models) == 0
        assert len(self.model_manager.model_capabilities) == 0

        # Test empty directory
        self._create_mock_directory("/models", [])
        combo_box = QComboBox()

        self.model_manager.populate_models(combo_box, "/models")

        assert combo_box.count() == 0
        assert len(self.model_manager.available_models) == 0

    def test_populate_and_get_models(self) -> None:
        """Test populating models and getting model info together."""
        # Create mock model directories
        self._create_mock_directory("/models", ["rife-v4.6", "rife-v4.7", "not-a-model"])

        combo_box = QComboBox()
        self.model_manager.populate_models(combo_box, "/models")

        # Verify combo box was populated (only directories starting with "rife-")
        assert combo_box.count() == 2
        model_names = [combo_box.itemText(i) for i in range(combo_box.count())]
        assert "rife-v4.6" in model_names
        assert "rife-v4.7" in model_names

        # Test getting model path
        model_path = self.model_manager.get_model_path("rife-v4.6")
        assert str(model_path) == "/models/rife-v4.6"

        # Test non-existent model
        assert self.model_manager.get_model_path("non-existent") is None

    def test_capabilities_and_supports_methods(self) -> None:
        """Test model capabilities and all supports_* methods together."""
        # Set up capabilities for multiple models at once
        capabilities = {
            "model1": {"ensemble": True, "fastmode": False, "hd": True},
            "model2": {"ensemble": False, "fastmode": True, "hd": False},
            "model3": {},  # Empty capabilities
        }

        for model, caps in capabilities.items():
            self.model_manager.model_capabilities[model] = caps

        # Test all models
        assert self.model_manager.supports_ensemble("model1") is True
        assert self.model_manager.supports_fastmode("model1") is False
        assert self.model_manager.supports_hd_mode("model1") is True

        assert self.model_manager.supports_ensemble("model2") is False
        assert self.model_manager.supports_fastmode("model2") is True
        assert self.model_manager.supports_hd_mode("model2") is False

        # Empty capabilities default to False
        assert self.model_manager.supports_ensemble("model3") is False
        assert self.model_manager.supports_fastmode("model3") is False
        assert self.model_manager.supports_hd_mode("model3") is False

        # Non-existent model
        assert self.model_manager.supports_ensemble("non-existent") is False

    def test_save_load_selected_model(self) -> None:
        """Test saving and loading selected model preferences."""
        model_name = "rife-v4.7"

        # Save and verify
        self.model_manager.save_selected_model(model_name)
        assert self.settings._data.get("selected_model") == model_name

        # Load and verify
        loaded = self.model_manager.load_selected_model()
        assert loaded == model_name

        # Test loading when nothing saved
        self.settings._data.clear()
        assert self.model_manager.load_selected_model() is None

    @patch("goesvfi.gui_components.model_manager.QMessageBox")
    def test_error_handling(self, mock_messagebox) -> None:
        """Test error handling during model population."""
        combo_box = QComboBox()

        # Directory that will raise permission error
        self._mock_fs["/restricted"] = {"is_dir": True, "children": []}

        # Make iterdir raise PermissionError
        with patch.object(self.mock_path_class.return_value, "iterdir", side_effect=PermissionError("Access denied")):
            self.model_manager.populate_models(combo_box, "/restricted")

        # Verify error dialog was shown
        mock_messagebox.critical.assert_called_once()
        assert combo_box.count() == 0

    @patch("goesvfi.gui_components.model_manager.RifeCapabilityDetector")
    def test_refresh_models_with_capabilities(self, mock_detector) -> None:
        """Test refreshing models and detecting capabilities efficiently."""
        # Create models with executables
        self._create_mock_directory("/models", ["model1", "model2"])
        self._mock_fs["/models/model1/rife-cli"] = {"is_dir": False}
        self._mock_fs["/models/model2/rife-cli"] = {"is_dir": False}

        # Mock capability detection for both models
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

        # Override exists for executables
        original_exists = self.mock_path_class.return_value.exists

        def mock_exists_with_exe(self):
            if self._path.endswith("/rife-cli"):
                return True
            return original_exists()

        with patch.object(self.mock_path_class.return_value, "exists", mock_exists_with_exe):
            self.model_manager.refresh_models("/models")

        # Verify capabilities were detected correctly
        caps1 = self.model_manager.get_model_capabilities("model1")
        caps2 = self.model_manager.get_model_capabilities("model2")

        assert caps1 == {"hd": True, "ensemble": True, "fastmode": False, "tiling": True}
        assert caps2 == {"hd": False, "ensemble": False, "fastmode": True, "tiling": False}

        # Test model without executable
        self._create_mock_directory("/models", ["model3"])
        self.model_manager.refresh_models("/models")
        assert self.model_manager.get_model_capabilities("model3") == {}


if __name__ == "__main__":
    unittest.main()
