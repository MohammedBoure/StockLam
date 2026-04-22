"""
auto_select_widgets.py
----------------------
Widgets مخصصة تقوم بتحديد النص تلقائياً عند التركيز عليها.
"""
from PySide6.QtWidgets import QSpinBox, QLineEdit, QDoubleSpinBox
from PySide6.QtCore import QTimer


class AutoSelectSpinBox(QSpinBox):
    def focusInEvent(self, event):
        super().focusInEvent(event)
        QTimer.singleShot(0, self._safe_select_all)

    def _safe_select_all(self):
        try:
            if self.isVisible():
                self.selectAll()
        except RuntimeError:
            pass


class AutoSelectLineEdit(QLineEdit):
    def focusInEvent(self, event):
        super().focusInEvent(event)
        QTimer.singleShot(0, self._safe_select_all)

    def _safe_select_all(self):
        try:
            if self.isVisible():
                self.selectAll()
        except RuntimeError:
            pass


class AutoSelectDoubleSpinBox(QDoubleSpinBox):
    def focusInEvent(self, event):
        super().focusInEvent(event)
        QTimer.singleShot(0, self._safe_select_all)

    def _safe_select_all(self):
        try:
            if self.isVisible():
                self.selectAll()
        except RuntimeError:
            pass
