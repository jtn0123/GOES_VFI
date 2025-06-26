"""
Unit tests for the FFmpeg Settings Tab component.

This file contains dedicated tests for the FFmpegSettingsTab class in isolation,
which helps prevent segmentation faults that occur when testing it through the MainWindow.
"""

from unittest.mock import patch

import pytest
from PyQt6.QtWidgets import QApplication

from goesvfi.gui_tabs.ffmpeg_settings_tab import FFmpegSettingsTab
from goesvfi.utils.config import FFMPEG_PROFILES


@pytest.fixture
def ffmpeg_tab(qtbot):
    """Create an FFmpeg Settings Tab instance for testing."""
    # Create the tab
    tab = FFmpegSettingsTab()

    # Add to qtbot to manage Qt events and cleanup
    qtbot.addWidget(tab)

    # Process events to ensure the widget is fully initialized
    QApplication.processEvents()

    # Return the tab
    yield tab

    # Teardown - explicitly process events before destruction
    QApplication.processEvents()


def test_initial_state(ffmpeg_tab):
    """Test the initial state of the FFmpeg settings tab."""
    # Test profile combo has expected items
    assert ffmpeg_tab.ffmpeg_profile_combo.count() > 0
    assert "Default" in [
        ffmpeg_tab.ffmpeg_profile_combo.itemText(i) for i in range(ffmpeg_tab.ffmpeg_profile_combo.count())
    ]
    assert "Custom" in [
        ffmpeg_tab.ffmpeg_profile_combo.itemText(i) for i in range(ffmpeg_tab.ffmpeg_profile_combo.count())
    ]

    # Test that the interpolation group exists and is checkable
    assert ffmpeg_tab.ffmpeg_settings_group.isCheckable()

    # Test that the unsharp mask group exists and is checkable
    assert ffmpeg_tab.ffmpeg_unsharp_group.isCheckable()

    # Test that quality controls are present
    assert hasattr(ffmpeg_tab, "ffmpeg_quality_combo")
    assert hasattr(ffmpeg_tab, "ffmpeg_crf_spinbox")

    # Check that the correct number of profiles is available
    assert ffmpeg_tab.ffmpeg_profile_combo.count() == len(FFMPEG_PROFILES) + 1  # +1 for "Custom"


def test_profile_selection(ffmpeg_tab):
    """Test changing profiles updates widget values correctly."""
    # Initial state check
    initial_profile = ffmpeg_tab.ffmpeg_profile_combo.currentText()

    # Force a selection to a specific profile (Default)
    with patch.object(ffmpeg_tab, "_verify_profile_match"):  # Prevent automatic verification
        ffmpeg_tab.ffmpeg_profile_combo.setCurrentText("Default")
        ffmpeg_tab._on_profile_selected("Default")

    QApplication.processEvents()

    # Check profile was applied
    assert ffmpeg_tab.ffmpeg_profile_combo.currentText() == "Default"

    # Check that values from the Default profile were applied
    default_profile = FFMPEG_PROFILES["Default"]
    assert ffmpeg_tab.ffmpeg_settings_group.isChecked() == default_profile["use_ffmpeg_interp"]
    assert ffmpeg_tab.ffmpeg_mi_mode_combo.currentText() == default_profile["mi_mode"]

    # Switch to a different profile
    with patch.object(ffmpeg_tab, "_verify_profile_match"):  # Prevent automatic verification
        ffmpeg_tab.ffmpeg_profile_combo.setCurrentText("Optimal")
        ffmpeg_tab._on_profile_selected("Optimal")

    QApplication.processEvents()

    # Check profile was applied
    assert ffmpeg_tab.ffmpeg_profile_combo.currentText() == "Optimal"

    # Check that values from the Optimal profile were applied
    optimal_profile = FFMPEG_PROFILES["Optimal"]
    assert ffmpeg_tab.ffmpeg_settings_group.isChecked() == optimal_profile["use_ffmpeg_interp"]
    assert ffmpeg_tab.ffmpeg_mi_mode_combo.currentText() == optimal_profile["mi_mode"]

    # Return to original profile
    with patch.object(ffmpeg_tab, "_verify_profile_match"):
        ffmpeg_tab.ffmpeg_profile_combo.setCurrentText(initial_profile)
        ffmpeg_tab._on_profile_selected(initial_profile)


def test_changing_setting_updates_profile(ffmpeg_tab):
    """Test changing a setting switches to Custom profile."""
    # First select a known profile
    with patch.object(ffmpeg_tab, "_verify_profile_match"):
        ffmpeg_tab.ffmpeg_profile_combo.setCurrentText("Default")
        ffmpeg_tab._on_profile_selected("Default")

    QApplication.processEvents()
    assert ffmpeg_tab.ffmpeg_profile_combo.currentText() == "Default"

    # Change a setting - this should switch to "Custom"
    original_state = ffmpeg_tab.ffmpeg_vsbmc_checkbox.isChecked()
    ffmpeg_tab.ffmpeg_vsbmc_checkbox.setChecked(not original_state)

    QApplication.processEvents()

    # Check profile changed to Custom
    assert ffmpeg_tab.ffmpeg_profile_combo.currentText() == "Custom"


def test_unsharp_controls_state(ffmpeg_tab):
    """Test unsharp mask controls enable/disable correctly when group is toggled."""
    # Get current state for reference
    original_state = ffmpeg_tab.ffmpeg_unsharp_group.isChecked()

    # Test disabling unsharp group
    ffmpeg_tab.ffmpeg_unsharp_group.setChecked(False)
    # Manually call the method since we're not using signals in this test
    ffmpeg_tab._update_unsharp_controls_state(False)
    QApplication.processEvents()

    # Check controls are disabled
    assert not ffmpeg_tab.ffmpeg_unsharp_lx_spinbox.isEnabled()
    assert not ffmpeg_tab.ffmpeg_unsharp_ly_spinbox.isEnabled()
    assert not ffmpeg_tab.ffmpeg_unsharp_la_spinbox.isEnabled()

    # Test enabling unsharp group
    ffmpeg_tab.ffmpeg_unsharp_group.setChecked(True)
    # Manually call the method since we're not using signals in this test
    ffmpeg_tab._update_unsharp_controls_state(True)
    QApplication.processEvents()

    # Check controls are enabled
    assert ffmpeg_tab.ffmpeg_unsharp_lx_spinbox.isEnabled()
    assert ffmpeg_tab.ffmpeg_unsharp_ly_spinbox.isEnabled()
    assert ffmpeg_tab.ffmpeg_unsharp_la_spinbox.isEnabled()

    # Return to original state
    ffmpeg_tab.ffmpeg_unsharp_group.setChecked(original_state)
    ffmpeg_tab._update_unsharp_controls_state(original_state)


def test_get_current_settings(ffmpeg_tab):
    """Test that get_current_settings returns the expected dictionary."""
    # Get current settings
    settings = ffmpeg_tab.get_current_settings()

    # Check that the dictionary has the expected keys
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

    for key in expected_keys:
        assert key in settings, f"Missing key '{key}' in settings"

    # Check that values match widget states
    assert settings["use_ffmpeg_interp"] == ffmpeg_tab.ffmpeg_settings_group.isChecked()
    assert settings["mi_mode"] == ffmpeg_tab.ffmpeg_mi_mode_combo.currentText()
    assert settings["vsbmc"] == ffmpeg_tab.ffmpeg_vsbmc_checkbox.isChecked()
    assert settings["apply_unsharp"] == ffmpeg_tab.ffmpeg_unsharp_group.isChecked()
    assert settings["unsharp_lx"] == ffmpeg_tab.ffmpeg_unsharp_lx_spinbox.value()


def test_check_settings_match_profile(ffmpeg_tab):
    """Test that _check_settings_match_profile correctly identifies matching profiles."""
    # Apply a known profile
    with patch.object(ffmpeg_tab, "_verify_profile_match"):
        ffmpeg_tab.ffmpeg_profile_combo.setCurrentText("Default")
        ffmpeg_tab._on_profile_selected("Default")

    QApplication.processEvents()

    # Check settings match the Default profile
    assert ffmpeg_tab._check_settings_match_profile(FFMPEG_PROFILES["Default"])

    # Change a setting
    original_vsbmc = ffmpeg_tab.ffmpeg_vsbmc_checkbox.isChecked()
    ffmpeg_tab.ffmpeg_vsbmc_checkbox.setChecked(not original_vsbmc)

    # Settings should no longer match Default profile
    assert not ffmpeg_tab._check_settings_match_profile(FFMPEG_PROFILES["Default"])
