# ui/widgets/master_data/external_partners_tab.py

import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QHeaderView, QPushButton, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QTableWidgetItem, QComboBox,
    QStyle, QMessageBox, QAbstractItemView
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor

from .dialogs import PartnerDialog


class ExternalPartnersTab(QWidget):
    def __init__(self, partners_manager):
        super().__init__()
        self.manager = partners_manager
        self.all_data = []
        self.init_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(5)
        layout.setContentsMargins(5, 5, 5, 5)

        # --- Recherche & Filtres ---
        filter_group = QGroupBox("🔎 Recherche & Filtres")
        filter_layout = QHBoxLayout(filter_group)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔎 Rechercher par nom, agrément, ville...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self.apply_filters_local)

        self.combo_type = QComboBox()
        self.combo_type.addItem("Tous les Types", None)
        self.combo_type.addItem("Laboratoire", "Laboratory")
        self.combo_type.addItem("Médecin", "Doctor")
        self.combo_type.addItem("Hôpital", "Hospital")
        self.combo_type.addItem("Pharmacie", "Pharmacy")
        self.combo_type.addItem("Salle de Soins", "CareRoom")
        self.combo_type.addItem("Clinique", "Clinic")
        self.combo_type.addItem("Autre", "Other")
        self.combo_type.currentIndexChanged.connect(self.apply_filters_local)

        btn_refresh = QPushButton()
        btn_refresh.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))
        btn_refresh.clicked.connect(self.load_data)

        filter_layout.addWidget(self.search_input, 3)
        filter_layout.addWidget(self.combo_type)
        filter_layout.addWidget(btn_refresh)
        layout.addWidget(filter_group)

        # --- Table ---
        self.table = QTableWidget()
        headers = ["Nom Partenaire", "Type", "Agrément", "Contact", "Téléphone", "Email", "Ville", "Adresse"]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        for i in range(1, len(headers)):
            header.setSectionResizeMode(i, QHeaderView.ResizeToContents)

        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.doubleClicked.connect(self.edit_partner)

        layout.addWidget(self.table)

        # --- Actions ---
        actions = QHBoxLayout()

        self.btn_add = QPushButton("➕ Nouveau Partenaire")
        self.btn_add.clicked.connect(self.add_partner)

        self.btn_edit = QPushButton("✏️ Modifier")
        self.btn_edit.clicked.connect(self.edit_partner)
        self.btn_edit.setEnabled(False)

        self.btn_delete = QPushButton("🗑️ Supprimer")
        self.btn_delete.clicked.connect(self.delete_partner)
        self.btn_delete.setEnabled(False)

        actions.addWidget(self.btn_add)
        actions.addWidget(self.btn_edit)
        actions.addWidget(self.btn_delete)
        actions.addStretch()

        layout.addLayout(actions)

        self.table.selectionModel().selectionChanged.connect(self.update_action_buttons_state)

        self.load_data()

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------
    def load_data(self):
        try:
            self.all_data = self.manager.get_all_partners()
            self.apply_filters_local()
        except Exception as e:
            logging.error(e)
            QMessageBox.critical(self, "Erreur", "Impossible de charger les partenaires.")

    def apply_filters_local(self):
        search = self.search_input.text().lower().strip()
        ptype = self.combo_type.currentData()

        filtered = []
        for p in self.all_data:
            text = f"{p.get('Partner_Name','')} {p.get('Agrement_Number','')} {p.get('City','')}".lower()
            if search and search not in text:
                continue
            if ptype and p.get('Partner_Type') != ptype:
                continue
            filtered.append(p)

        self.populate_table(filtered)

    def populate_table(self, data):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)

        for row, partner in enumerate(data):
            self.table.insertRow(row)

            # Col 0 (store full data)
            has_return = partner.get('Has_Return', False)
            if has_return:
                item_name = QTableWidgetItem(f"{partner.get('Partner_Name', '---')} 🔄 (A des retours)")
                item_name.setForeground(QColor("#8e44ad"))
                font = QFont()
                font.setBold(True)
                item_name.setFont(font)
            else:
                item_name = QTableWidgetItem(partner.get('Partner_Name', '---'))
                
            item_name.setData(Qt.UserRole, partner)
            item_name.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.table.setItem(row, 0, item_name)

            type_map = {
                "Laboratory": "Laboratoire",
                "Doctor": "Médecin",
                "Hospital": "Hôpital",
                "Pharmacy": "Pharmacie",
                "CareRoom": "Salle de Soins",
                "Clinic": "Clinique",
                "Other": "Autre"
            }
            self.table.setItem(row, 1, QTableWidgetItem(type_map.get(partner.get('Partner_Type'), '---')))
            self.table.setItem(row, 2, QTableWidgetItem(partner.get('Agrement_Number', '---')))
            self.table.setItem(row, 3, QTableWidgetItem(partner.get('Contact_Person', '---')))
            self.table.setItem(row, 4, QTableWidgetItem(partner.get('Phone', '---')))
            self.table.setItem(row, 5, QTableWidgetItem(partner.get('Email', '---')))
            self.table.setItem(row, 6, QTableWidgetItem(partner.get('City', '---')))
            self.table.setItem(row, 7, QTableWidgetItem(partner.get('Address_Line1', '---')))

        self.table.setSortingEnabled(True)
        self.update_action_buttons_state()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def update_action_buttons_state(self):
        selected = self.table.currentRow() >= 0
        self.btn_edit.setEnabled(selected)
        self.btn_delete.setEnabled(selected)

    def add_partner(self):
        dialog = PartnerDialog(self)
        if dialog.exec():
            data = dialog.get_data()
            if data and self.manager.add_partner(data):
                self.load_data()

    def edit_partner(self):
        row = self.table.currentRow()
        if row < 0:
            return

        item = self.table.item(row, 0)
        partner = item.data(Qt.UserRole)
        if not partner:
            return

        dialog = PartnerDialog(self, partner)
        if dialog.exec():
            new_data = dialog.get_data()
            if new_data:
                if self.manager.update_partner(partner["Partner_ID"], new_data):
                    self.load_data()

    def delete_partner(self):
        row = self.table.currentRow()
        if row < 0:
            return

        item = self.table.item(row, 0)
        partner = item.data(Qt.UserRole)

        reply = QMessageBox.question(
            self,
            "Confirmation",
            f"Supprimer '{partner.get('Partner_Name')}' ?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            if self.manager.delete_partner(partner["Partner_ID"]):
                self.load_data()
