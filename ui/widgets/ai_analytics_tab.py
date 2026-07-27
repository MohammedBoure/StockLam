# ui/widgets/ai_analytics_tab.py

import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView,
    QPushButton, QProgressBar
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor, QFont
from ui.formatting import format_quantity
from ai.ai_service import AIService

class AIWorkerThread(QThread):
    """خيط خلفي لتشغيل حسابات الذكاء الاصطناعي دون تجميد الواجهة (Non-blocking Thread)."""
    finished_signal = Signal(dict)

    def __init__(self, db_instance):
        super().__init__()
        self.db = db_instance

    def run(self):
        try:
            service = AIService(self.db)
            reorder = service.get_smart_reorder_recommendations()
            risks = service.get_expiry_risk_report()
            anomalies = service.get_consumption_anomalies()
            kpis = service.get_ai_kpi_summary()

            self.finished_signal.emit({
                "reorder": reorder,
                "risks": risks,
                "anomalies": anomalies,
                "kpis": kpis
            })
        except Exception as e:
            logging.error(f"AI Worker Error: {e}")
            self.finished_signal.emit({
                "reorder": [],
                "risks": [],
                "anomalies": [],
                "kpis": {}
            })

class AiAnalyticsTab(QWidget):
    """
    تبويب الذكاء الاصطناعي والتحليلات التنبؤية (Predictive AI Analytics Tab).
    """
    def __init__(self, db_instance=None):
        super().__init__()
        self.db = db_instance
        self._init_ui()

    def set_db(self, db_instance):
        self.db = db_instance

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        # --- Header ---
        header_frame = QFrame()
        header_frame.setStyleSheet("""
            QFrame {
                background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
                border-radius: 8px;
                padding: 15px;
            }
            QLabel { color: white; }
        """)
        header_layout = QHBoxLayout(header_frame)

        title_label = QLabel("🧠 الذكاء الاصطناعي والتحليلات التنبؤية (AI & Machine Learning Insights)")
        title_label.setFont(QFont("Segoe UI", 14, QFont.Bold))
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        self.btn_refresh = QPushButton("🔄 تحديث تحليلات الذكاء الاصطناعي")
        self.btn_refresh.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                font-weight: bold;
                padding: 8px 15px;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #219150; }
        """)
        self.btn_refresh.clicked.connect(self.refresh_ai_data)
        header_layout.addWidget(self.btn_refresh)

        main_layout.addWidget(header_frame)

        # --- KPI Cards Row ---
        kpi_layout = QHBoxLayout()
        self.card_reorder = self._create_kpi_card("📦 منتجات تتطلب إعادة طلب", "0", "#e67e22")
        self.card_risks = self._create_kpi_card("⚠️ دفعات عالية خطورة التلف", "0", "#e74c3c")
        self.card_anomalies = self._create_kpi_card("🚨 شذوذ استهلاك مكتشف", "0", "#8e44ad")
        
        kpi_layout.addWidget(self.card_reorder)
        kpi_layout.addWidget(self.card_risks)
        kpi_layout.addWidget(self.card_anomalies)

        main_layout.addLayout(kpi_layout)

        # --- Progress Bar for loading ---
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

        # --- Sub-Tabs ---
        self.tabs = QTabWidget()

        # Tab 1: Demand Forecasting & Auto-Reorder
        self.tab_reorder = QWidget()
        self._setup_reorder_tab()
        self.tabs.addTab(self.tab_reorder, "🔮 التنبؤ بالطلب والطلب الذاتي")

        # Tab 2: Expiry Risk Analyzer
        self.tab_risks = QWidget()
        self._setup_risks_tab()
        self.tabs.addTab(self.tab_risks, "⚠️ تنبؤات مخاطر الصلاحية (Expiry Risk)")

        # Tab 3: Anomaly Detection
        self.tab_anomalies = QWidget()
        self._setup_anomalies_tab()
        self.tabs.addTab(self.tab_anomalies, "🚨 كشف الشذوذ في الاستهلاك والهدر")

        main_layout.addWidget(self.tabs)

    def _create_kpi_card(self, title: str, value: str, color: str) -> QFrame:
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: white;
                border-left: 5px solid {color};
                border-radius: 6px;
                padding: 10px;
                border-top: 1px solid #dcdde1;
                border-right: 1px solid #dcdde1;
                border-bottom: 1px solid #dcdde1;
            }}
        """)
        layout = QVBoxLayout(card)
        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("color: #7f8c8d; font-weight: bold;")
        lbl_val = QLabel(value)
        lbl_val.setFont(QFont("Segoe UI", 16, QFont.Bold))
        lbl_val.setStyleSheet(f"color: {color};")
        lbl_val.setObjectName("value_label")

        layout.addWidget(lbl_title)
        layout.addWidget(lbl_val)
        return card

    def _setup_reorder_tab(self):
        layout = QVBoxLayout(self.tab_reorder)
        self.table_reorder = QTableWidget()
        cols = ["المنتج", "المخزون الحالي", "معدل الاستهلاك اليومي (EMA)", "الأيام المتبقية للنفاذ", "الكمية الموصى بشرائها (علبة)", "مستوى الثقة"]
        self.table_reorder.setColumnCount(len(cols))
        self.table_reorder.setHorizontalHeaderLabels(cols)
        self.table_reorder.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table_reorder)

    def _setup_risks_tab(self):
        layout = QVBoxLayout(self.tab_risks)
        self.table_risks = QTableWidget()
        cols = ["رقم الدفعة", "المنتج", "تاريخ الانتهاء", "الأيام المتبقية", "درجة الخطر (Risk Score)", "مستوى الخطر", "التوصية الذكية"]
        self.table_risks.setColumnCount(len(cols))
        self.table_risks.setHorizontalHeaderLabels(cols)
        self.table_risks.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table_risks)

    def _setup_anomalies_tab(self):
        layout = QVBoxLayout(self.tab_anomalies)
        self.table_anomalies = QTableWidget()
        cols = ["التاريخ", "المنتج", "نوع الحركة", "الكمية المهدورة", "المعدل الطبيعي للمنتج", "معامل الشذوذ (Z-Score)", "المشغل", "السبب"]
        self.table_anomalies.setColumnCount(len(cols))
        self.table_anomalies.setHorizontalHeaderLabels(cols)
        self.table_anomalies.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table_anomalies)

    def refresh_ai_data(self):
        if not self.db:
            return

        self.btn_refresh.setEnabled(False)
        self.progress_bar.setVisible(True)

        self.worker = AIWorkerThread(self.db)
        self.worker.finished_signal.connect(self._on_ai_data_loaded)
        self.worker.start()

    def _on_ai_data_loaded(self, data: dict):
        self.btn_refresh.setEnabled(True)
        self.progress_bar.setVisible(False)

        kpis = data.get('kpis', {})
        self.card_reorder.findChild(QLabel, "value_label").setText(str(kpis.get('products_needing_reorder', 0)))
        self.card_risks.findChild(QLabel, "value_label").setText(str(kpis.get('batches_high_expiry_risk', 0)))
        self.card_anomalies.findChild(QLabel, "value_label").setText(str(kpis.get('detected_waste_anomalies', 0)))

        # 1. Fill Reorder Table
        reorder_list = data.get('reorder', [])
        self.table_reorder.setRowCount(0)
        for row, item in enumerate(reorder_list):
            self.table_reorder.insertRow(row)
            self.table_reorder.setItem(row, 0, QTableWidgetItem(str(item.get('product_name'))))
            self.table_reorder.setItem(row, 1, QTableWidgetItem(f"{item.get('current_stock_boxes', 0)} U"))
            self.table_reorder.setItem(row, 2, QTableWidgetItem(f"{item.get('daily_demand_avg', 0)} / يوم"))
            
            days_item = QTableWidgetItem(f"{item.get('days_until_depletion', 0)} يوم")
            if item.get('days_until_depletion', 99) <= 7:
                days_item.setForeground(QColor("#e74c3c"))
                days_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            self.table_reorder.setItem(row, 3, days_item)

            rec_item = QTableWidgetItem(f"{item.get('recommended_reorder_qty_boxes', 0)} علبة")
            rec_item.setForeground(QColor("#27ae60"))
            rec_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            self.table_reorder.setItem(row, 4, rec_item)

            self.table_reorder.setItem(row, 5, QTableWidgetItem(f"{item.get('confidence_score', 0)}%"))

        # 2. Fill Risks Table
        risks_list = data.get('risks', [])
        self.table_risks.setRowCount(0)
        for row, item in enumerate(risks_list):
            self.table_risks.insertRow(row)
            self.table_risks.setItem(row, 0, QTableWidgetItem(str(item.get('batch_number'))))
            self.table_risks.setItem(row, 1, QTableWidgetItem(str(item.get('product_name'))))
            self.table_risks.setItem(row, 2, QTableWidgetItem(str(item.get('expiry_date'))))
            self.table_risks.setItem(row, 3, QTableWidgetItem(f"{item.get('days_left')} يوم"))
            
            score_item = QTableWidgetItem(f"{item.get('risk_score')}%")
            if item.get('risk_score', 0) >= 70:
                score_item.setForeground(QColor("#e74c3c"))
                score_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            self.table_risks.setItem(row, 4, score_item)

            self.table_risks.setItem(row, 5, QTableWidgetItem(str(item.get('risk_level'))))
            self.table_risks.setItem(row, 6, QTableWidgetItem(str(item.get('recommendation'))))

        # 3. Fill Anomalies Table
        anomalies_list = data.get('anomalies', [])
        self.table_anomalies.setRowCount(0)
        for row, item in enumerate(anomalies_list):
            self.table_anomalies.insertRow(row)
            self.table_anomalies.setItem(row, 0, QTableWidgetItem(str(item.get('transaction_date'))))
            self.table_anomalies.setItem(row, 1, QTableWidgetItem(str(item.get('product_name'))))
            self.table_anomalies.setItem(row, 2, QTableWidgetItem(str(item.get('movement_type'))))
            self.table_anomalies.setItem(row, 3, QTableWidgetItem(f"{item.get('qty_wasted')} {item.get('unit')}"))
            self.table_anomalies.setItem(row, 4, QTableWidgetItem(f"{item.get('mean_product_waste')} {item.get('unit')}"))
            
            z_item = QTableWidgetItem(f"{item.get('z_score')}")
            z_item.setForeground(QColor("#8e44ad"))
            z_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            self.table_anomalies.setItem(row, 5, z_item)

            self.table_anomalies.setItem(row, 6, QTableWidgetItem(str(item.get('operator_name'))))
            self.table_anomalies.setItem(row, 7, QTableWidgetItem(str(item.get('reason'))))
