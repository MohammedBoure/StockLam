# ui/widgets/dashboard/dashboard_view.py

import logging
import gc
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, 
                               QPushButton, QDateEdit, QLabel, QFrame, QTabWidget, QApplication)
from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QColor

try:
    import matplotlib.pyplot as plt
except ImportError:
    plt = None

from .overview_tab import OverviewTab 
from .alerts_section import AlertsSection
from .consumption_reports import ConsumptionReportSection
from .statistics_tabs import StockValuationTab, WasteAnalysisTab
from .family_reception_tab import FamilyReceptionTab

class DashboardTab(QWidget):
    def __init__(self, data_manager):
        super().__init__()
        self.data_manager = data_manager
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- Toolbar ---
        toolbar = QFrame()
        toolbar.setStyleSheet("background-color: white; border-bottom: 1px solid #dcdde1;")
        toolbar.setFixedHeight(75)
        tool_layout = QHBoxLayout(toolbar)
        tool_layout.setContentsMargins(25, 0, 25, 0)

        lbl_title = QLabel("📊 TABLEAU DE BORD INTÉGRAL")
        lbl_title.setStyleSheet("font-size: 18px; font-weight: 900; color: #2c3e50;")
        
        self.date_from = QDateEdit(QDate.currentDate().addDays(-30))
        self.date_to = QDateEdit(QDate.currentDate())
        for d in [self.date_from, self.date_to]:
            d.setCalendarPopup(True)
            d.setFixedWidth(120)
            d.setStyleSheet("padding: 5px; border: 1px solid #bdc3c7; border-radius: 4px;")

        self.btn_refresh = QPushButton("ACTUALISER")
        self.btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_refresh.setStyleSheet("""
            QPushButton { 
                background-color: #007572; color: white; font-weight: bold; 
                border-radius: 4px; padding: 8px 20px; border: none;
            }
            QPushButton:hover { background-color: #005a58; }
            QPushButton:disabled { background-color: #bdc3c7; color: #7f8c8d; }
        """)
        self.btn_refresh.clicked.connect(self.refresh_all)

        tool_layout.addWidget(lbl_title)
        tool_layout.addStretch()
        tool_layout.addWidget(QLabel("Du:"))
        tool_layout.addWidget(self.date_from)
        tool_layout.addWidget(QLabel("Au:"))
        tool_layout.addWidget(self.date_to)
        tool_layout.addSpacing(10)
        tool_layout.addWidget(self.btn_refresh)
        main_layout.addWidget(toolbar)

        # --- Content ---
        content_container = QWidget()
        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(15, 15, 15, 15)
        content_layout.setSpacing(10)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #dcdde1; background: white; border-radius: 8px; }
            QTabBar::tab { 
                background: #ecf0f1; color: #7f8c8d; padding: 12px 25px; 
                font-weight: bold; margin-right: 2px; border-top-left-radius: 6px; border-top-right-radius: 6px;
            }
            QTabBar::tab:selected { 
                background: white; color: #007572; border-top: 3px solid #007572; 
            }
            QTabBar::tab:hover { background: #e0e0e0; }
        """)

        # 1. الصفحة المجمعة (Overview: KPIs + Charts)
        self.page_overview = OverviewTab()
        
        # باقي الصفحات
        self.page_family_reception = FamilyReceptionTab(data_manager)
        self.page_valuation = StockValuationTab()
        self.page_consumption = ConsumptionReportSection(data_manager.stats)
        self.page_waste = WasteAnalysisTab()
        self.page_alerts = AlertsSection()

        content_layout.addWidget(self.tabs)
        main_layout.addWidget(content_container)
        
        # التحديث الأولي
        from PySide6.QtCore import QTimer
        QTimer.singleShot(100, self.refresh_all)

    def refresh_all(self):
        if not self.btn_refresh.isEnabled(): return
        self.btn_refresh.setEnabled(False)
        self.btn_refresh.setText("Chargement...")
        QApplication.processEvents()

        if plt: plt.close('all')
        gc.collect()

        d1_str = self.date_from.date().toString("yyyy-MM-dd")
        d2_str = self.date_to.date().toString("yyyy-MM-dd")

        try:
            # --- جلب البيانات ---
            stats_summary = self.data_manager.stats.get_kpi_summary()
            consumption_data = self.data_manager.stats.get_detailed_consumption_report(d1_str, d2_str)
            total_qty = sum(float(i.get('total_qty_consumed', 0)) for i in consumption_data)
            total_val = sum(float(i.get('total_cost_ttc', 0)) for i in consumption_data)
            
            # 1. تحديث الصفحة المجمعة (KPIs + Charts)
            # نصل إلى الأقسام الداخلية عبر page_overview
            self.page_overview.kpi_section.update_data(stats_summary, total_qty, total_val)
            
            # [تعديل] جلب بيانات المصاريف (Consommation) والمداخيل (Réception)
            cons_trend = self.data_manager.stats.get_consumption_trend(d1_str, d2_str)
            rec_trend = self.data_manager.stats.get_reception_trend(d1_str, d2_str)
            
            # [تعديل] تمرير البيانات (المصاريف + المداخيل) للمبيان
            self.page_overview.charts_section.update_charts(cons_trend, rec_trend)
            
            # 2. التبويبات الأخرى
            self.page_valuation.refresh(self.data_manager.stats)
            self.page_consumption.update_params(self.date_from.date(), self.date_to.date())
            self.page_consumption.refresh_report()
            self.page_waste.refresh(self.data_manager.stats, d1_str, d2_str)
            
            alerts = self.data_manager.stats.get_active_alerts()
            self.page_alerts.update_alerts(alerts)

            idx_alerts = self.tabs.indexOf(self.page_alerts)

            if idx_alerts != -1:
                crit_count = sum(1 for a in alerts if a.get('Criticality') == 'High')
                if crit_count > 0:
                    self.tabs.setTabText(idx_alerts, f"⚠️ Alertes ({len(alerts)})")
                    self.tabs.tabBar().setTabTextColor(idx_alerts, QColor("#c0392b"))
                else:
                    self.tabs.setTabText(idx_alerts, "✅ Alertes (0)")
                    self.tabs.tabBar().setTabTextColor(idx_alerts, QColor("#27ae60"))
            
            # تلوين تبويب التنبيهات (الاندكس 5 لأننا أضفنا 6 تبويبات والترتيب يبدأ من 0)
            crit_count = sum(1 for a in alerts if a.get('Criticality') == 'High')
            idx_alerts = 5
            if crit_count > 0:
                self.tabs.setTabText(idx_alerts, f"⚠️ Alertes ({len(alerts)})")
                self.tabs.tabBar().setTabTextColor(idx_alerts, QColor("#c0392b"))
            else:
                self.tabs.setTabText(idx_alerts, "✅ Alertes (0)")
                self.tabs.tabBar().setTabTextColor(idx_alerts, QColor("#27ae60"))
        except Exception as e:
            logging.error(f"Dashboard Refresh Error: {e}", exc_info=True)
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Erreur", f"Erreur lors de l'actualisation: {str(e)}")
        
        finally:
            self.btn_refresh.setEnabled(True)
            self.btn_refresh.setText("ACTUALISER")
            gc.collect()