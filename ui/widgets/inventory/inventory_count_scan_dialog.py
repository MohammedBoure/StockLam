import logging
from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ui.formatting import format_quantity, quantity_to_int


class InventoryCountScanDialog(QDialog):
    scan_recorded = Signal()

    def __init__(self, data_manager, session_id, current_user=None, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.session_id = session_id
        self.current_user = current_user or {}
        self.pending_barcode = ""
        self.pending_line = None
        self.detail_labels = {}

        self.setWindowTitle("Scanner inventaire")
        self.resize(900, 620)
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
        self.barcode_input.returnPressed.connect(self.load_barcode_details)
        form.addRow("Code-barres", self.barcode_input)

        self.qty_input = QSpinBox()
        self.qty_input.setRange(0, 999999)
        self.qty_input.setSingleStep(1)
        self.qty_input.setValue(1)
        self.qty_input.setMinimumHeight(38)
        self.qty_input.lineEdit().returnPressed.connect(self.record_current_quantity)
        form.addRow("Quantite", self.qty_input)
        layout.addLayout(form)

        details_group = QGroupBox("Produit scanne")
        details_layout = QGridLayout(details_group)
        details_layout.setHorizontalSpacing(18)
        details_layout.setVerticalSpacing(8)
        detail_fields = [
            ("Produit", "Product_Name"),
            ("Code-barres", "Internal_Barcode"),
            ("Lot", "Lot_Number"),
            ("Expiration", "Expiry_Date"),
            ("Emplacement", "Location_Name"),
            ("Stock programme", "Program_Qty_Snapshot"),
            ("Stock compte", "Counted_Qty"),
            ("Ecart", "Difference_Qty"),
            ("Statut", "Line_Status"),
            ("Stock actuel", "Quantity_Current"),
        ]
        for index, (label, key) in enumerate(detail_fields):
            row = index // 2
            col = (index % 2) * 2
            title = QLabel(f"{label}:")
            title.setStyleSheet("font-weight: 700; color: #34495e;")
            value = QLabel("-")
            value.setTextInteractionFlags(Qt.TextSelectableByMouse)
            value.setStyleSheet("color: #2c3e50;")
            details_layout.addWidget(title, row, col)
            details_layout.addWidget(value, row, col + 1)
            self.detail_labels[key] = value
        layout.addWidget(details_group)

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
        self.record_btn = QPushButton("Valider")
        self.record_btn.clicked.connect(self.record_current_quantity)
        footer.addWidget(self.record_btn)
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
        if status in {"READY", "MATCHED"}:
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

    def _quantity_value(self, line, key):
        return format_quantity(line.get(key))

    def _set_details(self, line=None, barcode=None):
        if not line:
            values = {
                "Product_Name": "Inconnu",
                "Internal_Barcode": barcode or "-",
                "Lot_Number": "-",
                "Expiry_Date": "-",
                "Location_Name": "-",
                "Program_Qty_Snapshot": "0",
                "Counted_Qty": "0",
                "Difference_Qty": "0",
                "Line_Status": "UNKNOWN",
                "Quantity_Current": "0",
            }
        else:
            values = {
                "Product_Name": line.get("Product_Name") or "-",
                "Internal_Barcode": line.get("Internal_Barcode") or barcode or "-",
                "Lot_Number": line.get("Lot_Number") or "-",
                "Expiry_Date": line.get("Expiry_Date") or "-",
                "Location_Name": line.get("Location_Name") or "-",
                "Program_Qty_Snapshot": self._quantity_value(line, "Program_Qty_Snapshot"),
                "Counted_Qty": self._quantity_value(line, "Counted_Qty"),
                "Difference_Qty": self._quantity_value(line, "Difference_Qty"),
                "Line_Status": line.get("Line_Status") or "-",
                "Quantity_Current": self._quantity_value(line, "Quantity_Current"),
            }

        for key, label in self.detail_labels.items():
            label.setText(str(values.get(key, "-")))

    def _find_line_for_barcode(self, barcode):
        manager = self._manager()
        if not manager:
            return None

        lines = manager.get_session_lines(self.session_id, search=barcode)
        normalized = barcode.strip()
        for line in lines:
            if str(line.get("Internal_Barcode") or "").strip() == normalized:
                return line
        return None

    def _default_quantity_for_line(self, line):
        if not line:
            return 1

        counted = quantity_to_int(line.get("Counted_Qty"))
        snapshot = quantity_to_int(line.get("Program_Qty_Snapshot"))
        if line.get("Line_Status") == "NOT_COUNTED":
            return max(0, snapshot)
        return max(0, counted)

    def _prepend_scan_row(self, barcode, qty, status, message):
        self.scan_table.insertRow(0)
        values = [barcode, format_quantity(qty), status, datetime.now().strftime("%H:%M:%S"), message]
        for column, value in enumerate(values):
            item = QTableWidgetItem(str(value))
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.scan_table.setItem(0, column, item)

        while self.scan_table.rowCount() > 20:
            self.scan_table.removeRow(self.scan_table.rowCount() - 1)
        self.scan_table.resizeColumnsToContents()

    def load_barcode_details(self):
        barcode = self.barcode_input.text().strip()
        if not barcode:
            self.barcode_input.setFocus()
            return

        manager = self._manager()
        if not manager:
            status = "ERROR"
            message = "Le gestionnaire d'inventaire n'est pas disponible."
            self._set_result(status, message)
            self.barcode_input.setFocus()
            return

        self.pending_barcode = barcode
        try:
            self.pending_line = self._find_line_for_barcode(barcode)
        except Exception as exc:
            logging.error(f"Unable to load inventory scan details: {exc}", exc_info=True)
            self.pending_line = None
            self._set_result("ERROR", str(exc))
            self.barcode_input.setFocus()
            return

        self._set_details(self.pending_line, barcode)
        self.qty_input.setValue(self._default_quantity_for_line(self.pending_line))
        self.qty_input.setFocus()
        self.qty_input.selectAll()

        if self.pending_line:
            product = self.pending_line.get("Product_Name") or barcode
            self._set_result("READY", f"{product} - saisissez la quantite physique puis Entrer.")
        else:
            self._set_result("UNKNOWN", "Code-barres inconnu. Saisissez une quantite pour l'enregistrer.")

    def record_current_quantity(self):
        barcode = self.pending_barcode or self.barcode_input.text().strip()
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
            self.barcode_input.setFocus()
            return

        try:
            result = manager.scan_barcode(
                self.session_id,
                barcode,
                qty,
                self._user_id(),
                replace_counted=True,
            )
        except Exception as exc:
            logging.error(f"Unable to record inventory scan: {exc}", exc_info=True)
            result = {"status": "ERROR", "message": str(exc)}

        status = result.get("status", "ERROR")
        message = result.get("message", "")

        self._set_result(status, message)
        self._prepend_scan_row(barcode, qty, status, message)
        self.scan_recorded.emit()

        self.pending_barcode = ""
        self.pending_line = result.get("line")
        self.barcode_input.clear()
        self.qty_input.setValue(1)
        self.barcode_input.setFocus()
        self.barcode_input.selectAll()

    scan_current_barcode = record_current_quantity
