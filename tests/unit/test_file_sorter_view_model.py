from unittest.mock import patch

from PyQt6.QtWidgets import QApplication
import pytest

from goesvfi.file_sorter.sorter import FileSorter
from goesvfi.file_sorter.view_model import FileSorterViewModel


@pytest.fixture()
def view_model(qtbot):
    if QApplication.instance() is None:
        QApplication([])
    return FileSorterViewModel(FileSorter())


def test_select_source_directory_updates_property(view_model, tmp_path) -> None:
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    with patch(
        "goesvfi.file_sorter.view_model.QFileDialog.getExistingDirectory",
        return_value=str(src_dir),
    ) as mocked:
        view_model.select_source_directory()
        mocked.assert_called_once()
        assert view_model.source_directory == str(src_dir)
        assert f"Source directory set to: {src_dir}" == view_model.status_message


def test_select_destination_directory_updates_property(view_model, tmp_path) -> None:
    dst_dir = tmp_path / "dst"
    dst_dir.mkdir()
    with patch(
        "goesvfi.file_sorter.view_model.QFileDialog.getExistingDirectory",
        return_value=str(dst_dir),
    ) as mocked:
        view_model.select_destination_directory()
        mocked.assert_called_once()
        assert view_model.destination_directory == str(dst_dir)
        assert f"Destination directory set to: {dst_dir}" == view_model.status_message
