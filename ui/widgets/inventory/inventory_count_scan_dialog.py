import logging
from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)


class InventoryCountScanDialog(QDialog):
    scan_recorded = Signal()

    def __init__(self, data_manager, session_id, current_user=None, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.session_id = session_id
        self.current_user = current_user or {}

        self.setWindowTitle("Scanner inventaire")
        self.resize(760, 480)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(14)

        form = QFormLayout()
        form.setSpacing(12)

        self.barcode_input = QLineEdit()
        self.barcode_input.setPlaceholderText("Scanner ou saisir un code-barres")
        self.barcode_input.setMinimumHeight(48)
        self.barcode_input.setStyleSheet("font-size: 20px; font-weight: 700; padding: 6px 10px;")
        self.barcode_input.returnPressed.connect(self.scan_current_barcode)
        form.addRow("Code-barres", self.barcode_input)

        self.qty_input = QDoubleSpinBox()
        self.qty_input.setRange(0.01, 999999.00)
        self.qty_input.setDecimals(2)
        self.qty_input.setSingleStep(1.0)
        self.qty_input.setValue(1.0)
        self.qty_input.setMinimumHeight(38)
        form.addRow("Quantite", self.qty_input)
        layout.addLayout(form)

        self.result_label = QLabel("Pret a scanner.")
        self.result_label.setMinimumHeight(54)
        self.result_label.setWordWrap(True)
        self.result_label.setAlignment(Qt.AlignVCenter)
        self.result_label.setStyleSheet(
            "font-size: 18px; font-weight: 800; color: #2c3e50; "
            "padding: 10px; border: 1px solid #dfe6e9; border-radius: 6px;"
        )
        layout.addWidget(self.result_label)

        self.scan_table = QTableWidget(0, 5)
        self.scan_table.setHorizontalHeaderLabels(["Barcode", "Qty", "Status", "Time", "Message"])
        self.scan_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.scan_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        layout.addWidget(self.scan_table)

        footer = QHBoxLayout()
        footer.addStretch()
        self.close_btn = QPushButton("Fermer")
        self.close_btn.clicked.connect(self.accept)
        footer.addWidget(self.close_btn)
        layout.addLayout(footer)

    def showEvent(self, event):
        super().showEvent(event)
        self.barcode_input.setFocus()
        self.barcode_input.selectAll()

    def _manager(self):
        return getattr(self.data_manager, "inventory_counts", None)

    def _user_id(self):
        return self.current_user.get("User_ID") or self.current_user.get("id")

    def _set_result(self, status, message):
        if status == "MATCHED":
            color = "#1e8449"
            border = "#82e0aa"
        elif status == "UNKNOWN":
            color = "#b9770e"
            border = "#f5c542"
        else:
            color = "#c0392b"
            border = "#f5b7b1"

        self.result_label.setStyleSheet(
            f"font-size: 18px; font-weight: 800; color: {color}; "
            f"padding: 10px; border: 1px solid {border}; border-radius: 6px;"
        )
        self.result_label.setText(f"{status}: {message}")

    def _prepend_scan_row(self, barcode, qty, status, message):
        self.scan_table.insertRow(0)
        values = [barcode, qty, status, datetime.now().strftime("%H:%M:%S"), message]
        for column, value in enumerate(values):
            item = QTableWidgetItem(str(value))
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.scan_table.setItem(0, column, item)

        while self.scan_table.rowCount() > 20:
            self.scan_table.removeRow(self.scan_table.rowCount() - 1)
        self.scan_table.resizeColumnsToContents()

    def scan_current_barcode(self):
        barcode = self.barcode_input.text().strip()
        qty = self.qty_input.value()
        if not barcode:
            self.barcode_input.setFocus()
            return

        manager = self._manager()
        if not manager:
            status = "ERROR"
            message = "Le gestionnaire d'inventaire n'est pas disponible."
            self._set_result(status, message)
            self._prepend_scan_row(barcode, qty, status, message)
            self.barcode_input.clear()
            self.barcode_input.setFocus()
            return

        try:
            result = manager.scan_barcode(self.session_id, barcode, qty, self._user_id())
        except Exception as exc:
            logging.error(f"Unable to record inventory scan: {exc}", exc_info=True)
            result = {"status": "ERROR", "message": str(exc)}

        status = result.get("status", "ERROR")
        message = result.get("message", "")

        self._set_result(status, message)
        self._prepend_scan_row(barcode, qty, status, message)
        self.scan_recorded.emit()

        self.barcode_input.clear()
        self.barcode_input.setFocus()
