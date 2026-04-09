# ui/widgets/supplier/supplier_financial_view.py

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QLabel, QFrame, 
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QComboBox, 
    QDateEdit, QSpacerItem, QSizePolicy, QMessageBox
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QColor, QBrush, QFont
import qtawesome as qta

# استيراد الواجهة السابقة (أو إعادة استخدام منطقها)
# سنفترض أننا دمجنا المنطق هنا لسهولة التصفح، أو يمكنك استيراد الكلاسات القديمة
from .supplier_stats_tab import SupplierStatsTab, AddPaymentDialog

# ==============================================================================
# 1. بطاقة إحصائية (KPI Card) - لعرض الأرقام المهمة في الأعلى
# ==============================================================================
class StatCard(QFrame):
    def __init__(self, title, value, icon_name, color, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: white;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                border-left: 5px solid {color};
            }}
        """)
        self.setFixedWidth(220)
        self.setFixedHeight(80)
        
        layout = QHBoxLayout(self)
        
        # Icon
        lbl_icon = QLabel()
        lbl_icon.setPixmap(qta.icon(icon_name, color=color).pixmap(32, 32))
        lbl_icon.setStyleSheet("border: none;")
        
        # Text
        text_layout = QVBoxLayout()
        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("color: #7f8c8d; font-size: 12px; font-weight: bold; border: none;")
        
        self.lbl_value = QLabel(value)
        self.lbl_value.setStyleSheet(f"color: #2c3e50; font-size: 18px; font-weight: bold; border: none;")
        
        text_layout.addWidget(lbl_title)
        text_layout.addWidget(self.lbl_value)
        
        layout.addWidget(lbl_icon)
        layout.addLayout(text_layout)

    def update_value(self, new_value):
        self.lbl_value.setText(new_value)

# ==============================================================================
# 2. تبويب لوحة القيادة (Dashboard Tab)
# ==============================================================================
class SupplierDashboard(QWidget):
    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # --- صف البطاقات ---
        cards_layout = QHBoxLayout()
        self.card_total_debt = StatCard("Dette Totale", "0.00 DA", "fa5s.hand-holding-usd", "#e74c3c")
        self.card_monthly_paid = StatCard("Payé ce Mois", "0.00 DA", "fa5s.check-circle", "#27ae60")
        self.card_suppliers_count = StatCard("Fournisseurs Actifs", "0", "fa5s.users", "#2980b9")
        
        cards_layout.addWidget(self.card_total_debt)
        cards_layout.addWidget(self.card_monthly_paid)
        cards_layout.addWidget(self.card_suppliers_count)
        cards_layout.addStretch()
        
        layout.addLayout(cards_layout)
        
        # --- رسالة ترحيبية أو رسم بياني (مساحة فارغة للتطوير المستقبلي) ---
        center_frame = QFrame()
        center_frame.setStyleSheet("background-color: white; border-radius: 8px; border: 1px solid #cfd8dc;")
        center_layout = QVBoxLayout(center_frame)
        
        lbl_info = QLabel("📊 Vue d'ensemble des finances fournisseurs")
        lbl_info.setAlignment(Qt.AlignCenter)
        lbl_info.setStyleSheet("font-size: 16px; color: #95a5a6; border: none;")
        
        center_layout.addStretch()
        center_layout.addWidget(lbl_info)
        center_layout.addStretch()
        
        layout.addWidget(center_frame)

    def refresh_stats(self):
        # هنا يمكنك إضافة دوال في المانجر لجلب هذه الأرقام الحقيقية
        # حالياً سأضع أرقام وهمية أو بسيطة كمثال
        try:
            suppliers = self.manager.suppliers.get_all_suppliers()
            self.card_suppliers_count.update_value(str(len(suppliers)))
            
            # مثال: حساب الديون يتطلب استعلاماً خاصاً، يمكنك إضافته لاحقاً
            # total_debt = self.manager.suppliers.get_total_debt()
            # self.card_total_debt.update_value(f"{total_debt:,.2f} DA")
        except:
            pass

# ==============================================================================
# 3. تبويب سجل المدفوعات (Payments Journal Tab)
# ==============================================================================
class PaymentsJournal(QWidget):
    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Filter Bar
        filter_layout = QHBoxLayout()
        self.date_from = QDateEdit(QDate.currentDate().addMonths(-1))
        self.date_from.setCalendarPopup(True)
        self.date_to = QDateEdit(QDate.currentDate())
        self.date_to.setCalendarPopup(True)
        
        btn_refresh = QPushButton("Actualiser")
        btn_refresh.setIcon(qta.icon("fa5s.sync"))
        btn_refresh.clicked.connect(self.load_payments)
        
        filter_layout.addWidget(QLabel("Du:"))
        filter_layout.addWidget(self.date_from)
        filter_layout.addWidget(QLabel("Au:"))
        filter_layout.addWidget(self.date_to)
        filter_layout.addWidget(btn_refresh)
        filter_layout.addStretch()
        
        layout.addLayout(filter_layout)
        
        # Table
        self.table = QTableWidget()
        cols = ["ID", "Date", "Fournisseur", "Montant", "Mode", "Référence", "Note"]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setColumnHidden(0, True) # ID Hidden
        layout.addWidget(self.table)
        
        # Load initial data
        # self.load_payments() # Uncomment when function is ready

    def load_payments(self):
        # ستحتاج لإضافة دالة في SupplierManager لجلب المدفوعات فقط
        # get_all_payments(start_date, end_date)
        pass

# ==============================================================================
# 4. الواجهة الرئيسية المجمعة (Main Container)
# ==============================================================================
class SupplierFinancialView(QWidget):
    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # --- العنوان الرئيسي ---
        header_frame = QFrame()
        header_frame.setStyleSheet("background-color: #ffffff; border-bottom: 1px solid #e0e0e0;")
        header_layout = QHBoxLayout(header_frame)
        
        lbl_title = QLabel("Gestion Financière Fournisseurs")
        lbl_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #2c3e50; border: none;")
        lbl_icon = QLabel()
        lbl_icon.setPixmap(qta.icon("fa5s.file-invoice-dollar", color="#2c3e50").pixmap(24, 24))
        lbl_icon.setStyleSheet("border: none;")
        
        header_layout.addWidget(lbl_icon)
        header_layout.addWidget(lbl_title)
        header_layout.addStretch()
        
        # زر إجراء سريع لإضافة دفعة
        btn_quick_pay = QPushButton("Nouveau Paiement")
        btn_quick_pay.setIcon(qta.icon("fa5s.plus", color="white"))
        btn_quick_pay.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; padding: 8px 15px; border-radius: 4px;")
        btn_quick_pay.clicked.connect(self.open_quick_payment)
        
        header_layout.addWidget(btn_quick_pay)
        layout.addWidget(header_frame)

        # --- التبويبات ---
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 0; background: #f4f7fa; }
            QTabBar::tab { min-width: 150px; }
        """)
        
        # 1. Situation (الموجودة سابقاً)
        self.tab_situation = SupplierStatsTab(self.manager)
        
        # 2. Dashboard (الجديدة)
        self.tab_dashboard = SupplierDashboard(self.manager)
        
        # 3. Journal (الجديدة)
        self.tab_journal = PaymentsJournal(self.manager)
        
        layout.addWidget(self.tabs)

    def open_quick_payment(self):
        """فتح نافذة الدفع مباشرة وتحديث التبويب الحالي"""
        # نستخدم نافذة الدفع من الكود السابق، لكن نطلب اختيار المورد أولاً
        # أو يمكننا فتحها بمورد فارغ إذا عدلنا الكود ليقبل ذلك
        
        # هنا سنقوم بفتح تبويب Situation ونطلب من المستخدم اختيار المورد
        self.tabs.setCurrentIndex(0)
        self.tab_situation.add_payment() # نستدعي الدالة الموجودة في التبويب