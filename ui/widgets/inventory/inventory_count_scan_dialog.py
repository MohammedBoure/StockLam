import logging
from datetime import datetime

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ui.formatting import format_quantity, quantity_to_int


SCAN_STYLE = """
QDialog#inventoryScanner {
    background: #f5f7fb;
    color: #243447;
}
QFrame#scannerTopPanel,
QFrame#productSummary {
    background: #ffffff;
    border: 1px solid #dfe6ee;
    border-radius: 8px;
}
QLabel#fieldLabel {
    color: #52616f;
    font-size: 11px;
    font-weight: 800;
}
QLabel#productTitle {
    color: #1f2d3d;
    font-size: 20px;
    font-weight: 900;
}
QLabel#productMeta {
    color: #607080;
    font-size: 12px;
    font-weight: 600;
}
QLineEdit,
QSpinBox {
    background: #ffffff;
    border: 1px solid #cfd9e2;
    border-radius: 6px;
    color: #1f2d3d;
    min-height: 34px;
    padding: 6px 10px;
}
QLineEdit#barcodeInput {
    border: 2px solid #007572;
    font-size: 20px;
    font-weight: 900;
    min-height: 44px;
}
QPushButton {
    background: #eef3f7;
    border: 1px solid #cfd9e2;
    border-radius: 5px;
    color: #243447;
    font-weight: 800;
    min-height: 32px;
    padding: 6px 14px;
}
QPushButton#validateButton {
    background: #007572;
    border-color: #00615f;
    color: #ffffff;
}
QGroupBox {
    background: #ffffff;
    border: 1px solid #dfe6ee;
    border-radius: 8px;
    color: #52616f;
    font-weight: 800;
    margin-top: 10px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 4px;
}
QLabel#detailTitle {
    color: #52616f;
    font-weight: 800;
}
QLabel#detailValue {
    color: #243447;
    font-weight: 600;
}
QTableWidget {
    background: #ffffff;
    alternate-background-color: #f8fafc;
    border: 1px solid #dfe6ee;
    gridline-color: #edf1f5;
    selection-background-color: #d7f0ee;
    selection-color: #1f2d3d;
}
QHeaderView::section {
    background: #eef3f7;
    border: 0;
    border-right: 1px solid #dfe6ee;
    border-bottom: 1px solid #dfe6ee;
    color: #52616f;
    font-size: 11px;
    font-weight: 800;
    padding: 6px;
}
QSplitter::handle {
    background: #dfe6ee;
}
QSplitter::handle:horizontal {
    width: 6px;
}
"""


class InventoryCountScanDialog(QDialog):
    scan_recorded = Signal()

    def __init__(self, data_manager, session_id, current_user=None, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.session_id = session_id
        self.current_user = current_user or {}
        self.pending_barcode = ""
        self.pending_line = None
        self.last_loaded_barcode = ""
        self._shown_maximized = False
        self.detail_labels = {}

        self.setWindowTitle("Scanner inventaire")
        self.setObjectName("inventoryScanner")
        self.setMinimumSize(900, 600)
        self.resize(1180, 760)
        self.setStyleSheet(SCAN_STYLE)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        scan_panel = QFrame()
        scan_panel.setObjectName("scannerTopPanel")
        form = QGridLayout(scan_panel)
        form.setContentsMargins(12, 10, 12, 12)
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(6)

        barcode_label = QLabel("Code-barres")
        barcode_label.setObjectName("fieldLabel")
        form.addWidget(barcode_label, 0, 0, 1, 2)
        self.barcode_input = QLineEdit()
        self.barcode_input.setObjectName("barcodeInput")
        self.barcode_input.setPlaceholderText("Scanner ou saisir un code-barres")
        self.barcode_input.returnPressed.connect(self.load_barcode_details)
        self.barcode_input.textChanged.connect(self.schedule_barcode_lookup)
        form.addWidget(self.barcode_input, 1, 0)

        self.barcode_lookup_timer = QTimer(self)
        self.barcode_lookup_timer.setSingleShot(True)
        self.barcode_lookup_timer.timeout.connect(self.load_barcode_details)

        qty_label = QLabel("Quantite")
        qty_label.setObjectName("fieldLabel")
        form.addWidget(qty_label, 0, 1)
        self.qty_input = QSpinBox()
        self.qty_input.setRange(0, 999999)
        self.qty_input.setSingleStep(1)
        self.qty_input.setValue(1)
        self.qty_input.lineEdit().returnPressed.connect(self.record_current_quantity)
        self.qty_input.setMaximumWidth(160)
        form.addWidget(self.qty_input, 1, 1)

        self.record_btn = QPushButton("Valider")
        self.record_btn.setObjectName("validateButton")
        self.record_btn.clicked.connect(self.record_current_quantity)
        self.record_btn.setFixedWidth(110)
        form.addWidget(self.record_btn, 1, 2)
        self.close_btn = QPushButton("Fermer")
        self.close_btn.clicked.connect(self.accept)
        self.close_btn.setFixedWidth(90)
        form.addWidget(self.close_btn, 1, 3)
        form.setColumnStretch(0, 1)
        layout.addWidget(scan_panel)

        self.product_summary = QFrame()
        self.product_summary.setObjectName("productSummary")
        product_summary_layout = QVBoxLayout(self.product_summary)
        product_summary_layout.setContentsMargins(12, 10, 12, 10)
        product_summary_layout.setSpacing(3)
        self.product_title_label = QLabel("Pret a scanner")
        self.product_title_label.setObjectName("productTitle")
        self.product_title_label.setWordWrap(True)
        self.product_meta_label = QLabel("-")
        self.product_meta_label.setObjectName("productMeta")
        self.product_meta_label.setWordWrap(True)
        product_summary_layout.addWidget(self.product_title_label)
        product_summary_layout.addWidget(self.product_meta_label)
        layout.addWidget(self.product_summary)

        details_group = QGroupBox("Produit scanne")
        details_layout = QGridLayout(details_group)
        details_layout.setContentsMargins(12, 14, 12, 10)
        details_layout.setHorizontalSpacing(14)
        details_layout.setVerticalSpacing(6)
        detail_fields = [
            ("Produit", "Product_Name"),
            ("Famille", "Family_Name"),
            ("Fabricant", "Manuf_Name"),
            ("Automate", "Automate_Name"),
            ("Code interne", "Internal_Barcode"),
            ("Code produit", "Product_Barcode"),
            ("Ref fabricant", "Manuf_Cat_No"),
            ("Lot", "Lot_Number"),
            ("Expiration", "Expiry_Date"),
            ("Emplacement", "Location_Name"),
            ("Statut lot", "Batch_Status"),
            ("Unite stock", "Stock_Unit"),
            ("Unite usage", "Usage_Unit"),
            ("Temp. stockage", "Storage_Temp_Req"),
            ("Stock programme", "Program_Qty_Snapshot"),
            ("Stock actuel", "Quantity_Current"),
            ("Stock initial", "Quantity_Initial"),
            ("Stock compte", "Counted_Qty"),
            ("Ecart", "Difference_Qty"),
            ("Statut", "Line_Status"),
            ("Note", "Reception_Note"),
        ]
        for index, (label, key) in enumerate(detail_fields):
            row = index // 2
            col = (index % 2) * 2
            title = QLabel(f"{label}:")
            title.setObjectName("detailTitle")
            value = QLabel("-")
            value.setObjectName("detailValue")
            value.setWordWrap(True)
            value.setTextInteractionFlags(Qt.TextSelectableByMouse)
            value.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            details_layout.addWidget(title, row, col)
            details_layout.addWidget(value, row, col + 1)
            self.detail_labels[key] = value
        details_layout.setColumnStretch(1, 1)
        details_layout.setColumnStretch(3, 1)

        details_scroll = QScrollArea()
        details_scroll.setWidgetResizable(True)
        details_scroll.setFrameShape(QFrame.NoFrame)
        details_scroll.setWidget(details_group)
        details_scroll.setMaximumWidth(620)

        self.scan_table = QTableWidget(0, 5)
        self.scan_table.setHorizontalHeaderLabels(["Code-barres", "Quantité", "Statut", "Heure", "Message"])
        self.scan_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.scan_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.scan_table.setAlternatingRowColors(True)
        self.scan_table.verticalHeader().setVisible(False)
        self.scan_table.verticalHeader().setDefaultSectionSize(28)
        self.scan_table.horizontalHeader().setHighlightSections(False)
        self.scan_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.scan_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.scan_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.scan_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.scan_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)

        content_splitter = QSplitter(Qt.Horizontal)
        content_splitter.setChildrenCollapsible(False)
        content_splitter.addWidget(details_scroll)
        content_splitter.addWidget(self.scan_table)
        content_splitter.setStretchFactor(0, 1)
        content_splitter.setStretchFactor(1, 2)
        content_splitter.setSizes([460, 820])
        layout.addWidget(content_splitter, 1)

        self.result_label = QLabel("Pret a scanner.")
        self.result_label.setObjectName("scanResult")
        self.result_label.setMinimumHeight(54)
        self.result_label.setWordWrap(True)
        self.result_label.setAlignment(Qt.AlignVCenter)
        self.result_label.setStyleSheet(
            "font-size: 18px; font-weight: 800; color: #2c3e50; "
            "padding: 10px; border: 1px solid #dfe6e9; border-radius: 6px;"
        )
        layout.addWidget(self.result_label)

    def showEvent(self, event):
        super().showEvent(event)
        if not self._shown_maximized:
            self._shown_maximized = True
            QTimer.singleShot(0, self.showMaximized)
        QTimer.singleShot(0, self._focus_barcode)

    def _focus_barcode(self):
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
            background = "#eef9f1"
        elif status == "UNKNOWN":
            color = "#b9770e"
            border = "#f5c542"
            background = "#fff8e6"
        else:
            color = "#c0392b"
            border = "#f5b7b1"
            background = "#fff0f0"

        self.result_label.setStyleSheet(
            f"font-size: 18px; font-weight: 800; color: {color}; "
            f"background: {background}; padding: 10px; border: 1px solid {border}; border-radius: 6px;"
        )
        self.result_label.setText(f"{status}: {message}")

    def _quantity_value(self, line, key):
        return format_quantity(line.get(key))

    def _text_value(self, line, key, default="-"):
        value = line.get(key) if line else None
        if value in (None, ""):
            return default
        return str(value)

    def _set_details(self, line=None, barcode=None):
        if not line:
            values = {
                "Product_Name": "Inconnu",
                "Family_Name": "-",
                "Manuf_Name": "-",
                "Automate_Name": "-",
                "Internal_Barcode": barcode or "-",
                "Product_Barcode": "-",
                "Manuf_Cat_No": "-",
                "Lot_Number": "-",
                "Expiry_Date": "-",
                "Location_Name": "-",
                "Batch_Status": "-",
                "Stock_Unit": "-",
                "Usage_Unit": "-",
                "Storage_Temp_Req": "-",
                "Program_Qty_Snapshot": "0",
                "Quantity_Current": "0",
                "Quantity_Initial": "0",
                "Counted_Qty": "0",
                "Difference_Qty": "0",
                "Line_Status": "UNKNOWN",
                "Reception_Note": "-",
            }
        else:
            values = {
                "Product_Name": self._text_value(line, "Product_Name"),
                "Family_Name": self._text_value(line, "Family_Name"),
                "Manuf_Name": self._text_value(line, "Manuf_Name"),
                "Automate_Name": self._text_value(line, "Automate_Name"),
                "Internal_Barcode": self._text_value(line, "Internal_Barcode", barcode or "-"),
                "Product_Barcode": self._text_value(line, "Product_Barcode"),
                "Manuf_Cat_No": self._text_value(line, "Manuf_Cat_No"),
                "Lot_Number": self._text_value(line, "Lot_Number"),
                "Expiry_Date": self._text_value(line, "Expiry_Date"),
                "Location_Name": self._text_value(line, "Location_Name"),
                "Batch_Status": self._text_value(line, "Batch_Status"),
                "Stock_Unit": self._text_value(line, "Stock_Unit"),
                "Usage_Unit": self._text_value(line, "Usage_Unit"),
                "Storage_Temp_Req": self._text_value(line, "Storage_Temp_Req"),
                "Program_Qty_Snapshot": self._quantity_value(line, "Program_Qty_Snapshot"),
                "Quantity_Current": self._quantity_value(line, "Quantity_Current"),
                "Quantity_Initial": self._quantity_value(line, "Quantity_Initial"),
                "Counted_Qty": self._quantity_value(line, "Counted_Qty"),
                "Difference_Qty": self._quantity_value(line, "Difference_Qty"),
                "Line_Status": self._text_value(line, "Line_Status"),
                "Reception_Note": self._text_value(line, "Reception_Note"),
            }

        for key, label in self.detail_labels.items():
            label.setText(str(values.get(key, "-")))

        self.product_title_label.setText(str(values.get("Product_Name", "Inconnu")))
        meta_values = [
            f"Lot {values.get('Lot_Number', '-')}",
            f"Emplacement {values.get('Location_Name', '-')}",
            f"Programme {values.get('Program_Qty_Snapshot', '0')}",
            f"Compte {values.get('Counted_Qty', '0')}",
            f"Ecart {values.get('Difference_Qty', '0')}",
            f"Statut {values.get('Line_Status', '-')}",
        ]
        self.product_meta_label.setText(" | ".join(meta_values))

    def _find_line_for_barcode(self, barcode):
        manager = self._manager()
        if not manager:
            return None

        exact_lookup = getattr(manager, "get_session_line_by_barcode", None)
        if callable(exact_lookup):
            line = exact_lookup(self.session_id, barcode)
            if line:
                return line

        lines = manager.get_session_lines(self.session_id, search=barcode)
        normalized = self._normalize_code(barcode)
        compact = self._compact_code(barcode)

        internal_matches = []
        product_matches = []
        for line in lines:
            internal = line.get("Internal_Barcode")
            product_barcode = line.get("Product_Barcode")
            manuf_ref = line.get("Manuf_Cat_No")
            if self._normalize_code(internal) == normalized or self._compact_code(internal) == compact:
                internal_matches.append(line)
            elif (
                self._normalize_code(product_barcode) == normalized
                or self._normalize_code(manuf_ref) == normalized
                or self._compact_code(product_barcode) == compact
                or self._compact_code(manuf_ref) == compact
            ):
                product_matches.append(line)

        if internal_matches:
            return internal_matches[0]
        if product_matches:
            return product_matches[0]
        return None

    def _normalize_code(self, value):
        return str(value or "").strip().lower()

    def _compact_code(self, value):
        return self._normalize_code(value).replace(" ", "").replace("-", "")

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

    def schedule_barcode_lookup(self, text):
        barcode = text.strip()
        if not barcode:
            self.barcode_lookup_timer.stop()
            self.pending_barcode = ""
            self.pending_line = None
            self.last_loaded_barcode = ""
            return

        if barcode == self.last_loaded_barcode:
            return

        if len(barcode) < 3:
            self.barcode_lookup_timer.stop()
            return

        self.barcode_lookup_timer.start(220)

    def load_barcode_details(self):
        barcode = self.barcode_input.text().strip()
        if not barcode:
            self.barcode_input.setFocus()
            return

        if barcode == self.last_loaded_barcode:
            self.qty_input.setFocus()
            self.qty_input.selectAll()
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

        self.last_loaded_barcode = barcode
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
        self._set_details(result.get("line"), barcode)
        self._prepend_scan_row(barcode, qty, status, message)
        self.scan_recorded.emit()

        self.pending_barcode = ""
        self.pending_line = result.get("line")
        self.last_loaded_barcode = ""
        self.barcode_input.clear()
        self.qty_input.setValue(1)
        self.barcode_input.setFocus()
        self.barcode_input.selectAll()

    scan_current_barcode = record_current_quantity
