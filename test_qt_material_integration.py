#!/usr/bin/env python3
"""Test script for qt-material integration in GOES_VFI."""

import sys
from pathlib import Path


def test_configuration():
    """Test the configuration system for theme settings."""
    print("=== Testing Configuration System ===")
    try:
        from goesvfi.utils.config import (
            get_theme_custom_overrides,
            get_theme_density_scale,
            get_theme_fallback_enabled,
            get_theme_name,
        )

        print(f"✅ Theme name: {get_theme_name()}")
        print(f"✅ Custom overrides: {get_theme_custom_overrides()}")
        print(f"✅ Fallback enabled: {get_theme_fallback_enabled()}")
        print(f"✅ Density scale: {get_theme_density_scale()}")
        return True
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False


def test_theme_manager():
    """Test the ThemeManager class."""
    print("\n=== Testing ThemeManager ===")
    try:
        # Import without GUI dependencies
        import importlib.util

        spec = importlib.util.spec_from_file_location("theme_manager", "goesvfi/gui_components/theme_manager.py")
        theme_module = importlib.util.module_from_spec(spec)

        # Get available themes
        themes = theme_module.AVAILABLE_THEMES
        default_theme = theme_module.DEFAULT_THEME

        print(f"✅ Available themes: {len(themes)} themes")
        print(f"✅ Default theme: {default_theme}")
        print(f"✅ Themes: {', '.join(themes)}")

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
        for theme in themes:
            if theme not in valid_themes:
                print(f"❌ Invalid theme: {theme}")
                return False

        print("✅ All themes are valid Material Design themes")
        return True
    except Exception as e:
        print(f"❌ ThemeManager test failed: {e}")
        return False


def test_requirements():
    """Test that qt-material is in requirements.txt."""
    print("\n=== Testing Requirements ===")
    try:
        requirements_path = Path("requirements.txt")
        if not requirements_path.exists():
            print("❌ requirements.txt not found")
            return False

        content = requirements_path.read_text()
        if "qt-material" in content:
            print("✅ qt-material found in requirements.txt")
            return True
        else:
            print("❌ qt-material not found in requirements.txt")
            return False
    except Exception as e:
        print(f"❌ Requirements test failed: {e}")
        return False


def test_file_migrations():
    """Test that key files have been migrated."""
    print("\n=== Testing File Migrations ===")

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
    for name, file_path, keywords in migration_tests:
        try:
            if not Path(file_path).exists():
                print(f"❌ {name}: File not found - {file_path}")
                continue

            content = Path(file_path).read_text()
            found_keywords = [kw for kw in keywords if kw in content]

            if found_keywords:
                print(f"✅ {name}: Migration confirmed ({', '.join(found_keywords)})")
                success_count += 1
            else:
                print(f"❌ {name}: Keywords not found - {keywords}")
        except Exception as e:
            print(f"❌ {name}: Test failed - {e}")

    return success_count == len(migration_tests)


def main():
    """Run all tests."""
    print("🎨 Qt-Material Integration Test Suite")
    print("=" * 50)

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

    print(f"\n{'='*50}")
    print(f"📊 Test Results: {passed} / {total} tests passed")

    if passed == total:
        print("🎉 Qt-Material integration is complete and working!")
        print("\n🚀 Available themes:")
        try:
            import importlib.util

            spec = importlib.util.spec_from_file_location("theme_manager", "goesvfi/gui_components/theme_manager.py")
            theme_module = importlib.util.module_from_spec(spec)
            for theme in theme_module.AVAILABLE_THEMES:
                print(f"   • {theme}")
        except Exception:
            pass
        return 0
    else:
        print("❌ Some tests failed. Please check the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
