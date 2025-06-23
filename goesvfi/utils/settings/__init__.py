"""
Settings management framework for reducing complexity in settings-heavy functions.

This module provides safe widget access and settings persistence utilities that help
reduce the complexity of functions with extensive Qt widget manipulation.
"""

from .base import SettingsSection, SettingsManager
from .widget_accessor import SafeWidgetAccessor, WidgetSafetyValidator
from .sections import MainTabSettings, FFmpegSettings, SanchezSettings

__all__ = [
    "SettingsSection",
    "SettingsManager", 
    "SafeWidgetAccessor",
    "WidgetSafetyValidator",
    "MainTabSettings",
    "FFmpegSettings", 
    "SanchezSettings",
]