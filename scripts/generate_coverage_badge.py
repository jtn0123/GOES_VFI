#!/usr/bin/env python3
"""
Generate coverage badge for GOES_VFI

This script generates a coverage badge based on the current coverage percentage.
"""

import json
from pathlib import Path
import sys


def get_badge_color(percentage: float) -> str:
    """Get badge color based on coverage percentage."""
    if percentage >= 90:
        return "brightgreen"
    if percentage >= 80:
        return "green"
    if percentage >= 70:
        return "yellowgreen"
    if percentage >= 60:
        return "yellow"
    if percentage >= 50:
        return "orange"
    return "red"


def get_coverage_percentage() -> tuple[float, bool]:
    """Get coverage percentage from coverage.json file."""
    coverage_file = Path(__file__).parent.parent / "coverage.json"

    if not coverage_file.exists():
        print("❌ coverage.json not found. Run coverage first:")
        print("   python run_coverage.py")
        return 0.0, False

    try:
        with open(coverage_file, encoding="utf-8") as f:
            data = json.load(f)

        percentage = data.get("totals", {}).get("percent_covered", 0.0)
        return percentage, True

    except Exception as e:
        print(f"❌ Error reading coverage.json: {e}")
        return 0.0, False


def generate_badge(percentage: float, output_path: Path) -> None:
    """Generate badge JSON configuration."""
    color = get_badge_color(percentage)

    badge_config = {
        "schemaVersion": 1,
        "label": "coverage",
        "message": f"{percentage:.1f}%",
        "color": color,
        "cacheSeconds": 300,
        "style": "flat-square",
        "namedLogo": "pytest",
        "logoColor": "white",
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(badge_config, f, indent=2)

    print(f"✅ Badge generated: {output_path}")
    print(f"   Coverage: {percentage:.1f}%")
    print(f"   Color: {color}")


def generate_shields_io_url(percentage: float) -> str:
    """Generate shields.io URL for dynamic badge."""
    color = get_badge_color(percentage)
    message = f"{percentage:.1f}%25"  # URL encode %

    return f"https://img.shields.io/badge/coverage-{message}-{color}?logo=pytest&logoColor=white&style=flat-square"


def update_readme_badge(percentage: float) -> bool:
    """Update coverage badge in README.md."""
    readme_path = Path(__file__).parent.parent / "README.md"

    if not readme_path.exists():
        print("❌ README.md not found")
        return False

    try:
        with open(readme_path, encoding="utf-8") as f:
            content = f.read()

        # Find and replace coverage badge line
        import re

        # Pattern to match coverage badge
        pattern = r"\[!\[Coverage\]\(.*?\)\]\(.*?\)"

        # New badge with updated percentage
        shields_url = generate_shields_io_url(percentage)
        replacement = f"[![Coverage]({shields_url})](https://codecov.io/gh/jtn0123/GOES_VFI)"

        # Replace in content
        new_content = re.sub(pattern, replacement, content)

        if new_content != content:
            with open(readme_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            print("✅ Updated README.md coverage badge")
            return True
        print("ℹ️  No changes needed in README.md")
        return True

    except Exception as e:
        print(f"❌ Error updating README.md: {e}")
        return False


def main() -> int:
    """Main function."""
    print("🔧 GOES_VFI Coverage Badge Generator")
    print("=" * 50)

    # Get coverage percentage
    percentage, success = get_coverage_percentage()

    if not success:
        return 1

    # Generate badge JSON
    badge_path = Path(__file__).parent.parent / ".github" / "coverage-badge.json"
    generate_badge(percentage, badge_path)

    # Generate shields.io URL
    shields_url = generate_shields_io_url(percentage)
    print("\n📊 Shields.io badge URL:")
    print(f"   {shields_url}")

    # Update README if requested
    if len(sys.argv) > 1 and sys.argv[1] == "--update-readme":
        print("\n📝 Updating README.md...")
        update_readme_badge(percentage)

    print("\n✅ Badge generation complete!")

    # Show badge markdown
    print("\n📋 Badge markdown:")
    print(f"   [![Coverage]({shields_url})](https://codecov.io/gh/jtn0123/GOES_VFI)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
