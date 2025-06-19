# \!/usr/bin/env python3
"""Fix final remaining MyPy strict issues."""

import re


def add_boto_type_ignores():
    """Add type: ignore comments for boto3/botocore imports."""
    files = [
        "goesvfi/integrity_check/goes_imagery.py",
        "goesvfi/integrity_check/remote/s3_store.py",
    ]

    for file_path in files:
        try:
            with open(file_path, "r") as f:
                content = f.read()

            # Add type: ignore for botocore imports
            content = re.sub(
                r"from botocore\.config import Config$",
                "from botocore.config import Config  # type: ignore[import-untyped]",
                content,
                flags=re.MULTILINE,
            )
            content = re.sub(
                r"import botocore\.exceptions$",
                "import botocore.exceptions  # type: ignore[import-untyped]",
                content,
                flags=re.MULTILINE,
            )
            content = re.sub(
                r"from botocore\.exceptions import",
                "from botocore.exceptions import  # type: ignore[import-untyped]",
                content,
            )
            content = re.sub(
                r"import botocore$",
                "import botocore  # type: ignore[import-untyped]",
                content,
                flags=re.MULTILINE,
            )

            with open(file_path, "w") as f:
                f.write(content)

            print(f"Fixed {file_path}")
        except FileNotFoundError:
            print(f"Skipping {file_path} - not found")


def fix_popen_types():
    """Fix Popen type parameters."""
    file_path = "goesvfi/pipeline/run_vfi.py"

    with open(file_path, "r") as f:
        content = f.read()

    # Fix Popen without type parameters
    content = re.sub(r"subprocess\.Popen\[([^]]+)\]", r"subprocess.Popen[\1]", content)

    # Fix bare Popen references
    content = re.sub(r": Popen\b", ": subprocess.Popen[bytes]", content)

    with open(file_path, "w") as f:
        f.write(content)

    print(f"Fixed {file_path}")


def fix_timeline_visualization_annotations():
    """Fix missing type annotations in timeline_visualization.py."""
    file_path = "goesvfi/integrity_check/timeline_visualization.py"

    with open(file_path, "r") as f:
        content = f.read()

    # Add type annotations for methods
    replacements = [
        (r"def update_theme\(self\):", "def update_theme(self) -> None:"),
        (r"def _update_colors\(self\):", "def _update_colors(self) -> None:"),
        (r"def _setup_theme\(self\):", "def _setup_theme(self) -> None:"),
        (r"def refresh\(self\):", "def refresh(self) -> None:"),
    ]

    for pattern, replacement in replacements:
        content = re.sub(pattern, replacement, content)

    with open(file_path, "w") as f:
        f.write(content)

    print(f"Fixed {file_path}")


def fix_visual_date_picker_callable():
    """Fix Callable type parameter in visual_date_picker.py."""
    file_path = "goesvfi/integrity_check/visual_date_picker.py"

    with open(file_path, "r") as f:
        content = f.read()

    # Fix Callable missing type parameters (line 128)
    content = re.sub(
        r"self, callback: Callable\)", "self, callback: Callable[..., None])", content
    )

    with open(file_path, "w") as f:
        f.write(content)

    print(f"Fixed {file_path}")


def fix_ffmpeg_settings_default():
    """Fix ffmpeg_settings_tab.py default parameter."""
    file_path = "goesvfi/gui_tabs/ffmpeg_settings_tab.py"

    with open(file_path, "r") as f:
        lines = f.readlines()

    # Find and fix line 956
    for i, line in enumerate(lines):
        if i == 955 and "current_settings: Dict[str, Any] = None" in line:
            lines[i] = line.replace(
                "current_settings: Dict[str, Any] = None",
                "current_settings: Optional[Dict[str, Any]] = None",
            )

    with open(file_path, "w") as f:
        f.writelines(lines)

    print(f"Fixed {file_path}")


def fix_tqdm_import():
    """Add type: ignore for tqdm import."""
    file_path = "goesvfi/run_vfi.py"

    with open(file_path, "r") as f:
        content = f.read()

    content = re.sub(
        r"from tqdm import tqdm$",
        "from tqdm import tqdm  # type: ignore[import-untyped]",
        content,
        flags=re.MULTILINE,
    )

    with open(file_path, "w") as f:
        f.write(content)

    print(f"Fixed {file_path}")


def main():
    """Run all fixes."""
    print("Applying final MyPy strict fixes...\n")

    add_boto_type_ignores()
    fix_popen_types()
    fix_timeline_visualization_annotations()
    fix_visual_date_picker_callable()
    fix_ffmpeg_settings_default()
    fix_tqdm_import()

    print("\nAll fixes applied\!")


if __name__ == "__main__":
    main()
