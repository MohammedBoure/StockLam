"""Thread-safe bridge from the mobile HTTP API to StockLam barcode fields."""

import logging

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWidgets import QApplication, QLineEdit


class MobileBarcodeBridge(QObject):
    barcode_received = Signal(str)

    def __init__(self, window=None):
        super().__init__()
        self.window = window
        self.barcode_received.connect(self._deliver)

    def set_window(self, window):
        self.window = window

    def submit(self, barcode):
        clean = str(barcode or "").strip()
        if not clean:
            return False
        self.barcode_received.emit(clean)
        return True

    @staticmethod
    def _is_usable_line_edit(widget):
        return (
            isinstance(widget, QLineEdit)
            and widget.isEnabled()
            and widget.echoMode() == QLineEdit.Normal
        )

    @staticmethod
    def _barcode_score(widget):
        text = " ".join((widget.objectName(), widget.placeholderText())).lower()
        score = 0
        for marker in ("barcode", "code-barres", "code barres", "scanner", "scannez", "smart_search"):
            if marker in text:
                score += 10
        if widget.hasFocus():
            score += 100
        if widget.isVisible():
            score += 5
        return score

    def _find_target(self):
        focused = QApplication.focusWidget()
        if self._is_usable_line_edit(focused):
            return focused
        if self.window is None:
            return None
        candidates = [
            widget
            for widget in self.window.findChildren(QLineEdit)
            if self._is_usable_line_edit(widget) and widget.isVisible()
        ]
        candidates.sort(key=self._barcode_score, reverse=True)
        if candidates and self._barcode_score(candidates[0]) > 5:
            return candidates[0]
        return None

    @Slot(str)
    def _deliver(self, barcode):
        target = self._find_target()
        if target is None:
            logging.warning(
                "Mobile barcode %s received, but no visible StockLam input field is available.",
                barcode,
            )
            self._show_status("Code reçu du téléphone, mais aucun champ de saisie n'est actif.")
            return

        target.setFocus()
        target.setText(barcode)
        target.returnPressed.emit()
        self._show_status(f"Code-barres reçu du téléphone : {barcode}")
        logging.info("Mobile barcode delivered to desktop field %s", target.objectName() or target.__class__.__name__)

    def _show_status(self, message):
        if self.window is not None and hasattr(self.window, "statusBar"):
            self.window.statusBar().showMessage(message, 5000)
