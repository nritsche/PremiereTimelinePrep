"""Premiere Timeline Prep desktop application entry point."""
import os
import sys


def main():
    try:
        from PySide6.QtWidgets import QApplication
        if __package__ in (None, ""):
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from app.gui.main_window import MainWindow
    except ImportError as exc:
        raise SystemExit("Install the GUI dependencies with: pip install -e '.[gui]'") from exc
    app = QApplication([])
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
