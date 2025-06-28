"""
Settings management framework for reducing complexity in settings-heavy functions.

This module provides safe widget access and settings persistence utilities that help
reduce the complexity of functions with extensive Qt widget manipulation.
"""

from .base import SettingsManager, SettingsSection
from .sections import FFmpegSettings, MainTabSettings, SanchezSettings
from .widget_accessor import SafeWidgetAccessor, WidgetSafetyValidator

__all__ = [
    "FFmpegSettings",
    "MainTabSettings",
    "SafeWidgetAccessor",
    "SanchezSettings",
    "SettingsManager",
    "SettingsSection",
    "WidgetSafetyValidator",
]
