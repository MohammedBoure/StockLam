import json
import logging
import random
import string
from decimal import Decimal

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QCompleter,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QInputDialog,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ui.formatting import format_money, format_quantity

from .inventory_count_scan_dialog import InventoryCountScanDialog


INVENTORY_STYLE = """
QWidget#inventoryCountPage {
    background: #f5f7fb;
    color: #243447;
}
QFrame#inventorySidebar,
QFrame#inventoryFilters {
    background: #ffffff;
    border: 1px solid #dfe6ee;
    border-radius: 8px;
}
QLabel#inventoryContext {
    color: #607080;
    font-size: 12px;
    font-weight: 700;
}
QLabel#sidebarSectionTitle {
    color: #607080;
    font-size: 12px;
    font-weight: 800;
}
QPushButton {
    background: #eef3f7;
    border: 1px solid #cfd9e2;
    border-radius: 5px;
    color: #243447;
    font-size: 13px;
    font-weight: 800;
    min-height: 32px;
    padding: 5px 9px;
    text-align: left;
}
QPushButton:hover {
    background: #e2ebf2;
}
QPushButton:disabled {
    background: #f4f6f8;
    border-color: #d8e0e8;
    color: #95a5a6;
}
QLineEdit,
QComboBox,
QTextEdit {
    background: #ffffff;
    border: 1px solid #cfd9e2;
    border-radius: 5px;
    color: #243447;
    min-height: 26px;
    padding: 4px 7px;
}
QTableWidget {
    background: #ffffff;
    alternate-background-color: #f8fafc;
    border: 1px solid #dfe6ee;
    gridline-color: #edf1f5;
    selection-background-color: #d7f0ee;
    selection-color: #1f2d3d;
    font-size: 12px;
}
QHeaderView::section {
    background: #eef3f7;
    border: 0;
    border-right: 1px solid #dfe6ee;
    border-bottom: 1px solid #dfe6ee;
    color: #52616f;
    font-size: 12px;
    font-weight: 800;
    padding: 6px 8px;
}
QSplitter::handle {
    background: #dfe6ee;
}
QSplitter::handle:horizontal {
    width: 5px;
}
QSplitter::handle:vertical {
    height: 5px;
}
QFrame#summaryRow {
    background: #ffffff;
    border: none;
}
QLabel#summaryTitle {
    color: #52616f;
    font-size: 13px;
    font-weight: 800;
}
QLabel#summaryValue {
    color: #243447;
    font-size: 13px;
    font-weight: 800;
}
"""


class NewInventorySessionDialog(QDialog):
    def __init__(self, data_manager=None, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.scope_options = {
            "ALL": [],
            "LOCATION": [],
            "FAMILY": [],
            "PRODUCT": [],
        }
        self.product_search_limit = 80
        self.product_search_min_chars = 2
        self.setWindowTitle("Nouvelle session inventaire")
        self.setMinimumWidth(480)
        self.resize(620, 420)
        self.setStyleSheet(INVENTORY_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        form = QFormLayout()
        form.setSpacing(10)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Inventaire mensuel")
        form.addRow("Nom", self.name_input)

        self.scope_combo = QComboBox()
        self.scope_combo.addItems(["ALL", "LOCATION", "FAMILY", "PRODUCT"])
        self.scope_combo.currentTextChanged.connect(self.update_scope_selector)
        form.addRow("Scope", self.scope_combo)

        self.scope_selector = QComboBox()
        self.scope_selector.setEditable(True)
        self.scope_selector.setInsertPolicy(QComboBox.NoInsert)
        self.scope_selector.setMinimumWidth(320)
        self.scope_selector.lineEdit().setPlaceholderText("Rechercher et choisir...")
        completer = self.scope_selector.completer()
        if completer:
            completer.setCompletionMode(QCompleter.PopupCompletion)
            completer.setFilterMode(Qt.MatchContains)
            completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.scope_selector.lineEdit().textEdited.connect(self.schedule_scope_search)
        form.addRow("Choix", self.scope_selector)

        self.scope_search_timer = QTimer(self)
        self.scope_search_timer.setSingleShot(True)
        self.scope_search_timer.timeout.connect(self.load_product_scope_options)

        self.notes_input = QTextEdit()
        self.notes_input.setFixedHeight(80)
        form.addRow("Notes", self.notes_input)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.load_scope_options()
        self.update_scope_selector(self.scope_combo.currentText())

    def load_scope_options(self):
        if not self.data_manager:
            return

        try:
            locations = self.data_manager.locations.get_all_locations()
            self.scope_options["LOCATION"] = [
                (loc.get("Location_Name") or f"Location #{loc.get('Location_ID')}", loc.get("Location_ID"))
                for loc in locations
                if loc.get("Location_ID") is not None
            ]
        except Exception as exc:
            logging.error(f"Unable to load inventory scope locations: {exc}", exc_info=True)

        try:
            families = self.data_manager.families.get_all_families()
            self.scope_options["FAMILY"] = [
                (family.get("Family_Name") or f"Family #{family.get('Family_ID')}", family.get("Family_ID"))
                for family in families
                if family.get("Family_ID") is not None
            ]
        except Exception as exc:
            logging.error(f"Unable to load inventory scope families: {exc}", exc_info=True)

        self.scope_options["PRODUCT"] = []

    def _product_scope_label(self, product):
        name = product.get("Product_Name") or f"Product #{product.get('Product_ID')}"
        family = product.get("Family_Name") or "-"
        barcode = product.get("Barcode") or product.get("Manuf_Cat_No") or "-"
        return f"{name} | {family} | {barcode}"

    def _populate_scope_selector(self, options, preserve_text=None):
        self.scope_selector.blockSignals(True)
        self.scope_selector.clear()
        for label, value in options:
            self.scope_selector.addItem(label, value)
        self.scope_selector.setCurrentIndex(-1)
        if preserve_text is not None:
            self.scope_selector.lineEdit().setText(preserve_text)
        self.scope_selector.blockSignals(False)

    def schedule_scope_search(self, text):
        if self.scope_combo.currentText() != "PRODUCT":
            return

        search_text = text.strip()
        if len(search_text) < self.product_search_min_chars:
            self.scope_search_timer.stop()
            self.scope_options["PRODUCT"] = []
            return

        self.scope_search_timer.start(280)

    def load_product_scope_options(self):
        if not self.data_manager or self.scope_combo.currentText() != "PRODUCT":
            return

        search_text = self.scope_selector.currentText().strip()
        if len(search_text) < self.product_search_min_chars:
            return

        try:
            products = self.data_manager.products.search_products(search_text, limit=self.product_search_limit)
            self.scope_options["PRODUCT"] = [
                (self._product_scope_label(product), product.get("Product_ID"))
                for product in products
                if product.get("Product_ID") is not None
            ]
            self._populate_scope_selector(self.scope_options["PRODUCT"], preserve_text=search_text)
            if self.scope_options["PRODUCT"]:
                self.scope_selector.showPopup()
        except Exception as exc:
            logging.error(f"Unable to search inventory scope products: {exc}", exc_info=True)

    def update_scope_selector(self, scope_type):
        self.scope_selector.clear()
        if scope_type == "ALL":
            self.scope_selector.addItem("Tout le stock", None)
            self.scope_selector.setEnabled(False)
            return

        self.scope_selector.setEnabled(True)
        if scope_type == "PRODUCT":
            self.scope_options["PRODUCT"] = []
            self.scope_selector.lineEdit().setPlaceholderText("Tapez au moins 2 caracteres...")
            self.scope_selector.setCurrentIndex(-1)
            return

        self.scope_selector.lineEdit().setPlaceholderText("Rechercher et choisir...")
        for label, value in self.scope_options.get(scope_type, []):
            self.scope_selector.addItem(label, value)
        self.scope_selector.setCurrentIndex(-1)

    def selected_scope_id(self):
        scope_type = self.scope_combo.currentText()
        if scope_type == "ALL":
            return None

        text = self.scope_selector.currentText().strip()
        if not text:
            return None

        exact_index = self.scope_selector.findText(text, Qt.MatchFixedString)
        if exact_index < 0:
            return None
        return self.scope_selector.itemData(exact_index)

    def values(self):
        return {
            "name": self.name_input.text().strip(),
            "scope_type": self.scope_combo.currentText(),
            "scope_id": self.selected_scope_id(),
            "notes": self.notes_input.toPlainText().strip() or None,
        }


class SummaryCard(QFrame):
    def __init__(self, title, accent="#007572"):
        super().__init__()
        self.setObjectName("summaryRow")
        self.setMinimumHeight(32)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(6)

        self.title_label = QLabel(f"{title}:")
        self.title_label.setObjectName("summaryTitle")
        self.value_label = QLabel("0")
        self.value_label.setObjectName("summaryValue")
        self.value_label.setStyleSheet(f"color: {accent};")
        layout.addWidget(self.title_label)
        layout.addStretch()
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
        self.setObjectName("inventoryCountPage")
        self.setStyleSheet(INVENTORY_STYLE)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        main_splitter = QSplitter(Qt.Horizontal)
        main_splitter.setChildrenCollapsible(False)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        tables_splitter = QSplitter(Qt.Vertical)
        tables_splitter.setChildrenCollapsible(False)

        self.sessions_table = QTableWidget(0, 5)
        self.sessions_table.setHorizontalHeaderLabels([
            "ID Session",
            "Nom Session",
            "Statut",
            "Débutée le",
            "Créée par",
        ])
        self.sessions_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.sessions_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.sessions_table.itemSelectionChanged.connect(self.load_current_session)
        self._configure_sessions_table()
        tables_splitter.addWidget(self.sessions_table)

        lines_panel = QWidget()
        lines_layout = QVBoxLayout(lines_panel)
        lines_layout.setContentsMargins(0, 0, 0, 0)
        lines_layout.setSpacing(0)

        self.lines_table = QTableWidget(0, 10)
        self.lines_table.setHorizontalHeaderLabels([
            "Produit",
            "Code-barres",
            "Lot",
            "Expiration",
            "Emplacement",
            "Stock\nProgrammé",
            "Stock\nCompté",
            "Écart",
            "Statut",
            "Commentaire",
        ])
        self.lines_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.lines_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._configure_lines_table()
        lines_layout.addWidget(self.lines_table)
        tables_splitter.addWidget(lines_panel)
        tables_splitter.setStretchFactor(0, 2)
        tables_splitter.setStretchFactor(1, 3)
        left_layout.addWidget(tables_splitter)

        sidebar = QFrame()
        sidebar.setObjectName("inventorySidebar")
        sidebar.setMinimumWidth(200)
        sidebar.setMaximumWidth(250)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(10, 10, 10, 10)
        sidebar_layout.setSpacing(10)

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

        action_buttons = (
            self.btn_new,
            self.btn_scan,
            self.btn_review,
            self.btn_apply,
            self.btn_cancel,
            self.btn_export,
            self.btn_refresh,
        )
        for button in action_buttons:
            button.setMinimumWidth(0)
            button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            sidebar_layout.addWidget(button)

        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setLineWidth(2)
        separator.setStyleSheet("background: #dfe6ee; min-height: 1px;")
        sidebar_layout.addWidget(separator)

        self.summary_cards = {
            "OK": SummaryCard("OK", "#238b55"),
            "SHORT": SummaryCard("Manquant", "#c0392b"),
            "EXCESS": SummaryCard("Excédent", "#d68910"),
            "NOT_COUNTED": SummaryCard("Non compté", "#607080"),
            "UNKNOWN": SummaryCard("Inconnu", "#8e44ad"),
            "Estimated_Variance_Value": SummaryCard("Valeur écart", "#007572"),
        }
        for card in self.summary_cards.values():
            sidebar_layout.addWidget(card)

        filters_frame = QFrame()
        filters_frame.setObjectName("inventoryFilters")
        filters_layout = QVBoxLayout(filters_frame)
        filters_layout.setContentsMargins(8, 8, 8, 8)
        filters_layout.setSpacing(6)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Recherche")
        self.search_input.textChanged.connect(self.load_lines)
        filters_layout.addWidget(self.search_input)

        self.status_filter = QComboBox()
        self.status_filter.addItems(["Tous", "OK", "Manquant", "Excédent", "Non compté", "Inconnu"])
        self.status_filter.currentTextChanged.connect(self.load_lines)
        filters_layout.addWidget(self.status_filter)
        sidebar_layout.addSpacing(4)
        sidebar_layout.addWidget(filters_frame)

        self.session_context_label = QLabel("Aucune session")
        self.session_context_label.setObjectName("inventoryContext")
        self.session_context_label.setWordWrap(True)
        sidebar_layout.addWidget(self.session_context_label)
        sidebar_layout.addStretch()

        main_splitter.addWidget(left_panel)
        main_splitter.addWidget(sidebar)
        main_splitter.setStretchFactor(0, 1)
        main_splitter.setStretchFactor(1, 0)
        main_splitter.setSizes([1000, 220])
        layout.addWidget(main_splitter)

    def _configure_table(self, table):
        table.setAlternatingRowColors(True)
        table.setShowGrid(True)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(28)
        table.horizontalHeader().setHighlightSections(False)
        table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        table.setWordWrap(False)
        table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)

    def _configure_sessions_table(self):
        self._configure_table(self.sessions_table)
        header = self.sessions_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)

    def _configure_lines_table(self):
        self._configure_table(self.lines_table)
        header = self.lines_table.horizontalHeader()
        header.setMinimumHeight(42)
        header.setMinimumSectionSize(84)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        for column in range(1, 9):
            header.setSectionResizeMode(column, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(9, QHeaderView.Stretch)

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
        if has_session:
            name = (self.current_session or {}).get("Session_Name") or f"Session #{self.current_session_id}"
            self.session_context_label.setText(f"#{self.current_session_id} - {name} - {status or '-'}")
        else:
            self.session_context_label.setText("Aucune session")
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

        status_text = self.status_filter.currentText()
        status_map = {
            "Tous": None,
            "OK": "OK",
            "Manquant": "SHORT",
            "Excédent": "EXCESS",
            "Non compté": "NOT_COUNTED",
            "Inconnu": "UNKNOWN"
        }
        status = status_map.get(status_text)
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

        dialog = NewInventorySessionDialog(self.data_manager, self)
        if dialog.exec() != QDialog.Accepted:
            return

        values = dialog.values()
        if not values["name"]:
            QMessageBox.warning(self, "Inventaire", "Le nom de la session est obligatoire.")
            return
        if values["scope_type"] != "ALL" and values["scope_id"] is None:
            QMessageBox.warning(self, "Inventaire", "Veuillez choisir un element valide pour le scope.")
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

    def _confirm_sensitive_action(self, title, action_text):
        alphabet = "".join(ch for ch in string.ascii_uppercase if ch not in "IO")
        code = "".join(random.choice(alphabet) for _ in range(3))
        prompt = (
            f"{action_text}\n\n"
            f"Pour confirmer, tapez exactement ce code de 3 lettres : {code}"
        )
        typed, accepted = QInputDialog.getText(self, title, prompt, QLineEdit.Normal, "")
        if not accepted:
            return False
        if typed.strip().upper() != code:
            QMessageBox.warning(
                self,
                title,
                "Code de confirmation incorrect. Operation annulee.",
            )
            return False
        return True

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

        uncounted_qty = summary.get("NOT_COUNTED", 0)
        uncounted_action = "ignore"
        if uncounted_qty > 0:
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Inventaire")
            msg_box.setText(f"Il y a {uncounted_qty} produits non comptés. Que voulez-vous faire ?")
            
            btn_ignore = msg_box.addButton("Ignorer (Garder le stock)", QMessageBox.ActionRole)
            btn_zero = msg_box.addButton("Mettre à zéro", QMessageBox.DestructiveRole)
            btn_cancel = msg_box.addButton("Annuler", QMessageBox.RejectRole)
            
            msg_box.exec()
            
            if msg_box.clickedButton() == btn_cancel:
                return
            elif msg_box.clickedButton() == btn_zero:
                uncounted_action = "zero"
            else:
                uncounted_action = "ignore"

        if not self._confirm_sensitive_action(
            "Inventaire",
            "Appliquer les ecarts sur le stock programme ? Cette operation modifie le stock reel.",
        ):
            return

        result = manager.apply_session(
            self.current_session_id, 
            self._user_id(), 
            allow_unknown=allow_unknown,
            uncounted_action=uncounted_action
        )
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
        if not self._confirm_sensitive_action(
            "Inventaire",
            "Annuler cette session d'inventaire ? Cette operation ferme la session sans appliquer les ecarts.",
        ):
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
