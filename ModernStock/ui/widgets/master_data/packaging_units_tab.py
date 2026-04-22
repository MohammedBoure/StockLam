# ui/widgets/master_data/packaging_units_tab.py - Version Française Mises à jour

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, 
                               QTableWidgetItem, QHeaderView, QPushButton, QLineEdit, 
                               QMessageBox)
from PySide6.QtCore import Qt
from .dialogs import PackagingUnitDialog

class PackagingUnitsTab(QWidget):
    """
    تبويب إدارة وحدات التغليف (Packaging Units).
    تم التحديث: محاذاة مركزية، ترتيب تلقائي، إخفاء عمود ID، ودعم النقر المزدوج.
    """
    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # --- Barre d'outils (Toolbar) ---
        toolbar = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Rechercher une unité (Nom, Description)...")
        self.search_input.setMinimumHeight(35)
        self.search_input.textChanged.connect(self.load_data)
        
        btn_add = QPushButton("➕ Ajouter Unité")
        btn_add.setMinimumHeight(35)
        btn_add.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold;")
        btn_add.clicked.connect(self.open_add_dialog)

        btn_refresh = QPushButton("🔄 Actualiser")
        btn_refresh.setMinimumHeight(35)
        btn_refresh.clicked.connect(self.load_data)
        
        toolbar.addWidget(self.search_input, 1)
        toolbar.addWidget(btn_add)
        toolbar.addWidget(btn_refresh)
        layout.addLayout(toolbar)

        # --- Tableau (Table) ---
        self.table = QTableWidget()
        # "ID" موجود برمجياً في العمود 0 ولكن سيتم إخفاؤه عن المستخدم
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["ID", "Nom de l'Unité", "Description"])
        
        # 1. تفعيل الترتيب عند الضغط على العناوين
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setSectionsClickable(True)
        
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)

        # 2. إخفاء عمود المعرف (ID) بصرياً
        self.table.setColumnHidden(0, True)
        
        # ربط النقر المزدوج لفتح واجهة التعديل
        self.table.doubleClicked.connect(self.open_edit_dialog)

        layout.addWidget(self.table)

        # --- Actions Inferieures ---
        actions = QHBoxLayout()
        self.btn_edit = QPushButton("✏️ Modifier")
        self.btn_edit.clicked.connect(self.open_edit_dialog)
        
        self.btn_delete = QPushButton("🗑️ Supprimer")
        self.btn_delete.setStyleSheet("color: #c0392b;")
        self.btn_delete.clicked.connect(self.delete_unit)
        
        actions.addStretch()
        actions.addWidget(self.btn_edit)
        actions.addWidget(self.btn_delete)
        layout.addLayout(actions)

        self.load_data()

    def _create_centered_item(self, text, is_numeric=False):
        """دالة مساعدة لإنشاء عنصر جدول محاذى للمركز مع دعم الترتيب الرقمي."""
        item = QTableWidgetItem()
        if is_numeric:
            try:
                # تخزين القيمة كـ float في EditRole لضمان الترتيب الصحيح
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
        self.load_data()

    def load_data(self):
        """تحميل بيانات الوحدات مع تطبيق التوسيط والترتيب وإخفاء الـ ID."""
        try:
            # إيقاف الترتيب مؤقتاً لتجنب المشاكل أثناء ملء الجدول
            self.table.setSortingEnabled(False)
            
            data = self.manager.packaging_units.get_all_units()
            search_txt = self.search_input.text().lower()
            
            self.table.setRowCount(0)
            for item in data:
                # فلترة البحث
                match_text = (str(item.get('Unit_Name', '')) + str(item.get('Description', ''))).lower()
                if search_txt and search_txt not in match_text:
                    continue

                row = self.table.rowCount()
                self.table.insertRow(row)

                # 0. ID (مخفي، يحمل البيانات الكاملة في UserRole)
                id_item = self._create_centered_item(item['Unit_ID'], is_numeric=True)
                id_item.setData(Qt.UserRole, item)
                self.table.setItem(row, 0, id_item)
                
                # 1. Nom de l'Unité
                self.table.setItem(row, 1, self._create_centered_item(item.get('Unit_Name', '')))
                
                # 2. Description
                self.table.setItem(row, 2, self._create_centered_item(item.get('Description', '---')))

            # إعادة تفعيل الترتيب
            self.table.setSortingEnabled(True)
        except Exception as e:
            print(f"Erreur lors du chargement des unités: {e}")

    def open_add_dialog(self):
        """فتح نافذة إضافة وحدة جديدة."""
        dialog = PackagingUnitDialog(parent=self)
        if dialog.exec():
            new_data = dialog.get_data()
            try:
                self.manager.packaging_units.add_unit(
                    name=new_data['Unit_Name'], 
                    description=new_data['Description']
                )
                self.load_data()
            except Exception as e:
                QMessageBox.critical(self, "Erreur", f"Échec de l'ajout : {e}")

    def open_edit_dialog(self):
        """تعديل الوحدة المختارة عند النقر المزدوج أو ضغط الزر."""
        row = self.table.currentRow()
        if row < 0:
            return
            
        # جلب البيانات من UserRole المخزن في العمود المخفي 0
        item_data = self.table.item(row, 0).data(Qt.UserRole)
        dialog = PackagingUnitDialog(parent=self, data=item_data)
        
        if dialog.exec():
            new_data = dialog.get_data()
            try:
                self.manager.packaging_units.update_unit(
                    item_data['Unit_ID'], 
                    name=new_data['Unit_Name'], 
                    description=new_data['Description']
                )
                self.load_data()
            except Exception as e:
                QMessageBox.critical(self, "Erreur", f"Échec de la modification : {e}")

    def delete_unit(self):
        """حذف الوحدة المختارة مع التحقق من الارتباطات."""
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Avertissement", "Veuillez sélectionner une unité à supprimer.")
            return
        
        item_data = self.table.item(row, 0).data(Qt.UserRole)
        confirm = QMessageBox.question(self, "Confirmation", 
                                     f"Supprimer l'unité '{item_data['Unit_Name']}' ?",
                                     QMessageBox.Yes | QMessageBox.No)
        
        if confirm == QMessageBox.Yes:
            try:
                # استخدام دالة الحذف المنطقي الأصلية التي تتحقق من وجود منتجات مرتبطة
                success, msg = self.manager.packaging_units.soft_delete_unit(item_data['Unit_ID'], item_data['Unit_Name'])
                if success:
                    self.load_data()
                    QMessageBox.information(self, "Succès", "Unité supprimée.")
                else:
                    QMessageBox.warning(self, "Erreur", msg)
            except Exception as e:
                QMessageBox.critical(self, "Erreur", f"Erreur système : {e}")