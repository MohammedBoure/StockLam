import logging
from PySide6.QtWidgets import (QFrame, QVBoxLayout, QTableWidget, QTableWidgetItem, 
                               QHeaderView, QHBoxLayout, QLabel, QStyledItemDelegate)
from PySide6.QtGui import QColor, QFont, QBrush, QIcon, QPainter
from PySide6.QtCore import Qt

# =============================================================================
# مفوض الرسم (Delegate) لتجاوز مشاكل الألوان
# =============================================================================
class ColorDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        painter.save()
        # جلب لون الخلفية من البيانات المخصصة
        bg_brush = index.data(Qt.BackgroundRole)
        if bg_brush:
            painter.fillRect(option.rect, bg_brush)
        painter.restore()
        # استدعاء الرسم الأصلي (للنصوص والأيقونات)
        super().paint(painter, option, index)

# =============================================================================
# واجهة التنبيهات
# =============================================================================
class AlertsSection(QFrame):
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger("AlertsSection")
        
        self.setStyleSheet("""
            QFrame { background: white; border-radius: 10px; }
            QTableWidget { border: none; gridline-color: #f0f0f0; }
            QHeaderView::section { background-color: #f8f9fa; border: none; font-weight: bold; color: #7f8c8d; }
        """) 
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        # --- العنوان ---
        header_layout = QHBoxLayout()
        title_lbl = QLabel("⚠️ ALERTES & NOTIFICATIONS")
        title_lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: #2c3e50;")
        header_layout.addWidget(title_lbl)
        header_layout.addStretch()
        layout.addLayout(header_layout)
        
        # --- الجدول ---
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["PRODUIT", "TYPE", "DÉTAILS & ACTION"])
        
        # تفعيل الـ Delegate لضمان ظهور الألوان
        self.table.setItemDelegate(ColorDelegate(self.table))
        
        self.table.setSortingEnabled(True) 
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setShowGrid(False)
        self.table.setFocusPolicy(Qt.NoFocus)
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(False) # إيقاف الألوان التلقائية
        
        layout.addWidget(self.table)

    def update_alerts(self, alerts):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        
        # 1. منطق الترتيب (Sorting Logic)
        # نريد ترتيب تواريخ الانتهاء من الأقرب (الأصغر) إلى الأبعد (الأكبر)
        def sort_key(a):
            type_str = str(a.get('Type', ''))
            is_expiry = "Péremption" in type_str
            # جلب الأيام بشكل آمن، القيمة الافتراضية كبيرة جداً لتكون في الأسفل
            days = a.get('DaysRemaining', 999999) 
            
            # الأولوية 0 لانتهاء الصلاحية لكي يظهر أولاً
            priority = 0 if is_expiry else 1
            
            return (priority, days)

        try:
            alerts.sort(key=sort_key)
        except Exception as e:
            self.logger.error(f"Erreur de tri: {e}")

        font_bold = QFont("Segoe UI", 9, QFont.Weight.Bold)
        font_normal = QFont("Segoe UI", 9)
        
        for row, a in enumerate(alerts):
            self.table.insertRow(row)
            
            product_name = str(a.get('Product', 'Inconnu'))
            alert_type = str(a.get('Type', 'Autre'))
            details_text = str(a.get('Details', ''))
            
            p_item = QTableWidgetItem(product_name)
            p_item.setFont(font_bold)
            
            t_item = QTableWidgetItem(alert_type)
            t_item.setTextAlignment(Qt.AlignCenter)
            t_item.setFont(font_bold)
            
            d_item = QTableWidgetItem(details_text)
            d_item.setFont(font_normal)

            # --- 2. منطق الألوان (Color Logic) ---
            bg_color = None
            text_color = None
            
            if "Péremption" in alert_type:
                days = a.get('DaysRemaining', 99999)
                
                # ترتيب الألوان حسب الأيام
                if days <= 0:
                    # منتهي الصلاحية (أسود أو أحمر غامق جداً)
                    bg_color = QColor("#2c3e50") 
                    text_color = QColor("#e74c3c")
                elif days <= 30:
                    # أحمر (Rouge)
                    bg_color = QColor("#fadbd8")
                    text_color = QColor("#c0392b")
                elif days <= 90:
                    # برتقالي (Orange)
                    bg_color = QColor("#fdebd0")
                    text_color = QColor("#d35400")
                elif days <= 180:
                    # أصفر (Jaune)
                    bg_color = QColor("#fcf3cf")
                    text_color = QColor("#7f8c8d") # نص رمادي ليظهر بوضوح
                elif days <= 365:
                    # أخضر فستقي (Vert pistache)
                    bg_color = QColor("#dcedc8") # درجة الفستقي
                    text_color = QColor("#33691e")
                else:
                    # أخضر غامق (Vert foncé)
                    bg_color = QColor("#e8f5e9")
                    text_color = QColor("#2e7d32")

                if QIcon.hasThemeIcon("fa5s.clock"):
                    t_item.setIcon(QIcon(":/icons/expiry.png"))

            elif "Rupture" in alert_type:
                # لون مميز للنفاد
                bg_color = QColor("#fce4ec") # وردي خفيف جداً
                text_color = QColor("#c2185b")
                
            # تطبيق الألوان باستخدام الفرشاة (Brush)
            final_bg = bg_color if bg_color else QColor("white")
            final_txt = text_color if text_color else QColor("#2c3e50")

            for item in [p_item, t_item, d_item]:
                item.setBackground(QBrush(final_bg))
                item.setForeground(QBrush(final_txt))
            
            self.table.setItem(row, 0, p_item)
            self.table.setItem(row, 1, t_item)
            self.table.setItem(row, 2, d_item)
            
        self.table.resizeRowsToContents()
        self.table.setSortingEnabled(True)