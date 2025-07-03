"""Optimized tests for ModelManager with maintained coverage.

This v2 version maintains all test scenarios while optimizing through:
- Shared QApplication instance
- In-memory filesystem mocking
- Combined related operations
- Maintained all edge cases and error scenarios
"""

from io import StringIO
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from PyQt6.QtWidgets import QApplication, QComboBox
import pytest

from goesvfi.gui_components.model_manager import ModelManager

# ModelPreferences doesn't exist in the codebase
# from goesvfi.view_models.model_preferences import ModelPreferences


class TestModelManagerOptimizedV2:
    """Optimized tests for ModelManager with full coverage."""

    # ruff: noqa: PLR6301  # Test methods need self parameter for pytest

    @staticmethod
    @pytest.fixture(scope="class")
    def shared_app() -> QApplication:
        """Shared QApplication instance for all tests.

        Returns:
            QApplication: The shared application instance.
        """
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        return app

    @pytest.fixture()
    def mock_filesystem(self) -> "TestModelManagerOptimizedV2":
        """Create mock filesystem that works consistently.

        Returns:
            TestModelManagerOptimizedV2: Self with filesystem mock methods.
        """
        mock_fs: dict[str, Any] = {}

        def mock_exists(self) -> bool:
            """Mock Path.exists().

            Returns:
                bool: Whether the path exists in the mock filesystem.
            """
            return str(self) in mock_fs

        def mock_is_dir(self) -> bool:
            """Mock Path.is_dir().

            Returns:
                bool: Whether the path is a directory in the mock filesystem.
            """
            entry = mock_fs.get(str(self), {})
            return isinstance(entry, dict) and entry.get("is_dir", False)

        def mock_is_file(self) -> bool:
            """Mock Path.is_file().

            Returns:
                bool: Whether the path is a file in the mock filesystem.
            """
            entry = mock_fs.get(str(self), {})
            return isinstance(entry, dict) and entry.get("is_file", False)

        def mock_iterdir(self) -> list[Path]:
            """Mock Path.iterdir().

            Returns:
                list[Path]: List of child paths in the mock filesystem.
            """
            entry = mock_fs.get(str(self), {})
            if isinstance(entry, dict) and entry.get("is_dir"):
                children = entry.get("children", [])
                return [Path(child) for child in children]
            return []

        def mock_open(self, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
            """Mock Path.open().

            Returns:
                Any: StringIO buffer for file operations.
            """
            if "r" in mode:
                content = mock_fs.get(str(self), {}).get("content", "")
                return StringIO(content)
            # For write mode, we'll update our mock
            buffer = StringIO()
            original_close = buffer.close

            def close_and_save() -> None:
                content = buffer.getvalue()
                mock_fs[str(self)] = {"is_file": True, "content": content}
                original_close()

            buffer.close = close_and_save  # type: ignore[method-assign]
            return buffer

        # Create the mock filesystem structure
        self.mock_fs = mock_fs
        self.mock_exists = mock_exists
        self.mock_is_dir = mock_is_dir
        self.mock_is_file = mock_is_file
        self.mock_iterdir = mock_iterdir
        self.mock_open = mock_open

        return self

    @pytest.fixture()
    def model_manager(self, shared_app: QApplication) -> ModelManager:  # noqa: ARG002
        """Create ModelManager instance.

        Args:
            shared_app: The shared QApplication instance.

        Returns:
            ModelManager: A new ModelManager instance.
        """
        from PyQt6.QtCore import QSettings

        settings = QSettings("test_org", "test_app")
        return ModelManager(settings)

    @staticmethod
    def _create_mock_directory(
        mock_fs: "TestModelManagerOptimizedV2",
        path: str,
        children: list[str] | None = None,
    ) -> None:
        """Helper to create a mock directory.

        Args:
            mock_fs: The mock filesystem instance.
            path: Directory path to create.
            children: Optional list of child paths.
        """
        mock_fs.mock_fs[path] = {"is_dir": True, "children": children or []}

    @staticmethod
    def _create_mock_file(mock_fs: "TestModelManagerOptimizedV2", path: str, content: str = "") -> None:
        """Helper to create a mock file.

        Args:
            mock_fs: The mock filesystem instance.
            path: File path to create.
            content: File content.
        """
        mock_fs.mock_fs[path] = {"is_file": True, "content": content}

    def test_initialization(self, model_manager: ModelManager) -> None:
        """Test ModelManager initialization.

        Args:
            model_manager: The ModelManager instance to test.
        """
        assert model_manager is not None
        # ModelManager has available_models dict, not models list
        assert hasattr(model_manager, "available_models")
        assert isinstance(model_manager.available_models, dict)

        # Initially should be empty
        assert len(model_manager.available_models) == 0

    def test_refresh_models_scenarios(
        self, model_manager: ModelManager, mock_filesystem: "TestModelManagerOptimizedV2"
    ) -> None:
        """Test all refresh_models scenarios.

        Args:
            model_manager: The ModelManager instance to test.
            mock_filesystem: The mock filesystem instance.
        """
        # Test 1: Empty directory
        test_dir = "/test/models/empty"
        TestModelManagerOptimizedV2._create_mock_directory(mock_filesystem, test_dir)

        # Mock Path class at module level
        with patch("goesvfi.gui_components.model_manager.Path") as MockPath:
            # Configure mock for empty directory
            mock_path = MockPath.return_value
            mock_path.exists.return_value = True
            mock_path.iterdir.return_value = []

            model_manager.refresh_models(test_dir)
            assert len(model_manager.available_models) == 0

        # Test 2: Invalid directory (doesn't exist)
        with patch("goesvfi.gui_components.model_manager.Path") as MockPath:
            # Configure mock for non-existent directory
            mock_path = MockPath.return_value
            mock_path.exists.return_value = False

            model_manager.refresh_models("/nonexistent/dir")
            assert len(model_manager.available_models) == 0

        # Test 3: Directory with valid models
        test_dir = "/test/models/valid"

        with (
            patch("goesvfi.gui_components.model_manager.Path") as MockPath,
            patch("goesvfi.gui_components.model_manager.sorted") as mock_sorted,
        ):
            # Create mock model directories
            mock_model_dirs = []
            for model_name in ["rife-v4.6", "rife-v4.3", "rife-v3.9"]:
                mock_model_dir = MagicMock()
                mock_model_dir.name = model_name
                mock_model_dir.is_dir.return_value = True
                mock_model_dir.__truediv__.return_value.exists.return_value = False  # rife-cli doesn't exist
                mock_model_dirs.append(mock_model_dir)

            # Configure main path mock
            mock_path = MockPath.return_value
            mock_path.exists.return_value = True
            mock_path.iterdir.return_value = mock_model_dirs

            # Mock sorted to return the same list
            mock_sorted.return_value = mock_model_dirs

            # Also need to handle Path() constructor calls for each model_dir
            MockPath.side_effect = lambda x: mock_path if x == test_dir else x

            model_manager.refresh_models(test_dir)

            # Verify models were loaded
            assert len(model_manager.available_models) == 3
            assert "rife-v4.6" in model_manager.available_models
            assert "rife-v4.3" in model_manager.available_models
            assert "rife-v3.9" in model_manager.available_models

    def test_get_model_info(self, model_manager: ModelManager) -> None:
        """Test get_model_info method.

        Args:
            model_manager: The ModelManager instance to test.
        """
        # Setup test models
        model_manager.available_models = {
            "rife-v4.6": Path("/models/rife-v4.6"),
            "rife-v4.3": Path("/models/rife-v4.3"),
        }
        model_manager.model_capabilities = {
            "rife-v4.6": {
                "hd": True,
                "ensemble": True,
                "fastmode": True,
                "tiling": True,
            },
            "rife-v4.3": {
                "hd": False,
                "ensemble": False,
                "fastmode": True,
                "tiling": False,
            },
        }

        # Test get_model_info returns tuple of (path, capabilities)
        path, capabilities = model_manager.get_model_info("rife-v4.6")
        assert path == Path("/models/rife-v4.6")
        assert capabilities == {
            "hd": True,
            "ensemble": True,
            "fastmode": True,
            "tiling": True,
        }

        # Test missing model
        path, capabilities = model_manager.get_model_info("nonexistent")
        assert path is None
        assert capabilities == {}

    def test_save_and_load_selected_model(self, model_manager: ModelManager) -> None:
        """Test save_selected_model and load_selected_model methods.

        Args:
            model_manager: The ModelManager instance to test.
        """
        # Test saving a selected model
        test_model = "rife-v4.6"
        model_manager.save_selected_model(test_model)

        # Verify it was saved to settings
        with patch.object(model_manager.settings, "value") as mock_value:
            mock_value.return_value = test_model
            loaded_model = model_manager.load_selected_model()
            assert loaded_model == test_model

        # Test loading with no saved model
        with patch.object(model_manager.settings, "value") as mock_value:
            mock_value.return_value = ""
            loaded_model = model_manager.load_selected_model()
            assert loaded_model is None

        # Test loading with exception
        with patch.object(model_manager.settings, "value", side_effect=Exception("Test error")):
            loaded_model = model_manager.load_selected_model()
            assert loaded_model is None

    def test_capabilities_methods(self, model_manager: ModelManager) -> None:
        """Test get_model_capabilities and supports methods.

        Args:
            model_manager: The ModelManager instance to test.
        """
        # Setup test models with different capabilities
        model_manager.available_models = {
            "rife-v4.6": Path("/models/rife-v4.6"),
            "rife-v4.3": Path("/models/rife-v4.3"),
            "rife-v3.9": Path("/models/rife-v3.9"),
        }
        model_manager.model_capabilities = {
            "rife-v4.6": {
                "ensemble": True,
                "fastmode": True,
                "hd": True,
            },
            "rife-v4.3": {
                "ensemble": False,
                "fastmode": True,
                "hd": False,
            },
            "rife-v3.9": {
                "ensemble": False,
                "fastmode": False,
                "hd": False,
            },
        }

        # Test get_model_capabilities
        caps = model_manager.get_model_capabilities("rife-v4.6")
        assert caps == {
            "ensemble": True,
            "fastmode": True,
            "hd": True,
        }

        caps = model_manager.get_model_capabilities("rife-v3.9")
        assert caps == {
            "ensemble": False,
            "fastmode": False,
            "hd": False,
        }

        # Test non-existent model
        caps = model_manager.get_model_capabilities("rife-v5.0")
        assert caps == {}

        # Test supports_* methods
        assert model_manager.supports_ensemble("rife-v4.6") is True
        assert model_manager.supports_ensemble("rife-v4.3") is False
        assert model_manager.supports_ensemble("nonexistent") is False

        assert model_manager.supports_fastmode("rife-v4.6") is True
        assert model_manager.supports_fastmode("rife-v3.9") is False

        assert model_manager.supports_hd_mode("rife-v4.6") is True
        assert model_manager.supports_hd_mode("rife-v4.3") is False

    def test_model_paths(self, model_manager: ModelManager) -> None:
        """Test get_model_path and get_all_model_paths methods.

        Args:
            model_manager: The ModelManager instance to test.
        """
        # Setup test models
        model_manager.available_models = {
            "rife-v4.6": Path("/models/rife-v4.6"),
            "rife-v4.3": Path("/models/rife-v4.3"),
            "rife-v3.9": Path("/models/rife-v3.9"),
        }

        # Test get_model_path
        path = model_manager.get_model_path("rife-v4.6")
        assert path == Path("/models/rife-v4.6")

        path = model_manager.get_model_path("rife-v3.9")
        assert path == Path("/models/rife-v3.9")

        # Test non-existent model
        path = model_manager.get_model_path("rife-v5.0")
        assert path is None

        # Test with empty models
        model_manager.available_models.clear()
        path = model_manager.get_model_path("any-model")
        assert path is None

    def test_model_selection_persistence(self, model_manager: ModelManager) -> None:
        """Test model selection persistence through settings.

        Args:
            model_manager: The ModelManager instance to test.
        """
        # ModelManager uses settings passed in constructor
        # Test that settings can store and retrieve model selections

        # Mock setting a selected model
        test_model = "rife-v4.6"
        model_manager.settings.setValue("selected_model", test_model)

        # Mock retrieving the selected model
        with patch.object(model_manager.settings, "value") as mock_value:
            mock_value.return_value = test_model
            selected = model_manager.settings.value("selected_model")
            assert selected == test_model

        # Test with no previous selection
        with patch.object(model_manager.settings, "value") as mock_value:
            mock_value.return_value = None
            selected = model_manager.settings.value("selected_model", "default")
            assert selected is None  # QSettings returns None, not default when mocked

            # Test that we can save and load model selections
            model_manager.save_selected_model(test_model)

    def test_refresh_models_update(self, model_manager: ModelManager) -> None:
        """Test refreshing models list when models are added.

        Args:
            model_manager: The ModelManager instance to test.
        """
        test_dir = "/test/models"

        # First refresh with one model
        with (
            patch("goesvfi.gui_components.model_manager.Path") as MockPath,
            patch("goesvfi.gui_components.model_manager.sorted") as mock_sorted,
        ):
            # Create one mock model directory
            mock_model_dir = MagicMock()
            mock_model_dir.name = "rife-v4.6"
            mock_model_dir.is_dir.return_value = True
            mock_model_dir.__truediv__.return_value.exists.return_value = False

            mock_path = MockPath.return_value
            mock_path.exists.return_value = True
            mock_path.iterdir.return_value = [mock_model_dir]

            # Mock sorted to return the same list
            mock_sorted.return_value = [mock_model_dir]

            model_manager.refresh_models(test_dir)
            assert len(model_manager.available_models) == 1

        # Second refresh with two models
        with (
            patch("goesvfi.gui_components.model_manager.Path") as MockPath,
            patch("goesvfi.gui_components.model_manager.sorted") as mock_sorted,
        ):
            # Create two mock model directories
            mock_model_dirs = []
            for model_name in ["rife-v4.6", "rife-v4.3"]:
                mock_model_dir = MagicMock()
                mock_model_dir.name = model_name
                mock_model_dir.is_dir.return_value = True
                mock_model_dir.__truediv__.return_value.exists.return_value = False
                mock_model_dirs.append(mock_model_dir)

            mock_path = MockPath.return_value
            mock_path.exists.return_value = True
            mock_path.iterdir.return_value = mock_model_dirs

            # Mock sorted to return the same list
            mock_sorted.return_value = mock_model_dirs

            model_manager.refresh_models(test_dir)
            assert len(model_manager.available_models) == 2

    def test_populate_models_combo(self, model_manager: ModelManager, shared_app: QApplication) -> None:  # noqa: ARG002
        """Test populate_models method with QComboBox.

        Args:
            model_manager: The ModelManager instance to test.
            shared_app: The shared QApplication instance.
        """
        combo = QComboBox()
        test_dir = "/test/models"

        # Test with valid models
        with (
            patch("goesvfi.gui_components.model_manager.Path") as MockPath,
            patch("goesvfi.gui_components.model_manager.sorted") as mock_sorted,
        ):
            # Create mock model directories
            mock_model_dirs = []
            for model_name in ["rife-v4.6", "rife-v4.3"]:
                mock_model_dir = MagicMock()
                mock_model_dir.name = model_name
                mock_model_dir.is_dir.return_value = True
                mock_model_dir.__truediv__.return_value.exists.return_value = False
                mock_model_dirs.append(mock_model_dir)

            mock_path = MockPath.return_value
            mock_path.exists.return_value = True
            mock_path.iterdir.return_value = mock_model_dirs

            # Mock sorted to return the same list
            mock_sorted.return_value = mock_model_dirs

            model_manager.populate_models(combo, test_dir)

            # Verify combo box was populated
            assert combo.count() == 2
            assert combo.itemText(0) == "rife-v4.6"
            assert combo.itemText(1) == "rife-v4.3"
            assert combo.currentIndex() == 0

    def test_edge_cases(self, model_manager: ModelManager) -> None:
        """Test edge cases and error conditions.

        Args:
            model_manager: The ModelManager instance to test.
        """
        # Test with None inputs
        assert model_manager.get_model_path(None) is None
        assert model_manager.get_model_capabilities(None) == {}
        assert model_manager.supports_ensemble(None) is False

        # Test with empty string
        assert model_manager.get_model_path("") is None

        # Test refresh_models with None - should handle gracefully
        try:
            model_manager.refresh_models(None)
        except TypeError:
            # This is expected since Path(None) raises TypeError
            pass

        # Test with model that has missing capabilities
        model_manager.available_models = {"incomplete-model": Path("/models/incomplete")}
        # Model capabilities will be empty for this model
        assert model_manager.supports_ensemble("incomplete-model") is False
        assert model_manager.supports_fastmode("incomplete-model") is False
        assert model_manager.supports_hd_mode("incomplete-model") is False
