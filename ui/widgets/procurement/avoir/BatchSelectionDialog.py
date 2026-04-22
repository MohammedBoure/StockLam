from PySide6.QtWidgets import (
    QVBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QLabel, QMessageBox, 
    QAbstractItemView, QDialog, QDialogButtonBox
)
from PySide6.QtCore import Qt




class BatchSelectionDialog(QDialog):
    def __init__(self, matches, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sélectionner le Lot")
        self.resize(650, 300)
        self.selected_item = None
        
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Ce produit existe en plusieurs lots/dates.\nVeuillez choisir la ligne exacte à retourner :"))
        
        self.table = QTableWidget()
        cols = ["Désignation", "Lot", "Péremption", "Qté Reçue", "Prix Unitaire"]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        
        self.table.setRowCount(len(matches))
        for i, item in enumerate(matches):
            self.table.setItem(i, 0, QTableWidgetItem(str(item.get('Product_Name'))))
            self.table.setItem(i, 1, QTableWidgetItem(str(item.get('Lot_Number'))))
            self.table.setItem(i, 2, QTableWidgetItem(str(item.get('Expiry_Date') or '---')))
            
            qty = item.get('Quantity_Initial') or item.get('Qty_Received') or 0
            self.table.setItem(i, 3, QTableWidgetItem(str(qty)))
            
            price = float(item.get('Unit_Price_Received') or item.get('Purchase_Price') or 0)
            self.table.setItem(i, 4, QTableWidgetItem(f"{price:.2f}"))
            
            self.table.item(i, 0).setData(Qt.UserRole, item)
            
        self.table.doubleClicked.connect(self.accept_selection)
        layout.addWidget(self.table)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept_selection)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
    def accept_selection(self):
        row = self.table.currentRow()
        if row >= 0:
            self.selected_item = self.table.item(row, 0).data(Qt.UserRole)
            self.accept()
        else:
            QMessageBox.warning(self, "Attention", "Veuillez sélectionner une ligne.")
