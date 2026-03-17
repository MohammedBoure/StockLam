import logging
from PySide6.QtWidgets import (QFrame, QVBoxLayout, QTableWidget, QTableWidgetItem, 
                               QHeaderView, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                               QButtonGroup, QComboBox)
from PySide6.QtGui import QColor, QFont, QBrush
from PySide6.QtCore import Qt

class AlertsSection(QFrame):
    def __init__(self, data_manager=None):
        super().__init__()
        self.all_data = [] 
        self.active_filter = "All"
        self.init_ui()

    def init_ui(self):
        self.setObjectName("AlertsSection")
        self.setStyleSheet("""
            #AlertsSection { background: white; border-radius: 12px; border: 1px solid #ecf0f1; }
            QTableWidget { border: none; gridline-color: #f8f9fa; }
            QHeaderView::section { background-color: #f8f9fa; border: none; font-weight: bold; color: #7f8c8d; padding: 10px; }
            QLineEdit, QComboBox { border: 1px solid #dcdde1; border-radius: 6px; padding: 6px; background: #fdfdfd; }
            QPushButton { padding: 6px 12px; border-radius: 15px; font-weight: bold; border: 1px solid #dcdde1; background: #f8f9fa; color: #7f8c8d; }
            QPushButton:checked { background: #007572; color: white; border: none; }
            QPushButton#btn_urgent:checked { background: #c0392b; }
            QPushButton#btn_anticip:checked { background: #d35400; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # --- 1. أزرار أنواع التنبيهات ---
        type_layout = QHBoxLayout()
        self.btn_group = QButtonGroup(self)
        self.btn_all = QPushButton("Tout")
        self.btn_urgent = QPushButton("Urgents 🚨"); self.btn_urgent.setObjectName("btn_urgent")
        self.btn_anticip = QPushButton("Anticipés ⏳"); self.btn_anticip.setObjectName("btn_anticip")
        self.btn_stock = QPushButton("Stocks 📦")

        for i, btn in enumerate([self.btn_all, self.btn_urgent, self.btn_anticip, self.btn_stock]):
            btn.setCheckable(True)
            self.btn_group.addButton(btn, i)
        self.btn_all.setChecked(True)
        self.btn_group.idClicked.connect(self.on_filter_clicked)
        
        type_layout.addWidget(self.btn_all)
        type_layout.addWidget(self.btn_urgent)
        type_layout.addWidget(self.btn_anticip)
        type_layout.addWidget(self.btn_stock)
        type_layout.addStretch()
        layout.addLayout(type_layout)

        # --- 2. فلاتر البحث المتقدم ---
        filters_layout = QHBoxLayout()
        
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("🔍 Recherche par nom...")
        self.search_box.setFixedWidth(200)
        self.search_box.textChanged.connect(self.refresh_table_view)
        
        self.combo_fam = QComboBox()
        self.combo_fam.addItem("Toutes Familles")
        self.combo_fam.setFixedWidth(180)
        self.combo_fam.currentTextChanged.connect(self.refresh_table_view)
        
        self.combo_brand = QComboBox()
        self.combo_brand.addItem("Toutes Marques")
        self.combo_brand.setFixedWidth(180)
        self.combo_brand.currentTextChanged.connect(self.refresh_table_view)

        filters_layout.addWidget(self.search_box)
        filters_layout.addWidget(QLabel("Famille:"))
        filters_layout.addWidget(self.combo_fam)
        filters_layout.addWidget(QLabel("Marque:"))
        filters_layout.addWidget(self.combo_brand)
        filters_layout.addStretch()
        layout.addLayout(filters_layout)

        # --- 3. الجدول ---
        self.table = QTableWidget()
        # 5 أعمدة فقط (تمت إزالة Action)
        self.table.setColumnCount(5) 
        self.table.setHorizontalHeaderLabels(["PRODUIT", "FAMILLE", "TYPE", "VALEUR", "DÉTAILS"])
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)       # Product
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents) # Family
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents) # Type
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents) # Value
        header.setSectionResizeMode(4, QHeaderView.Stretch)       # Details
        
        layout.addWidget(self.table)

    def update_filters_lists(self):
        """تحديث القوائم المنسدلة"""
        current_fam = self.combo_fam.currentText()
        current_brand = self.combo_brand.currentText()
        
        self.combo_fam.blockSignals(True)
        self.combo_brand.blockSignals(True)
        
        self.combo_fam.clear()
        self.combo_brand.clear()
        self.combo_fam.addItem("Toutes Familles")
        self.combo_brand.addItem("Toutes Marques")
        
        fams = sorted(list(set(a.get('Family', '') for a in self.all_data if a.get('Family'))))
        brands = sorted(list(set(a.get('Brand', '') for a in self.all_data if a.get('Brand'))))
        
        self.combo_fam.addItems(fams)
        self.combo_brand.addItems(brands)
        
        if self.combo_fam.findText(current_fam) >= 0:
            self.combo_fam.setCurrentText(current_fam)
        if self.combo_brand.findText(current_brand) >= 0:
            self.combo_brand.setCurrentText(current_brand)
        
        self.combo_fam.blockSignals(False)
        self.combo_brand.blockSignals(False)

    def on_filter_clicked(self, id):
        filters = ["All", "Urgente", "Anticipée", "Stock"]
        self.active_filter = filters[id]
        self.refresh_table_view()

    def update_alerts(self, alerts):
        self.all_data = alerts
        self.update_filters_lists()
        self.refresh_table_view()

    def refresh_table_view(self):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        
        txt = self.search_box.text().lower()
        fam = self.combo_fam.currentText()
        brand = self.combo_brand.currentText()
        
        filtered = []
        for a in self.all_data:
            # فلترة النوع
            if self.active_filter != "All" and self.active_filter not in a['Type']: continue
            # فلترة النص
            if txt and txt not in a['Product'].lower(): continue
            # فلترة العائلة
            if fam != "Toutes Familles" and a.get('Family') != fam: continue
            # فلترة الماركة
            if brand != "Toutes Marques" and a.get('Brand') != brand: continue
            
            filtered.append(a)
        
        # الترتيب حسب القيمة
        filtered.sort(key=lambda x: x.get('RawValue', 9999))

        for row, a in enumerate(filtered):
            self.table.insertRow(row)
            
            p_item = QTableWidgetItem(a['Product'])
            p_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            
            fam_item = QTableWidgetItem(a.get('Family', '-'))
            
            t_item = QTableWidgetItem(a['Type'])
            t_item.setTextAlignment(Qt.AlignCenter)
            
            v_item = QTableWidgetItem()
            v_item.setData(Qt.EditRole, a['RawValue'])
            v_item.setTextAlignment(Qt.AlignCenter)
            
            d_item = QTableWidgetItem(a['Details'])

            # الألوان
            text_color = QColor("#2c3e50")
            if "Urgente" in a['Type']: text_color = QColor("#c0392b")
            elif "Anticipée" in a['Type']: text_color = QColor("#d35400")
            elif "Stock" in a['Type']: text_color = QColor("#c2185b")

            for item in [p_item, fam_item, t_item, v_item, d_item]:
                item.setForeground(QBrush(text_color))

            self.table.setItem(row, 0, p_item)
            self.table.setItem(row, 1, fam_item)
            self.table.setItem(row, 2, t_item)
            self.table.setItem(row, 3, v_item)
            self.table.setItem(row, 4, d_item)

        self.table.setSortingEnabled(True)