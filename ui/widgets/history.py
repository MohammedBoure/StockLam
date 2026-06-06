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
from ui.formatting import format_quantity

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
        self._build_details_view()
        return

    def _build_details_view(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        def value(*keys, default="-"):
            for key in keys:
                val = self.data.get(key)
                if val not in (None, ""):
                    return str(val)
            return default

        def add_row(form, label, text):
            label_widget = QLabel(f"<b>{label}</b>")
            value_widget = QLabel(text)
            value_widget.setWordWrap(True)
            value_widget.setTextInteractionFlags(Qt.TextSelectableByMouse)
            form.addRow(label_widget, value_widget)

        type_map = {
            'Purchase_Receive': 'Reception (Achat)',
            'Patient_Test': 'Consommation',
            'QC_Run': 'QC',
            'Calibration': 'Calibration',
            'Open_Pack': 'Ouverture',
            'Adjustment': 'Ajustement',
            'Waste': 'Perte',
            'Transfer': 'Transfert',
            'External_Transfer': 'Vente/Externe',
            'Return_To_Supplier': 'Retour Fournisseur',
        }

        movement_type = value('Movement_Type')
        qty_raw = self.data.get('Qty_Change')
        try:
            qty_text = format_quantity(qty_raw, value('Unit_Used', default=''))
        except (TypeError, ValueError):
            qty_text = value('Qty_Change')

        main_group = QGroupBox("Operation")
        main_form = QFormLayout(main_group)
        add_row(main_form, "Date :", value('Transaction_Date')[:19])
        add_row(main_form, "Type :", type_map.get(movement_type, movement_type))
        add_row(main_form, "Quantite :", qty_text)
        add_row(main_form, "Stock apres mouvement :", value('Stock_After', 'Batch_Historical_Stock', 'Historical_Stock'))
        add_row(main_form, "Utilisateur :", value('Operator_Name'))
        layout.addWidget(main_group)

        product_group = QGroupBox("Produit et lot")
        product_form = QFormLayout(product_group)
        add_row(product_form, "Produit :", value('Product_Name'))
        add_row(product_form, "Code-barres :", value('Batch_Barcode', 'Product_Barcode'))
        add_row(product_form, "Lot :", value('Lot_Number'))
        add_row(product_form, "Emplacement :", value('Location_Name'))
        add_row(product_form, "Batch ID :", value('Batch_ID'))
        layout.addWidget(product_group)

        notes_group = QGroupBox("Notes")
        notes_form = QFormLayout(notes_group)
        add_row(notes_form, "Raison :", value('Reason_Name'))
        add_row(notes_form, "Notes :", value('Notes'))
        add_row(notes_form, "Mouvement ID :", value('Movement_ID', 'Log_ID'))
        layout.addWidget(notes_group)

        btn_close = QPushButton("Fermer")
        btn_close.clicked.connect(self.accept)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)
        return

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
            "💰 Ventes / Transf. Externes",
            "↩️ Retours Fournisseurs (Avoirs)"
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
        self.combo_type.setItemData(10, "Return_To_Supplier")

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
            "💰 Ventes / Transf. Externes",
            "↩️ Retours Fournisseurs (Avoirs)"  
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
        self.combo_type.setItemData(10, "Return_To_Supplier")

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
        
        self.table.doubleClicked.connect(self.show_full_details)

        layout.addWidget(self.table)
        
        self.raw_data = []
        self.load_data()

    def filter_by_product(self, product_name):
        if product_name:
            self.search_input.setText(product_name)
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
        تعبئة الجدول وعرض رصيد (الكود بار) المحدد.
        نسخة مصححة 100% (تم إصلاح خطأ stock_display).
        """
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        
        type_map = {
            'Purchase_Receive': 'Réception (Achat)',
            'Patient_Test': 'Consommation',
            'QC_Run': 'QC',
            'Calibration': 'Calibration',
            'Open_Pack': 'Ouverture',
            'Adjustment': 'Ajustement',
            'Waste': 'Perte',
            'Transfer': 'Transfert',
            'External_Transfer': 'Vente/Externe',
            'Return_To_Supplier': 'Retour Fourn.'
        }

        for r, mov in enumerate(data):
            self.table.insertRow(r)
            
            def item(text, align=Qt.AlignCenter, color=None, font=None):
                val = str(text) if text is not None else "-"
                it = QTableWidgetItem(val)
                it.setTextAlignment(align) 
                if color: it.setForeground(QBrush(QColor(color)))
                if font: it.setFont(font)
                return it

            # 1. التاريخ
            self.table.setItem(r, 0, item(str(mov['Transaction_Date'])[:16]))
            self.table.item(r, 0).setData(Qt.UserRole, mov)
            
            # 2. المنتج
            self.table.setItem(r, 1, item(mov.get('Product_Name', '-'), font=QFont("Segoe UI", 9, QFont.Bold)))
            
            # 3. الباركود واللوت
            self.table.setItem(r, 2, item(mov.get('Batch_Barcode') or '-')) 
            self.table.setItem(r, 3, item(mov.get('Lot_Number') or '-'))
            
            # 4. نوع الحركة
            raw_type = mov['Movement_Type']
            t_item = item(type_map.get(raw_type, raw_type))
            if raw_type == 'Purchase_Receive': t_item.setBackground(QBrush(QColor("#e8f5e9")))
            elif raw_type == 'Waste': t_item.setBackground(QBrush(QColor("#ffebee")))
            elif raw_type in ['Patient_Test', 'QC_Run']: t_item.setForeground(QBrush(QColor("#1976d2")))
            self.table.setItem(r, 4, t_item)
            
            # 5. الكمية
            qty = float(mov.get('Qty_Change', 0))
            self.table.setItem(r, 5, item(format_quantity(qty), Qt.AlignCenter, "#c0392b" if qty < 0 else "#27ae60"))
            
            # 6. رصيد الباركود (Batch Stock)
            batch_stock = mov.get('Batch_Historical_Stock')
            
            if batch_stock is None:
                batch_stock = mov.get('Historical_Stock')
            
            # --- التصحيح هنا ---
            stock_txt = format_quantity(batch_stock) if batch_stock is not None else "?"
            
            # تم استخدام المتغير الصحيح stock_txt
            s_item = item(stock_txt, font=QFont("Arial", 9, QFont.Bold))
            
            if batch_stock is not None and float(batch_stock) <= 0:
                s_item.setForeground(QBrush(QColor("#c0392b"))) 
            else:
                s_item.setForeground(QBrush(QColor("#2c3e50")))

            self.table.setItem(r, 6, s_item)
            
            # 7. باقي الأعمدة
            self.table.setItem(r, 7, item(mov.get('Location_Name', '---'), Qt.AlignCenter, "#2980b9"))
            self.table.setItem(r, 8, item(mov.get('Operator_Name') or "Système", Qt.AlignCenter, "#7f8c8d"))
            
            full_note = f"{mov.get('Reason_Name','') or ''} {mov.get('Notes','') or ''}".strip()
            self.table.setItem(r, 9, item(full_note, Qt.AlignLeft | Qt.AlignVCenter))

        self.table.setSortingEnabled(True)
    def show_full_details(self):
        row = self.table.currentRow()
        if row < 0: return
        data = self.table.item(row, 0).data(Qt.UserRole)
        if data:
            dlg = MovementDetailsDialog(data, self)
            dlg.exec()
