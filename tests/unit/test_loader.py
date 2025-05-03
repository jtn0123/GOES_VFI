import pathlib
import pytest
from goesvfi.pipeline import loader


def test_discover_frames_only_supported_extensions(temp_dir):
    # Create files with supported and unsupported extensions
    supported_files = ["frame1.png", "frame2.jpg", "frame3.jpeg"]
    unsupported_files = ["frame4.bmp", "frame5.gif", "frame6.txt"]
    for filename in supported_files + unsupported_files:
        (temp_dir / filename).write_text("dummy content")

    result = loader.discover_frames(temp_dir)
    # Check that only supported files are returned
    result_filenames = [p.name for p in result]
    for f in supported_files:
        assert f in result_filenames
    for f in unsupported_files:
        assert f not in result_filenames


def test_discover_frames_sorted_order(temp_dir):
    # Create files with names that sort lexicographically by timestamp
    filenames = ["20230101_0000.png", "20230101_0001.png", "20230101_0002.png"]
    for filename in filenames:
        (temp_dir / filename).write_text("dummy content")

    result = loader.discover_frames(temp_dir)
    result_filenames = [p.name for p in result]
    assert result_filenames == sorted(filenames)


def test_discover_frames_empty_directory(temp_dir):
    # No files in directory
    result = loader.discover_frames(temp_dir)
    assert result == []


def test_discover_frames_case_insensitive_extension(temp_dir):
    # Create files with uppercase extensions
    filenames = ["frame1.PNG", "frame2.JpG", "frame3.JPEG"]
    for filename in filenames:
        (temp_dir / filename).write_text("dummy content")

    result = loader.discover_frames(temp_dir)
    result_filenames = [p.name for p in result]
    for f in filenames:
        assert f in result_filenames
