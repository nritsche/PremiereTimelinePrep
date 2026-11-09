"""Premiere Timeline Prep desktop application entry point."""
import os
import sys


def main():
    if __package__ in (None, ""):
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if "--self-test" in sys.argv:
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--self-test", required=True, metavar="RESULT_JSON")
        parser.add_argument("--media", required=True)
        args = parser.parse_args()
        from app.self_test import run_self_test
        return run_self_test(args.self_test, args.media)
    try:
        from PySide6.QtWidgets import QApplication
        if __package__ in (None, ""):
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from app.gui.main_window import MainWindow
    except ImportError as exc:
        raise SystemExit("Install the GUI dependencies with: pip install -e '.[gui]'") from exc
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
