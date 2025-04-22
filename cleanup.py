#!/usr/bin/env python3
import pathlib
import shutil
import os

def main() -> None:
    """Removes cache directories and log files from the project."""
    project_root = pathlib.Path(__file__).parent.resolve()
    print(f"Running cleanup in: {project_root}")

    # 1. Remove __pycache__ directories
    print("\nRemoving __pycache__ directories...")
    count_pycache = 0
    for path in project_root.rglob("__pycache__"):
        if path.is_dir():
            try:
                shutil.rmtree(path)
                print(f"  Removed: {path.relative_to(project_root)}")
                count_pycache += 1
            except OSError as e:
                print(f"  Error removing {path}: {e}")
    if count_pycache == 0:
        print("  No __pycache__ directories found.")

    # 2. Remove ffmpeg logs
    print("\nRemoving ffmpeg log files...")
    count_ffmpeg = 0
    for path in project_root.glob("ffmpeg-*.log"):
        if path.is_file():
            try:
                path.unlink()
                print(f"  Removed: {path.name}")
                count_ffmpeg += 1
            except OSError as e:
                print(f"  Error removing {path.name}: {e}")
    if count_ffmpeg == 0:
        print("  No ffmpeg log files found.")

    # 3. Remove x265 logs
    print("\nRemoving x265 log files...")
    count_x265 = 0
    for pattern in ["x265_*.log", "x265_*.log.cutree"]:
        for path in project_root.glob(pattern):
            if path.is_file():
                try:
                    path.unlink()
                    print(f"  Removed: {path.name}")
                    count_x265 += 1
                except OSError as e:
                    print(f"  Error removing {path.name}: {e}")
    if count_x265 == 0:
        print("  No x265 log files found.")

    # 4. Remove .mypy_cache directory
    print("\nRemoving .mypy_cache directory...")
    mypy_cache_path = project_root / ".mypy_cache"
    if mypy_cache_path.is_dir():
        try:
            shutil.rmtree(mypy_cache_path)
            print(f"  Removed: {mypy_cache_path.name}")
        except OSError as e:
            print(f"  Error removing {mypy_cache_path.name}: {e}")
    else:
        print("  .mypy_cache directory not found.")

    print("\nCleanup complete.")

if __name__ == "__main__":
    main() 