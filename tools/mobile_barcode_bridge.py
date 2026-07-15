"""Thread-safe bridge from the mobile HTTP API to StockLam barcode fields."""

import logging
from threading import Lock

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot
from PySide6.QtWidgets import QApplication, QLineEdit


class MobileBarcodeBridge(QObject):
    barcode_received = Signal(str)

    def __init__(self, window=None):
        super().__init__()
        self.window = window
        self._submit_lock = Lock()
        self._delivery_result = False
        # The HTTP server runs outside Qt's GUI thread. Wait until the GUI has
        # actually handled the barcode before reporting success to the phone.
        self.barcode_received.connect(
            self._deliver,
            Qt.ConnectionType.BlockingQueuedConnection,
        )

    def set_window(self, window):
        self.window = window

    def submit(self, barcode):
        clean = str(barcode or "").strip()
        if not clean:
            return False

        with self._submit_lock:
            # BlockingQueuedConnection cannot be used when the caller is
            # already the GUI thread, otherwise Qt would deadlock itself.
            if QThread.currentThread() == self.thread():
                return self._deliver(clean)

            self._delivery_result = False
            try:
                self.barcode_received.emit(clean)
            except RuntimeError:
                logging.exception(
                    "Mobile barcode delivery could not reach the Qt GUI thread."
                )
                return False
            return self._delivery_result

    @staticmethod
    def _is_usable_line_edit(widget):
        return (
            isinstance(widget, QLineEdit)
            and widget.isEnabled()
            and not widget.isReadOnly()
            and widget.echoMode() == QLineEdit.Normal
        )

    @staticmethod
    def _barcode_score(widget):
        text = " ".join((widget.objectName(), widget.placeholderText())).lower()
        score = 0
        for marker in (
            "barcode",
            "code-barres",
            "code barres",
            "scanner",
            "scannez",
            "smart_search",
        ):
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

    def _open_inventory_scan_target(self):
        """Open the stock transfer screen when no barcode field is visible.

        MainWindow loads pages on demand. A phone scan should therefore still
        have a deterministic destination when the user is currently on the
        dashboard, automates, or another page without a barcode input.
        """
        if self.window is None:
            return None

        switch_page = getattr(self.window, "switch_page", None)
        if not callable(switch_page):
            return None

        try:
            switch_page(3)  # Inventory page
            loaded_pages = getattr(self.window, "loaded_pages", {})
            inventory_page = loaded_pages.get(3)
            if inventory_page is None:
                return None

            dispatch_tab = getattr(inventory_page, "dispatch_tab", None)
            tabs = getattr(inventory_page, "tabs", None)
            target = getattr(dispatch_tab, "barcode_input", None)
            if tabs is not None and dispatch_tab is not None:
                tabs.setCurrentWidget(dispatch_tab)
                QApplication.processEvents()

            if self._is_usable_line_edit(target):
                logging.info(
                    "Mobile barcode target opened automatically: %s",
                    target.objectName() or target.__class__.__name__,
                )
                return target
        except Exception:
            logging.exception("Could not open the StockLam barcode target for mobile input.")
        return None

    @Slot(str)
    def _deliver(self, barcode):
        target = self._find_target()
        if target is None:
            target = self._open_inventory_scan_target()
        if target is None:
            logging.warning(
                "Mobile barcode %s received, but no visible StockLam input field is available.",
                barcode,
            )
            self._delivery_result = False
            self._show_status(
                "Code reçu du téléphone, mais aucun champ de saisie n'est actif."
            )
            return False

        try:
            target.setFocus(Qt.FocusReason.OtherFocusReason)
            target.setText(barcode)
            print(f"🎯 BARCODE TYPED IN TARGET: {target.objectName() or target.__class__.__name__}")
            target.returnPressed.emit()
        except Exception:
            self._delivery_result = False
            logging.exception("Could not insert the mobile barcode into the desktop field.")
            self._show_status(
                "Échec de l'insertion du code-barres reçu du téléphone."
            )
            return False

        self._delivery_result = True
        logging.info(
            "Mobile barcode delivery accepted: field=%s class=%s placeholder=%r value=%s",
            target.objectName() or "<unnamed>",
            target.__class__.__name__,
            target.placeholderText(),
            target.text(),
        )
        self._show_status(
            f"Code-barres envoyé dans {target.objectName() or 'le champ actif'} : {barcode}"
        )
        logging.info(
            "Mobile barcode delivered to desktop field %s",
            target.objectName() or target.__class__.__name__,
        )
        return True

    def _show_status(self, message):
        if self.window is not None and hasattr(self.window, "statusBar"):
            self.window.statusBar().showMessage(message, 5000)
