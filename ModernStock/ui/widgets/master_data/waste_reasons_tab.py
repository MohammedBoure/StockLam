# ui/widgets/master_data/waste_reasons_tab.py - Version Française Mises à jour

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, 
                               QTableWidgetItem, QHeaderView, QPushButton, QLineEdit, 
                               QMessageBox)
from PySide6.QtCore import Qt
from .dialogs import WasteReasonDialog

class WasteReasonsTab(QWidget):
    """
    تبويب إدارة أسباب التلف (Waste Reasons).
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
        self.search_input.setPlaceholderText("🔍 Rechercher les raisons (Nom)...")
        self.search_input.setMinimumHeight(35)
        self.search_input.textChanged.connect(self.load_data)
        
        btn_add = QPushButton("➕ Ajouter une Raison")
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
        self.table.setHorizontalHeaderLabels(["ID", "Raison", "Statut (Active)"])
        
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
        btn_edit = QPushButton("✏️ Modifier")
        btn_edit.clicked.connect(self.open_edit_dialog)
        
        btn_delete = QPushButton("🗑️ Désactiver la Raison")
        btn_delete.setStyleSheet("color: red;")
        btn_delete.clicked.connect(self.delete_reason)
        
        actions.addStretch()
        actions.addWidget(btn_edit)
        actions.addWidget(btn_delete)
        layout.addLayout(actions)

        self.load_data()

    def _create_centered_item(self, text, is_numeric=False):
        """دالة مساعدة لإنشاء عنصر جدول محاذى للمركز مع دعم الترتيب الرقمي."""
        item = QTableWidgetItem()
        if is_numeric:
            try:
                # تخزين القيمة رقمياً لضمان ترتيب صحيح
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
        """تحميل بيانات أسباب التلف مع تطبيق التوسيط والترتيب وإخفاء الـ ID."""
        if not self.manager: return
        try:
            # إيقاف الترتيب مؤقتاً لتجنب المشاكل أثناء ملء الجدول
            self.table.setSortingEnabled(False)
            
            # جلب كافة الأسباب بما في ذلك غير النشطة للعرض
            data = self.manager.get_all_reasons(include_inactive=True)
            txt = self.search_input.text().lower()
            
            self.table.setRowCount(0)
            row_idx = 0
            for item in data:
                # فلترة البحث
                if txt and txt not in str(item.get('Reason_Name')).lower():
                    continue
                
                self.table.insertRow(row_idx)
                
                # 0. ID (مخفي، يحمل البيانات الكاملة في UserRole)
                id_item = self._create_centered_item(item['Reason_ID'], is_numeric=True)
                id_item.setData(Qt.UserRole, item)
                self.table.setItem(row_idx, 0, id_item)
                
                # 1. Raison (الاسم)
                name_item = self._create_centered_item(item.get('Reason_Name', ''))
                
                # تمييز العناصر غير النشطة باللون الرمادي
                is_active = bool(item.get('Is_Active'))
                if not is_active:
                     name_item.setForeground(Qt.gray)
                self.table.setItem(row_idx, 1, name_item)
                
                # 2. Statut (الحالة)
                active_str = "✅ Oui" if is_active else "❌ Non"
                self.table.setItem(row_idx, 2, self._create_centered_item(active_str))
                
                row_idx += 1

            # إعادة تفعيل الترتيب
            self.table.setSortingEnabled(True)
        except Exception as e:
            print(f"Erreur lors du chargement des raisons : {e}")

    def open_add_dialog(self):
        """فتح نافذة إضافة سبب جديد."""
        dialog = WasteReasonDialog(self)
        if dialog.exec():
            data = dialog.get_data()
            try:
                # الحفاظ على منطق الإضافة الأصلي (الاسم فقط)
                self.manager.add_reason(name=data['Reason_Name'])
                self.load_data()
            except Exception as e:
                QMessageBox.critical(self, "Erreur", f"Échec de l'ajout : {e}")

    def open_edit_dialog(self):
        """تعديل السبب المختار عند النقر المزدوج أو ضغط الزر."""
        row = self.table.currentRow()
        if row < 0: return
        
        # جلب البيانات من UserRole المخزن في العمود المخفي 0
        item_data = self.table.item(row, 0).data(Qt.UserRole)
        dialog = WasteReasonDialog(self, item_data)
        
        if dialog.exec():
            new_data = dialog.get_data()
            try:
                reason_id = item_data['Reason_ID']
                
                # الحفاظ على منطق التعديل المنفصل في الـ Backend
                # 1. تحديث الاسم إذا تغير
                if new_data['Reason_Name'] != item_data['Reason_Name']:
                    self.manager.update_reason_name(reason_id, new_data['Reason_Name'])
                
                # 2. تحديث حالة التفعيل إذا تغيرت
                if new_data['Is_Active'] != item_data['Is_Active']:
                    self.manager.set_reason_active_status(reason_id, new_data['Is_Active'])

                self.load_data()
            except Exception as e:
                QMessageBox.critical(self, "Erreur", f"Échec de la modification : {e}")

    def delete_reason(self):
        """تعطيل السبب المختار (إلغاء تفعيل) بدلاً من الحذف الفيزيائي."""
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Avertissement", "Sélectionnez une raison à désactiver")
            return
            
        item_data = self.table.item(row, 0).data(Qt.UserRole)
        
        # التحقق إذا كان السبب غير نشط بالفعل
        if not item_data['Is_Active']:
             QMessageBox.information(self, "Avertissement", "Cet élément est déjà inactif.")
             return

        if QMessageBox.question(self, "Confirmation", f"Voulez-vous désactiver la raison : '{item_data['Reason_Name']}' ?") == QMessageBox.Yes:
            try:
                # استخدام وظيفة تغيير الحالة الأصلية
                self.manager.set_reason_active_status(item_data['Reason_ID'], False)
                self.load_data()
            except Exception as e:
                QMessageBox.critical(self, "Erreur", f"Échec de l'opération : {e}")