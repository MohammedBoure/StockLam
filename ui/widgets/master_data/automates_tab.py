# ui/widgets/master_data/automates_tab.py - Version Française Mises à jour

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, 
                               QTableWidgetItem, QHeaderView, QPushButton, QLineEdit, QMessageBox)
from PySide6.QtCore import Qt
from .dialogs import AutomateDialog

class AutomatesTab(QWidget):
    """
    تبويب إدارة أجهزة التحليل (Automates).
    تم التحديث: محاذاة مركزية، ترتيب تلقائي، وإخفاء عمود ID.
    """
    def __init__(self, automate_manager, location_manager):
        super().__init__()
        self.manager = automate_manager
        self.location_manager = location_manager
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # --- Barre d'outils (Toolbar) ---
        toolbar = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Rechercher des automates (Nom, Modèle, S/N)...")
        self.search_input.setMinimumHeight(35)
        self.search_input.textChanged.connect(self.load_data)
        
        btn_add = QPushButton("➕ Ajouter un Automate")
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
        # "ID" موجود برمجياً ولكن سيتم إخفاؤه عن المستخدم
        columns = ["ID", "Nom de l'Automate", "Modèle", "N° S/N", "Emplacement"]
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)

        # 1. تفعيل الترتيب عند الضغط على العناوين
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setSectionsClickable(True)
        
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)

        # 2. إخفاء عمود المعرف (ID) بصرياً من واجهة المستخدم
        self.table.setColumnHidden(0, True)
        
        # ربط النقر المزدوج للتعديل
        self.table.doubleClicked.connect(self.open_edit_dialog)
        
        layout.addWidget(self.table)

        # --- Actions Inferieures ---
        actions = QHBoxLayout()
        self.btn_edit = QPushButton("✏️ Modifier l'Automate")
        self.btn_edit.clicked.connect(self.open_edit_dialog)
        
        self.btn_delete = QPushButton("🗑️ Supprimer")
        self.btn_delete.setStyleSheet("color: #c0392b;")
        self.btn_delete.clicked.connect(self.delete_automate)
        
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
                # تخزين كقيمة رقمية لضمان الترتيب الصحيح
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
        """تحميل بيانات الأجهزة مع تطبيق التوسيط والترتيب وإخفاء الـ ID."""
        if not self.manager: return
        try:
            # إيقاف الترتيب مؤقتاً لتجنب المشاكل أثناء ملء الجدول
            self.table.setSortingEnabled(False)
            
            data = self.manager.get_all_automates()
            search_txt = self.search_input.text().lower()
            
            self.table.setRowCount(0)
            for item in data:
                # فلترة البحث البسيط
                match_text = (str(item.get('Automate_Name', '')) + 
                              str(item.get('Model_Number', '')) + 
                              str(item.get('Serial_Number', ''))).lower()
                if search_txt and search_txt not in match_text:
                    continue

                row = self.table.rowCount()
                self.table.insertRow(row)

                # 0. ID (مخفي، يحمل البيانات الكاملة في UserRole لاستخدامها في التعديل)
                id_item = self._create_centered_item(item['Automate_ID'], is_numeric=True)
                id_item.setData(Qt.UserRole, item)
                self.table.setItem(row, 0, id_item)
                
                # 1. Nom de l'Automate
                self.table.setItem(row, 1, self._create_centered_item(item.get('Automate_Name', '')))
                
                # 2. Modèle
                self.table.setItem(row, 2, self._create_centered_item(item.get('Model_Number', '')))
                
                # 3. N° S/N
                self.table.setItem(row, 3, self._create_centered_item(item.get('Serial_Number', '')))
                
                # 4. Emplacement
                self.table.setItem(row, 4, self._create_centered_item(item.get('Location_Name', '---')))

            # إعادة تفعيل الترتيب
            self.table.setSortingEnabled(True)
        except Exception as e:
            print(f"Erreur loading automates: {e}")

    def open_add_dialog(self):
        """فتح نافذة إضافة جهاز جديد."""
        locations = self.location_manager.get_all_locations_flat()
        dialog = AutomateDialog(locations, parent=self)
        if dialog.exec():
            new_data = dialog.get_data()
            try:
                self.manager.add_automate(
                    name=new_data['Automate_Name'],
                    model_number=new_data['Model_Number'],
                    serial_number=new_data['Serial_Number'],
                    date_of_purchase=new_data['Date_of_Purchase'],
                    location_id=new_data['Location_ID']
                )
                self.load_data()
            except Exception as e:
                QMessageBox.critical(self, "Erreur", f"Échec de l'ajout : {e}")

    def open_edit_dialog(self):
        """تعديل الجهاز المحدد عند النقر المزدوج أو ضغط الزر."""
        row = self.table.currentRow()
        if row < 0:
            return
        
        # جلب البيانات من UserRole المخزن في العمود المخفي 0
        item_data = self.table.item(row, 0).data(Qt.UserRole)
        locations = self.location_manager.get_all_locations_flat()
        
        dialog = AutomateDialog(locations, parent=self, data=item_data)
        if dialog.exec():
            new_data = dialog.get_data()
            try:
                self.manager.update_automate(
                    item_data['Automate_ID'],
                    name=new_data['Automate_Name'],
                    model_number=new_data['Model_Number'],
                    serial_number=new_data['Serial_Number'],
                    date_of_purchase=new_data['Date_of_Purchase'],
                    location_id=new_data['Location_ID']
                )
                self.load_data()
            except Exception as e:
                QMessageBox.critical(self, "Erreur", f"Échec de la modification : {e}")

    def delete_automate(self):
        """حذف الجهاز المختار (الحذف المنطقي)."""
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Avertissement", "Sélectionnez un automate à supprimer")
            return
            
        item_data = self.table.item(row, 0).data(Qt.UserRole)
        confirm = QMessageBox.question(self, "Suppression", f"Supprimer l'automate : {item_data['Automate_Name']}?")
        
        if confirm == QMessageBox.Yes:
            try:
                success = self.manager.soft_delete_automate(item_data['Automate_ID'])
                if success:
                    self.load_data()
                else:
                    QMessageBox.warning(self, "Erreur", "Impossible de supprimer (lié à des produits).")
            except Exception as e:
                QMessageBox.critical(self, "Erreur", f"Échec : {e}")