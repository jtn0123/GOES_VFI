#!/usr/bin/env python3
"""
cleanup.py - Intelligent cleanup script for GOES VFI project

This script removes test artifacts, temporary files, and large data files that should
not be committed to the repository. It includes safety checks to prevent accidental
deletion of important files.
"""

import argparse
import shutil
from pathlib import Path
from typing import List, Optional, Set, Tuple


class CleanupManager:
    """Manages cleanup operations for the GOES VFI project."""

    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.project_root = Path(__file__).parent
        self.files_to_delete: List[Path] = []
        self.directories_to_delete: List[Path] = []
        self.total_size = 0

        # Define patterns for files to clean
        self.file_patterns = {
            # Test outputs
            "test_outputs": [
                "**/test_output/**/*.png",
                "**/test_output/**/*.jpg",
                "**/test_output/**/*.txt",
                "**/test_output/**/*.log",
            ],
            # Coverage files
            "coverage": [
                ".coverage",
                ".coverage.*",
                "coverage.xml",
                "htmlcov/**/*",
            ],
            # Large data files
            "large_data": [
                "**/*.nc",  # NetCDF files
                "data/**/*.png",  # Large PNG files in data dir
                "satpy_images/**/*",
                "temp_netcdf_downloads/**/*",
            ],
            # FFmpeg logs
            "ffmpeg_logs": [
                "ffmpeg-*.log",
                "x265_*.log",
                "x265_*.log.cutree",
            ],
            # Python artifacts
            "python_artifacts": [
                "**/__pycache__/**/*",
                "**/*.pyc",
                "**/*.pyo",
                "**/.pytest_cache/**/*",
                ".ruff_cache/**/*",
            ],
            # Temporary and backup files
            "temp_files": [
                "**/*.bak",
                "**/*.orig",
                "**/*~",
                "**/*#",
                "**/._*",
            ],
            # Test artifacts
            "test_artifacts": [
                "MagicMock/**/*",
                "*MagicMock*",
                "test_results*.txt",
                "linting_*.txt",
                "linter_output.txt",
                "linter_flake8_qt_output.txt",
                "s3_test_results.log",
            ],
        }

        # Directories to clean entirely
        self.directory_patterns = [
            "__pycache__",
            ".pytest_cache",
            "htmlcov",
            ".ruff_cache",
            "MagicMock",
            "test_output",
        ]

        # Protected patterns - never delete these
        self.protected_patterns = {
            ".git/*",  # Direct .git files
            ".git/**/*",  # .git subdirectory files (depth 1)
            ".git/**/**/*",  # .git subdirectory files (depth 2+)
            ".venv/*",
            ".venv/**/*",
            ".venv/**/**/*",
            "venv/*",
            "venv/**/*",
            "venv/**/**/*",
            "*.py",  # Don't delete Python source files
            "*.md",  # Don't delete documentation
            "*.toml",  # Don't delete config files
            "*.yaml",
            "*.yml",
            "*.json",
            "requirements*.txt",
            "LICENSE*",
            "README*",
            ".gitignore",
            ".pre-commit-config.yaml",
        }

        # Size threshold for "large" files (10MB)
        self.large_file_threshold = 10 * 1024 * 1024  # 10MB

    def is_protected(self, path: Path) -> bool:
        """Check if a path is protected from deletion."""
        try:
            path_str = str(path.relative_to(self.project_root))
        except ValueError:
            # Path is outside project root - protect it
            return True

        for pattern in self.protected_patterns:
            # Convert to PurePath for pattern matching
            from pathlib import PurePosixPath

            path_pure = PurePosixPath(path_str)

            # Use pathlib's match method which handles ** patterns correctly
            if path_pure.match(pattern):
                return True

        return False

    def find_files_to_clean(self, patterns: List[str]) -> List[Path]:
        """Find files matching the given patterns."""
        files = []
        for pattern in patterns:
            for path in self.project_root.glob(pattern):
                if path.is_file() and not self.is_protected(path):
                    files.append(path)
        return files

    def find_directories_to_clean(self) -> List[Path]:
        """Find directories that should be cleaned entirely."""
        directories = []
        for pattern in self.directory_patterns:
            for path in self.project_root.rglob(pattern):
                if path.is_dir() and not self.is_protected(path):
                    directories.append(path)
        return directories

    def find_large_files(self) -> List[Tuple[Path, int]]:
        """Find files larger than the threshold."""
        large_files = []
        for ext in ["*.nc", "*.png", "*.jpg", "*.mp4", "*.avi"]:
            for path in self.project_root.rglob(ext):
                if path.is_file() and not self.is_protected(path):
                    size = path.stat().st_size
                    if size > self.large_file_threshold:
                        large_files.append((path, size))
        return large_files

    def format_size(self, size: int) -> str:
        """Format file size in human-readable format."""
        size_float = float(size)
        for unit in ["B", "KB", "MB", "GB"]:
            if size_float < 1024:
                return f"{size_float:.2f} {unit}"
            size_float /= 1024
        return f"{size_float:.2f} TB"

    def analyze(self, categories: Optional[Set[str]] = None):
        """Analyze files to be cleaned."""
        if categories is None:
            categories = set(self.file_patterns.keys())

        print(f"\nAnalyzing files in {self.project_root}...")
        print("=" * 80)

        # Find files by category
        for category, patterns in self.file_patterns.items():
            if category not in categories:
                continue

            files = self.find_files_to_clean(patterns)
            if files:
                print(f"\n{category.upper()}:")
                category_size = 0
                for file in files:
                    size = file.stat().st_size
                    category_size += size
                    self.total_size += size
                    self.files_to_delete.append(file)
                    if self.dry_run or len(files) <= 10:
                        print(
                            f"  - {file.relative_to(self.project_root)} ({self.format_size(size)})"
                        )
                if len(files) > 10 and not self.dry_run:
                    print(f"  ... and {len(files) - 10} more files")
                print(f"  Total: {len(files)} files, {self.format_size(category_size)}")

        # Find directories to clean
        self.directories_to_delete = self.find_directories_to_clean()
        if self.directories_to_delete:
            print("\nDIRECTORIES TO CLEAN:")
            for directory in self.directories_to_delete:
                dir_size = sum(
                    f.stat().st_size for f in directory.rglob("*") if f.is_file()
                )
                self.total_size += dir_size
                print(
                    f"  - {directory.relative_to(self.project_root)} ({self.format_size(dir_size)})"
                )

        # Find large files
        large_files = self.find_large_files()
        if large_files:
            print(f"\nLARGE FILES (>{self.format_size(self.large_file_threshold)}):")
            for file, size in sorted(large_files, key=lambda x: x[1], reverse=True)[
                :10
            ]:
                if file not in self.files_to_delete:
                    print(
                        f"  - {file.relative_to(self.project_root)} ({self.format_size(size)})"
                    )
                    self.files_to_delete.append(file)
                    self.total_size += size

        print("\n" + "=" * 80)
        print(f"Total files to delete: {len(self.files_to_delete)}")
        print(f"Total directories to delete: {len(self.directories_to_delete)}")
        print(f"Total size to free: {self.format_size(self.total_size)}")

    def clean(self, force: bool = False):
        """Perform the cleanup operation."""
        if self.dry_run:
            print("\nDRY RUN - No files will be deleted.")
            print("Run with --delete to actually delete files.")
            return

        if not self.files_to_delete and not self.directories_to_delete:
            print("\nNothing to clean!")
            return

        # Confirm before deletion (unless forced)
        if not force:
            response = input(
                f"\nDelete {len(self.files_to_delete)} files and {len(self.directories_to_delete)} directories? [y/N]: "
            )
            if response.lower() != "y":
                print("Cleanup cancelled.")
                return

        # Delete files
        deleted_files = 0
        for file in self.files_to_delete:
            try:
                file.unlink()
                deleted_files += 1
            except Exception as e:
                print(f"Error deleting {file}: {e}")

        # Delete directories
        deleted_dirs = 0
        for directory in self.directories_to_delete:
            try:
                shutil.rmtree(directory)
                deleted_dirs += 1
            except Exception as e:
                print(f"Error deleting {directory}: {e}")

        print(f"\nDeleted {deleted_files} files and {deleted_dirs} directories.")
        print(f"Freed {self.format_size(self.total_size)} of disk space.")


def main():
    """Main entry point for the cleanup script."""
    parser = argparse.ArgumentParser(
        description="Clean up test artifacts and large files from the GOES VFI project"
    )
    parser.add_argument(
        "--list-only",
        action="store_true",
        help="List files that would be deleted without deleting them (dry run)",
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Actually delete the files (use with caution!)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompt when deleting files",
    )
    parser.add_argument(
        "--delete-data",
        action="store_true",
        help="Delete large data files (.nc, large .png files)",
    )
    parser.add_argument(
        "--categories",
        nargs="+",
        choices=[
            "test_outputs",
            "coverage",
            "large_data",
            "ffmpeg_logs",
            "python_artifacts",
            "temp_files",
            "test_artifacts",
        ],
        help="Specific categories to clean (default: all)",
    )

    args = parser.parse_args()

    # Determine mode
    dry_run = not args.delete

    # Determine categories
    if args.categories:
        categories = set(args.categories)
    elif args.delete_data:
        categories = {"large_data"}
    else:
        categories = None  # All categories

    # Create cleanup manager and run
    manager = CleanupManager(dry_run=dry_run)
    manager.analyze(categories)

    if not dry_run:
        manager.clean(force=args.force)


if __name__ == "__main__":
    main()
