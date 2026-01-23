from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, 
    QTableWidgetItem, QPushButton, QHeaderView, QMessageBox, 
    QAbstractItemView, QFormLayout, QLineEdit, QComboBox
)
from PySide6.QtCore import Qt
import qtawesome as qta
from ui.widgets.master_data.dialogs import BaseDialog 

# =================================================================================
# 1. CLASS UserDialog (يجب أن تكون في الأعلى)
# =================================================================================
class UserDialog(BaseDialog):
    """Boîte de dialogue pour ajouter/modifier un utilisateur"""
    def __init__(self, parent=None, data=None):
        title = "Modifier l'utilisateur" if data else "Ajouter un utilisateur"
        super().__init__(title, parent)
        self.data = data
        self.init_ui()

    def init_ui(self):
        layout = QFormLayout(self.form_widget)
        
        self.username_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        
        if self.data:
            self.password_input.setPlaceholderText("Laissez vide pour ne pas changer")
        
        self.full_name_input = QLineEdit()
        
        self.role_combo = QComboBox()
        # الأسماء المعروضة بالفرنسية
        self.role_combo.addItems(['Administrateur', 'Responsable', 'Technicien'])

        layout.addRow("Nom d'utilisateur:", self.username_input)
        layout.addRow("Mot de passe:", self.password_input)
        layout.addRow("Nom complet:", self.full_name_input)
        layout.addRow("Rôle:", self.role_combo)

        if self.data:
            self.username_input.setText(self.data.get('Username', ''))
            self.full_name_input.setText(self.data.get('Full_Name', ''))
            
            # تحويل القيمة الإنجليزية (DB) إلى فرنسية (UI)
            db_role = self.data.get('Role', 'Technician')
            display_role = "Technicien"
            
            if db_role == 'Admin': display_role = 'Administrateur'
            elif db_role == 'Manager': display_role = 'Responsable'
            
            self.role_combo.setCurrentText(display_role)

    def get_data(self):
        # تحويل القيمة المختارة (UI - Fr) إلى القيمة المخزنة (DB - En)
        role_map = {
            'Administrateur': 'Admin',
            'Responsable': 'Manager',
            'Technicien': 'Technician'
        }
        
        selected_display_role = self.role_combo.currentText()
        db_role = role_map.get(selected_display_role, 'Technician')

        data = {
            "Username": self.username_input.text().strip(),
            "Full_Name": self.full_name_input.text().strip(),
            "Role": db_role
        }
        
        pwd = self.password_input.text().strip()
        if pwd:
            data["Password"] = pwd
            
        return data

# =================================================================================
# 2. CLASS UserManagementTab
# =================================================================================
class UserManagementTab(QWidget):
    def __init__(self, data_manager):
        super().__init__() 
        self.data_manager = data_manager
        self.users_list = []
        self.init_ui()
        self.load_users()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # --- Barre d'outils ---
        toolbar = QHBoxLayout()
        
        # زر إضافة
        self.btn_add = QPushButton(" Ajouter")
        self.btn_add.setIcon(qta.icon("fa5s.plus", color="white"))
        self.btn_add.setStyleSheet("background-color: #28a745; color: white; padding: 8px 15px; font-weight: bold;")
        self.btn_add.clicked.connect(self.add_user)
        
        # زر تعديل
        self.btn_edit = QPushButton(" Modifier")
        self.btn_edit.setIcon(qta.icon("fa5s.edit", color="white"))
        self.btn_edit.setStyleSheet("background-color: #007bff; color: white; padding: 8px 15px; font-weight: bold;")
        self.btn_edit.clicked.connect(self.edit_selected_user)
        
        # زر حذف
        self.btn_delete = QPushButton(" Supprimer")
        self.btn_delete.setIcon(qta.icon("fa5s.trash-alt", color="white"))
        self.btn_delete.setStyleSheet("background-color: #dc3545; color: white; padding: 8px 15px; font-weight: bold;")
        self.btn_delete.clicked.connect(self.delete_selected_user)

        # زر تحديث
        self.btn_refresh = QPushButton(" Actualiser")
        self.btn_refresh.setIcon(qta.icon("fa5s.sync-alt", color="white"))
        self.btn_refresh.setStyleSheet("background-color: #17a2b8; color: white; padding: 8px 15px; font-weight: bold;") 
        self.btn_refresh.clicked.connect(self.load_users)

        toolbar.addWidget(self.btn_add)
        toolbar.addWidget(self.btn_edit)
        toolbar.addWidget(self.btn_delete)
        toolbar.addSpacing(10)
        toolbar.addWidget(self.btn_refresh)
        
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # --- Tableau ---
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["ID", "Nom d'utilisateur", "Nom Complet", "Rôle"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        
        layout.addWidget(self.table)

    def load_users(self):
        """Charger les données et traduire les rôles pour l'affichage"""
        # قاموس العرض (DB -> UI)
        role_translation = {
            "Admin": "Administrateur",
            "Manager": "Responsable",
            "Technician": "Technicien"
        }

        self.users_list = self.data_manager.users.get_all_users(include_inactive=True)
        self.table.setRowCount(0)
        
        for row, u in enumerate(self.users_list):
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(str(u['User_ID'])))
            self.table.setItem(row, 1, QTableWidgetItem(u['Username']))
            self.table.setItem(row, 2, QTableWidgetItem(u['Full_Name'] or ""))
            
            db_role = u['Role']
            translated_role = role_translation.get(db_role, db_role)
            
            self.table.setItem(row, 3, QTableWidgetItem(translated_role))

    def get_selected_user_data(self):
        selected_row = self.table.currentRow()
        if selected_row >= 0:
            user_id = int(self.table.item(selected_row, 0).text())
            for user in self.users_list:
                if user['User_ID'] == user_id:
                    return user
        return None

    def add_user(self):
        # الآن UserDialog معروف لأنه معرف في الأعلى
        dlg = UserDialog(self)
        if dlg.exec():
            data = dlg.get_data()
            if data['Username'] and data.get('Password'):
                res = self.data_manager.users.add_user(
                    data['Username'], data['Password'], data['Role'], data['Full_Name']
                )
                if res == -1:
                    QMessageBox.warning(self, "Erreur", "Ce nom d'utilisateur existe déjà.")
                elif res is None:
                    QMessageBox.critical(self, "Erreur", "Erreur base de données.")
                
                self.load_users()
            else:
                QMessageBox.warning(self, "Champs requis", "Nom d'utilisateur et mot de passe obligatoires.")

    def edit_selected_user(self):
        user_data = self.get_selected_user_data()
        if not user_data:
            QMessageBox.warning(self, "Sélection", "Veuillez sélectionner un utilisateur.")
            return

        dlg = UserDialog(self, data=user_data)
        if dlg.exec():
            updated_data = dlg.get_data()
            success = self.data_manager.users.update_user(user_data['User_ID'], **updated_data)
            if success:
                self.load_users()
            else:
                QMessageBox.critical(self, "Erreur", "Échec de la modification.")

    def delete_selected_user(self):
        user_data = self.get_selected_user_data()
        if not user_data:
            QMessageBox.warning(self, "Sélection", "Veuillez sélectionner un utilisateur.")
            return

        if user_data['Username'].lower() == "admin":
            QMessageBox.critical(self, "Interdit", "L'utilisateur 'admin' ne peut pas être supprimé.")
            return

        confirm = QMessageBox.question(
            self, "Confirmation", 
            f"Voulez-vous vraiment supprimer '{user_data['Username']}' ?",
            QMessageBox.Yes | QMessageBox.No
        )

        if confirm == QMessageBox.Yes:
            success = self.data_manager.users.update_user(user_data['User_ID'], Is_Active=0)
            if success:
                self.load_users()
            else:
                QMessageBox.critical(self, "Erreur", "Échec de la suppression.")