from PySide6.QtWidgets import (QFrame, QVBoxLayout, QTableWidget, QTableWidgetItem, 
                               QHeaderView, QHBoxLayout, QLabel)
from PySide6.QtGui import QColor, QFont, QBrush, QIcon
from PySide6.QtCore import Qt

class AlertsSection(QFrame):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("""
            QFrame { background: white; border-radius: 10px; }
            QTableWidget { border: none; gridline-color: #f0f0f0; }
            QTableWidget::item { padding: 5px; }
            QHeaderView::section { background-color: #f8f9fa; border: none; font-weight: bold; color: #7f8c8d; }
        """) 
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        # --- 1. إضافة عنوان للقسم (Header) ---
        header_layout = QHBoxLayout()
        title_lbl = QLabel("⚠️ ALERTES & NOTIFICATIONS")
        title_lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: #2c3e50;")
        header_layout.addWidget(title_lbl)
        header_layout.addStretch()
        layout.addLayout(header_layout)
        
        # --- 2. الجدول ---
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["PRODUIT", "TYPE", "DÉTAILS & ACTION"])
        
        self.table.setSortingEnabled(True) 
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setShowGrid(False) # إخفاء الخطوط لزيادة الجمالية
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch) # المنتج يأخذ مساحة
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents) # النوع على قد الكلام
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch) # التفاصيل تأخذ الباقي
        
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        
        layout.addWidget(self.table)

    def update_alerts(self, alerts):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        
        font_bold = QFont("Segoe UI", 9, QFont.Weight.Bold)
        font_normal = QFont("Segoe UI", 9)
        
        for row, a in enumerate(alerts):
            self.table.insertRow(row)
            
            # --- العمود 1: المنتج ---
            product_name = str(a['Product'])
            p_item = QTableWidgetItem(product_name)
            p_item.setFont(font_bold)
            p_item.setToolTip(product_name) # إظهار الاسم كاملاً عند التحويم
            
            # --- العمود 2: النوع (مع تنسيق لوني) ---
            alert_type = str(a['Type'])
            t_item = QTableWidgetItem(alert_type)
            t_item.setTextAlignment(Qt.AlignCenter)
            t_item.setFont(font_bold)
            
            # تحديد الألوان والأيقونات حسب النوع
            if "Péremption" in alert_type:
                t_item.setForeground(QColor("#c0392b")) # أحمر
                t_item.setIcon(QIcon(":/icons/expiry.png")) # (اختياري: إذا كان لديك أيقونات)
            elif "Rupture" in alert_type:
                t_item.setForeground(QColor("#e67e22")) # برتقالي
            elif "Stabilité" in alert_type:
                t_item.setForeground(QColor("#8e44ad")) # بنفسجي
            
            # --- العمود 3: التفاصيل ---
            details_text = str(a['Details'])
            d_item = QTableWidgetItem(details_text)
            d_item.setFont(font_normal)
            d_item.setForeground(QBrush(QColor("#555555"))) # رمادي غامق للقراءة المريحة
            d_item.setToolTip(details_text)
            
            # إذا كانت الخطورة عالية، نلون خلفية السطر بلون خفيف جداً للتنبيه
            if a.get('Criticality') == 'High':
                light_red = QColor(255, 235, 238) # خلفية حمراء باهتة جداً
                for item in [p_item, t_item, d_item]:
                    item.setBackground(light_red)

            self.table.setItem(row, 0, p_item)
            self.table.setItem(row, 1, t_item)
            self.table.setItem(row, 2, d_item)
            
        # تعديل ارتفاع الصفوف ليتناسب مع المحتوى
        self.table.resizeRowsToContents()
        self.table.setSortingEnabled(True)