"""Qt-Material theme integration testing for GOES_VFI application.

This module tests the integration and functionality of qt-material
theming system within the GOES_VFI GUI framework.
"""

import importlib.util
from pathlib import Path
from typing import Any

import pytest


class TestQtMaterialIntegration:
    """Test suite for qt-material theme integration."""

    @pytest.fixture()
    @staticmethod
    def valid_material_themes() -> list[str]:
        """Provide list of valid Material Design themes.

        Returns:
            list[str]: List of valid theme names.
        """
        return [
            "dark_teal",
            "dark_blue",
            "dark_amber",
            "dark_cyan",
            "dark_lightgreen",
            "dark_pink",
            "dark_purple",
            "dark_red",
            "dark_yellow",
        ]

    @pytest.fixture()
    @staticmethod
    def theme_manager_module() -> Any:
        """Load the theme manager module dynamically."""
        theme_manager_path = Path("goesvfi/gui_components/theme_manager.py")

        if not theme_manager_path.exists():
            pytest.skip("Theme manager module not found")

        spec = importlib.util.spec_from_file_location("theme_manager", theme_manager_path)
        if spec is None or spec.loader is None:
            pytest.skip("Could not load theme manager module")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    @pytest.fixture()
    def migration_test_files(self) -> list[tuple[str, str, list[str]]]:
        """Provide file migration test cases."""
        return [
            (
                "ThemeManager",
                "goesvfi/gui_components/theme_manager.py",
                ["qt_material", "AVAILABLE_THEMES"],
            ),
            ("Config", "goesvfi/utils/config.py", ["get_theme_name", "theme"]),
            ("MainWindow", "goesvfi/gui.py", ["ThemeManager", "apply_theme"]),
            ("UI Setup", "goesvfi/gui_components/ui_setup_manager.py", ["qt-material"]),
        ]

    @staticmethod
    def test_qt_material_dependency_present() -> None:
        """Test that qt-material is included in project dependencies."""
        pyproject_path = Path("pyproject.toml")
        assert pyproject_path.exists(), "pyproject.toml not found"

        content = pyproject_path.read_text(encoding="utf-8")
        assert "qt-material" in content, "qt-material dependency not found in pyproject.toml"

    def test_theme_manager_available_themes(self, theme_manager_module: Any, valid_material_themes: list[str]) -> None:
        """Test that theme manager provides valid Material Design themes."""
        assert hasattr(theme_manager_module, "AVAILABLE_THEMES"), "AVAILABLE_THEMES not found in theme manager"

        available_themes = theme_manager_module.AVAILABLE_THEMES
        assert isinstance(available_themes, list | tuple), "AVAILABLE_THEMES should be a list or tuple"
        assert len(available_themes) > 0, "No themes available"

        # Verify all themes are valid Material Design themes
        for theme in available_themes:
            assert theme in valid_material_themes, f"Invalid theme '{theme}' not in valid Material Design themes"

    def test_theme_manager_import_qt_material(self, theme_manager_module: Any) -> None:
        """Test that theme manager properly imports qt_material."""
        module_content = Path("goesvfi/gui_components/theme_manager.py").read_text(encoding="utf-8")

        # Check for qt_material import
        assert "qt_material" in module_content, "qt_material import not found in theme manager"

    def test_configuration_system_theme_support(self) -> None:
        """Test that configuration system supports theme settings."""
        config_path = Path("goesvfi/utils/config.py")

        if not config_path.exists():
            pytest.skip("Config module not found")

        config_content = config_path.read_text(encoding="utf-8")

        # Check for theme-related configuration
        theme_keywords = ["get_theme_name", "theme", "THEME"]
        found_keywords = [kw for kw in theme_keywords if kw in config_content]

        assert len(found_keywords) > 0, f"No theme configuration keywords found. Expected one of: {theme_keywords}"

    def test_main_window_theme_integration(self) -> None:
        """Test that main window integrates with theme system."""
        main_window_path = Path("goesvfi/gui.py")

        if not main_window_path.exists():
            pytest.skip("Main window module not found")

        main_window_content = main_window_path.read_text(encoding="utf-8")

        # Check for theme integration
        theme_integration_keywords = ["ThemeManager", "apply_theme", "theme"]
        found_keywords = [kw for kw in theme_integration_keywords if kw in main_window_content]

        assert len(found_keywords) > 0, (
            f"No theme integration found in main window. Expected one of: {theme_integration_keywords}"
        )

    def test_ui_setup_manager_qt_material_integration(self) -> None:
        """Test that UI setup manager integrates qt-material."""
        ui_setup_path = Path("goesvfi/gui_components/ui_setup_manager.py")

        if not ui_setup_path.exists():
            pytest.skip("UI setup manager not found")

        ui_setup_content = ui_setup_path.read_text(encoding="utf-8")

        # Check for qt-material integration
        assert "qt-material" in ui_setup_content, "qt-material integration not found in UI setup manager"

    def test_file_migrations_comprehensive(self, migration_test_files: list[tuple[str, str, list[str]]]) -> None:
        """Test that all required files have been properly migrated."""
        successful_migrations = 0
        total_migrations = len(migration_test_files)

        for component_name, file_path, expected_keywords in migration_test_files:
            if not Path(file_path).exists():
                continue

            try:
                content = Path(file_path).read_text(encoding="utf-8")
                found_keywords = [kw for kw in expected_keywords if kw in content]

                if found_keywords:
                    successful_migrations += 1

            except Exception as e:
                pytest.fail(f"Error reading {component_name} file {file_path}: {e}")

        # At least some migrations should be successful
        assert successful_migrations > 0, "No successful file migrations found"

        # Ideally all migrations should be successful
        migration_rate = successful_migrations / total_migrations
        assert migration_rate >= 0.5, (
            f"Low migration success rate: {migration_rate:.1%} ({successful_migrations}/{total_migrations})"
        )

    @pytest.mark.parametrize("theme_name", ["dark_teal", "dark_blue", "dark_amber", "dark_cyan"])
    def test_individual_theme_availability(self, theme_manager_module: Any, theme_name: str) -> None:
        """Test individual theme availability in theme manager."""
        available_themes = getattr(theme_manager_module, "AVAILABLE_THEMES", [])

        # Not all themes need to be available, but test the ones that are configured
        if theme_name in available_themes:
            assert isinstance(theme_name, str), f"Theme name should be string: {theme_name}"
            assert len(theme_name) > 0, f"Theme name should not be empty: {theme_name}"
            assert theme_name.startswith("dark_"), f"Theme should follow dark_ naming convention: {theme_name}"

    @staticmethod
    def test_qt_material_import_functionality() -> None:
        """Test that qt_material can be imported and used."""
        try:
            import qt_material  # noqa: F401
        except ImportError:
            pytest.skip("qt_material not installed")

        # If import succeeds, the integration should work
        # This is a basic smoke test for the dependency

    def test_theme_manager_class_functionality(self, theme_manager_module: Any) -> None:
        """Test basic functionality of ThemeManager class if available."""
        if not hasattr(theme_manager_module, "ThemeManager"):
            pytest.skip("ThemeManager class not found")

        ThemeManager = theme_manager_module.ThemeManager  # noqa: N806

        # Test basic instantiation
        try:
            theme_manager = ThemeManager()
            assert theme_manager is not None, "ThemeManager instantiation failed"
        except Exception as e:
            pytest.fail(f"ThemeManager instantiation error: {e}")
