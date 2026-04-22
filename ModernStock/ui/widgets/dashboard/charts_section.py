# ui/widgets/dashboard/charts_section.py

import logging
from datetime import date, datetime, timedelta
from PySide6.QtWidgets import QWidget, QVBoxLayout, QToolTip 
from PySide6.QtCharts import (QChart, QChartView, QLineSeries, QDateTimeAxis, 
                              QValueAxis, QAreaSeries, QLegend)
from PySide6.QtCore import Qt, QDateTime, QTime, QPointF, QMargins
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QLinearGradient, QGradient, QCursor

class ChartsSection(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # 1. إعداد الشارت
        self.chart = QChart()
        self.chart.setTitle("💸 Comparaison Financière : Entrées (Achats) vs Sorties (Consommation)")
        self.chart.setTitleFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)
        self.chart.setBackgroundVisible(False)
        self.chart.setMargins(QMargins(0, 0, 0, 0))

        # 2. وسيلة الإيضاح (Legend)
        self.chart.legend().setVisible(True)
        self.chart.legend().setAlignment(Qt.AlignmentFlag.AlignBottom)
        self.chart.legend().setFont(QFont("Segoe UI", 10))
        self.chart.legend().setMarkerShape(QLegend.MarkerShape.MarkerShapeCircle)

        # 3. العرض
        self.view = QChartView(self.chart)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # تفعيل تتبع الماوس ضروري لظهور التلميحات بسلاسة
        self.view.setMouseTracking(True)
        
        self.view.setStyleSheet("""
            background-color: white; 
            border-radius: 12px; 
            border: 1px solid #eef2f5;
        """)
        layout.addWidget(self.view)

    def _parse_date(self, date_val):
        """تحويل موحد للتاريخ"""
        if isinstance(date_val, datetime): return date_val.date()
        if isinstance(date_val, date): return date_val
        if isinstance(date_val, str):
            try: 
                if "T" in date_val: return datetime.fromisoformat(date_val).date()
                return datetime.strptime(date_val, "%Y-%m-%d").date()
            except: pass
        return None

    def _align_and_fill_data(self, consumption_data, reception_data):
        """توحيد البيانات زمنياً"""
        from collections import defaultdict

        cons_map = defaultdict(float)
        for x in consumption_data:
            d = self._parse_date(x.get('date'))
            val = float(x.get('daily_cost', 0) or x.get('daily_value', 0))
            if d: cons_map[d] += val

        rec_map = defaultdict(float)
        for x in reception_data:
            d = self._parse_date(x.get('date'))
            val = float(x.get('daily_cost', 0) or x.get('daily_value', 0))
            if d: rec_map[d] += val

        all_dates = list(set(list(cons_map.keys()) + list(rec_map.keys())))
        all_dates.sort()
        
        if not all_dates:
            return [], [], 0.0, date.today(), date.today()

        min_date = all_dates[0]
        max_date = all_dates[-1]

        points_cons = []
        points_rec = []
        
        current_date = min_date
        max_val_found = 0.0

        while current_date <= max_date:
            q_dt = QDateTime(current_date, QTime(0, 0))
            ms_ts = q_dt.toMSecsSinceEpoch()

            val_c = cons_map.get(current_date, 0.0)
            val_r = rec_map.get(current_date, 0.0)

            if val_c > max_val_found: max_val_found = val_c
            if val_r > max_val_found: max_val_found = val_r

            points_cons.append(QPointF(ms_ts, val_c))
            points_rec.append(QPointF(ms_ts, val_r))

            current_date += timedelta(days=1)

        return points_cons, points_rec, max_val_found, min_date, max_date

    def show_tooltip(self, point, state):
        """
        دالة لعرض القيمة والتاريخ عند مرور الماوس
        point: إحداثيات النقطة في الرسم
        state: True إذا دخل الماوس للنقطة، False إذا خرج
        """
        if state:
            # 1. تحويل التاريخ من ميلي ثانية إلى نص مقروء
            date_val = QDateTime.fromMSecsSinceEpoch(int(point.x())).toString("dd/MM/yyyy")
            
            # 2. تنسيق المبلغ (بدون فواصل عشرية وبإضافة DA)
            amount_val = point.y()
            formatted_amount = f"{amount_val:,.0f} DA".replace(",", " ")
            
            # 3. إعداد نص التلميح
            tooltip_text = f"📅 Date: {date_val}\n💰 Montant: {formatted_amount}"
            
            # 4. إظهار التلميح بجانب الماوس
            QToolTip.showText(QCursor.pos(), tooltip_text)
        else:
            # إخفاء التلميح عند الابتعاد
            QToolTip.hideText()

    def update_charts(self, consumption_data, reception_data):
        try:
            self.chart.removeAllSeries()
            for ax in self.chart.axes():
                self.chart.removeAxis(ax)

            pts_cons, pts_rec, max_val, start_date, end_date = self._align_and_fill_data(consumption_data, reception_data)

            if not pts_cons and not pts_rec:
                return

            q_start = QDateTime(start_date, QTime(0,0))
            q_end = QDateTime(end_date, QTime(0,0))
            
            # --- رسم الخطوط ---
            
            # 1. استهلاك (أحمر)
            series_cons = QLineSeries()
            series_cons.setName("Sorties (Consommation)")
            series_cons.setPen(QPen(QColor("#e74c3c"), 3))
            
            # تفعيل النقاط لتسهيل عملية Hover
            series_cons.setPointsVisible(True) 
            series_cons.setPointLabelsVisible(False)
            
            # ربط إشارة التمرير بدالة العرض
            series_cons.hovered.connect(self.show_tooltip) 

            for p in pts_cons: series_cons.append(p)

            area_cons = QAreaSeries(series_cons)
            grad_cons = QLinearGradient(0, 0, 0, 1)
            grad_cons.setCoordinateMode(QGradient.CoordinateMode.ObjectBoundingMode)
            grad_cons.setColorAt(0.0, QColor(231, 76, 60, 80)) 
            grad_cons.setColorAt(1.0, QColor(231, 76, 60, 10))
            area_cons.setBrush(grad_cons)
            area_cons.setPen(QPen(Qt.PenStyle.NoPen))

            # 2. مشتريات (أخضر)
            series_rec = QLineSeries()
            series_rec.setName("Entrées (Achats)")
            series_rec.setPen(QPen(QColor("#27ae60"), 3))
            
            # تفعيل النقاط وربط الإشارة
            series_rec.setPointsVisible(True)
            series_rec.hovered.connect(self.show_tooltip)

            for p in pts_rec: series_rec.append(p)

            area_rec = QAreaSeries(series_rec)
            grad_rec = QLinearGradient(0, 0, 0, 1)
            grad_rec.setCoordinateMode(QGradient.CoordinateMode.ObjectBoundingMode)
            grad_rec.setColorAt(0.0, QColor(39, 174, 96, 80))
            grad_rec.setColorAt(1.0, QColor(39, 174, 96, 10))
            area_rec.setBrush(grad_rec)
            area_rec.setPen(QPen(Qt.PenStyle.NoPen))

            self.chart.addSeries(area_rec)
            self.chart.addSeries(area_cons)
            self.chart.addSeries(series_rec)
            self.chart.addSeries(series_cons)

            # إخفاء التكرار في المفتاح
            for marker in self.chart.legend().markers(area_cons): marker.setVisible(False)
            for marker in self.chart.legend().markers(area_rec): marker.setVisible(False)

            # --- المحاور ---
            ax_x = QDateTimeAxis()
            ax_x.setFormat("dd/MM")
            ax_x.setTickCount(min(len(pts_cons), 8))
            ax_x.setRange(q_start, q_end)
            self.chart.addAxis(ax_x, Qt.AlignmentFlag.AlignBottom)

            ax_y = QValueAxis()
            ax_y.setLabelFormat("%.0f") 
            if max_val > 1000000:
                ax_y.setTitleText("Montant (DA)")
            ax_y.setRange(0, max_val * 1.1) 
            self.chart.addAxis(ax_y, Qt.AlignmentFlag.AlignLeft)

            for s in [series_cons, area_cons, series_rec, area_rec]:
                s.attachAxis(ax_x)
                s.attachAxis(ax_y)

        except Exception as e:
            logging.error(f"Error updating charts: {e}")