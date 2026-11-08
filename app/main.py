"""Application entry point (GUI is added in the next implementation stage)."""


def main():
    try:
        from PySide6.QtWidgets import QApplication, QLabel, QMainWindow
    except ImportError as exc:
        raise SystemExit("Install the GUI dependencies with: pip install -e '.[gui]'") from exc
    app = QApplication([])
    window = QMainWindow()
    window.setWindowTitle("Premiere Timeline Prep")
    window.setCentralWidget(QLabel("Premiere Timeline Prep\nMetadata and timestamp engine ready"))
    window.resize(720, 420)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
