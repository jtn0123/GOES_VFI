import sys

from PyQt6.QtCore import QObject, pyqtSignal


class Test(QObject):
    signal = pyqtSignal()

    def emit_signal(self):
        print("Emitting signal")
        self.signal.emit()
        print("Signal emitted")


def handler():
    print("Handler called")


print("Creating object")
obj = Test()
print("Connecting signal to handler")
obj.signal.connect(handler)
print("Connection established")
obj.emit_signal()
print("Done")
