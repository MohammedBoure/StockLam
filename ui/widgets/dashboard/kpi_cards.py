# ui/widgets/dashboard/kpi_cards.py

from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QFrame
from PySide6.QtCore import Qt

from ui.formatting import format_money, format_quantity

class KPICard(QFrame):
    # أضفنا معامل جديد sub_value (اختياري)
    def __init__(self, title, value, icon_char, color="#007572", sub_value=None):
        super().__init__()
        self.setMinimumHeight(130)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: white; 
                border-radius: 12px; 
                border: 1px solid #eef2f5;
            }}
            QFrame:hover {{ 
                border: 2px solid {color}; 
                background-color: #fcfdfd;
            }}
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 15, 20, 15)
        
        text_side = QVBoxLayout()
        text_side.setSpacing(2) # تقليل المسافة بين العناصر العمودية
        
        lbl_title = QLabel(title.upper())
        lbl_title.setStyleSheet("color: #7f8c8d; font-size: 11px; font-weight: 700; letter-spacing: 1px; border:none;")
        
        # القيمة الرئيسية (الكمية)
        self.lbl_value = QLabel(value)
        self.lbl_value.setStyleSheet(f"color: {color}; font-size: 24px; font-weight: 900; border:none;")
        
        text_side.addWidget(lbl_title)
        text_side.addWidget(self.lbl_value)
        
        # --- الإضافة الجديدة: النص السفلي (القيمة المالية) ---
        if sub_value:
            self.lbl_sub = QLabel(sub_value)
            # تنسيق النص السفلي: أصغر حجماً، ولون أفتح قليلاً
            self.lbl_sub.setStyleSheet(f"color: {color}; font-size: 13px; font-weight: 600; opacity: 0.8; border:none;")
            text_side.addWidget(self.lbl_sub)
        
        text_side.addStretch()
        
        # أيقونة
        icon_circle = QLabel(icon_char)
        icon_circle.setFixedSize(60, 60)
        icon_circle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_circle.setStyleSheet(f"""
            background-color: {color}15; 
            border-radius: 30px; 
            font-size: 28px; 
            color: {color}; 
            border:none;
        """)
        
        layout.addLayout(text_side, 1)
        layout.addWidget(icon_circle)

class KPICardsSection(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(15)

    def update_data(self, stats, total_consumed_qty=0, total_consumed_value=0):
        # تنظيف البطاقات القديمة
        while self.layout.count():
            child = self.layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()
        
        # --- 1. VALEUR STOCK ---
        val_stock = stats.get('total_stock_value', 0)
        stock_str = format_money(val_stock, "DA").replace(',', ' ')
        
        # --- 2. CONSOMMATION ---
        val_consumed_money = stats.get('total_consumed_value', total_consumed_value)
        cons_str = format_money(val_consumed_money, "DA").replace(',', ' ')
        
        # --- 3. SORTIES STOCK ---
        val_consumed_qty = stats.get('total_consumed_units', total_consumed_qty)
        qty_str = format_quantity(val_consumed_qty)
        
        # --- 4. PERTES & DÉCHETS ---
        waste_qty = stats.get('total_waste_units', 0.0)
        waste_val = stats.get('total_waste_value', 0)
        
        # الكمية (الرقم الكبير)
        waste_qty_str = format_quantity(waste_qty)
        # القيمة (الرقم الصغير بالأسفل)
        waste_val_str = format_money(waste_val, "DA").replace(',', ' ')
        
        # --- إنشاء البطاقات ---
        # البطاقات العادية (بدون قيمة سفلية)
        self.layout.addWidget(KPICard("VALEUR STOCK", stock_str, "💰", "#27ae60"))
        self.layout.addWidget(KPICard("CONSOMMATION", cons_str, "💸", "#2980b9"))
        self.layout.addWidget(KPICard("SORTIES STOCK", qty_str, "📦", "#16a085"))
        
        # البطاقة الرابعة (مع القيمة السفلية)
        # نمرر waste_qty_str كقيمة رئيسية، و waste_val_str كقيمة فرعية
        self.layout.addWidget(KPICard(
            title="PERTES & DÉCHETS", 
            value=waste_qty_str,         # الكمية (كبير)
            icon_char="🗑️", 
            color="#c0392b",             # أحمر
            sub_value=waste_val_str      # القيمة المالية (صغير تحته)
        ))
