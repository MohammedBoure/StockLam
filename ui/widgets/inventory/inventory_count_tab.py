import logging

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class InventoryCountTab(QWidget):
    def __init__(self, data_manager, current_user=None):
        super().__init__()
        self.data_manager = data_manager
        self.current_user = current_user or {}
        self.current_session_id = None
        self.init_ui()
        self.load_sessions()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        header_layout = QHBoxLayout()
        title = QLabel("Inventaire")
        title.setObjectName("page_title")
        title.setStyleSheet("font-size: 22px; font-weight: 700; color: #2c3e50;")
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.btn_refresh = QPushButton("Actualiser")
        self.btn_refresh.clicked.connect(self.load_sessions)
        header_layout.addWidget(self.btn_refresh)
        layout.addLayout(header_layout)

        self.sessions_table = QTableWidget(0, 5)
        self.sessions_table.setHorizontalHeaderLabels([
            "ID",
            "Nom",
            "Statut",
            "Debut",
            "Lignes",
        ])
        self.sessions_table.itemSelectionChanged.connect(self.on_session_selected)
        layout.addWidget(self.sessions_table)

        self.lines_table = QTableWidget(0, 9)
        self.lines_table.setHorizontalHeaderLabels([
            "Produit",
            "Code-barres",
            "Lot",
            "Expiration",
            "Emplacement",
            "Programme",
            "Compte",
            "Ecart",
            "Statut",
        ])
        layout.addWidget(self.lines_table)

    def _manager(self):
        return getattr(self.data_manager, "inventory_counts", None)

    def _set_row(self, table, row_index, values):
        table.insertRow(row_index)
        for column_index, value in enumerate(values):
            table.setItem(row_index, column_index, QTableWidgetItem("" if value is None else str(value)))

    def load_sessions(self):
        manager = self._manager()
        self.sessions_table.setRowCount(0)
        self.lines_table.setRowCount(0)
        if not manager:
            return

        try:
            sessions = manager.get_sessions(limit=100)
        except Exception as exc:
            logging.error(f"Unable to load inventory count sessions: {exc}", exc_info=True)
            return

        for row_index, session in enumerate(sessions):
            self._set_row(
                self.sessions_table,
                row_index,
                [
                    session.get("Session_ID"),
                    session.get("Session_Name"),
                    session.get("Status"),
                    session.get("Started_At"),
                    session.get("Total_Lines"),
                ],
            )
        self.sessions_table.resizeColumnsToContents()

    def on_session_selected(self):
        selected = self.sessions_table.selectedItems()
        if not selected:
            return
        try:
            self.current_session_id = int(self.sessions_table.item(selected[0].row(), 0).text())
        except (AttributeError, TypeError, ValueError):
            self.current_session_id = None
            return
        self.load_lines()

    def load_lines(self):
        manager = self._manager()
        self.lines_table.setRowCount(0)
        if not manager or not self.current_session_id:
            return

        try:
            lines = manager.get_session_lines(self.current_session_id)
        except Exception as exc:
            logging.error(f"Unable to load inventory count lines: {exc}", exc_info=True)
            return

        for row_index, line in enumerate(lines):
            self._set_row(
                self.lines_table,
                row_index,
                [
                    line.get("Product_Name"),
                    line.get("Internal_Barcode"),
                    line.get("Lot_Number"),
                    line.get("Expiry_Date"),
                    line.get("Location_Name"),
                    line.get("Program_Qty_Snapshot"),
                    line.get("Counted_Qty"),
                    line.get("Difference_Qty"),
                    line.get("Line_Status"),
                ],
            )
        self.lines_table.resizeColumnsToContents()
