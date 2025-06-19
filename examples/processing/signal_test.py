from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication, QPushButton, QVBoxLayout, QWidget


class Emitter(QObject):
    test_signal = pyqtSignal(dict)


def emit_signal(self):
    print("Emitting signal...")


self.test_signal.emit({"test": "value"})
print("Signal emitted")


class Handler(QObject):
    def handle_signal(self, data):
        print(f"Handler received signal with data: {data}")


class TestApp(QWidget):
    def __init__(self):
        super().__init__()


self.emitter = Emitter()
self.handler = Handler()

# Connect signal
self.emitter.test_signal.connect(self.handler.handle_signal)

layout = QVBoxLayout()
self.button = QPushButton("Test Signal")
self.button.clicked.connect(self.on_button_click)
layout.addWidget(self.button)

self.setLayout(layout)
self.setWindowTitle("Signal Test")
self.resize(300, 100)


def on_button_click(self):
    print("Button clicked")


self.emitter.emit_signal()


if __name__ == "__main__":
    pass
app = QApplication([])
window = TestApp()
window.show()
app.exec()
