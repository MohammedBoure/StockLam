# ui/widgets/master_data/manufacturers_tab.py - Version Française Mises à jour

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, 
                               QTableWidgetItem, QHeaderView, QPushButton, QLineEdit, QMessageBox)
from PySide6.QtCore import Qt
from .dialogs import ManufacturerDialog

class ManufacturersTab(QWidget):
    """
    تبويب إدارة الشركات المصنعة (Manufacturers).
    تم التحديث: محاذاة مركزية، ترتيب تلقائي، إخفاء عمود ID، ودعم النقر المزدوج.
    """
    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # --- Barre d'outils (Toolbar) ---
        toolbar = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Rechercher un fabricant...")
        self.search_input.setMinimumHeight(35)
        self.search_input.textChanged.connect(self.load_data)
        
        btn_add = QPushButton("➕ Ajouter Fabricant")
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
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["ID", "Nom du Fabricant", "Pays d'Origine", "Site Web"])
        
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
        self.btn_delete.clicked.connect(self.delete_item)
        
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
                # تخزين القيمة كـ float في EditRole لضمان الترتيب الصحيح (10 > 2)
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
        """تحميل بيانات الشركات مع تطبيق التوسيط والترتيب وإخفاء الـ ID."""
        try:
            # إيقاف الترتيب مؤقتاً لتجنب المشاكل أثناء ملء الجدول
            self.table.setSortingEnabled(False)
            
            data = self.manager.get_manufacturer_usage_stats()
            search_txt = self.search_input.text().lower()
            
            self.table.setRowCount(0)
            for item in data:
                # فلترة البحث
                if search_txt and search_txt not in str(item.get('Manuf_Name', '')).lower():
                    continue

                row = self.table.rowCount()
                self.table.insertRow(row)

                # 0. ID (مخفي، يحمل البيانات الكاملة في UserRole)
                id_item = self._create_centered_item(item['Manuf_ID'], is_numeric=True)
                id_item.setData(Qt.UserRole, item)
                self.table.setItem(row, 0, id_item)
                
                # 1. Nom du Fabricant
                self.table.setItem(row, 1, self._create_centered_item(item.get('Manuf_Name', '')))
                
                # 2. Pays d'Origine
                self.table.setItem(row, 2, self._create_centered_item(item.get('Country_of_Origin', '')))
                
                # 3. Site Web
                self.table.setItem(row, 3, self._create_centered_item(item.get('Website', '---')))

            # إعادة تفعيل الترتيب
            self.table.setSortingEnabled(True)
        except Exception as e:
            print(f"Erreur lors du chargement des fabricants: {e}")

    def open_add_dialog(self):
        """فتح نافذة إضافة شركة مصنعة جديدة."""
        dialog = ManufacturerDialog(parent=self)
        if dialog.exec():
            new_data = dialog.get_data()
            try:
                self.manager.add_manufacturer(
                    name=new_data['Manuf_Name'],
                    country_of_origin=new_data['Country_of_Origin'],
                    website=new_data['Website']
                )
                self.load_data()
            except Exception as e:
                QMessageBox.critical(self, "Erreur", str(e))

    def open_edit_dialog(self):
        """تعديل الشركة المختارة عند النقر المزدوج أو ضغط الزر."""
        row = self.table.currentRow()
        if row < 0:
            return
            
        # جلب البيانات من UserRole المخزن في العمود المخفي 0
        item_data = self.table.item(row, 0).data(Qt.UserRole)
        dialog = ManufacturerDialog(parent=self, data=item_data)
        
        if dialog.exec():
            new_data = dialog.get_data()
            try:
                # تحديث البيانات مع الحفاظ على أسماء المعاملات الأصلية
                self.manager.update_manufacturer(
                    item_data['Manuf_ID'],
                    name=new_data['Manuf_Name'],
                    country_of_origin=new_data['Country_of_Origin'],
                    website=new_data['Website']
                )
                self.load_data()
            except Exception as e:
                QMessageBox.critical(self, "Erreur", str(e))

    def delete_item(self):
        """حذف الشركة المختارة (الحذف المنطقي)."""
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Avertissement", "Veuillez sélectionner un élément à supprimer")
            return
            
        data = self.table.item(row, 0).data(Qt.UserRole)
        ans = QMessageBox.question(self, "Confirmation", f"Supprimer le fabricant : {data['Manuf_Name']}?")
        
        if ans == QMessageBox.Yes:
            try:
                # استخدام الحذف المنطقي الأصلي
                success = self.manager.soft_delete_manufacturer(data['Manuf_ID'])
                if success:
                    self.load_data()
                else:
                    QMessageBox.warning(self, "Erreur", "Impossible de supprimer (lié à des produits actifs).")
            except Exception as e:
                QMessageBox.critical(self, "Erreur", f"Échec : {e}")