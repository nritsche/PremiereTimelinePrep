"""Small dialog for applying a camera-group time correction."""
from PySide6.QtCore import QDateTime, Qt
from PySide6.QtWidgets import (QDateTimeEdit, QDialog, QDialogButtonBox,
                               QFormLayout, QGroupBox, QHBoxLayout, QLabel,
                               QRadioButton, QSpinBox, QVBoxLayout, QWidget)


class CameraCorrectionDialog(QDialog):
    def __init__(self, source_name, reference_time=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Correct camera timestamps")
        self.setMinimumWidth(430)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Apply a correction to every clip assigned to <b>{}</b>.".format(source_name)))

        self.offset_mode = QRadioButton("Apply a time offset")
        self.offset_mode.setChecked(True)
        offset_box = QGroupBox()
        offset_layout = QFormLayout(offset_box)
        fields = QHBoxLayout()
        self.days = QSpinBox()
        self.days.setRange(-36500, 36500)
        self.days.setSuffix(" days")
        self.hours = QSpinBox()
        self.hours.setRange(-23, 23)
        self.hours.setSuffix(" hr")
        self.minutes = QSpinBox()
        self.minutes.setRange(-59, 59)
        self.minutes.setSuffix(" min")
        self.seconds = QSpinBox()
        self.seconds.setRange(-59, 59)
        self.seconds.setSuffix(" sec")
        for field in (self.days, self.hours, self.minutes, self.seconds):
            fields.addWidget(field)
        offset_layout.addRow(fields)
        layout.addWidget(self.offset_mode)
        layout.addWidget(offset_box)

        self.reference_mode = QRadioButton("Set a reference clip to its actual time and shift this group")
        reference_box = QGroupBox()
        reference_layout = QVBoxLayout(reference_box)
        reference_layout.addWidget(QLabel("The currently selected clip will be used as the reference."))
        initial = QDateTime.currentDateTimeUtc()
        if reference_time:
            initial = QDateTime.fromString(reference_time.strftime("%Y-%m-%dT%H:%M:%SZ"), Qt.ISODate)
        self.reference_datetime = QDateTimeEdit(initial)
        self.reference_datetime.setDisplayFormat("yyyy-MM-dd HH:mm:ss 'UTC'")
        self.reference_datetime.setCalendarPopup(True)
        reference_layout.addWidget(self.reference_datetime)
        layout.addWidget(self.reference_mode)
        layout.addWidget(reference_box)
        self.offset_mode.toggled.connect(lambda enabled: self._set_enabled(offset_box, enabled))
        self.reference_mode.toggled.connect(lambda enabled: self._set_enabled(reference_box, enabled))

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText("Apply correction")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @staticmethod
    def _set_enabled(widget: QWidget, enabled: bool):
        widget.setEnabled(enabled)

    def offset_seconds(self):
        return self.days.value() * 86400 + self.hours.value() * 3600 + self.minutes.value() * 60 + self.seconds.value()

    def actual_reference_time(self):
        return self.reference_datetime.dateTime().toPython()
