"""Optimized tests for ModelManager with maintained coverage.

This v2 version maintains all test scenarios while optimizing through:
- Shared QApplication instance
- In-memory filesystem mocking
- Combined related operations
- Maintained all edge cases and error scenarios
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication

from goesvfi.view_models.model_manager import ModelManager
from goesvfi.view_models.model_preferences import ModelPreferences


class TestModelManagerOptimizedV2:
    """Optimized tests for ModelManager with full coverage."""

    @pytest.fixture(scope="class")
    def shared_app(self):
        """Shared QApplication instance for all tests."""
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        yield app

    @pytest.fixture
    def mock_filesystem(self):
        """Create mock filesystem that works consistently."""
        mock_fs = {}

        def mock_exists(path):
            """Mock Path.exists()"""
            return str(path) in mock_fs

        def mock_is_dir(path):
            """Mock Path.is_dir()"""
            entry = mock_fs.get(str(path), {})
            return isinstance(entry, dict) and entry.get('is_dir', False)

        def mock_is_file(path):
            """Mock Path.is_file()"""
            entry = mock_fs.get(str(path), {})
            return isinstance(entry, dict) and entry.get('is_file', False)

        def mock_iterdir(path):
            """Mock Path.iterdir()"""
            entry = mock_fs.get(str(path), {})
            if isinstance(entry, dict) and entry.get('is_dir'):
                children = entry.get('children', [])
                return [Path(child) for child in children]
            return []

        def mock_open(path, mode='r', *args, **kwargs):
            """Mock Path.open()"""
            if 'r' in mode:
                content = mock_fs.get(str(path), {}).get('content', '')
                from io import StringIO
                return StringIO(content)
            else:
                # For write mode, we'll update our mock
                from io import StringIO
                buffer = StringIO()
                original_close = buffer.close

                def close_and_save():
                    content = buffer.getvalue()
                    mock_fs[str(path)] = {'is_file': True, 'content': content}
                    original_close()

                buffer.close = close_and_save
                return buffer

        # Create the mock filesystem structure
        self._mock_fs = mock_fs
        self._mock_exists = mock_exists
        self._mock_is_dir = mock_is_dir
        self._mock_is_file = mock_is_file
        self._mock_iterdir = mock_iterdir
        self._mock_open = mock_open

        yield self

    @pytest.fixture
    def model_manager(self, shared_app):
        """Create ModelManager instance."""
        return ModelManager()

    def _create_mock_directory(self, mock_fs, path: str, children: list = None):
        """Helper to create a mock directory."""
        mock_fs._mock_fs[path] = {'is_dir': True, 'children': children or []}

    def _create_mock_file(self, mock_fs, path: str, content: str = ""):
        """Helper to create a mock file."""
        mock_fs._mock_fs[path] = {'is_file': True, 'content': content}

    def test_initialization(self, model_manager):
        """Test ModelManager initialization."""
        assert model_manager is not None
        assert hasattr(model_manager, 'models')
        assert hasattr(model_manager, 'model_preferences')
        assert isinstance(model_manager.models, list)
        assert isinstance(model_manager.model_preferences, ModelPreferences)

        # Initially should be empty
        assert len(model_manager.models) == 0

    def test_populate_models_scenarios(self, model_manager, mock_filesystem):
        """Test all populate_models scenarios."""
        with (
            patch('pathlib.Path.exists', side_effect=mock_filesystem._mock_exists),
            patch('pathlib.Path.is_dir', side_effect=mock_filesystem._mock_is_dir),
            patch('pathlib.Path.is_file', side_effect=mock_filesystem._mock_is_file),
            patch('pathlib.Path.iterdir', side_effect=mock_filesystem._mock_iterdir),
            patch('pathlib.Path.open', side_effect=mock_filesystem._mock_open),
        ):
            # Test 1: Empty directory
            test_dir = "/test/models/empty"
            self._create_mock_directory(mock_filesystem, test_dir)

            model_manager.populate_models(test_dir)
            assert len(model_manager.models) == 0

            # Test 2: Invalid directory (doesn't exist)
            model_manager.populate_models("/nonexistent/dir")
            assert len(model_manager.models) == 0

            # Test 3: Directory with valid models
            test_dir = "/test/models/valid"
            self._create_mock_directory(mock_filesystem, test_dir)

            # Create model directories
            model_dirs = []
            for i, model_name in enumerate(["rife-v4.6", "rife-v4.3", "rife-v3.9"]):
                model_path = f"{test_dir}/{model_name}"
                self._create_mock_directory(mock_filesystem, model_path)
                model_dirs.append(model_path)

                # Add model info file
                info_content = json.dumps({
                    "name": model_name,
                    "version": model_name.split("-v")[1],
                    "description": f"RIFE model {model_name}",
                    "supports_ensemble": i == 0,  # Only first model
                    "supports_fast_mode": i < 2,  # First two models
                })
                self._create_mock_file(
                    mock_filesystem,
                    f"{model_path}/model_info.json",
                    info_content
                )

            # Update parent directory children
            mock_filesystem._mock_fs[test_dir]['children'] = model_dirs

            # Populate models
            model_manager.populate_models(test_dir)

            # Verify models were loaded
            assert len(model_manager.models) == 3
            assert model_manager.models[0]["name"] == "rife-v4.6"
            assert model_manager.models[1]["name"] == "rife-v4.3"
            assert model_manager.models[2]["name"] == "rife-v3.9"

            # Test 4: Directory with invalid models (no model_info.json)
            test_dir_invalid = "/test/models/invalid"
            self._create_mock_directory(mock_filesystem, test_dir_invalid)

            invalid_model_path = f"{test_dir_invalid}/bad-model"
            self._create_mock_directory(mock_filesystem, invalid_model_path)
            mock_filesystem._mock_fs[test_dir_invalid]['children'] = [invalid_model_path]

            # Clear and repopulate
            model_manager.models.clear()
            model_manager.populate_models(test_dir_invalid)

            # Should have no models (invalid ones are skipped)
            assert len(model_manager.models) == 0

    def test_get_model_info(self, model_manager, mock_filesystem):
        """Test get_model_info method."""
        with (
            patch('pathlib.Path.exists', side_effect=mock_filesystem._mock_exists),
            patch('pathlib.Path.is_file', side_effect=mock_filesystem._mock_is_file),
            patch('pathlib.Path.open', side_effect=mock_filesystem._mock_open),
        ):
            # Test valid model info
            model_path = "/test/model/rife-v4.6"
            info_content = json.dumps({
                "name": "rife-v4.6",
                "version": "4.6",
                "description": "Latest RIFE model",
            })
            self._create_mock_file(
                mock_filesystem,
                f"{model_path}/model_info.json",
                info_content
            )

            info = model_manager.get_model_info(model_path)
            assert info is not None
            assert info["name"] == "rife-v4.6"
            assert info["version"] == "4.6"

            # Test missing model info
            info = model_manager.get_model_info("/nonexistent/model")
            assert info is None

            # Test invalid JSON
            bad_model_path = "/test/model/bad"
            self._create_mock_file(
                mock_filesystem,
                f"{bad_model_path}/model_info.json",
                "invalid json content"
            )

            info = model_manager.get_model_info(bad_model_path)
            assert info is None

    def test_get_model_by_name(self, model_manager):
        """Test get_model_by_name method."""
        # Add test models
        model_manager.models = [
            {"name": "rife-v4.6", "path": "/models/rife-v4.6"},
            {"name": "rife-v4.3", "path": "/models/rife-v4.3"},
            {"name": "rife-v3.9", "path": "/models/rife-v3.9"},
        ]

        # Test finding existing models
        model = model_manager.get_model_by_name("rife-v4.6")
        assert model is not None
        assert model["name"] == "rife-v4.6"

        model = model_manager.get_model_by_name("rife-v3.9")
        assert model is not None
        assert model["name"] == "rife-v3.9"

        # Test non-existent model
        model = model_manager.get_model_by_name("rife-v5.0")
        assert model is None

        # Test with empty models list
        model_manager.models.clear()
        model = model_manager.get_model_by_name("rife-v4.6")
        assert model is None

    def test_capabilities_methods(self, model_manager):
        """Test get_model_capabilities and supports methods."""
        # Setup test models with different capabilities
        model_manager.models = [
            {
                "name": "rife-v4.6",
                "supports_ensemble": True,
                "supports_fast_mode": True,
                "supports_hd": True,
            },
            {
                "name": "rife-v4.3",
                "supports_ensemble": False,
                "supports_fast_mode": True,
                "supports_hd": False,
            },
            {
                "name": "rife-v3.9",
                "supports_ensemble": False,
                "supports_fast_mode": False,
                "supports_hd": False,
            },
        ]

        # Test get_model_capabilities
        caps = model_manager.get_model_capabilities("rife-v4.6")
        assert caps == {
            "supports_ensemble": True,
            "supports_fast_mode": True,
            "supports_hd": True,
        }

        caps = model_manager.get_model_capabilities("rife-v3.9")
        assert caps == {
            "supports_ensemble": False,
            "supports_fast_mode": False,
            "supports_hd": False,
        }

        # Test non-existent model
        caps = model_manager.get_model_capabilities("rife-v5.0")
        assert caps == {}

        # Test supports_* methods
        assert model_manager.supports_ensemble("rife-v4.6") is True
        assert model_manager.supports_ensemble("rife-v4.3") is False
        assert model_manager.supports_ensemble("nonexistent") is False

        assert model_manager.supports_fast_mode("rife-v4.6") is True
        assert model_manager.supports_fast_mode("rife-v3.9") is False

        assert model_manager.supports_hd("rife-v4.6") is True
        assert model_manager.supports_hd("rife-v4.3") is False

    def test_model_paths(self, model_manager):
        """Test get_model_path and get_all_model_paths methods."""
        # Setup test models
        model_manager.models = [
            {"name": "rife-v4.6", "path": "/models/rife-v4.6"},
            {"name": "rife-v4.3", "path": "/models/rife-v4.3"},
            {"name": "rife-v3.9", "path": "/models/rife-v3.9"},
        ]

        # Test get_model_path
        path = model_manager.get_model_path("rife-v4.6")
        assert path == "/models/rife-v4.6"

        path = model_manager.get_model_path("rife-v3.9")
        assert path == "/models/rife-v3.9"

        # Test non-existent model
        path = model_manager.get_model_path("rife-v5.0")
        assert path is None

        # Test get_all_model_paths
        all_paths = model_manager.get_all_model_paths()
        assert len(all_paths) == 3
        assert "/models/rife-v4.6" in all_paths
        assert "/models/rife-v4.3" in all_paths
        assert "/models/rife-v3.9" in all_paths

        # Test with empty models
        model_manager.models.clear()
        all_paths = model_manager.get_all_model_paths()
        assert all_paths == []

    def test_model_preferences_integration(self, model_manager):
        """Test integration with ModelPreferences."""
        # Mock QSettings
        with patch('PyQt6.QtCore.QSettings') as mock_settings_class:
            mock_settings = MagicMock()
            mock_settings_class.return_value = mock_settings

            # Setup models
            model_manager.models = [
                {"name": "rife-v4.6", "path": "/models/rife-v4.6"},
                {"name": "rife-v4.3", "path": "/models/rife-v4.3"},
            ]

            # Test saving selected model
            mock_settings.value.return_value = None  # No previous selection

            # Select a model
            model_manager.model_preferences.set_selected_model("rife-v4.6")

            # Verify it was saved
            mock_settings.setValue.assert_called_with("selected_model", "rife-v4.6")

            # Test loading selected model
            mock_settings.value.return_value = "rife-v4.3"
            selected = model_manager.model_preferences.get_selected_model()
            assert selected == "rife-v4.3"

            # Test get_selected_model_info
            info = model_manager.get_selected_model_info()
            assert info is not None
            assert info["name"] == "rife-v4.3"

    def test_refresh_models(self, model_manager, mock_filesystem):
        """Test refreshing models list."""
        with (
            patch('pathlib.Path.exists', side_effect=mock_filesystem._mock_exists),
            patch('pathlib.Path.is_dir', side_effect=mock_filesystem._mock_is_dir),
            patch('pathlib.Path.iterdir', side_effect=mock_filesystem._mock_iterdir),
        ):
            # Initial population
            test_dir = "/test/models"
            self._create_mock_directory(mock_filesystem, test_dir)

            # Start with one model
            model1_path = f"{test_dir}/rife-v4.6"
            self._create_mock_directory(mock_filesystem, model1_path)
            mock_filesystem._mock_fs[test_dir]['children'] = [model1_path]

            model_manager.populate_models(test_dir)
            assert len(model_manager.models) == 1

            # Add another model and refresh
            model2_path = f"{test_dir}/rife-v4.3"
            self._create_mock_directory(mock_filesystem, model2_path)
            mock_filesystem._mock_fs[test_dir]['children'] = [model1_path, model2_path]

            # Refresh by calling populate_models again
            model_manager.populate_models(test_dir)
            assert len(model_manager.models) == 2

    def test_edge_cases(self, model_manager):
        """Test edge cases and error conditions."""
        # Test with None inputs
        assert model_manager.get_model_by_name(None) is None
        assert model_manager.get_model_path(None) is None
        assert model_manager.get_model_capabilities(None) == {}
        assert model_manager.supports_ensemble(None) is False

        # Test with empty string
        assert model_manager.get_model_by_name("") is None
        assert model_manager.get_model_path("") is None

        # Test populate_models with None
        model_manager.populate_models(None)
        # Should not crash

        # Test with model that has missing capabilities
        model_manager.models = [{"name": "incomplete-model", "path": "/models/incomplete"}]
        assert model_manager.supports_ensemble("incomplete-model") is False
        assert model_manager.supports_fast_mode("incomplete-model") is False
        assert model_manager.supports_hd("incomplete-model") is False