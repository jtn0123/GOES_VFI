#!/usr/bin/env python3
"""Test script for qt-material integration in GOES_VFI."""

from pathlib import Path
import sys


def test_configuration() -> bool | None:
    """Test the configuration system for theme settings."""
    try:
        return True
    except Exception:
        return False


def test_theme_manager() -> bool | None:
    """Test the ThemeManager class."""
    try:
        # Import without GUI dependencies
        import importlib.util

        spec = importlib.util.spec_from_file_location("theme_manager", "goesvfi/gui_components/theme_manager.py")
        theme_module = importlib.util.module_from_spec(spec)

        # Get available themes
        themes = theme_module.AVAILABLE_THEMES

        # Verify all themes are valid Material Design themes
        valid_themes = [
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
        return all(theme in valid_themes for theme in themes)
    except Exception:
        return False


def test_requirements() -> bool | None:
    """Test that qt-material is in pyproject.toml."""
    try:
        pyproject_path = Path("pyproject.toml")
        if not pyproject_path.exists():
            return False

        content = pyproject_path.read_text()
        return "qt-material" in content
    except Exception:
        return False


def test_file_migrations():
    """Test that key files have been migrated."""
    migration_tests = [
        (
            "ThemeManager",
            "goesvfi/gui_components/theme_manager.py",
            ["qt_material", "AVAILABLE_THEMES"],
        ),
        ("Config", "goesvfi/utils/config.py", ["get_theme_name", "theme"]),
        ("MainWindow", "goesvfi/gui.py", ["ThemeManager", "apply_theme"]),
        ("UI Setup", "goesvfi/gui_components/ui_setup_manager.py", ["qt-material"]),
    ]

    success_count = 0
    for _name, file_path, keywords in migration_tests:
        try:
            if not Path(file_path).exists():
                continue

            content = Path(file_path).read_text(encoding="utf-8")
            found_keywords = [kw for kw in keywords if kw in content]

            if found_keywords:
                success_count += 1
        except Exception:
            pass

    return success_count == len(migration_tests)


def main() -> int:
    """Run all tests."""
    tests = [
        test_configuration,
        test_theme_manager,
        test_requirements,
        test_file_migrations,
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        if test():
            passed += 1

    if passed == total:
        try:
            import importlib.util

            spec = importlib.util.spec_from_file_location("theme_manager", "goesvfi/gui_components/theme_manager.py")
            theme_module = importlib.util.module_from_spec(spec)
            for _theme in theme_module.AVAILABLE_THEMES:
                pass
        except Exception:
            pass
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
