# ui/widgets/master_data/suppliers_tab.py - Version Française Mises à jour

import logging
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, 
                               QHeaderView, QPushButton, QHBoxLayout, QMessageBox, QLineEdit)
from PySide6.QtCore import Qt
from .dialogs import SupplierDialog

class SuppliersTab(QWidget):
    """
    تبويب إدارة الموردين (Suppliers).
    تم التحديث: محاذاة مركزية، ترتيب تلقائي، إخفاء عمود ID، ودعم النقر المزدوج.
    """
    def __init__(self, supplier_manager):
        super().__init__()
        self.supplier_manager = supplier_manager
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # --- Barre d'outils (Toolbar) ---
        control_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Rechercher un fournisseur (Nom, Email, Ville)...")
        self.search_input.setMinimumHeight(35)
        self.search_input.textChanged.connect(self.load_suppliers_data)

        self.add_button = QPushButton("➕ Ajouter Fournisseur")
        self.add_button.setMinimumHeight(35)
        self.add_button.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold;")
        self.add_button.clicked.connect(self.open_add_dialog)
        
        self.refresh_button = QPushButton("🔄 Actualiser")
        self.refresh_button.setMinimumHeight(35)
        self.refresh_button.clicked.connect(self.load_suppliers_data)
        
        control_layout.addWidget(self.search_input, 1)
        control_layout.addWidget(self.add_button)
        control_layout.addWidget(self.refresh_button)
        main_layout.addLayout(control_layout)

        # --- Tableau (Table) ---
        self.suppliers_table = QTableWidget()
        columns = ["ID", "Nom du Fournisseur", "Contact", "Téléphone", "Email", "Ville"]
        self.suppliers_table.setColumnCount(len(columns))
        self.suppliers_table.setHorizontalHeaderLabels(columns)

        # 1. تفعيل الترتيب عند الضغط على العناوين
        self.suppliers_table.setSortingEnabled(True)
        self.suppliers_table.horizontalHeader().setSectionsClickable(True)
        
        self.suppliers_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.suppliers_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.suppliers_table.setAlternatingRowColors(True)
        self.suppliers_table.verticalHeader().setDefaultSectionSize(40)
        self.suppliers_table.setEditTriggers(QTableWidget.NoEditTriggers)

        # 2. إخفاء عمود المعرف (ID) بصرياً
        self.suppliers_table.setColumnHidden(0, True)
        
        # ربط النقر المزدوج لفتح واجهة التعديل
        self.suppliers_table.doubleClicked.connect(self.open_edit_dialog)
        
        main_layout.addWidget(self.suppliers_table)

        # --- Actions Inferieures ---
        actions_layout = QHBoxLayout()
        self.edit_button = QPushButton("✏️ Modifier le Fournisseur")
        self.edit_button.clicked.connect(self.open_edit_dialog)
        
        self.delete_button = QPushButton("🗑️ Supprimer")
        self.delete_button.setStyleSheet("color: #c0392b;")
        self.delete_button.clicked.connect(self.delete_supplier)
        
        actions_layout.addStretch()
        actions_layout.addWidget(self.edit_button)
        actions_layout.addWidget(self.delete_button)
        main_layout.addLayout(actions_layout)

        self.load_suppliers_data()

    def _create_centered_item(self, text, is_numeric=False):
        """دالة مساعدة لإنشاء عنصر جدول محاذى للمركز مع دعم الترتيب الرقمي."""
        item = QTableWidgetItem()
        if is_numeric:
            try:
                # تخزين القيمة رقمياً لضمان ترتيب صحيح (10 تأتي بعد 9)
                val = float(str(text))
                item.setData(Qt.EditRole, val)
            except:
                item.setText(str(text))
        else:
            item.setText(str(text))
        
        item.setTextAlignment(Qt.AlignCenter)
        return item
    
    def showEvent(self, event):
        super().showEvent(event)
        self.load_suppliers_data()

    def load_suppliers_data(self):
        """تحميل بيانات الموردين مع تطبيق التوسيط والترتيب وإخفاء الـ ID."""
        try:
            # إيقاف الترتيب مؤقتاً لتجنب المشاكل أثناء ملء الجدول
            self.suppliers_table.setSortingEnabled(False)
            
            suppliers = self.supplier_manager.get_all_suppliers()
            search_term = self.search_input.text().lower()
            
            self.suppliers_table.setRowCount(0)
            for row_idx, supplier in enumerate(suppliers):
                # فلترة البحث
                match_text = (str(supplier.get('Supplier_Name', '')) + 
                              str(supplier.get('Email', '')) + 
                              str(supplier.get('City', ''))).lower()
                if search_term and search_term not in match_text:
                    continue

                row = self.suppliers_table.rowCount()
                self.suppliers_table.insertRow(row)
                
                # 0. ID (مخفي، يحمل البيانات الكاملة في UserRole)
                id_item = self._create_centered_item(supplier['Supplier_ID'], is_numeric=True)
                id_item.setData(Qt.UserRole, supplier)
                self.suppliers_table.setItem(row, 0, id_item)
                
                # 1. Nom du Fournisseur
                self.suppliers_table.setItem(row, 1, self._create_centered_item(supplier.get('Supplier_Name', '')))
                
                # 2. Contact
                self.suppliers_table.setItem(row, 2, self._create_centered_item(supplier.get('Contact_Person', '---')))
                
                # 3. Téléphone
                self.suppliers_table.setItem(row, 3, self._create_centered_item(supplier.get('Phone', '---')))
                
                # 4. Email
                self.suppliers_table.setItem(row, 4, self._create_centered_item(supplier.get('Email', '---')))
                
                # 5. Ville
                self.suppliers_table.setItem(row, 5, self._create_centered_item(supplier.get('City', '---')))

            # إعادة تفعيل الترتيب
            self.suppliers_table.setSortingEnabled(True)
        except Exception as e:
            logging.error(f"Error loading suppliers: {e}")

    def open_add_dialog(self):
        dialog = SupplierDialog(parent=self)
        if dialog.exec():
            new_data = dialog.get_data()
            
            if new_data is None:
                return
            try:
                self.supplier_manager.add_supplier(**new_data)
                self.load_suppliers_data()
            except Exception as e:
                logging.error(f"Failed to add supplier: {e}")
                QMessageBox.critical(self, "Erreur", f"Échec de l'ajout : {e}")

    def open_edit_dialog(self):
        """تعديل المورد المختار عند النقر المزدوج أو ضغط الزر."""
        row = self.suppliers_table.currentRow()
        if row < 0:
            return
        
        # جلب البيانات من UserRole المخزن في العمود المخفي 0
        current_data = self.suppliers_table.item(row, 0).data(Qt.UserRole)
        dialog = SupplierDialog(parent=self, data=current_data)
        
        if dialog.exec():
            new_data = dialog.get_data()
            try:
                self.supplier_manager.update_supplier(current_data['Supplier_ID'], **new_data)
                self.load_suppliers_data()
            except Exception as e:
                QMessageBox.critical(self, "Erreur", f"Échec de la modification : {e}")

    def delete_supplier(self):
        """حذف المورد المختار مع التحقق من الارتباطات."""
        row = self.suppliers_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Avertissement", "Veuillez sélectionner un fournisseur à supprimer.")
            return

        current_data = self.suppliers_table.item(row, 0).data(Qt.UserRole)
        confirm = QMessageBox.question(self, "Confirmation de Suppression", 
                                     f"Êtes-vous sûr de vouloir supprimer le fournisseur : {current_data['Supplier_Name']}?",
                                     QMessageBox.Yes | QMessageBox.No)
        if confirm == QMessageBox.Yes:
            try:
                # استخدام دالة الحذف المنطقي الأصلية
                success = self.supplier_manager.soft_delete_supplier(current_data['Supplier_ID'])
                if success:
                    self.load_suppliers_data()
                else:
                    QMessageBox.warning(self, "Erreur", "Impossible de supprimer le fournisseur (lié à des commandes d'achat actives).")
            except Exception as e:
                QMessageBox.critical(self, "Erreur", f"Échec de la suppression : {e}")