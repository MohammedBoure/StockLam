# ui/widgets/dashboard/overview_tab.py

from PySide6.QtWidgets import QWidget, QVBoxLayout, QFrame
from .kpi_cards import KPICardsSection
from .charts_section import ChartsSection

class OverviewTab(QWidget):
    def __init__(self, stats_manager=None):
        super().__init__()
        self.stats_manager = stats_manager
        self.init_ui()

    def init_ui(self):
        # تخطيط عمودي: البطاقات فوق، المبيان تحت
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        # 1. قسم البطاقات (KPIs)
        self.kpi_section = KPICardsSection()
        self.kpi_section.setFixedHeight(150) # تحديد ارتفاع ثابت للقسم العلوي لكي لا يأخذ مساحة المبيان
        layout.addWidget(self.kpi_section)

        # خط فاصل (اختياري)
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: #ecf0f1;")
        layout.addWidget(line)

        # 2. قسم المبيان (Charts)
        self.charts_section = ChartsSection(stats_manager=self.stats_manager)
        # الرقم 1 يعني أن المبيان سيأخذ كل المساحة المتبقية
        layout.addWidget(self.charts_section, 1)