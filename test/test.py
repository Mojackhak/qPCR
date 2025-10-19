import sys
from PySide6 import __version__ as PYSIDE_VER
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton, QStackedWidget, QLabel
)

# Try to import WebEngine safely; fall back if unavailable
try:
    from PySide6.QtWebEngineWidgets import QWebEngineView  # type: ignore
    HAS_WEBENGINE = True
except Exception:
    QWebEngineView = None  # type: ignore
    HAS_WEBENGINE = False


def main():
    app = QApplication(sys.argv)

    # Root window
    window = QWidget()
    layout = QVBoxLayout(window)

    # Info label + version button
    info = QLabel(f"PySide6 {PYSIDE_VER}")
    btn = QPushButton("Show Web (Wikipedia)")

    # Stacked widget: page 0 is a placeholder label
    stack = QStackedWidget()
    placeholder = QLabel("This is a placeholder page. If WebEngine is available, click the button to load Wikipedia.")
    placeholder.setWordWrap(True)
    stack.addWidget(placeholder)  # index 0

    # Optional: WebEngine page (only if import succeeded)
    web = None
    if HAS_WEBENGINE and QWebEngineView is not None:
        web = QWebEngineView()
        stack.addWidget(web)  # index 1
        def show_web():
            stack.setCurrentIndex(1)
            web.setUrl(QUrl("https://en.wikipedia.org"))
        btn.clicked.connect(show_web)
        btn.setEnabled(True)
    else:
        btn.setText("QtWebEngine not available in this environment")
        btn.setEnabled(False)

    layout.addWidget(info)
    layout.addWidget(btn)
    layout.addWidget(stack)

    window.resize(600, 480)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()