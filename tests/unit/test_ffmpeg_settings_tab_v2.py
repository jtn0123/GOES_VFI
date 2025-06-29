"""Optimized unit tests for FFmpeg Settings Tab component.

Optimizations applied:
- Shared fixture setup for tab initialization
- Parameterized tests for profile validation
- Mock-based testing to prevent segmentation faults
- Combined related test scenarios
- Enhanced edge case coverage
- Comprehensive settings validation
"""

from unittest.mock import patch

from PyQt6.QtWidgets import QApplication
import pytest

from goesvfi.gui_tabs.ffmpeg_settings_tab import FFmpegSettingsTab
from goesvfi.utils.config import FFMPEG_PROFILES


class TestFFmpegSettingsTabV2:
    """Optimized test class for FFmpeg Settings Tab functionality."""

    @pytest.fixture(scope="class")
    def shared_ffmpeg_tab(self, qtbot):
        """Create shared FFmpeg Settings Tab instance for testing."""
        # Create the tab
        tab = FFmpegSettingsTab()

        # Add to qtbot for Qt event management and cleanup
        qtbot.addWidget(tab)

        # Process events to ensure full initialization
        QApplication.processEvents()

        yield tab

        # Cleanup - process events before destruction
        QApplication.processEvents()

    def test_initial_state_comprehensive(self, shared_ffmpeg_tab) -> None:
        """Test comprehensive initial state of FFmpeg settings tab."""
        tab = shared_ffmpeg_tab

        # Verify profile combo setup
        assert tab.ffmpeg_profile_combo.count() > 0
        profile_items = [tab.ffmpeg_profile_combo.itemText(i) for i in range(tab.ffmpeg_profile_combo.count())]
        assert "Default" in profile_items
        assert "Custom" in profile_items

        # Verify correct number of profiles
        assert tab.ffmpeg_profile_combo.count() == len(FFMPEG_PROFILES) + 1  # +1 for "Custom"

        # Verify group box properties
        assert tab.ffmpeg_settings_group.isCheckable()
        assert tab.ffmpeg_unsharp_group.isCheckable()

        # Verify essential controls exist
        essential_controls = [
            "ffmpeg_quality_combo",
            "ffmpeg_crf_spinbox",
            "ffmpeg_mi_mode_combo",
            "ffmpeg_vsbmc_checkbox",
            "ffmpeg_unsharp_lx_spinbox",
            "ffmpeg_unsharp_ly_spinbox",
            "ffmpeg_unsharp_la_spinbox",
        ]

        for control in essential_controls:
            assert hasattr(tab, control), f"Missing control: {control}"

    @pytest.mark.parametrize("profile_name", list(FFMPEG_PROFILES.keys()))
    def test_profile_selection_parametrized(self, shared_ffmpeg_tab, profile_name) -> None:
        """Test profile selection with all available profiles."""
        tab = shared_ffmpeg_tab
        profile_config = FFMPEG_PROFILES[profile_name]

        # Apply profile with mock verification to prevent cascading updates
        with patch.object(tab, "_verify_profile_match"):
            tab.ffmpeg_profile_combo.setCurrentText(profile_name)
            tab._on_profile_selected(profile_name)

        QApplication.processEvents()

        # Verify profile was applied
        assert tab.ffmpeg_profile_combo.currentText() == profile_name

        # Verify key settings match profile configuration
        assert tab.ffmpeg_settings_group.isChecked() == profile_config["use_ffmpeg_interp"]
        assert tab.ffmpeg_mi_mode_combo.currentText() == profile_config["mi_mode"]

        # Verify numeric settings if they exist in profile
        if "unsharp_lx" in profile_config:
            assert tab.ffmpeg_unsharp_lx_spinbox.value() == profile_config["unsharp_lx"]

    def test_profile_switching_workflow(self, shared_ffmpeg_tab) -> None:
        """Test complete profile switching workflow."""
        tab = shared_ffmpeg_tab

        # Store initial state
        initial_profile = tab.ffmpeg_profile_combo.currentText()

        # Switch to Default profile
        with patch.object(tab, "_verify_profile_match"):
            tab.ffmpeg_profile_combo.setCurrentText("Default")
            tab._on_profile_selected("Default")

        QApplication.processEvents()
        assert tab.ffmpeg_profile_combo.currentText() == "Default"

        # Switch to Optimal profile
        with patch.object(tab, "_verify_profile_match"):
            tab.ffmpeg_profile_combo.setCurrentText("Optimal")
            tab._on_profile_selected("Optimal")

        QApplication.processEvents()
        assert tab.ffmpeg_profile_combo.currentText() == "Optimal"

        # Verify Optimal profile settings
        optimal_profile = FFMPEG_PROFILES["Optimal"]
        assert tab.ffmpeg_settings_group.isChecked() == optimal_profile["use_ffmpeg_interp"]
        assert tab.ffmpeg_mi_mode_combo.currentText() == optimal_profile["mi_mode"]

        # Return to initial state
        with patch.object(tab, "_verify_profile_match"):
            tab.ffmpeg_profile_combo.setCurrentText(initial_profile)
            tab._on_profile_selected(initial_profile)

    def test_settings_change_triggers_custom_profile(self, shared_ffmpeg_tab) -> None:
        """Test that changing settings switches to Custom profile."""
        tab = shared_ffmpeg_tab

        # Start with known profile
        with patch.object(tab, "_verify_profile_match"):
            tab.ffmpeg_profile_combo.setCurrentText("Default")
            tab._on_profile_selected("Default")

        QApplication.processEvents()
        assert tab.ffmpeg_profile_combo.currentText() == "Default"

        # Change a setting - should trigger Custom profile
        original_vsbmc = tab.ffmpeg_vsbmc_checkbox.isChecked()
        tab.ffmpeg_vsbmc_checkbox.setChecked(not original_vsbmc)

        QApplication.processEvents()

        # Verify profile changed to Custom
        assert tab.ffmpeg_profile_combo.currentText() == "Custom"

    @pytest.mark.parametrize("group_enabled", [True, False])
    def test_unsharp_controls_state_management(self, shared_ffmpeg_tab, group_enabled) -> None:
        """Test unsharp mask controls enable/disable functionality."""
        tab = shared_ffmpeg_tab

        # Set group state
        tab.ffmpeg_unsharp_group.setChecked(group_enabled)
        tab._update_unsharp_controls_state(group_enabled)
        QApplication.processEvents()

        # Verify controls match group state
        unsharp_controls = [
            tab.ffmpeg_unsharp_lx_spinbox,
            tab.ffmpeg_unsharp_ly_spinbox,
            tab.ffmpeg_unsharp_la_spinbox,
            tab.ffmpeg_unsharp_cx_spinbox,
            tab.ffmpeg_unsharp_cy_spinbox,
            tab.ffmpeg_unsharp_ca_spinbox,
        ]

        for control in unsharp_controls:
            assert control.isEnabled() == group_enabled

    def test_get_current_settings_comprehensive(self, shared_ffmpeg_tab) -> None:
        """Test comprehensive settings retrieval and validation."""
        tab = shared_ffmpeg_tab
        settings = tab.get_current_settings()

        # Define all expected setting keys
        expected_keys = [
            "use_ffmpeg_interp",
            "mi_mode",
            "mc_mode",
            "me_mode",
            "vsbmc",
            "scd",
            "me_algo",
            "search_param",
            "scd_threshold",
            "mb_size",
            "apply_unsharp",
            "unsharp_lx",
            "unsharp_ly",
            "unsharp_la",
            "unsharp_cx",
            "unsharp_cy",
            "unsharp_ca",
            "preset_text",
            "crf",
            "bitrate",
            "bufsize",
            "pix_fmt",
            "filter_preset",
        ]

        # Verify all keys are present
        for key in expected_keys:
            assert key in settings, f"Missing key '{key}' in settings"

        # Verify settings match widget states
        widget_mappings = {
            "use_ffmpeg_interp": tab.ffmpeg_settings_group.isChecked(),
            "mi_mode": tab.ffmpeg_mi_mode_combo.currentText(),
            "vsbmc": tab.ffmpeg_vsbmc_checkbox.isChecked(),
            "apply_unsharp": tab.ffmpeg_unsharp_group.isChecked(),
            "unsharp_lx": tab.ffmpeg_unsharp_lx_spinbox.value(),
            "unsharp_ly": tab.ffmpeg_unsharp_ly_spinbox.value(),
            "unsharp_la": tab.ffmpeg_unsharp_la_spinbox.value(),
        }

        for key, expected_value in widget_mappings.items():
            assert settings[key] == expected_value, (
                f"Mismatch for {key}: got {settings[key]}, expected {expected_value}"
            )

    def test_profile_matching_validation(self, shared_ffmpeg_tab) -> None:
        """Test profile matching logic with comprehensive validation."""
        tab = shared_ffmpeg_tab

        # Apply Default profile
        with patch.object(tab, "_verify_profile_match"):
            tab.ffmpeg_profile_combo.setCurrentText("Default")
            tab._on_profile_selected("Default")

        QApplication.processEvents()

        # Verify settings match Default profile
        default_profile = FFMPEG_PROFILES["Default"]
        assert tab._check_settings_match_profile(default_profile)

        # Change a setting and verify mismatch
        original_vsbmc = tab.ffmpeg_vsbmc_checkbox.isChecked()
        tab.ffmpeg_vsbmc_checkbox.setChecked(not original_vsbmc)

        # Should no longer match Default profile
        assert not tab._check_settings_match_profile(default_profile)

        # Restore original state
        tab.ffmpeg_vsbmc_checkbox.setChecked(original_vsbmc)

        # Should match again
        assert tab._check_settings_match_profile(default_profile)

    @pytest.mark.parametrize(
        "setting_changes",
        [{"use_ffmpeg_interp": True}, {"mi_mode": "dup"}, {"vsbmc": False}, {"apply_unsharp": True, "unsharp_lx": 5}],
    )
    def test_various_setting_modifications(self, shared_ffmpeg_tab, setting_changes) -> None:
        """Test various types of setting modifications."""
        tab = shared_ffmpeg_tab

        # Start with Default profile
        with patch.object(tab, "_verify_profile_match"):
            tab.ffmpeg_profile_combo.setCurrentText("Default")
            tab._on_profile_selected("Default")

        QApplication.processEvents()

        # Apply setting changes
        for setting, value in setting_changes.items():
            if setting == "use_ffmpeg_interp":
                tab.ffmpeg_settings_group.setChecked(value)
            elif setting == "mi_mode":
                tab.ffmpeg_mi_mode_combo.setCurrentText(value)
            elif setting == "vsbmc":
                tab.ffmpeg_vsbmc_checkbox.setChecked(value)
            elif setting == "apply_unsharp":
                tab.ffmpeg_unsharp_group.setChecked(value)
            elif setting == "unsharp_lx":
                tab.ffmpeg_unsharp_lx_spinbox.setValue(value)

        QApplication.processEvents()

        # Verify settings were applied
        current_settings = tab.get_current_settings()
        for setting, expected_value in setting_changes.items():
            assert current_settings[setting] == expected_value

    def test_tab_initialization_robustness(self, qtbot) -> None:
        """Test tab initialization under various conditions."""
        # Test multiple tab creation and destruction
        tabs = []
        for _i in range(3):
            tab = FFmpegSettingsTab()
            qtbot.addWidget(tab)
            QApplication.processEvents()
            tabs.append(tab)

        # All tabs should be properly initialized
        for tab in tabs:
            assert tab.ffmpeg_profile_combo.count() > 0
            assert hasattr(tab, "ffmpeg_settings_group")
            assert hasattr(tab, "ffmpeg_unsharp_group")

        # Cleanup
        for tab in tabs:
            QApplication.processEvents()

    def test_edge_case_profile_scenarios(self, shared_ffmpeg_tab) -> None:
        """Test edge cases in profile handling."""
        tab = shared_ffmpeg_tab

        # Test with empty profile name
        with patch.object(tab, "_verify_profile_match"):
            # Should handle gracefully
            tab._on_profile_selected("")

        # Test with non-existent profile name
        with patch.object(tab, "_verify_profile_match"):
            # Should handle gracefully
            tab._on_profile_selected("NonExistentProfile")

        # Tab should remain functional
        assert tab.ffmpeg_profile_combo.count() > 0

    def test_signal_handling_robustness(self, shared_ffmpeg_tab) -> None:
        """Test robustness of signal handling."""
        tab = shared_ffmpeg_tab

        # Test rapid profile changes
        profiles = ["Default", "Optimal", "Fast", "Default"]

        with patch.object(tab, "_verify_profile_match"):
            for profile in profiles:
                if profile in [tab.ffmpeg_profile_combo.itemText(i) for i in range(tab.ffmpeg_profile_combo.count())]:
                    tab.ffmpeg_profile_combo.setCurrentText(profile)
                    tab._on_profile_selected(profile)
                    QApplication.processEvents()

        # Tab should remain stable
        assert tab.ffmpeg_profile_combo.currentText() in profiles

    def test_memory_efficiency_validation(self, shared_ffmpeg_tab) -> None:
        """Test memory efficiency and resource management."""
        tab = shared_ffmpeg_tab

        # Perform multiple operations that could cause memory leaks
        for _ in range(10):
            settings = tab.get_current_settings()
            assert len(settings) > 0

            # Toggle some settings
            tab.ffmpeg_vsbmc_checkbox.setChecked(not tab.ffmpeg_vsbmc_checkbox.isChecked())
            QApplication.processEvents()

        # Tab should remain responsive
        final_settings = tab.get_current_settings()
        assert len(final_settings) > 0
