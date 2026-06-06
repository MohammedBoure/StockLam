import json
import logging
from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ui.formatting import format_money, format_quantity

from .inventory_count_scan_dialog import InventoryCountScanDialog


class NewInventorySessionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nouvelle session inventaire")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Inventaire mensuel")
        form.addRow("Nom", self.name_input)

        self.scope_combo = QComboBox()
        self.scope_combo.addItems(["ALL", "LOCATION", "FAMILY", "PRODUCT"])
        form.addRow("Scope", self.scope_combo)

        self.scope_id_input = QLineEdit()
        self.scope_id_input.setPlaceholderText("Optionnel")
        form.addRow("Scope ID", self.scope_id_input)

        self.notes_input = QTextEdit()
        self.notes_input.setFixedHeight(80)
        form.addRow("Notes", self.notes_input)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self):
        scope_id_text = self.scope_id_input.text().strip()
        return {
            "name": self.name_input.text().strip(),
            "scope_type": self.scope_combo.currentText(),
            "scope_id": int(scope_id_text) if scope_id_text.isdigit() else None,
            "notes": self.notes_input.toPlainText().strip() or None,
        }


class SummaryCard(QFrame):
    def __init__(self, title):
        super().__init__()
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet("QFrame { border: 1px solid #dfe6e9; border-radius: 6px; background: #ffffff; }")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("color: #607d8b; font-size: 11px;")
        self.value_label = QLabel("0")
        self.value_label.setStyleSheet("color: #2c3e50; font-size: 18px; font-weight: 800;")
        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)

    def set_value(self, value):
        self.value_label.setText(str(value))


class InventoryCountTab(QWidget):
    def __init__(self, data_manager, current_user=None):
        super().__init__()
        self.data_manager = data_manager
        self.current_user = current_user or {}
        self.current_session_id = None
        self.current_session = None
        self.sessions = []
        self.init_ui()
        self.apply_permissions()
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

        self.btn_new = QPushButton("Nouvelle session")
        self.btn_scan = QPushButton("Scanner")
        self.btn_review = QPushButton("Revue")
        self.btn_apply = QPushButton("Appliquer")
        self.btn_cancel = QPushButton("Annuler")
        self.btn_export = QPushButton("Exporter")
        self.btn_refresh = QPushButton("Actualiser")

        self.btn_new.clicked.connect(self.create_session)
        self.btn_scan.clicked.connect(self.open_scan_dialog)
        self.btn_review.clicked.connect(self.mark_review)
        self.btn_apply.clicked.connect(self.apply_session)
        self.btn_cancel.clicked.connect(self.cancel_session)
        self.btn_export.clicked.connect(self.export_session)
        self.btn_refresh.clicked.connect(self.load_sessions)

        for button in (
            self.btn_new,
            self.btn_scan,
            self.btn_review,
            self.btn_apply,
            self.btn_cancel,
            self.btn_export,
            self.btn_refresh,
        ):
            header_layout.addWidget(button)
        layout.addLayout(header_layout)

        summary_layout = QGridLayout()
        self.summary_cards = {
            "OK": SummaryCard("OK"),
            "SHORT": SummaryCard("Manquant"),
            "EXCESS": SummaryCard("Excedent"),
            "NOT_COUNTED": SummaryCard("Non compte"),
            "UNKNOWN": SummaryCard("Inconnu"),
            "Estimated_Variance_Value": SummaryCard("Valeur ecart"),
        }
        for index, card in enumerate(self.summary_cards.values()):
            summary_layout.addWidget(card, 0, index)
        layout.addLayout(summary_layout)

        filters_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Rechercher produit, code-barres, lot, emplacement")
        self.search_input.textChanged.connect(self.load_lines)
        filters_layout.addWidget(self.search_input, 1)

        self.status_filter = QComboBox()
        self.status_filter.addItems(["Tous", "OK", "SHORT", "EXCESS", "NOT_COUNTED", "UNKNOWN"])
        self.status_filter.currentTextChanged.connect(self.load_lines)
        filters_layout.addWidget(self.status_filter)
        layout.addLayout(filters_layout)

        self.sessions_table = QTableWidget(0, 5)
        self.sessions_table.setHorizontalHeaderLabels([
            "Session_ID",
            "Session_Name",
            "Status",
            "Started_At",
            "Created_By",
        ])
        self.sessions_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.sessions_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.sessions_table.itemSelectionChanged.connect(self.load_current_session)
        layout.addWidget(self.sessions_table)

        self.lines_table = QTableWidget(0, 10)
        self.lines_table.setHorizontalHeaderLabels([
            "Produit",
            "Code-barres",
            "Lot",
            "Expiration",
            "Emplacement",
            "Stock programme",
            "Stock compte",
            "Ecart",
            "Statut",
            "Commentaire",
        ])
        self.lines_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.lines_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        layout.addWidget(self.lines_table)

    def _manager(self):
        return getattr(self.data_manager, "inventory_counts", None)

    def _user_id(self):
        return self.current_user.get("User_ID") or self.current_user.get("id")

    def has_action(self, permission_key):
        permissions = self.current_user.get("Permissions", {})
        if isinstance(permissions, str):
            try:
                permissions = json.loads(permissions)
            except json.JSONDecodeError:
                permissions = []
        if isinstance(permissions, dict):
            return bool(permissions.get(permission_key))
        if isinstance(permissions, list):
            return permission_key in permissions
        return False

    def apply_permissions(self):
        permission_map = {
            self.btn_new: "act_inventory_create",
            self.btn_scan: "act_inventory_scan",
            self.btn_apply: "act_inventory_apply",
            self.btn_cancel: "act_inventory_cancel",
            self.btn_export: "act_inventory_export",
        }
        for button, permission in permission_map.items():
            button.setVisible(self.has_action(permission))

    def _set_row(self, table, row_index, values):
        table.insertRow(row_index)
        for column_index, value in enumerate(values):
            item = QTableWidgetItem("" if value is None else str(value))
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            table.setItem(row_index, column_index, item)

    def _selected_session_id(self):
        row = self.sessions_table.currentRow()
        if row < 0:
            return None
        item = self.sessions_table.item(row, 0)
        try:
            return int(item.text())
        except (AttributeError, TypeError, ValueError):
            return None

    def _set_buttons_for_session(self):
        has_session = self.current_session_id is not None
        status = (self.current_session or {}).get("Status")
        is_open = status in {"Counting", "Review"}
        self.btn_scan.setEnabled(has_session and is_open)
        self.btn_review.setEnabled(has_session and status == "Counting")
        self.btn_apply.setEnabled(has_session and is_open)
        self.btn_cancel.setEnabled(has_session and status not in {"Applied", "Cancelled"})
        self.btn_export.setEnabled(has_session)

    def load_sessions(self):
        manager = self._manager()
        self.sessions_table.setRowCount(0)
        self.lines_table.setRowCount(0)
        self.current_session_id = None
        self.current_session = None
        self.refresh_summary()
        if not manager:
            QMessageBox.warning(self, "Inventaire", "Le gestionnaire d'inventaire n'est pas disponible.")
            self._set_buttons_for_session()
            return

        try:
            self.sessions = manager.get_sessions(limit=100)
        except Exception as exc:
            logging.error(f"Unable to load inventory count sessions: {exc}", exc_info=True)
            QMessageBox.warning(self, "Inventaire", f"Impossible de charger les sessions:\n{exc}")
            self.sessions = []

        for row_index, session in enumerate(self.sessions):
            self._set_row(
                self.sessions_table,
                row_index,
                [
                    session.get("Session_ID"),
                    session.get("Session_Name"),
                    session.get("Status"),
                    session.get("Started_At"),
                    session.get("Created_By") or session.get("Created_By_Name") or "",
                ],
            )
        self.sessions_table.resizeColumnsToContents()
        self._set_buttons_for_session()

    def load_current_session(self):
        self.current_session_id = self._selected_session_id()
        self.current_session = None
        if self.current_session_id:
            for session in self.sessions:
                if int(session.get("Session_ID")) == self.current_session_id:
                    self.current_session = session
                    break
        self.load_lines()
        self.refresh_summary()
        self._set_buttons_for_session()

    def load_lines(self):
        manager = self._manager()
        self.lines_table.setRowCount(0)
        if not manager or not self.current_session_id:
            return

        status = self.status_filter.currentText()
        if status == "Tous":
            status = None
        search = self.search_input.text().strip() or None

        try:
            lines = manager.get_session_lines(self.current_session_id, status=status, search=search)
        except Exception as exc:
            logging.error(f"Unable to load inventory count lines: {exc}", exc_info=True)
            QMessageBox.warning(self, "Inventaire", f"Impossible de charger les lignes:\n{exc}")
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
                    format_quantity(line.get("Program_Qty_Snapshot")),
                    format_quantity(line.get("Counted_Qty")),
                    format_quantity(line.get("Difference_Qty")),
                    line.get("Line_Status"),
                    line.get("Comment"),
                ],
            )
        self.lines_table.resizeColumnsToContents()

    def refresh_summary(self):
        for card in self.summary_cards.values():
            card.set_value("0")
        manager = self._manager()
        if not manager or not self.current_session_id:
            return

        try:
            summary = manager.get_session_summary(self.current_session_id)
        except Exception as exc:
            logging.error(f"Unable to refresh inventory count summary: {exc}", exc_info=True)
            return

        for key, card in self.summary_cards.items():
            value = summary.get(key, 0)
            if key == "Estimated_Variance_Value":
                value = format_money(value)
            elif isinstance(value, Decimal):
                value = format_quantity(value)
            card.set_value(value)

    def create_session(self):
        manager = self._manager()
        if not manager:
            QMessageBox.warning(self, "Inventaire", "Le gestionnaire d'inventaire n'est pas disponible.")
            return

        dialog = NewInventorySessionDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return

        values = dialog.values()
        if not values["name"]:
            QMessageBox.warning(self, "Inventaire", "Le nom de la session est obligatoire.")
            return

        session_id = manager.create_session(
            values["name"],
            scope_type=values["scope_type"],
            scope_id=values["scope_id"],
            created_by=self._user_id(),
            notes=values["notes"],
        )
        if not session_id:
            QMessageBox.warning(self, "Inventaire", "Impossible de creer la session.")
            return

        QMessageBox.information(self, "Inventaire", f"Session creee: #{session_id}")
        self.load_sessions()
        self._select_session(session_id)

    def _select_session(self, session_id):
        for row in range(self.sessions_table.rowCount()):
            item = self.sessions_table.item(row, 0)
            if item and item.text() == str(session_id):
                self.sessions_table.selectRow(row)
                break

    def open_scan_dialog(self):
        manager = self._manager()
        if not manager or not self.current_session_id:
            QMessageBox.warning(self, "Inventaire", "Selectionnez une session.")
            return
        status = (self.current_session or {}).get("Status")
        if status not in {"Counting", "Review"}:
            QMessageBox.warning(self, "Inventaire", "Cette session n'est pas ouverte au comptage.")
            return
        session_id = self.current_session_id
        dialog = InventoryCountScanDialog(self.data_manager, session_id, self.current_user, self)
        dialog.scan_recorded.connect(self.on_scan_recorded)
        dialog.exec()
        self.current_session_id = session_id
        self.load_sessions()
        self._select_session(session_id)
        self.load_lines()
        self.refresh_summary()

    def on_scan_recorded(self):
        self.load_lines()
        self.refresh_summary()

    def mark_review(self):
        manager = self._manager()
        if not manager or not self.current_session_id:
            QMessageBox.warning(self, "Inventaire", "Selectionnez une session.")
            return
        if manager.mark_review(self.current_session_id):
            QMessageBox.information(self, "Inventaire", "Session envoyee en revue.")
        else:
            QMessageBox.warning(self, "Inventaire", "Impossible de passer la session en revue.")
        session_id = self.current_session_id
        self.load_sessions()
        self._select_session(session_id)

    def apply_session(self):
        manager = self._manager()
        if not manager or not self.current_session_id:
            QMessageBox.warning(self, "Inventaire", "Selectionnez une session.")
            return
        status = (self.current_session or {}).get("Status")
        if status not in {"Counting", "Review"}:
            QMessageBox.warning(self, "Inventaire", "Cette session ne peut pas etre appliquee.")
            return

        allow_unknown = False
        summary = manager.get_session_summary(self.current_session_id)
        if summary.get("UNKNOWN", 0):
            confirm_unknown = QMessageBox.question(
                self,
                "Inventaire",
                "Des codes inconnus existent. Voulez-vous les ignorer et appliquer quand meme ?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            allow_unknown = confirm_unknown == QMessageBox.Yes
            if not allow_unknown:
                return

        confirm = QMessageBox.question(
            self,
            "Inventaire",
            "Appliquer les ecarts sur le stock programme ?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return

        result = manager.apply_session(self.current_session_id, self._user_id(), allow_unknown=allow_unknown)
        if result.get("success"):
            QMessageBox.information(self, "Inventaire", result.get("message", "Inventaire applique."))
        else:
            conflicts = result.get("conflicts") or []
            details = f"\nConflits: {len(conflicts)}" if conflicts else ""
            QMessageBox.warning(self, "Inventaire", f"{result.get('message', 'Echec application.')}{details}")

        session_id = self.current_session_id
        self.load_sessions()
        self._select_session(session_id)

    def cancel_session(self):
        manager = self._manager()
        if not manager or not self.current_session_id:
            QMessageBox.warning(self, "Inventaire", "Selectionnez une session.")
            return
        status = (self.current_session or {}).get("Status")
        if status in {"Applied", "Cancelled"}:
            QMessageBox.warning(self, "Inventaire", "Cette session ne peut pas etre annulee.")
            return
        confirm = QMessageBox.question(
            self,
            "Inventaire",
            "Annuler cette session d'inventaire ?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        result = manager.cancel_session(self.current_session_id, self._user_id())
        if result.get("success"):
            QMessageBox.information(self, "Inventaire", result.get("message", "Session annulee."))
        else:
            QMessageBox.warning(self, "Inventaire", result.get("message", "Impossible d'annuler."))
        self.load_sessions()

    def export_session(self):
        manager = self._manager()
        if not manager or not self.current_session_id:
            QMessageBox.warning(self, "Inventaire", "Selectionnez une session.")
            return

        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "Exporter inventaire",
            f"inventaire_{self.current_session_id}.xlsx",
            "Excel (*.xlsx)",
        )
        if not output_path:
            return
        if not output_path.lower().endswith(".xlsx"):
            output_path += ".xlsx"

        result = manager.export_session_to_excel(self.current_session_id, output_path)
        if result.get("success"):
            QMessageBox.information(self, "Inventaire", result.get("message", "Export termine."))
        else:
            QMessageBox.warning(self, "Inventaire", result.get("message", "Export impossible."))
