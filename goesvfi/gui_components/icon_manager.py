"""Icon management system for replacing emoji icons with proper resources."""

from pathlib import Path
from typing import cast

from PyQt6.QtCore import QSize
from PyQt6.QtGui import QFont, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication, QStyle

from goesvfi.utils import log

LOGGER = log.get_logger(__name__)

# Icon mappings from emoji to icon names
ICON_MAPPINGS = {
    "🎬": "video",
    "🎥": "video-camera",
    "📚": "book",
    "📁": "folder",
    "📅": "calendar",
    "🛰️": "satellite",
    "⚙️": "settings",
    "🔍": "search",
    "📃": "document",
    "🗂️": "folder-open",
    "🗺️": "map",
    "🤖": "robot",
    "📊": "chart",
    "💾": "save",
    "➕": "plus",  # noqa: RUF001
    "🔢": "numbers",
    "⏱️": "timer",
    "✨": "sparkles",
    "💡": "lightbulb",
    "🖼️": "image",
}

# Standard icon sizes
ICON_SMALL = QSize(16, 16)
ICON_MEDIUM = QSize(24, 24)
ICON_LARGE = QSize(32, 32)
ICON_XLARGE = QSize(48, 48)


class IconManager:
    """Manages application icons with fallback to emojis."""

    def __init__(self, icon_path: Path | None = None) -> None:
        """Initialize the icon manager.

        Args:
            icon_path: Path to icon resources directory
        """
        self.icon_path = icon_path
        self.icon_cache: dict[str, QIcon] = {}
        self.fallback_to_emoji = True  # For gradual migration

        # Try to find icon directory
        if not self.icon_path:
            self._find_icon_directory()

        LOGGER.info("IconManager initialized with path: %s", self.icon_path)

    def _find_icon_directory(self) -> None:
        """Try to find the icon resources directory."""
        # Common locations to check
        possible_paths = [
            Path(__file__).parent.parent / "resources" / "icons",
            Path(__file__).parent.parent.parent / "resources" / "icons",
            Path(__file__).parent.parent / "icons",
            Path.cwd() / "resources" / "icons",
            Path.cwd() / "icons",
        ]

        for path in possible_paths:
            if path.exists() and path.is_dir():
                self.icon_path = path
                LOGGER.debug("Found icon directory: %s", path)
                return

        LOGGER.warning("No icon directory found, will use fallbacks")

    def get_icon(self, icon_name: str, size: QSize = ICON_MEDIUM) -> QIcon:
        """Get an icon by name with caching.

        Args:
            icon_name: Name of the icon or emoji
            size: Desired icon size

        Returns:
            QIcon instance
        """
        # Check if it's an emoji that needs mapping
        if icon_name in ICON_MAPPINGS:
            mapped_name = ICON_MAPPINGS[icon_name]
            LOGGER.debug("Mapped emoji %s to icon %s", icon_name, mapped_name)
            icon_name = mapped_name

        # Check cache
        cache_key = f"{icon_name}_{size.width()}x{size.height()}"
        if cache_key in self.icon_cache:
            return self.icon_cache[cache_key]

        # Try to load icon
        icon = self._load_icon(icon_name, size)

        # Cache and return
        self.icon_cache[cache_key] = icon
        return icon

    def _load_icon(self, icon_name: str, size: QSize) -> QIcon:
        """Load an icon from various sources.

        Args:
            icon_name: Name of the icon
            size: Desired size

        Returns:
            QIcon instance
        """
        # Try file-based icon first
        if self.icon_path:
            icon = self._load_file_icon(icon_name, size)
            if not icon.isNull():
                return icon

        # Try theme icon
        icon = self._load_theme_icon(icon_name)
        if not icon.isNull():
            return icon

        # Try standard pixmap
        icon = self._load_standard_icon(icon_name)
        if not icon.isNull():
            return icon

        # Fallback to emoji if enabled
        if self.fallback_to_emoji:
            # Reverse lookup emoji
            for emoji, mapped in ICON_MAPPINGS.items():
                if mapped == icon_name:
                    return self._create_emoji_icon(emoji, size)

        # Final fallback - create text icon
        return self._create_text_icon(icon_name, size)

    def _load_file_icon(self, icon_name: str, size: QSize) -> QIcon:  # noqa: ARG002
        """Load icon from file.

        Args:
            icon_name: Icon name
            size: Desired size

        Returns:
            QIcon or null icon
        """
        if not self.icon_path:
            return QIcon()

        # Try different formats
        formats = [".svg", ".png", ".ico"]

        for fmt in formats:
            icon_file = self.icon_path / f"{icon_name}{fmt}"
            if icon_file.exists():
                LOGGER.debug("Loading icon from file: %s", icon_file)
                return QIcon(str(icon_file))

        return QIcon()

    def _load_theme_icon(self, icon_name: str) -> QIcon:  # noqa: PLR6301
        """Load icon from system theme.

        Args:
            icon_name: Icon name

        Returns:
            QIcon or null icon
        """
        # Map our names to common theme icon names
        theme_mappings = {
            "video": "video-x-generic",
            "video-camera": "camera-video",
            "book": "accessories-dictionary",
            "folder": "folder",
            "calendar": "x-office-calendar",
            "satellite": "network-wireless",
            "settings": "preferences-system",
            "search": "edit-find",
            "document": "text-x-generic",
            "folder-open": "folder-open",
            "map": "applications-internet",
            "robot": "applications-science",
            "chart": "office-chart-bar",
            "save": "document-save",
            "plus": "list-add",
            "numbers": "accessories-calculator",
            "timer": "chronometer",
            "sparkles": "weather-clear",
            "lightbulb": "help-hint",
            "image": "image-x-generic",
        }

        theme_name = theme_mappings.get(icon_name, icon_name)
        icon = QIcon.fromTheme(theme_name)

        if not icon.isNull():
            LOGGER.debug("Loaded theme icon: %s", theme_name)

        return icon

    def _load_standard_icon(self, icon_name: str) -> QIcon:  # noqa: PLR6301
        """Load standard application icon.

        Args:
            icon_name: Icon name

        Returns:
            QIcon or null icon
        """
        app = QApplication.instance()
        if not app:
            return QIcon()

        # QApplication.instance() returns QCoreApplication, cast to QApplication
        qapp = cast("QApplication", app) if isinstance(app, QApplication) else None
        if not qapp:
            return QIcon()

        style = qapp.style()
        if not style:
            return QIcon()

        # Map to standard pixmaps
        standard_mappings = {
            "folder": QStyle.StandardPixmap.SP_DirIcon,
            "file": QStyle.StandardPixmap.SP_FileIcon,
            "save": QStyle.StandardPixmap.SP_DialogSaveButton,
            "settings": QStyle.StandardPixmap.SP_ComputerIcon,
            "search": QStyle.StandardPixmap.SP_FileDialogDetailedView,
            "document": QStyle.StandardPixmap.SP_FileIcon,
            "plus": QStyle.StandardPixmap.SP_DialogYesButton,
        }

        if icon_name in standard_mappings:
            LOGGER.debug("Using standard pixmap for: %s", icon_name)
            return style.standardIcon(standard_mappings[icon_name])

        return QIcon()

    def _create_emoji_icon(self, emoji: str, size: QSize) -> QIcon:  # noqa: PLR6301
        """Create icon from emoji text.

        Args:
            emoji: Emoji character
            size: Icon size

        Returns:
            QIcon with rendered emoji
        """
        pixmap = QPixmap(size)
        pixmap.fill()  # Transparent

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Use larger font for emojis
        font = QFont()
        font.setPixelSize(int(size.height() * 0.8))
        painter.setFont(font)

        # Draw emoji centered
        painter.drawText(pixmap.rect(), 0x0004, emoji)  # Qt.AlignCenter
        painter.end()

        return QIcon(pixmap)

    def _create_text_icon(self, text: str, size: QSize) -> QIcon:  # noqa: PLR6301
        """Create icon from text abbreviation.

        Args:
            text: Text to abbreviate
            size: Icon size

        Returns:
            QIcon with text
        """
        # Create abbreviation (first letters)
        abbrev = "".join(word[0].upper() for word in text.split("-")[:2])
        if not abbrev:
            abbrev = text[:2].upper()

        pixmap = QPixmap(size)
        pixmap.fill()  # Transparent

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        font = QFont()
        font.setPixelSize(int(size.height() * 0.5))
        font.setBold(True)
        painter.setFont(font)

        painter.drawText(pixmap.rect(), 0x0004, abbrev)  # Qt.AlignCenter
        painter.end()

        return QIcon(pixmap)

    def clear_cache(self) -> None:
        """Clear the icon cache."""
        self.icon_cache.clear()
        LOGGER.debug("Icon cache cleared")

    def set_fallback_to_emoji(self, *, enabled: bool) -> None:
        """Enable or disable emoji fallback.

        Args:
            enabled: Whether to fall back to emojis
        """
        self.fallback_to_emoji = enabled
        self.clear_cache()  # Clear cache to regenerate icons


# Global icon manager instance
_icon_manager: IconManager | None = None


def get_icon_manager() -> IconManager:
    """Get the global icon manager instance.

    Returns:
        The global IconManager instance
    """
    global _icon_manager  # noqa: PLW0603
    if _icon_manager is None:
        _icon_manager = IconManager()
    return _icon_manager


def get_icon(icon_name: str, size: QSize = ICON_MEDIUM) -> QIcon:
    """Convenience function to get an icon.

    Args:
        icon_name: Icon name or emoji
        size: Desired size

    Returns:
        QIcon instance
    """
    return get_icon_manager().get_icon(icon_name, size)
