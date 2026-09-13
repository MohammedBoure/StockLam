import os
import logging
from datetime import datetime
from xml.sax.saxutils import escape as escape_xml
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget,
    QHeaderView, QPushButton, QLabel, QLineEdit,
    QComboBox, QDateEdit, QGroupBox, QTableWidgetItem,
    QAbstractItemView, QMessageBox, QFileDialog, QMenu,
    QFrame, QTabWidget
)
from PySide6.QtCore import Qt, QDate, Signal
from PySide6.QtGui import QFont, QColor
import qtawesome as qta
import json
from branding import get_banner_path
from ui.formatting import format_quantity, format_money

# ReportLab Imports
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False

from ui.widgets.settings.pdf.pdf_stamp import (
    FOOTER_TITLE_HEIGHT_CM,
    fit_stamp_size_cm,
    get_active_stamp,
    SignatureFooter,
    draw_stamp_image,
)
from ui.widgets.settings.local_settings import get_local_settings_store

class NumericTableWidgetItem(QTableWidgetItem):
    def __lt__(self, other):
        if other is None:
            return False
        v1 = self.data(Qt.UserRole)
        v2 = other.data(Qt.UserRole)
        if v1 is not None and v2 is not None:
            try:
                return float(v1) < float(v2)
            except (ValueError, TypeError):
                pass
        return super().__lt__(other)

class InvoicesListWidget(QWidget):
    """
    Interface for the list of invoices/delivery notes.
    Supports filtering, professional PDF export, and stock-safe deletion.
    """
    request_new = Signal(object)
    request_new_return = Signal(object)
    request_edit = Signal(int)
    request_pdf = Signal(int)
    request_delete = Signal(int)
    
    request_view_partner = Signal(int)
    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # --- 1. Filter Bar ---
        filter_group = QFrame()
        filter_group.setStyleSheet("QFrame { background-color: #f8f9fa; border: 1px solid #e0e0e0; border-radius: 6px; }")
        filter_layout = QHBoxLayout(filter_group)
        filter_layout.setContentsMargins(10, 6, 10, 6)
        filter_layout.setSpacing(8)

        self.date_from = QDateEdit(QDate.currentDate().addDays(-30))
        self.date_from.setCalendarPopup(True)
        self.date_from.setFixedWidth(135)

        self.date_to = QDateEdit(QDate.currentDate())
        self.date_to.setCalendarPopup(True)
        self.date_to.setFixedWidth(135)

        self.combo_filter_partner = QComboBox()
        self.combo_filter_partner.setMinimumWidth(200)
        self.load_partners()

        btn_filter = QPushButton(" Appliquer")
        btn_filter.setIcon(qta.icon("fa5s.filter", color="white"))
        btn_filter.setStyleSheet("background-color: #007572; color: white; font-weight: bold; padding: 6px 16px; border-radius: 4px;")
        btn_filter.clicked.connect(self.load_data)

        filter_layout.addWidget(QLabel("Du :"))
        filter_layout.addWidget(self.date_from)
        filter_layout.addWidget(QLabel("Au :"))
        filter_layout.addWidget(self.date_to)
        filter_layout.addWidget(QLabel("Sous-Traitant / Partenaire :"))
        filter_layout.addWidget(self.combo_filter_partner, stretch=1)
        filter_layout.addWidget(btn_filter)
        layout.addWidget(filter_group)

        # --- 2. Tabs: Bons de Livraison vs Bons de Retour ---
        self.tabs = QTabWidget()
        self.tabs.currentChanged.connect(self.on_tab_changed)

        # === Tab 1: Bons de Livraison ===
        self.tab_bl = QWidget()
        tab_bl_layout = QVBoxLayout(self.tab_bl)
        tab_bl_layout.setContentsMargins(8, 8, 8, 8)
        tab_bl_layout.setSpacing(8)

        bl_actions_bar = QHBoxLayout()
        self.search_input_bl = QLineEdit()
        self.search_input_bl.setPlaceholderText("🔍 Rechercher par N° BL ou par Client / Sous-Traitant...")
        self.search_input_bl.setMinimumHeight(35)
        self.search_input_bl.setClearButtonEnabled(True)
        self.search_input_bl.textChanged.connect(self.filter_table_bl)

        self.btn_new = QPushButton(" Nouveau BL")
        self.btn_new.setIcon(qta.icon("fa5s.file-export", color="white"))
        self.btn_new.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; border-radius: 4px; padding: 8px 15px;")
        self.btn_new.clicked.connect(self.on_new_clicked)

        self.btn_create_return_from_bl = QPushButton(" Créer Retour pour ce BL")
        self.btn_create_return_from_bl.setIcon(qta.icon("fa5s.file-import", color="white"))
        self.btn_create_return_from_bl.setStyleSheet("background-color: #8e44ad; color: white; font-weight: bold; border-radius: 4px; padding: 8px 15px;")
        self.btn_create_return_from_bl.setEnabled(False)
        self.btn_create_return_from_bl.clicked.connect(self.on_create_return_for_selected_bl)

        self.btn_edit_bl = QPushButton(" Modifier")
        self.btn_edit_bl.setIcon(qta.icon("fa5s.edit", color="white"))
        self.btn_edit_bl.setEnabled(False)
        self.btn_edit_bl.setStyleSheet("background-color: #f39c12; color: white; font-weight: bold; border-radius: 4px; padding: 8px 15px;")
        self.btn_edit_bl.clicked.connect(self.on_edit_bl_clicked)

        self.btn_pdf_bl = QPushButton(" Imprimer PDF")
        self.btn_pdf_bl.setIcon(qta.icon("fa5s.file-pdf", color="white"))
        self.btn_pdf_bl.setEnabled(False)
        self.btn_pdf_bl.setStyleSheet("background-color: #c0392b; color: white; font-weight: bold; border-radius: 4px; padding: 8px 15px;")
        self.btn_pdf_bl.clicked.connect(self.on_pdf_bl_clicked)

        self.btn_delete_bl = QPushButton(" Supprimer")
        self.btn_delete_bl.setIcon(qta.icon("fa5s.trash-alt", color="white"))
        self.btn_delete_bl.setEnabled(False)
        self.btn_delete_bl.setStyleSheet("background-color: #d35400; color: white; font-weight: bold; border-radius: 4px; padding: 8px 15px;")
        self.btn_delete_bl.clicked.connect(self.on_delete_bl_clicked)

        bl_actions_bar.addWidget(self.search_input_bl, stretch=1)
        bl_actions_bar.addWidget(self.btn_new)
        bl_actions_bar.addWidget(self.btn_create_return_from_bl)
        bl_actions_bar.addWidget(self.btn_edit_bl)
        bl_actions_bar.addWidget(self.btn_pdf_bl)
        bl_actions_bar.addWidget(self.btn_delete_bl)
        tab_bl_layout.addLayout(bl_actions_bar)

        self.table_bl = QTableWidget(0, 4)
        columns_bl = ["N° BL", "Date & Heure", "Client / Sous-Traitant", "Montant (DA)"]
        self.table_bl.setHorizontalHeaderLabels(columns_bl)

        header_bl = self.table_bl.horizontalHeader()
        header_bl.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header_bl.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header_bl.setSectionResizeMode(2, QHeaderView.Stretch)
        header_bl.setSectionResizeMode(3, QHeaderView.ResizeToContents)

        self.table_bl.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_bl.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table_bl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_bl.setAlternatingRowColors(True)
        self.table_bl.setSortingEnabled(True)
        header_bl.setSectionsClickable(True)
        self.table_bl.itemSelectionChanged.connect(self.on_bl_selection_changed)
        self.table_bl.cellDoubleClicked.connect(lambda r, c: self.on_edit_bl_clicked())
        self.table_bl.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_bl.customContextMenuRequested.connect(self.show_context_menu_bl)

        tab_bl_layout.addWidget(self.table_bl)

        # === Tab 2: Bons de Retour ===
        self.tab_br = QWidget()
        tab_br_layout = QVBoxLayout(self.tab_br)
        tab_br_layout.setContentsMargins(8, 8, 8, 8)
        tab_br_layout.setSpacing(8)

        br_actions_bar = QHBoxLayout()
        self.search_input_br = QLineEdit()
        self.search_input_br.setPlaceholderText("🔍 Rechercher par N° Bon de Retour, Client / Sous-Traitant, BL d'origine...")
        self.search_input_br.setMinimumHeight(35)
        self.search_input_br.setClearButtonEnabled(True)
        self.search_input_br.textChanged.connect(self.filter_table_br)

        self.btn_new_return = QPushButton(" Nouveau Bon de Retour")
        self.btn_new_return.setIcon(qta.icon("fa5s.file-import", color="white"))
        self.btn_new_return.setStyleSheet("background-color: #8e44ad; color: white; font-weight: bold; border-radius: 4px; padding: 8px 15px;")
        self.btn_new_return.clicked.connect(self.on_new_return_clicked)

        self.btn_view_orig_bl = QPushButton(" Voir BL d'origine")
        self.btn_view_orig_bl.setIcon(qta.icon("fa5s.file-invoice", color="white"))
        self.btn_view_orig_bl.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; border-radius: 4px; padding: 8px 15px;")
        self.btn_view_orig_bl.setEnabled(False)
        self.btn_view_orig_bl.clicked.connect(self.on_view_orig_bl_clicked)

        self.btn_edit_br = QPushButton(" Modifier")
        self.btn_edit_br.setIcon(qta.icon("fa5s.edit", color="white"))
        self.btn_edit_br.setEnabled(False)
        self.btn_edit_br.setStyleSheet("background-color: #f39c12; color: white; font-weight: bold; border-radius: 4px; padding: 8px 15px;")
        self.btn_edit_br.clicked.connect(self.on_edit_br_clicked)

        self.btn_pdf_br = QPushButton(" Imprimer PDF")
        self.btn_pdf_br.setIcon(qta.icon("fa5s.file-pdf", color="white"))
        self.btn_pdf_br.setEnabled(False)
        self.btn_pdf_br.setStyleSheet("background-color: #c0392b; color: white; font-weight: bold; border-radius: 4px; padding: 8px 15px;")
        self.btn_pdf_br.clicked.connect(self.on_pdf_br_clicked)

        self.btn_delete_br = QPushButton(" Supprimer")
        self.btn_delete_br.setIcon(qta.icon("fa5s.trash-alt", color="white"))
        self.btn_delete_br.setEnabled(False)
        self.btn_delete_br.setStyleSheet("background-color: #d35400; color: white; font-weight: bold; border-radius: 4px; padding: 8px 15px;")
        self.btn_delete_br.clicked.connect(self.on_delete_br_clicked)

        br_actions_bar.addWidget(self.search_input_br, stretch=1)
        br_actions_bar.addWidget(self.btn_new_return)
        br_actions_bar.addWidget(self.btn_view_orig_bl)
        br_actions_bar.addWidget(self.btn_edit_br)
        br_actions_bar.addWidget(self.btn_pdf_br)
        br_actions_bar.addWidget(self.btn_delete_br)
        tab_br_layout.addLayout(br_actions_bar)

        self.table_br = QTableWidget(0, 5)
        columns_br = ["N° Bon de Retour", "Date & Heure", "Client / Sous-Traitant", "BL d'origine", "Montant (DA)"]
        self.table_br.setHorizontalHeaderLabels(columns_br)

        header_br = self.table_br.horizontalHeader()
        header_br.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header_br.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header_br.setSectionResizeMode(2, QHeaderView.Stretch)
        header_br.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header_br.setSectionResizeMode(4, QHeaderView.ResizeToContents)

        self.table_br.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_br.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table_br.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_br.setAlternatingRowColors(True)
        self.table_br.setSortingEnabled(True)
        header_br.setSectionsClickable(True)
        self.table_br.itemSelectionChanged.connect(self.on_br_selection_changed)
        self.table_br.cellDoubleClicked.connect(self.on_br_cell_double_clicked)
        self.table_br.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_br.customContextMenuRequested.connect(self.show_context_menu_br)

        tab_br_layout.addWidget(self.table_br)

        # Add tabs
        self.tabs.addTab(self.tab_bl, "📦 Bons de Livraison")
        self.tabs.addTab(self.tab_br, "↩️ Bons de Retour")
        layout.addWidget(self.tabs)
        filter_group.raise_()

    @property
    def current_table(self):
        if hasattr(self, 'tabs') and self.tabs.currentIndex() == 1:
            return getattr(self, 'table_br', None)
        return getattr(self, 'table_bl', None)

    @property
    def table(self):
        """Compatibility property pointing to the currently active table."""
        return self.current_table

    @property
    def btn_edit(self):
        return self.btn_edit_br if (hasattr(self, 'tabs') and self.tabs.currentIndex() == 1) else self.btn_edit_bl

    @property
    def btn_pdf(self):
        return self.btn_pdf_br if (hasattr(self, 'tabs') and self.tabs.currentIndex() == 1) else self.btn_pdf_bl

    @property
    def btn_delete(self):
        return self.btn_delete_br if (hasattr(self, 'tabs') and self.tabs.currentIndex() == 1) else self.btn_delete_bl

    @property
    def search_input(self):
        return self.search_input_br if (hasattr(self, 'tabs') and self.tabs.currentIndex() == 1) else self.search_input_bl

    def on_tab_changed(self, index):
        if index == 0:
            self.on_bl_selection_changed()
        else:
            self.on_br_selection_changed()

    def on_new_clicked(self):
        partner_id = self.combo_filter_partner.currentData()
        self.request_new.emit(partner_id)

    def on_new_return_clicked(self):
        partner_id = self.get_selected_partner_id(self.table_br) or self.combo_filter_partner.currentData()
        self.request_new_return.emit({'partner_id': partner_id, 'ref_transfer_id': None})

    def on_create_return_for_selected_bl(self):
        tid = self.get_selected_id(self.table_bl)
        partner_id = self.get_selected_partner_id(self.table_bl)
        if not tid or not partner_id:
            QMessageBox.warning(self, "Attention", "Veuillez sélectionner un Bon de Livraison pour créer son Bon de Retour.")
            return
        self.request_new_return.emit({'partner_id': partner_id, 'ref_transfer_id': tid})

    def on_view_orig_bl_clicked(self):
        row = self.table_br.currentRow()
        if row >= 0:
            item = self.table_br.item(row, 0)
            if item:
                ref_tid = item.data(Qt.UserRole + 2)
                if ref_tid:
                    self.request_edit.emit(ref_tid)
                    return
        QMessageBox.information(self, "Information", "Ce bon de retour n'est lié à aucun Bon de Livraison d'origine.")

    def on_br_cell_double_clicked(self, row, column):
        if column == 3:
            item = self.table_br.item(row, 0)
            if item:
                ref_id = item.data(Qt.UserRole + 2)
                if ref_id:
                    self.request_edit.emit(ref_id)
                    return
        self.on_edit_br_clicked()

    def format_id(self, raw_id, date_str):
        """تحويل ID الرقمي إلى تنسيق YYYY/NNN"""
        try:
            year = date_str.split('-')[0] if date_str else str(datetime.now().year)
            return f"{year}/{int(raw_id):03d}"
        except:
            return str(raw_id)

    def _format_date_text(self, raw_date):
        if hasattr(raw_date, 'strftime'):
            return raw_date.strftime("%Y-%m-%d %H:%M")
        elif isinstance(raw_date, str) and raw_date:
            return raw_date[:16]
        return str(raw_date or "")

    def on_bl_selection_changed(self):
        has_sel = len(self.table_bl.selectedItems()) > 0
        self.btn_edit_bl.setEnabled(has_sel)
        self.btn_pdf_bl.setEnabled(has_sel)
        self.btn_delete_bl.setEnabled(has_sel)
        self.btn_create_return_from_bl.setEnabled(has_sel)

    def on_br_selection_changed(self):
        has_sel = len(self.table_br.selectedItems()) > 0
        self.btn_edit_br.setEnabled(has_sel)
        self.btn_pdf_br.setEnabled(has_sel)
        self.btn_delete_br.setEnabled(has_sel)
        has_ref = False
        if has_sel:
            row = self.table_br.currentRow()
            if row >= 0:
                item = self.table_br.item(row, 0)
                if item and item.data(Qt.UserRole + 2):
                    has_ref = True
        self.btn_view_orig_bl.setEnabled(has_ref)

    def on_selection_changed(self):
        self.on_bl_selection_changed()
        self.on_br_selection_changed()

    def get_selected_id(self, table=None):
        target_table = table or self.current_table
        if target_table:
            row = target_table.currentRow()
            if row >= 0:
                item = target_table.item(row, 0)
                if item:
                    return item.data(Qt.UserRole)
        return None

    def get_selected_partner_id(self, table=None):
        target_table = table or self.current_table
        if target_table:
            row = target_table.currentRow()
            if row >= 0:
                item = target_table.item(row, 0)
                if item:
                    return item.data(Qt.UserRole + 1)
        return None

    def show_context_menu_bl(self, pos):
        item = self.table_bl.itemAt(pos)
        if not item: return
        row = item.row()
        tid = self.table_bl.item(row, 0).data(Qt.UserRole)
        partner_id = self.table_bl.item(row, 0).data(Qt.UserRole + 1)

        menu = QMenu(self)
        action_return = menu.addAction("Créer un Bon de Retour pour ce BL")
        action_return.setIcon(qta.icon("fa5s.file-import", color="#8e44ad"))
        action_return.triggered.connect(lambda: self.request_new_return.emit({'partner_id': partner_id, 'ref_transfer_id': tid}))

        menu.addSeparator()

        action_edit = menu.addAction("Modifier ce BL")
        action_edit.setIcon(qta.icon("fa5s.edit", color="#f39c12"))
        action_edit.triggered.connect(lambda: self.request_edit.emit(tid))

        action_pdf = menu.addAction("Imprimer PDF")
        action_pdf.setIcon(qta.icon("fa5s.file-pdf", color="#c0392b"))
        action_pdf.triggered.connect(lambda: (self.request_pdf.emit(tid), self.export_transfer_to_pdf(tid)))

        action_delete = menu.addAction("Supprimer ce BL")
        action_delete.setIcon(qta.icon("fa5s.trash-alt", color="#d35400"))
        action_delete.triggered.connect(self.on_delete_bl_clicked)

        menu.addSeparator()

        action_partner = menu.addAction("Consulter le Sous-traitant (Profil)")
        action_partner.setIcon(qta.icon("fa5s.user-tie", color="#2980b9"))
        action_partner.triggered.connect(lambda: self.request_view_partner.emit(partner_id))

        menu.exec(self.table_bl.viewport().mapToGlobal(pos))

    def show_context_menu_br(self, pos):
        item = self.table_br.itemAt(pos)
        if not item: return
        row = item.row()
        tid = self.table_br.item(row, 0).data(Qt.UserRole)
        partner_id = self.table_br.item(row, 0).data(Qt.UserRole + 1)
        ref_transfer_id = self.table_br.item(row, 0).data(Qt.UserRole + 2)

        menu = QMenu(self)
        if ref_transfer_id:
            action_orig = menu.addAction("Consulter le BL d'origine")
            action_orig.setIcon(qta.icon("fa5s.file-invoice", color="#27ae60"))
            action_orig.triggered.connect(lambda: self.request_edit.emit(ref_transfer_id))
            menu.addSeparator()

        action_edit = menu.addAction("Modifier ce Bon de Retour")
        action_edit.setIcon(qta.icon("fa5s.edit", color="#f39c12"))
        action_edit.triggered.connect(lambda: self.request_edit.emit(tid))

        action_pdf = menu.addAction("Imprimer PDF")
        action_pdf.setIcon(qta.icon("fa5s.file-pdf", color="#c0392b"))
        action_pdf.triggered.connect(lambda: (self.request_pdf.emit(tid), self.export_transfer_to_pdf(tid)))

        action_delete = menu.addAction("Supprimer ce Bon de Retour")
        action_delete.setIcon(qta.icon("fa5s.trash-alt", color="#d35400"))
        action_delete.triggered.connect(self.on_delete_br_clicked)

        menu.addSeparator()

        action_partner = menu.addAction("Consulter le Sous-traitant (Profil)")
        action_partner.setIcon(qta.icon("fa5s.user-tie", color="#2980b9"))
        action_partner.triggered.connect(lambda: self.request_view_partner.emit(partner_id))

        menu.exec(self.table_br.viewport().mapToGlobal(pos))

    def show_context_menu(self, pos):
        if hasattr(self, 'tabs') and self.tabs.currentIndex() == 1:
            self.show_context_menu_br(pos)
        else:
            self.show_context_menu_bl(pos)

    def on_edit_bl_clicked(self):
        tid = self.get_selected_id(self.table_bl)
        if tid: self.request_edit.emit(tid)

    def on_edit_br_clicked(self):
        tid = self.get_selected_id(self.table_br)
        if tid: self.request_edit.emit(tid)

    def on_edit_clicked(self):
        tid = self.get_selected_id()
        if tid: self.request_edit.emit(tid)

    def on_pdf_bl_clicked(self):
        tid = self.get_selected_id(self.table_bl)
        if tid:
            self.request_pdf.emit(tid)
            self.export_transfer_to_pdf(tid)

    def on_pdf_br_clicked(self):
        tid = self.get_selected_id(self.table_br)
        if tid:
            self.request_pdf.emit(tid)
            self.export_transfer_to_pdf(tid)

    def on_pdf_clicked(self):
        tid = self.get_selected_id()
        if tid:
            self.request_pdf.emit(tid)
            self.export_transfer_to_pdf(tid)

    def on_delete_bl_clicked(self):
        self._delete_transfer_from_table(self.table_bl, "Bon de Livraison")

    def on_delete_br_clicked(self):
        self._delete_transfer_from_table(self.table_br, "Bon de Retour")

    def on_delete_clicked(self):
        target_table = self.current_table
        doc_type = "Bon de Retour" if target_table == self.table_br else "Bon de Livraison"
        self._delete_transfer_from_table(target_table, doc_type)

    def _delete_transfer_from_table(self, target_table, doc_type):
        tid = self.get_selected_id(target_table)
        if not tid: return

        reply = QMessageBox.question(
            self, "Confirmation",
            f"Voulez-vous vraiment supprimer le {doc_type} N° {tid} ?\n"
            "Cette action restaurera les quantités dans le stock.",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                success, msg = self.manager.external_transfers.delete_transfer_and_restore_stock(tid)
                if success:
                    QMessageBox.information(self, "Succès", msg)
                    self.load_data()
                else:
                    QMessageBox.warning(self, "Erreur", msg)
            except Exception as e:
                logging.error(f"Error deleting transfer: {e}")
                QMessageBox.critical(self, "Erreur", str(e))

    def load_partners(self):
        self.combo_filter_partner.clear()
        self.combo_filter_partner.addItem("Tous les partenaires", None)
        if hasattr(self.manager, 'partners'):
            for p in self.manager.partners.get_all_partners():
                self.combo_filter_partner.addItem(p['Partner_Name'], p['Partner_ID'])

    def load_data(self):
        start = self.date_from.date().toString("yyyy-MM-dd")
        end = self.date_to.date().toString("yyyy-MM-dd") + " 23:59:59"
        p_id = self.combo_filter_partner.currentData()

        if not hasattr(self.manager, 'external_transfers'):
            return

        transfers = self.manager.external_transfers.get_transfers_filtered(start, end, p_id, None)

        ref_map = {}
        for t in transfers:
            tid = t['Transfer_ID']
            ref_map[tid] = t.get('Display_Ref') or self.format_id(tid, str(t.get('Transaction_Date', '')))

        bl_transfers = [t for t in transfers if (t.get('Transfer_Type') or 'Outbound') != 'Return']
        br_transfers = [t for t in transfers if (t.get('Transfer_Type') or 'Outbound') == 'Return']

        font_bold = QFont()
        font_bold.setBold(True)

        # 1. Bons de Livraison
        self.table_bl.setSortingEnabled(False)
        self.table_bl.setRowCount(0)
        for row, t in enumerate(bl_transfers):
            self.table_bl.insertRow(row)

            formatted_ref = t.get('Display_Ref') or self.format_id(t['Transfer_ID'], str(t.get('Transaction_Date', '')))
            id_item = NumericTableWidgetItem(formatted_ref)
            id_item.setTextAlignment(Qt.AlignCenter)
            id_item.setFont(font_bold)
            id_item.setForeground(QColor("#27ae60"))
            id_item.setData(Qt.UserRole, t['Transfer_ID'])
            id_item.setData(Qt.UserRole + 1, t.get('Partner_ID'))
            id_item.setData(Qt.UserRole + 2, t.get('Ref_Transfer_ID'))

            date_text = self._format_date_text(t.get('Transaction_Date'))
            date_item = QTableWidgetItem(date_text)
            date_item.setTextAlignment(Qt.AlignCenter)

            partner_text = t.get('Partner_Name') or t.get('City') or "-"
            partner_item = QTableWidgetItem(str(partner_text))

            amount = float(t.get('Total_Amount') or 0)
            amount_item = NumericTableWidgetItem(format_money(amount, 'DA'))
            amount_item.setData(Qt.UserRole, amount)
            amount_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            amount_item.setFont(font_bold)

            self.table_bl.setItem(row, 0, id_item)
            self.table_bl.setItem(row, 1, date_item)
            self.table_bl.setItem(row, 2, partner_item)
            self.table_bl.setItem(row, 3, amount_item)

        self.table_bl.setSortingEnabled(True)
        self.table_bl.resizeColumnsToContents()
        self.table_bl.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.on_bl_selection_changed()
        self.filter_table_bl(self.search_input_bl.text())

        # 2. Bons de Retour
        self.table_br.setSortingEnabled(False)
        self.table_br.setRowCount(0)
        for row, t in enumerate(br_transfers):
            self.table_br.insertRow(row)

            formatted_ref = t.get('Display_Ref') or self.format_id(t['Transfer_ID'], str(t.get('Transaction_Date', '')))
            id_item = NumericTableWidgetItem(formatted_ref)
            id_item.setTextAlignment(Qt.AlignCenter)
            id_item.setFont(font_bold)
            id_item.setForeground(QColor("#8e44ad"))
            id_item.setData(Qt.UserRole, t['Transfer_ID'])
            id_item.setData(Qt.UserRole + 1, t.get('Partner_ID'))
            id_item.setData(Qt.UserRole + 2, t.get('Ref_Transfer_ID'))

            date_text = self._format_date_text(t.get('Transaction_Date'))
            date_item = QTableWidgetItem(date_text)
            date_item.setTextAlignment(Qt.AlignCenter)

            partner_text = t.get('Partner_Name') or t.get('City') or "-"
            partner_item = QTableWidgetItem(str(partner_text))

            ref_id = t.get('Ref_Transfer_ID')
            if ref_id:
                orig_ref = ref_map.get(ref_id)
                if not orig_ref and hasattr(self.manager.external_transfers, 'get_transfer_by_id'):
                    try:
                        orig_t = self.manager.external_transfers.get_transfer_by_id(ref_id)
                        if orig_t:
                            orig_ref = orig_t.get('Display_Ref') or self.format_id(ref_id, str(orig_t.get('Transaction_Date', '')))
                            ref_map[ref_id] = orig_ref
                    except Exception:
                        pass
                orig_ref_text = orig_ref or f"BL #{ref_id}"
            else:
                orig_ref_text = "-"

            orig_bl_item = QTableWidgetItem(orig_ref_text)
            orig_bl_item.setTextAlignment(Qt.AlignCenter)
            if ref_id:
                orig_bl_item.setForeground(QColor("#007572"))
                orig_bl_item.setFont(font_bold)
                orig_bl_item.setToolTip(f"Double-cliquez pour ouvrir le BL d'origine ({orig_ref_text})")

            amount = float(t.get('Total_Amount') or 0)
            amount_item = NumericTableWidgetItem(format_money(amount, 'DA'))
            amount_item.setData(Qt.UserRole, amount)
            amount_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            amount_item.setFont(font_bold)

            self.table_br.setItem(row, 0, id_item)
            self.table_br.setItem(row, 1, date_item)
            self.table_br.setItem(row, 2, partner_item)
            self.table_br.setItem(row, 3, orig_bl_item)
            self.table_br.setItem(row, 4, amount_item)

        self.table_br.setSortingEnabled(True)
        self.table_br.resizeColumnsToContents()
        self.table_br.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.on_br_selection_changed()
        self.filter_table_br(self.search_input_br.text())

        # 3. Update Tab Titles with Counts
        self.tabs.setTabText(0, f"📦 Bons de Livraison ({len(bl_transfers)})")
        self.tabs.setTabText(1, f"↩️ Bons de Retour ({len(br_transfers)})")

    def filter_table_bl(self, text=None):
        if text is None:
            text = self.search_input_bl.text()
        text_lower = text.strip().lower()
        for r in range(self.table_bl.rowCount()):
            match = not text_lower or any(
                text_lower in (self.table_bl.item(r, col).text().lower() if self.table_bl.item(r, col) else "")
                for col in range(self.table_bl.columnCount())
            )
            self.table_bl.setRowHidden(r, not match)

    def filter_table_br(self, text=None):
        if text is None:
            text = self.search_input_br.text()
        text_lower = text.strip().lower()
        for r in range(self.table_br.rowCount()):
            match = not text_lower or any(
                text_lower in (self.table_br.item(r, col).text().lower() if self.table_br.item(r, col) else "")
                for col in range(self.table_br.columnCount())
            )
            self.table_br.setRowHidden(r, not match)

    def filter_table(self, text):
        self.filter_table_bl(text)
        self.filter_table_br(text)

    @staticmethod
    def _pdf_setting_enabled(settings, key, default=True):
        value = settings.get(key, default)
        if isinstance(value, str):
            return value.strip().lower() not in {"0", "false", "no", "non", "off", ""}
        return bool(value)

    @staticmethod
    def _partner_value(partner_info, *field_names):
        # Read Master Data fields while tolerating DB-driver key casing.
        if not isinstance(partner_info, dict):
            return ""
        values_by_lower_name = {str(key).lower(): value for key, value in partner_info.items()}
        for field_name in field_names:
            value = values_by_lower_name.get(str(field_name).lower())
            if value not in (None, ""):
                return value
        return ""

    @classmethod
    def _partner_pdf_lines(cls, partner_info, settings):
        value = cls._partner_value
        lines = []

        def text(raw):
            if raw is None:
                return ""
            result = str(raw).replace("\n", " ").replace("\r", " ").strip()
            return "" if result.lower() in {"none", "null", "n/a", "-", "."} else result

        def add(label, raw):
            cleaned = text(raw)
            if cleaned:
                lines.append((label, cleaned))

        def show(field_key, legacy_group_key=None):
            legacy_default = cls._pdf_setting_enabled(settings, legacy_group_key, True) if legacy_group_key else True
            return cls._pdf_setting_enabled(settings, field_key, legacy_default)

        if show("partner_show_contact_person", "partner_show_contact"):
            add("Contact :", value(partner_info, "Contact_Person", "Contact", "Correspondant"))
        if show("partner_show_phone", "partner_show_contact"):
            add("Tél. :", value(partner_info, "Phone", "Telephone", "Mobile"))
        if show("partner_show_email", "partner_show_contact"):
            add("Email :", value(partner_info, "Email", "E_mail"))
        if show("partner_show_website", "partner_show_contact"):
            add("Site web :", value(partner_info, "Website", "WebSite"))

        if show("partner_show_address_line1", "partner_show_address"):
            add("Adresse :", value(partner_info, "Address_Line1", "Address"))
        if show("partner_show_address_line2", "partner_show_address"):
            add("Adresse (complément) :", value(partner_info, "Address_Line2"))
        if show("partner_show_postal_code", "partner_show_address"):
            add("Code postal :", value(partner_info, "Postal_Code", "Zip_Code"))
        if show("partner_show_city", "partner_show_address"):
            add("Ville :", value(partner_info, "City"))

        if show("partner_show_type", "partner_show_identity"):
            add("Type :", value(partner_info, "Partner_Type"))
        if show("partner_show_agrement", "partner_show_identity"):
            add("Agrément :", value(partner_info, "Agrement_Number", "Agreement_Number"))
        if show("partner_show_tax_id", "partner_show_identity"):
            add("NIF :", value(partner_info, "Tax_ID_Number", "Tax_ID", "NIF"))
        if show("partner_show_commercial_reg", "partner_show_identity"):
            add("Reg. Commerce :", value(partner_info, "Commercial_Reg_No", "RC"))

        if show("partner_show_bank_name", "partner_show_bank"):
            add("Banque :", value(partner_info, "Bank_Name"))
        if show("partner_show_iban", "partner_show_bank"):
            add("RIB :", value(partner_info, "Bank_Account_IBAN", "IBAN"))

        return lines

    # =========================================================================
    # PDF Export Logic - PROFESSIONNAL & DYNAMIC (BL / BON DE RETOUR)
    # =========================================================================
    def export_transfer_to_pdf(self, transfer_id):
        """
        توليد ملف PDF احترافي يدعم كلاً من (Bon de Livraison) و (Bon de Retour)
        مع تنسيق وتصميم مخصص لكل حالة.
        """
        print("\n" + "🚀" * 10 + " PDF EXPORT START " + "🚀" * 10)

        if not HAS_REPORTLAB:
            QMessageBox.warning(self, "Erreur", "La bibliothèque 'reportlab' est manquante.")
            return

        # 1. تحديد المسارات وتحميل الإعدادات
        try:
            local_store = get_local_settings_store(self.manager)
            settings = local_store.load_merged_pdf_settings()
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Configuration error: {str(e)}")
            return

        # 2. جلب البيانات من قاعدة البيانات
        try:
            mgr = self.manager.external_transfers
            header_data = mgr.get_transfer_by_id(transfer_id)
            if not header_data:
                transfers = mgr.get_all_transfers()
                header_data = next((t for t in transfers if t['Transfer_ID'] == transfer_id), None)

            if not header_data:
                QMessageBox.warning(self, "Erreur", "Données introuvables.")
                return

            details_data = mgr.get_transfer_details(transfer_id)
            partner_info = self.manager.partners.get_partner_by_id(header_data['Partner_ID']) or {}
        except Exception as e:
            QMessageBox.critical(self, "Erreur BD", str(e))
            return

        # --- التمييز بين الإرجاع والبيع ---
        transfer_type = header_data.get('Transfer_Type', 'Outbound')
        is_return = (transfer_type == 'Return')
        document_title = settings.get('doc_title_rt', 'Retourné à Sous-Traitant') if is_return else settings.get('doc_title_bl', 'BON DE LIVRAISON')
        
        # استخراج المرجع المنسق
        raw_date = str(header_data.get('Transaction_Date', ''))
        try:
            year_val = raw_date.split('-')[0] if '-' in raw_date else str(datetime.now().year)
            formatted_ref = header_data.get('Display_Ref') or f"{year_val}/{int(transfer_id):03d}"
        except:
            formatted_ref = str(transfer_id)

        ref_bl_text = ""
        ref_id = header_data.get('Ref_Transfer_ID')
        if is_return and ref_id:
            ref_transfer = mgr.get_transfer_by_id(ref_id)
            if ref_transfer:
                ref_bl_display = ref_transfer.get('Display_Ref') or f"{year_val}/{int(ref_id):03d}"
                ref_bl_text = f"<br/><font color='#e67e22'><b>Réf. BL d'origine : {ref_bl_display}</b></font>"

        # 3. حوار حفظ الملف
        partner_clean = str(header_data.get('Partner_Name', 'Client')).replace(" ", "_")
        safe_ref_for_filename = formatted_ref.replace("/", "-")
        prefix_name = "BR" if is_return else "BL"
        default_name = f"{prefix_name}_{partner_clean}_{safe_ref_for_filename}.pdf"

        path, _ = QFileDialog.getSaveFileName(self, "Enregistrer PDF", default_name, "PDF Files (*.pdf)")
        if not path: return

        # 4. بناء المستند (ReportLab)
        try:
            PAGE_WIDTH, PAGE_HEIGHT = A4
            # تغيير لون الثيم بناءً على النوع (استخدام الثيم المحدد للجميع)
            default_color = settings.get('theme_color', '#0b666a')
            primary_color = colors.HexColor(default_color)
            banner_h_cm = settings.get('banner_height_cm', 4.8)

            elements = []
            styles = getSampleStyleSheet()

            current_time = datetime.now().strftime('%d/%m/%Y %H:%M')

            # --- الترويسة العلوية (المعلومات) ---
            lab_addr = settings.get('lab_address', '')
            lab_nif = settings.get('lab_nif', '')
            lab_rc = settings.get('lab_rc', '')

            lab_info_lines = [
                f"<font size=14 color='{default_color}'><b>{escape_xml(str(document_title))} N°: {escape_xml(str(formatted_ref))}</b></font>{ref_bl_text}<br/>"
            ]
            def clean_str(val):
                if not val: return ""
                v = str(val).replace('\n', '').replace('\r', '').strip()
                if v.lower() in ["none", "n/a", "null", "nan", "-", "", "."]:
                    return ""
                return v

            def safe_markup(val):
                return escape_xml(clean_str(val))

            if clean_str(lab_addr): lab_info_lines.append(f"<font size=9>{safe_markup(lab_addr)}</font>")
            if clean_str(lab_nif): lab_info_lines.append(f"<font size=9>NIF : {safe_markup(lab_nif)}</font>")
            if clean_str(lab_rc): lab_info_lines.append(f"<font size=9>RC : {safe_markup(lab_rc)}</font>")
            
            bank_name = settings.get('bank_name', '')
            bank_acc = settings.get('bank_acc', '')
            
            if clean_str(bank_name): lab_info_lines.append(f"<font size=9>Banque : {safe_markup(bank_name)}</font>")
            if clean_str(bank_acc): lab_info_lines.append(f"<font size=9>RIB : {safe_markup(bank_acc)}</font>")

            raw_date = header_data.get('Transaction_Date')
            if hasattr(raw_date, 'strftime'):
                bon_date = raw_date.strftime("%d/%m/%Y %H:%M")
            else:
                bon_date = str(raw_date or "")
                
            creation_date_text = f"Date de création : {current_time}"
            if bon_date:
                creation_date_text = f"Date du Bon : {bon_date}    |    {creation_date_text}"

            left_text_top = "<br/>".join(lab_info_lines)

            p_name = self._partner_value(partner_info, 'Partner_Name', 'Name') or 'Inconnu'
            label_key = 'dest_label_rt' if is_return else 'dest_label_bl'
            dest_label = clean_str(settings.get(label_key, ''))
            if dest_label.lower() in {'destinataire :', 'destinataire:', 'retourné à (sous-traitant) :'}:
                dest_label = 'Correspondant :'
            if not dest_label:
                dest_label = 'Correspondant :'

            right_text_lines = [
                f"<b>{safe_markup(dest_label)}</b>",
                "",
            ]
            if self._pdf_setting_enabled(settings, "partner_show_name", True):
                right_text_lines.append(f"<font size=11><b>{safe_markup(p_name)}</b></font>")
            for label, value in self._partner_pdf_lines(partner_info, settings):
                right_text_lines.append(f"{safe_markup(label)} {safe_markup(value)}")

            right_text = "<br/>".join(right_text_lines)

            header_info_x_cm = float(settings.get('header_info_x_cm', 1.0))
            header_info_y_cm = float(settings.get('header_info_y_cm', 5.4))
            header_info_w_cm = float(settings.get('header_info_w_cm', 9.5))
            creation_date_x_cm = float(settings.get('creation_date_x_cm', 1.0))
            creation_date_y_cm = float(settings.get('creation_date_y_cm', 9.3))
            date_p = Paragraph(f"<font size=9>{safe_markup(creation_date_text)}</font>", styles["Normal"])
            date_w, date_h = date_p.wrap(10.0 * cm, 1.0 * cm)

            left_p = Paragraph(left_text_top, styles["Normal"])
            left_w, left_h = left_p.wrap(header_info_w_cm * cm, 6.0 * cm)
            right_p = Paragraph(right_text, styles["Normal"])
            dest_w_cm = float(settings.get('dest_box_w_cm', 8.0))
            right_w, right_h = right_p.wrap(max(1.0, dest_w_cm - 0.5) * cm, 10.0 * cm)
            configured_dest_h_cm = float(settings.get('dest_box_h_cm', 6.5))
            dest_box_h = max(right_h + 1.0 * cm, configured_dest_h_cm * cm, 2.5 * cm)

            requested_table_y_cm = float(settings.get('table_start_y_cm', 10.5))
            safe_table_y_cm = max(
                requested_table_y_cm,
                header_info_y_cm + left_h / cm + 0.35,
                creation_date_y_cm + date_h / cm + 0.35,
                float(settings.get('dest_box_y_cm', 5.4)) + dest_box_h / cm + 0.35,
            )
            table_start_x_cm = float(settings.get('table_start_x_cm', 1.0))

            doc = SimpleDocTemplate(
                path, pagesize=A4, rightMargin=1.0 * cm, leftMargin=1.0 * cm,
                topMargin=safe_table_y_cm * cm, bottomMargin=50
            )

            def draw_header_compact(canvas, doc):
                canvas.saveState()
                img_x = settings.get('banner_img_x_cm', 0.0) * cm
                img_w = settings.get('banner_img_w_cm', 21.0) * cm
                img_h = settings.get('banner_img_h_cm', 4.8) * cm
                y_offset = settings.get('banner_img_y_cm', 0.2) * cm
                img_y = PAGE_HEIGHT - img_h - y_offset

                img_bytes = local_store.load_banner_bytes(settings)
                if img_bytes:
                    from reportlab.lib.utils import ImageReader
                    import io
                    img = ImageReader(io.BytesIO(img_bytes))
                    canvas.drawImage(img, img_x, img_y, width=img_w, height=img_h)
                else:
                    canvas.setStrokeColor(colors.red)
                    canvas.rect(img_x, img_y, img_w, img_h, stroke=1)
                    
                left_p.drawOn(
                    canvas,
                    header_info_x_cm * cm,
                    PAGE_HEIGHT - header_info_y_cm * cm - left_h,
                )

                dest_x = settings.get('dest_box_x_cm', 11.5) * cm
                dest_y_abs = PAGE_HEIGHT - settings.get('dest_box_y_cm', 5.4) * cm
                dest_w = dest_w_cm * cm
                box_h = dest_box_h

                canvas.setFillColor(colors.HexColor("#f8f9fa"))
                canvas.setStrokeColor(colors.lightgrey)
                canvas.setLineWidth(0.5)
                canvas.rect(dest_x, dest_y_abs - box_h, dest_w, box_h, fill=1, stroke=1)
                
                right_p.drawOn(canvas, dest_x + 0.25*cm, dest_y_abs - right_h - 0.5*cm)
                date_p.drawOn(
                    canvas,
                    creation_date_x_cm * cm,
                    PAGE_HEIGHT - creation_date_y_cm * cm - date_h,
                )
                canvas.restoreState()

            # --- جدول المنتجات ---
            header_col1 = settings.get('col1_name', 'Désignation Produit')
            header_col2 = settings.get('qty_header_rt', 'Qté Rtr.') if is_return else settings.get('qty_header_bl', 'Qté')
            header_col3 = settings.get('col3_name', 'P.U')
            header_col4 = settings.get('col4_name', 'Total / Obs')
            table_data = [[header_col1, header_col2, header_col3, header_col4]]
            
            grand_total = 0.0
            for item in details_data:
                is_billable = bool(item.get('Is_Billable', False))
                qty = item.get('Qty_Transferred', 0)
                qty_numeric = float(qty or 0)
                price = float(item.get('Unit_Price', 0))
                line_val = (qty_numeric * price) if is_billable else 0.0
                grand_total += line_val

                pu_text = format_money(price) if is_billable else "/"
                obs_text = format_money(line_val) if is_billable else "<font color='red'>Gratuit</font>"
                lot_info = item.get('Lot_Number', '-')
                exp_info = str(item.get('Expiry_Date', '-'))[:10]
                p_info = f"<b>{item.get('Product_Name', '-')}</b><br/><font size=8 color='#555555'>Lot: {lot_info} | Exp: {exp_info}</font>"

                table_data.append([
                    Paragraph(p_info, styles["Normal"]), 
                    format_quantity(qty), 
                    pu_text, 
                    Paragraph(obs_text, styles["Normal"])
                ])

            total_label = settings.get('total_label_rt', 'VALEUR TOTALE DU RETOUR') if is_return else settings.get('total_label_bl', 'MONTANT TOTAL À PAYER')
            table_data.append([Paragraph(f"<b>{total_label}</b>", styles["Normal"]), "", "", format_money(grand_total, 'DA')])

            items_table = Table(table_data, colWidths=[9.5*cm, 2.0*cm, 2.5*cm, 4.0*cm])
            items_table.hAlign = 'LEFT'
            items_table.leftIndent = max(0.0, table_start_x_cm * cm - doc.leftMargin)
            items_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), primary_color),
                ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
                ('ALIGN', (1,0), (2,-1), 'CENTER'),
                ('ALIGN', (3,0), (3,-1), 'RIGHT'),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('SPAN', (0, -1), (2, -1)), # دمج خلايا المجموع
                ('PADDING', (0,0), (-1,-1), 6),
                ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor("#f4f6f6")), # لون خلفية للمجموع
            ]))
            elements.append(items_table)
            footer_y_offset = settings.get('footer_y_offset_cm', 1.5)
            elements.append(Spacer(1, footer_y_offset * cm))

            # --- التوقيعات ---
            if is_return:
                f_left = settings.get('footer_left_rt', 'Signature Magasin / Expéditeur')
                f_right = settings.get('footer_right_rt', 'Accusé de Réception (Fournisseur)')
            else:
                f_left = settings.get('footer_left_bl', 'Responsable Stock')
                f_right = settings.get('footer_right_bl', 'Accusé de réception (Client)')

            footer_height = settings.get('footer_height_cm', 2.5)
            left_x = settings.get('footer_left_x_cm', 1.0)
            right_x = settings.get('footer_right_x_cm', 12.0)
            stamp_gap = float(settings.get('footer_stamp_gap_cm', 0.3))
            stamp_area_w = float(settings.get('footer_stamp_area_w_cm', 6.0))
            stamp_area_h = float(settings.get('footer_stamp_area_h_cm', 3.5))
            footer_height = max(
                float(footer_height),
                FOOTER_TITLE_HEIGHT_CM + stamp_gap + stamp_area_h,
            )
            stamp_provider = getattr(self.manager, "company_settings", None) or local_store
            active_stamp = get_active_stamp(stamp_provider)
            
            footer = SignatureFooter(
                f_left,
                f_right,
                left_x,
                right_x,
                footer_height,
                active_stamp,
                stamp_gap,
                stamp_area_w,
                stamp_area_h,
            )
            elements.append(footer)

            doc.build(elements, onFirstPage=draw_header_compact, onLaterPages=draw_header_compact)

            # فتح الملف تلقائياً
            if os.name == 'nt': os.startfile(path)
            else: os.system(f'xdg-open "{path}"')

        except Exception as e:
            QMessageBox.critical(self, "Erreur PDF", f"Échec de création du PDF: {str(e)}")

        print("="*50 + " PDF EXPORT END " + "="*50)
