#!/usr/bin/env python3
import pathlib
import shutil
import os
import glob
from typing import List, Tuple, Optional


def find_large_files(
    patterns: List[str], exclude_patterns: Optional[List[str]] = None, min_size_mb: float = 0
) -> List[Tuple[str, float]]:
    """
    Find files matching the given pattern(s) that are larger than min_size_mb.
    
    Args:
        patterns: List of file patterns to match
        exclude_patterns: List of patterns to exclude
        min_size_mb: Minimum file size in MB to include
        
    Returns:
        List of (file_path, size_mb) tuples
    """
    matched_files = []
    project_root = pathlib.Path(__file__).parent.resolve()
    
    for pattern in patterns:
        for file_path in project_root.glob(pattern):
            if file_path.is_file():
                matched_files.append(str(file_path))
    
    # Filter out excluded patterns
    if exclude_patterns:
        for exclude_pattern in exclude_patterns:
            excluded_files = []
            for pattern in exclude_patterns:
                for file_path in project_root.glob(pattern):
                    excluded_files.append(str(file_path))
            matched_files = [f for f in matched_files if f not in excluded_files]
    
    # Get file sizes and filter by minimum size
    result = []
    for file_path in matched_files:
        try:
            size_mb = os.path.getsize(file_path) / (1024 * 1024)
            if size_mb >= min_size_mb:
                result.append((file_path, size_mb))
        except OSError:
            pass
    
    # Sort by size (largest first)
    result.sort(key=lambda x: x[1], reverse=True)
    return result


def main() -> None:
    """Removes cache directories, log files, and large data files from the project."""
    import argparse

    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Clean up cache and large data files")
    parser.add_argument("--delete-data", action="store_true",
                       help="Automatically delete large data files without confirmation")
    parser.add_argument("--list-only", action="store_true",
                       help="Only list large files, don't delete anything")
    args = parser.parse_args()

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

    # 5. Clean up log files in sanchez/bin directory
    print("\nRemoving log files from sanchez/bin directory...")
    count_sanchez_logs = 0
    sanchez_bin_path = project_root / "goesvfi" / "sanchez" / "bin"
    if sanchez_bin_path.exists():
        for log_pattern in ["**/*.log", "**/*.txt", "**/log_*"]:
            for log_file in sanchez_bin_path.glob(log_pattern):
                if log_file.is_file():
                    try:
                        log_file.unlink()
                        print(f"  Removed: {log_file.relative_to(project_root)}")
                        count_sanchez_logs += 1
                    except OSError as e:
                        print(f"  Error removing {log_file.relative_to(project_root)}: {e}")
        if count_sanchez_logs == 0:
            print("  No log files found in sanchez/bin directory.")
    else:
        print("  sanchez/bin directory not found.")
    
    # 6. List and optionally remove large data files
    print("\nChecking for large data files...")
    
    # Find NetCDF files
    nc_files = find_large_files(
        patterns=["**/*.nc"], 
        exclude_patterns=["venv/**/*", "venv-*/**/*"],
        min_size_mb=1
    )
    
    # Find large PNG files
    png_files = find_large_files(
        patterns=["**/*.png"],
        exclude_patterns=[
            "docs/assets/**/*.png",
            "venv/**/*",
            "venv-*/**/*",
            "goesvfi/sanchez/bin/**/*.png"  # Exclude PNGs in sanchez/bin directory
        ],
        min_size_mb=1
    )
    
    # Print NetCDF files
    if nc_files:
        print(f"\nFound {len(nc_files)} large NetCDF (.nc) files:")
        total_nc_size = sum(size for _, size in nc_files)
        for file_path, size in nc_files:
            print(f"  {file_path} ({size:.2f} MB)")
        print(f"Total NetCDF size: {total_nc_size:.2f} MB")
    else:
        print("No large NetCDF files found.")
    
    # Print PNG files
    if png_files:
        print(f"\nFound {len(png_files)} large PNG image files:")
        total_png_size = sum(size for _, size in png_files)
        for file_path, size in png_files:
            print(f"  {file_path} ({size:.2f} MB)")
        print(f"Total PNG size: {total_png_size:.2f} MB")
    else:
        print("No large PNG files found.")
    
    # Determine if we should delete the data files
    if nc_files or png_files:
        should_delete = False

        # Check command-line arguments
        if args.list_only:
            print("\nList-only mode: No files will be deleted.")
        elif args.delete_data:
            should_delete = True
            print("\nAuto-delete mode: Deleting large data files...")
        else:
            # Interactive mode - ask for confirmation
            try:
                response = input("\nDo you want to delete these large data files? (y/n): ")
                should_delete = response.lower() == 'y'
            except (EOFError, KeyboardInterrupt):
                # Handle non-interactive environments
                print("\nNon-interactive environment detected. Use --delete-data to auto-delete files.")
                should_delete = False

        if should_delete:
            # Delete NetCDF files
            for file_path, _ in nc_files:
                try:
                    os.remove(file_path)
                    print(f"Deleted: {file_path}")
                except Exception as e:
                    print(f"Error deleting {file_path}: {e}")

            # Delete PNG files
            for file_path, _ in png_files:
                try:
                    os.remove(file_path)
                    print(f"Deleted: {file_path}")
                except Exception as e:
                    print(f"Error deleting {file_path}: {e}")

            print("\nLarge data files deleted.")
        else:
            print("\nLarge data files kept.")

    print("\nCleanup complete.")


if __name__ == "__main__":
    main()