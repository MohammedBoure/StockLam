import logging
import random
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QWidget, QLabel,
    QTableWidget,QDialog,
    QTableWidgetItem, QPushButton, QMessageBox, 
    QHeaderView, QCheckBox, QAbstractItemView
)
from PySide6.QtCore import Qt, QDate, QTimer, QLocale
from ui.widgets.master_data.dialogs import BaseDialog
import qtawesome as qta

from PySide6.QtCore import Qt


class BulkBarcodeSelectionDialog(QDialog):
    def __init__(self, items_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sélection pour impression en masse")
        self.resize(600, 400)
        self.items_data = items_data
        self.selected_items = []

        layout = QVBoxLayout(self)

        # Instructions
        layout.addWidget(QLabel("Décochez les produits que vous ne souhaitez pas imprimer :"))

        # Tableau
        self.table = QTableWidget(len(items_data), 4)
        self.table.setHorizontalHeaderLabels(["", "Produit", "Code à barre", "Qté Étiquettes"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        
        for row, item in enumerate(items_data):
            # Checkbox
            chk_widget = QWidget()
            chk_layout = QHBoxLayout(chk_widget)
            chk_layout.setContentsMargins(0,0,0,0)
            chk_layout.setAlignment(Qt.AlignCenter)
            chk = QCheckBox()
            chk.setChecked(True) # Coché par défaut
            chk_layout.addWidget(chk)
            self.table.setCellWidget(row, 0, chk_widget)

            # Données (Non modifiables)
            name_item = QTableWidgetItem(str(item.get('Product_Name', '')))
            name_item.setFlags(name_item.flags() ^ Qt.ItemIsEditable)
            
            code_item = QTableWidgetItem(str(item.get('Internal_Barcode', '')))
            code_item.setFlags(code_item.flags() ^ Qt.ItemIsEditable)
            
            # Calcul quantité (Unités stock)
            qty = int(item.get('Qty_Received', 0))
            qty_item = QTableWidgetItem(str(qty))
            qty_item.setFlags(qty_item.flags() ^ Qt.ItemIsEditable) # Lecture seule
            
            self.table.setItem(row, 1, name_item)
            self.table.setItem(row, 2, code_item)
            self.table.setItem(row, 3, qty_item)

        layout.addWidget(self.table)

        # Boutons
        btn_box = QHBoxLayout()
        self.btn_print = QPushButton(qta.icon('fa5s.print', color='white'), " Lancer l'impression")
        self.btn_print.setStyleSheet("background-color: #2c3e50; color: white; padding: 8px;")
        self.btn_print.clicked.connect(self.accept_selection)
        
        self.btn_cancel = QPushButton("Annuler")
        self.btn_cancel.clicked.connect(self.reject)

        btn_box.addStretch()
        btn_box.addWidget(self.btn_cancel)
        btn_box.addWidget(self.btn_print)
        layout.addLayout(btn_box)

    def accept_selection(self):
        self.selected_items = []
        for row in range(self.table.rowCount()):
            # Récupérer la checkbox
            widget = self.table.cellWidget(row, 0)
            chk = widget.layout().itemAt(0).widget()
            
            if chk.isChecked():
                self.selected_items.append(self.items_data[row])
        
        if not self.selected_items:
            QMessageBox.warning(self, "Attention", "Aucun produit sélectionné.")
            return

        self.accept()

    def get_items_to_print(self):
        return self.selected_items