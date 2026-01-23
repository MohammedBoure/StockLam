# ui/widgets/inventory/tabs_history.py

import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QHeaderView, QPushButton, 
    QHBoxLayout, QLabel, QLineEdit, QTableWidgetItem, QComboBox, 
    QDateEdit, QStyle, QDialog, QFormLayout, QGroupBox, QFrame,
    QAbstractItemView
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QColor, QBrush, QFont

# استيراد حقل البحث المطور
from .inventory.dialogs import BarcodeLineEdit 

# ==============================================================================
# نافذة التفاصيل الكاملة (تظهر عند النقر المزدوج)
# ==============================================================================
class MovementDetailsDialog(QDialog):
    def __init__(self, data, parent=None):
        super().__init__(parent)
        self.data = data
        self.setWindowTitle("📄 Détails de l'Opération")
        self.resize(550, 600)
        self.init_ui()

    def init_ui(self):
        """
        بناء واجهة سجل حركات المخزون مع فلاتر شاملة وتنسيق عرض مرن.
        تم حل مشكلة ضيق القائمة المنسدلة وزيادة خيارات الفلترة.
        """
        layout = QVBoxLayout(self)
        layout.setSpacing(5)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # --- 1. منطقة الفلاتر (Filter Bar) ---
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(10)
        
        # إعدادات حقول التاريخ
        self.date_from = QDateEdit(QDate.currentDate().addDays(-7)) 
        self.date_from.setCalendarPopup(True) 
        self.date_from.setDisplayFormat("yyyy-MM-dd") 
        self.date_from.setFixedWidth(115)
        
        self.date_to = QDateEdit(QDate.currentDate())
        self.date_to.setCalendarPopup(True)
        self.date_to.setDisplayFormat("yyyy-MM-dd")
        self.date_to.setFixedWidth(115)
        
        # --- القائمة المنسدلة لأنواع الحركات (المصححة) ---
        self.combo_type = QComboBox()
        self.combo_type.addItems([
            "📋 Tous les mouvements",          
            "📥 Réceptions (Achats)",    
            "🧪 Consommations (Patients)",
            "🛡️ Contrôles Qualité (QC)",
            "⚙️ Calibrations",
            "📦 Ouvertures Boîtes",
            "✏️ Ajustements Manuels",    
            "🗑️ Rebuts / Pertes", 
            "🚚 Transferts Internes",
            "💰 Ventes / Transf. Externes"
        ])
        
        # ربط البيانات البرمجية للفلترة بناءً على الأنواع المعرفة في السجل
        self.combo_type.setItemData(0, None)
        self.combo_type.setItemData(1, "Purchase_Receive")
        self.combo_type.setItemData(2, "Patient_Test") 
        self.combo_type.setItemData(3, "QC_Run")
        self.combo_type.setItemData(4, "Calibration")
        self.combo_type.setItemData(5, "Open_Pack")
        self.combo_type.setItemData(6, "Adjustment")
        self.combo_type.setItemData(7, "Waste")
        self.combo_type.setItemData(8, "Transfer")
        self.combo_type.setItemData(9, "External_Transfer")

        # حل مشكلة العرض: استخدام MinimumWidth بدلاً من FixedWidth لضمان ظهور الكلمات بالكامل
        self.combo_type.setMinimumWidth(220) 
        self.combo_type.setStyleSheet("""
            QComboBox { 
                padding: 5px; 
                font-size: 13px; 
                border: 1px solid #bdc3c7; 
                border-radius: 4px; 
            }
            QComboBox QAbstractItemView { 
                min-width: 250px; /* لضمان عرض القائمة المنسدلة نفسها بوضوح */
            }
        """)
        
        # حقل البحث بالباركود أو النص
        self.search_input = BarcodeLineEdit() 
        self.search_input.setPlaceholderText("🔍 Barcode, Produit, Lot...")
        self.search_input.setMinimumWidth(200)

        # زر التحديث اليدوي
        btn_refresh = QPushButton()
        btn_refresh.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))
        btn_refresh.setFixedSize(35, 35)
        btn_refresh.setCursor(Qt.PointingHandCursor)
        btn_refresh.clicked.connect(self.load_data)
        
        # إضافة العناصر لشريط الفلترة
        filter_layout.addWidget(QLabel("<b>Du:</b>"))
        filter_layout.addWidget(self.date_from)
        filter_layout.addWidget(QLabel("<b>Au:</b>"))
        filter_layout.addWidget(self.date_to)
        filter_layout.addWidget(QLabel("<b>Type:</b>"))
        filter_layout.addWidget(self.combo_type)
        filter_layout.addSpacing(10)
        filter_layout.addWidget(self.search_input, stretch=1)
        filter_layout.addWidget(btn_refresh)
        
        layout.addLayout(filter_layout)

        # --- 2. الجدول الرئيسي (Main Table) ---
        self.table = QTableWidget()
        cols = [
            "Date", "Produit", "Code-Barres", "Lot", "Type", 
            "Mvt", "Stock", "Emplacement", "Utilisateur", "Notes"
        ]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        
        # تنسيق الخط وحجم الجدول
        f = self.table.font()
        f.setPointSize(9)
        self.table.setFont(f)
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents) 
        header.setSectionResizeMode(1, QHeaderView.Stretch) # اسم المنتج يأخذ المساحة الأكبر
        header.setSectionResizeMode(9, QHeaderView.Stretch) # الملاحظات تأخذ المساحة المتبقية
        
        self.table.verticalHeader().setDefaultSectionSize(30) 
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows) 
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        
        # تفعيل النقر المزدوج لفتح نافذة التفاصيل
        self.table.doubleClicked.connect(self.show_full_details)

        layout.addWidget(self.table)
        
        # --- 3. ربط الإشارات (Signals) ---
        self.date_from.dateChanged.connect(self.apply_filter_local)
        self.date_to.dateChanged.connect(self.apply_filter_local)
        self.combo_type.currentIndexChanged.connect(self.load_data)
        self.search_input.textChanged.connect(self.apply_filter_local)

        # التحميل الأولي للبيانات
        self.raw_data = []
        self.load_data()


# ==============================================================================
# التبويب الرئيسي للسجل
# ==============================================================================
class MovementHistoryTab(QWidget):
    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(2)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # --- 1. منطقة الفلاتر ---
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(5)
        
        # إعدادات حقول التاريخ
        self.date_from = QDateEdit(QDate.currentDate().addDays(-7)) 
        self.date_from.setCalendarPopup(True) 
        self.date_from.setDisplayFormat("yyyy-MM-dd") 
        self.date_from.setFixedWidth(120)
        self.date_from.dateChanged.connect(self.apply_filter_local) 
        
        self.date_to = QDateEdit(QDate.currentDate())
        self.date_to.setCalendarPopup(True)
        self.date_to.setDisplayFormat("yyyy-MM-dd")
        self.date_to.setFixedWidth(120)
        self.date_to.dateChanged.connect(self.apply_filter_local)
        
        self.combo_type = QComboBox()
        self.combo_type.addItems([
            "📋 Tous les mouvements",          
            "📥 Réceptions (Achats)",    
            "🧪 Consommations (Patients)",
            "🛡️ Contrôles Qualité (QC)",
            "⚙️ Calibrations",
            "📦 Ouvertures Boîtes",
            "✏️ Ajustements Manuels",    
            "🗑️ Rebuts / Pertes", 
            "🚚 Transferts Internes",
            "💰 Ventes / Transf. Externes"
        ])
        
        self.combo_type.setItemData(0, None)
        self.combo_type.setItemData(1, "Purchase_Receive")
        self.combo_type.setItemData(2, "Patient_Test") 
        self.combo_type.setItemData(3, "QC_Run")
        self.combo_type.setItemData(4, "Calibration")
        self.combo_type.setItemData(5, "Open_Pack")
        self.combo_type.setItemData(6, "Adjustment")
        self.combo_type.setItemData(7, "Waste")
        self.combo_type.setItemData(8, "Transfer")
        self.combo_type.setItemData(9, "External_Transfer")

        # حل مشكلة العرض: زيادة العرض الثابت واستخدام الحد الأدنى المناسب
        self.combo_type.setMinimumWidth(220) 
        self.combo_type.setStyleSheet("QComboBox { padding: 5px; font-size: 13px; }")
        self.combo_type.currentIndexChanged.connect(self.load_data)
        
        self.combo_type.setFixedWidth(130)
        self.combo_type.currentIndexChanged.connect(self.load_data)
        
        self.search_input = BarcodeLineEdit() 
        self.search_input.setPlaceholderText("🔍 Barcode, Produit, Lot...")
        self.search_input.textChanged.connect(self.apply_filter_local) 

        btn_refresh = QPushButton()
        btn_refresh.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))
        btn_refresh.setFixedSize(30, 30)
        btn_refresh.clicked.connect(self.load_data)
        
        filter_layout.addWidget(QLabel("Du:"))
        filter_layout.addWidget(self.date_from)
        filter_layout.addWidget(QLabel("Au:"))
        filter_layout.addWidget(self.date_to)
        filter_layout.addWidget(self.combo_type)
        filter_layout.addWidget(self.search_input)
        filter_layout.addWidget(btn_refresh)
        
        layout.addLayout(filter_layout)

        # --- 2. الجدول الرئيسي ---
        self.table = QTableWidget()
        cols = [
            "Date", "Produit", "Code-Barres", "Lot", "Type", 
            "Mvt", "Stock", "Emplacement", "Utilisateur", "Notes"
        ]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        
        f = self.table.font()
        f.setPointSize(8)
        self.table.setFont(f)
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents) 
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(8, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(9, QHeaderView.Stretch)
        
        self.table.verticalHeader().setDefaultSectionSize(25) 
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows) 
        self.table.setAlternatingRowColors(True)
        
        # *** تفعيل النقر المزدوج ***
        self.table.doubleClicked.connect(self.show_full_details)

        layout.addWidget(self.table)
        
        self.raw_data = []
        self.load_data()

    def filter_by_product(self, product_name):
        """تستقبل اسم المنتج وتحدث واجهة السجل"""
        if product_name:
            # وضع النص في حقل البحث
            self.search_input.setText(product_name)
            # استدعاء التحميل للتأكد من تحديث البيانات فوراً
            self.load_data()

    def load_data(self):
        try:
            m_type = self.combo_type.currentData()
            self.raw_data = self.manager.movement.get_movements_log(limit=500, movement_type=m_type)
            self.apply_filter_local()
        except Exception as e:
            logging.error(f"Error loading history data: {e}")

    def apply_filter_local(self):
        d_from = self.date_from.date().toString("yyyy-MM-dd")
        d_to = self.date_to.date().toString("yyyy-MM-dd")
        txt = self.search_input.text().lower().strip()

        filtered = []
        for m in self.raw_data:
            m_date = str(m['Transaction_Date'])[:10]
            if not (d_from <= m_date <= d_to): continue
            
            full_text = f"{m.get('Product_Name','')} {m.get('Lot_Number','')} {m.get('Batch_Barcode','')} {m.get('Product_Barcode','')} {m.get('Operator_Name','')}".lower()
            if txt and txt not in full_text: continue
            filtered.append(m)
            
        self._populate_table(filtered)

    def _populate_table(self, data):
        """
        تعبئة الجدول بكافة حركات المخزون مع التنسيق اللوني الاحترافي.
        """
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        
        # خريطة الترجمة الكاملة للأنواع البرمجية المدعومة
        type_map = {
            'Purchase_Receive': 'Réception (Achat)',
            'Patient_Test': 'Consommation',
            'QC_Run': 'Contrôle Qualité (QC)',
            'Calibration': 'Calibration',
            'Open_Pack': 'Ouverture Boîte',
            'Adjustment': 'Ajustement',
            'Waste': 'Rebut / Perte',
            'Transfer': 'Transfert Interne',
            'External_Transfer': 'Vente / Transf. Externe' 
        }

        for r, mov in enumerate(data):
            self.table.insertRow(r)
            
            def item(text, align=Qt.AlignCenter, color=None):
                it = QTableWidgetItem(str(text if text is not None else "-"))
                it.setTextAlignment(align) 
                if color: it.setForeground(QBrush(QColor(color)))
                return it

            # 1. التاريخ (تخزين بيانات السجل كاملة في العمود الأول للنقر المزدوج)
            first_item = item(str(mov['Transaction_Date'])[:16])
            first_item.setData(Qt.UserRole, mov) 
            self.table.setItem(r, 0, first_item)
            
            # 2. المنتج (خط عريض وواضح)
            p_item = item(mov.get('Product_Name', '-')) 
            p_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            self.table.setItem(r, 1, p_item)
            
            # 3. الباركود واللوت
            self.table.setItem(r, 2, item(mov.get('Batch_Barcode') or '-'))
            self.table.setItem(r, 3, item(mov.get('Lot_Number') or '-'))
            
            # 4. نوع الحركة مع تمييز لوني احترافي
            raw_type = mov['Movement_Type']
            display_type = type_map.get(raw_type, raw_type)
            t_item = item(display_type)
            
            if raw_type == 'Purchase_Receive': 
                t_item.setBackground(QBrush(QColor("#e8f5e9"))) # أخضر (دخول مخزون)
            elif raw_type == 'External_Transfer': 
                t_item.setBackground(QBrush(QColor("#fff3e0"))) # برتقالي (خروج مالي)
                t_item.setForeground(QBrush(QColor("#e65100")))
            elif raw_type in ['Patient_Test', 'QC_Run', 'Calibration']: 
                t_item.setBackground(QBrush(QColor("#e3f2fd"))) # أزرق (استهلاك تقني)
                t_item.setForeground(QBrush(QColor("#1976d2")))
            elif raw_type == 'Open_Pack':
                t_item.setBackground(QBrush(QColor("#f3e5f5"))) # بنفسجي (تحضير)
            elif raw_type == 'Waste': 
                t_item.setBackground(QBrush(QColor("#ffebee"))) # أحمر (خسارة)
            elif raw_type == 'Adjustment':
                t_item.setForeground(QBrush(QColor("#d35400"))) # بني (تعديل جرد)
                
            self.table.setItem(r, 4, t_item)
            
            # 5. كمية الحركة (Mvt)
            qty = float(mov['Qty_Change'])
            self.table.setItem(r, 5, item(f"{qty:g}", Qt.AlignCenter, "#c0392b" if qty < 0 else "#27ae60"))
            
            # 6. الرصيد الحالي للمخزن (Stock)
            stock_val = mov.get('Quantity_Current')
            s_item = item(f"{float(stock_val):g}" if stock_val is not None else "0")
            s_item.setFont(QFont("Arial", 8, QFont.Bold))
            self.table.setItem(r, 6, s_item)
            
            # 7. الموقع والمستخدم والملاحظات
            self.table.setItem(r, 7, item(mov.get('Location_Name', '---'), Qt.AlignCenter, "#2980b9"))
            self.table.setItem(r, 8, item(mov.get('Operator_Name') or "Système", Qt.AlignCenter, "#7f8c8d"))
            
            reason = mov.get('Reason_Name', '')
            notes = mov.get('Notes', '')
            self.table.setItem(r, 9, item(f"{reason} {notes}".strip(), Qt.AlignLeft | Qt.AlignVCenter))

        self.table.setSortingEnabled(True)

    def show_full_details(self):
        row = self.table.currentRow()
        if row < 0: return
        data = self.table.item(row, 0).data(Qt.UserRole)
        if data:
            dlg = MovementDetailsDialog(data, self)
            dlg.exec()