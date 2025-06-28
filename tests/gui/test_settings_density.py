"""Test UI density functionality in settings tab."""

from unittest.mock import patch

from PyQt6.QtWidgets import QApplication
import pytest

from goesvfi.gui_components.theme_manager import ThemeManager
from goesvfi.gui_tabs.settings_tab import SettingsTab
from goesvfi.utils import config


class TestUIDatensityFunctionality:
    """Test class for UI density functionality in settings tab."""

    @pytest.fixture(autouse=True)
    def setup(self, qtbot):
        """Set up test fixtures."""
        self.app = QApplication.instance()
        if not self.app:
            self.app = QApplication([])

        # Mock the dynamic theme manager to avoid circular imports
        with patch("goesvfi.gui_tabs.settings_tab.DynamicThemeManager"):
            self.settings_tab = SettingsTab()
        qtbot.addWidget(self.settings_tab)

        yield

        # Clean up
        if hasattr(self, "settings_tab"):
            self.settings_tab.deleteLater()

    def test_density_combo_box_exists_and_setup(self, qtbot) -> None:
        """Test that the density scale combo box exists and is properly set up."""
        # Check the combo box exists
        assert hasattr(self.settings_tab, "density_scale_combo")
        assert self.settings_tab.density_scale_combo is not None

        # Check that the combo box has the expected items
        expected_items = [
            "0 (Normal)",
            "-1 (Compact)",
            "-2 (Very Compact)",
            "1 (Spacious)",
            "2 (Very Spacious)",
        ]

        actual_items = [
            self.settings_tab.density_scale_combo.itemText(i)
            for i in range(self.settings_tab.density_scale_combo.count())
        ]

        assert actual_items == expected_items

        # Check tooltip exists and is meaningful
        tooltip = self.settings_tab.density_scale_combo.toolTip()
        assert len(tooltip) > 0
        assert any(word in tooltip.lower() for word in ["spacing", "sizing", "ui", "element"])

    def test_density_scale_config_integration(self, qtbot) -> None:
        """Test that density scale properly integrates with config system."""
        # Clear config cache to ensure fresh load
        config._load_config.cache_clear()

        # Get the current density scale from config
        current_density = config.get_theme_density_scale()

        # Check that the settings tab loads this value correctly
        self.settings_tab._load_current_settings()

        # Map density values to combo box indices
        density_mapping = {"0": 0, "-1": 1, "-2": 2, "1": 3, "2": 4}
        expected_index = density_mapping.get(current_density, 0)

        actual_index = self.settings_tab.density_scale_combo.currentIndex()
        assert actual_index == expected_index

        # Verify that changing the combo box updates the settings correctly
        for test_index, expected_value in enumerate(["0", "-1", "-2", "1", "2"]):
            self.settings_tab.density_scale_combo.setCurrentIndex(test_index)
            settings = self.settings_tab.get_current_settings()
            assert settings["theme"]["density_scale"] == expected_value

    def test_density_scale_signal_connections(self, qtbot) -> None:
        """Test that density scale combo box signal connections work."""
        # Track signal emissions
        signal_emitted = []

        def on_setting_changed() -> None:
            signal_emitted.append("settings_changed")

        self.settings_tab.settingsChanged.connect(on_setting_changed)

        # Change the density scale and verify signal is emitted
        original_index = self.settings_tab.density_scale_combo.currentIndex()
        new_index = (original_index + 1) % self.settings_tab.density_scale_combo.count()

        self.settings_tab.density_scale_combo.setCurrentIndex(new_index)

        # Process events to ensure signal is processed
        qtbot.wait(10)

        assert len(signal_emitted) > 0, "Settings changed signal should be emitted"

    def test_density_mapping_correctness(self, qtbot) -> None:
        """Test that the density mapping between UI and config is correct."""
        # Test each density option
        test_cases = [
            (0, "0"),  # Normal
            (1, "-1"),  # Compact
            (2, "-2"),  # Very Compact
            (3, "1"),  # Spacious
            (4, "2"),  # Very Spacious
        ]

        for combo_index, expected_config_value in test_cases:
            # Set combo box to test index
            self.settings_tab.density_scale_combo.setCurrentIndex(combo_index)

            # Get settings and verify the mapping
            settings = self.settings_tab.get_current_settings()
            actual_config_value = settings["theme"]["density_scale"]

            assert actual_config_value == expected_config_value, (
                f"Index {combo_index} should map to '{expected_config_value}', got '{actual_config_value}'"
            )

    def test_theme_manager_density_scale_property(self, qtbot) -> None:
        """Test that ThemeManager properly exposes density scale."""
        theme_manager = ThemeManager()

        # Check that theme manager has the density scale property
        assert hasattr(theme_manager, "_density_scale")

        # Verify it matches the config value
        config_density = config.get_theme_density_scale()
        assert theme_manager._density_scale == config_density

        # Verify that density scale is used in theme application
        import inspect

        apply_theme_source = inspect.getsource(theme_manager.apply_theme)
        assert "density_scale" in apply_theme_source, "ThemeManager.apply_theme should use density_scale"

    def test_density_scale_ui_layout(self, qtbot) -> None:
        """Test that density scale UI is properly positioned in the layout."""
        # The density scale combo should be in the appearance tab
        appearance_tab = None
        for i in range(self.settings_tab.settings_tabs.count()):
            if "Appearance" in self.settings_tab.settings_tabs.tabText(i):
                appearance_tab = self.settings_tab.settings_tabs.widget(i)
                break

        assert appearance_tab is not None, "Appearance tab should exist"

        # Check that the density combo box is a child of the appearance tab
        def find_widget_in_hierarchy(parent, target_widget) -> bool:
            """Recursively find a widget in the parent hierarchy."""
            if parent == target_widget:
                return True
            return any(child == target_widget for child in parent.findChildren(type(target_widget)))

        assert find_widget_in_hierarchy(appearance_tab, self.settings_tab.density_scale_combo), (
            "Density scale combo should be in the Appearance tab"
        )

    def test_reset_to_defaults_includes_density(self, qtbot) -> None:
        """Test that resetting to defaults properly handles density scale."""
        # Change density to non-default value
        self.settings_tab.density_scale_combo.setCurrentIndex(2)  # Very Compact

        # Reset to defaults
        self.settings_tab._reset_to_defaults()

        # Verify density is reset to default (index 0 = Normal)
        assert self.settings_tab.density_scale_combo.currentIndex() == 0

        # Verify the setting value is correct
        settings = self.settings_tab.get_current_settings()
        assert settings["theme"]["density_scale"] == "0"

    def test_density_persistence_on_reload(self, qtbot) -> None:
        """Test that density settings persist when reloading settings."""
        # Set a specific density value
        test_index = 3  # Spacious
        self.settings_tab.density_scale_combo.setCurrentIndex(test_index)

        # Get the current setting value
        settings_before = self.settings_tab.get_current_settings()
        density_before = settings_before["theme"]["density_scale"]

        # Simulate settings reload
        with patch.object(config, "get_theme_density_scale", return_value=density_before):
            self.settings_tab._load_current_settings()

        # Verify the UI reflects the reloaded value
        assert self.settings_tab.density_scale_combo.currentIndex() == test_index

        # Verify the setting value is preserved
        settings_after = self.settings_tab.get_current_settings()
        assert settings_after["theme"]["density_scale"] == density_before

    def test_density_edge_cases(self, qtbot) -> None:
        """Test edge cases for density functionality."""
        # Test with invalid density scale from config
        with patch.object(config, "get_theme_density_scale", return_value="invalid"):
            self.settings_tab._load_current_settings()
            # Should default to index 0 (Normal) for invalid values
            assert self.settings_tab.density_scale_combo.currentIndex() == 0

        # Test with empty density scale
        with patch.object(config, "get_theme_density_scale", return_value=""):
            self.settings_tab._load_current_settings()
            # Should default to index 0 (Normal) for empty values
            assert self.settings_tab.density_scale_combo.currentIndex() == 0

        # Test with None density scale
        with patch.object(config, "get_theme_density_scale", return_value=None):
            # Should handle None gracefully and default to 0
            try:
                self.settings_tab._load_current_settings()
                # If no exception, then it handled None gracefully
                assert True
            except Exception as e:
                pytest.fail(f"Should handle None density scale gracefully, but got: {e}")

    def test_density_validation_in_theme_manager(self, qtbot) -> None:
        """Test that ThemeManager validates density scale values properly."""
        theme_manager = ThemeManager()

        # Test the validation method if it exists
        if hasattr(theme_manager, "validate_theme_config"):
            is_valid, issues = theme_manager.validate_theme_config()

            # Should be valid with default config
            assert is_valid, f"Default theme config should be valid, issues: {issues}"

            # Test with invalid density scale
            original_density = theme_manager._density_scale
            try:
                theme_manager._density_scale = "99"  # Invalid value
                is_valid, issues = theme_manager.validate_theme_config()
                assert not is_valid, "Should detect invalid density scale"
                assert any("density" in issue.lower() for issue in issues), (
                    f"Should report density issue, got: {issues}"
                )
            finally:
                theme_manager._density_scale = original_density


def test_density_functionality_integration() -> None:
    """Integration test for overall density functionality."""
    # Test that all components work together

    # 1. Config provides density scale
    current_density = config.get_theme_density_scale()
    assert current_density in {"0", "-1", "-2", "1", "2"}, (
        f"Config should provide valid density scale, got: {current_density}"
    )

    # 2. ThemeManager uses density scale
    theme_manager = ThemeManager()
    assert theme_manager._density_scale == current_density, "ThemeManager should use same density as config"

    # 3. Theme application includes density (test without GUI)
    app = QApplication.instance()
    if not app:
        app = QApplication([])

    # Check that theme manager would use density in qt-material
    import inspect

    apply_theme_source = inspect.getsource(theme_manager.apply_theme)
    assert "extra" in apply_theme_source and "density_scale" in apply_theme_source, (
        "ThemeManager should pass density_scale to qt-material"
    )


if __name__ == "__main__":
    # Run the integration test directly
    test_density_functionality_integration()
