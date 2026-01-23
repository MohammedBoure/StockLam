# ui/widgets/master_data/location_types_manager.py

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QListWidget, 
                               QListWidgetItem, QPushButton, QMessageBox, QLabel)
from PySide6.QtCore import Qt
from .dialogs import LocationTypeInputDialog

class LocationTypesManagerDialog(QDialog):
    """
    نافذة لإدارة قائمة أنواع المواقع (إضافة، تعديل، حذف).
    """
    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Gérer les Types d'Emplacements")
        self.resize(400, 500)
        self.manager = manager # LocationManager
        self.init_ui()
        self.load_types()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Header
        lbl_info = QLabel("Définissez ici les types d'emplacements (ex: Bâtiment, Salle, Frigo, Etagère).")
        lbl_info.setWordWrap(True)
        lbl_info.setStyleSheet("color: #555; font-style: italic; margin-bottom: 10px;")
        layout.addWidget(lbl_info)

        # List
        self.types_list = QListWidget()
        self.types_list.setAlternatingRowColors(True)
        layout.addWidget(self.types_list)

        # Buttons
        btn_layout = QHBoxLayout()
        
        self.btn_add = QPushButton("➕ Ajouter")
        self.btn_edit = QPushButton("✏️ Modifier")
        self.btn_delete = QPushButton("🗑️ Supprimer")
        
        self.btn_add.clicked.connect(self.add_type)
        self.btn_edit.clicked.connect(self.edit_type)
        self.btn_delete.clicked.connect(self.delete_type)
        
        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_edit)
        btn_layout.addWidget(self.btn_delete)
        
        layout.addLayout(btn_layout)
        
        # Close Button
        btn_close = QPushButton("Fermer")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)

    def load_types(self):
        self.types_list.clear()
        types = self.manager.get_all_location_types()
        for t in types:
            item = QListWidgetItem(t['Type_Name'])
            item.setData(Qt.UserRole, t) # تخزين الكائن بالكامل
            self.types_list.addItem(item)

    def add_type(self):
        dialog = LocationTypeInputDialog(self)
        if dialog.exec():
            data = dialog.get_data()
            if data:
                if self.manager.add_location_type(data['Type_Name']):
                    self.load_types()
                else:
                    QMessageBox.warning(self, "Erreur", "Erreur lors de l'ajout (nom dupliqué ?).")

    def edit_type(self):
        item = self.types_list.currentItem()
        if not item: return
        data = item.data(Qt.UserRole)
        
        dialog = LocationTypeInputDialog(self, data=data)
        if dialog.exec():
            new_data = dialog.get_data()
            if new_data:
                if self.manager.update_location_type(data['Type_ID'], new_data['Type_Name']):
                    self.load_types()
                else:
                    QMessageBox.warning(self, "Erreur", "Erreur lors de la modification.")

    def delete_type(self):
        item = self.types_list.currentItem()
        if not item: return
        data = item.data(Qt.UserRole)
        
        if QMessageBox.question(self, "Confirmer", f"Supprimer le type '{data['Type_Name']}' ?") == QMessageBox.Yes:
            if self.manager.delete_location_type(data['Type_ID']):
                self.load_types()
            else:
                QMessageBox.warning(self, "Impossible", "Ce type est utilisé par des emplacements existants.\nSupprimez ou modifiez les emplacements d'abord.")