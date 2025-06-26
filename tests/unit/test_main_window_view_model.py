import pytest

from goesvfi.date_sorter.sorter import DateSorter
from goesvfi.file_sorter.sorter import FileSorter
from goesvfi.gui_components import PreviewManager, ProcessingManager
from goesvfi.view_models.main_window_view_model import MainWindowViewModel


@pytest.fixture()
def main_window_vm(qtbot):
    vm = MainWindowViewModel(
        FileSorter(),
        DateSorter(),
        PreviewManager(),
        ProcessingManager(),
    )
    yield vm
    vm.deleteLater()


def test_status_signal_emitted(main_window_vm, qtbot):
    with qtbot.waitSignal(main_window_vm.status_updated, timeout=1000) as blocker:
        main_window_vm.status = "Working"
    assert blocker.args == ["Working"]
    assert main_window_vm.status == "Working"


def test_active_tab_signal_emitted(main_window_vm, qtbot):
    with qtbot.waitSignal(main_window_vm.active_tab_changed, timeout=1000) as blocker:
        main_window_vm.active_tab_index = 1
    assert blocker.args == [1]
    assert main_window_vm.active_tab_index == 1


def test_processing_vm_has_dependencies(main_window_vm):
    assert main_window_vm.processing_vm.preview_manager is main_window_vm.preview_manager
    assert main_window_vm.processing_vm.processing_manager is main_window_vm.processing_manager
