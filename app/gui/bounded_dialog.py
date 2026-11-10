"""Screen-bounded dialogs with scrollable content and a separate action footer."""
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QLayout,
                               QPlainTextEdit, QScrollArea, QVBoxLayout, QWidget)


class BoundedDialog(QDialog):
    def __init__(self, parent=None, *, width=1100, height=760):
        super().__init__(parent)
        self.outer_layout = QVBoxLayout(self)
        # Child size hints must never force the native window beyond the screen.
        self.outer_layout.setSizeConstraint(QLayout.SetNoConstraint)
        self.body_scroll = QScrollArea()
        self.body_scroll.setWidgetResizable(True)
        self.body_scroll.setMinimumSize(0, 0)
        self.body_scroll.setFrameShape(QScrollArea.NoFrame)
        self.body = QWidget()
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSizeConstraint(QLayout.SetMinimumSize)
        self.body_scroll.setWidget(self.body)
        self.outer_layout.addWidget(self.body_scroll, 1)
        self._fit_screen()
        self.resize(min(width, self.maximumWidth()), min(height, self.maximumHeight()))

    def _fit_screen(self):
        screen = (self.parentWidget().screen() if self.parentWidget() else self.screen()).availableGeometry()
        self.setMinimumSize(0, 0)
        self.setMaximumSize(max(1, screen.width() - 40), max(1, screen.height() - 80))
        self.resize(min(self.width(), self.maximumWidth()), min(self.height(), self.maximumHeight()))

    def showEvent(self, event):
        self._fit_screen()
        super().showEvent(event)


class WarningDialog(BoundedDialog):
    def __init__(self, title, message, parent=None):
        super().__init__(parent, width=720, height=420)
        self.setWindowTitle(title)
        self.message = QPlainTextEdit()
        self.message.setReadOnly(True)
        self.message.setPlainText(str(message))
        self.message.setMinimumSize(0, 0)
        self.body_layout.addWidget(self.message, 1)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        self.buttons.accepted.connect(self.accept)
        self.outer_layout.addWidget(self.buttons)
        self.buttons.button(QDialogButtonBox.Ok).setDefault(True)


def show_warning(parent, title, message):
    return WarningDialog(title, message, parent).exec()
