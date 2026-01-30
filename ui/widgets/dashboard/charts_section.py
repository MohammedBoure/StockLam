# ui/widgets/dashboard/charts_section.py

import logging
from datetime import date, datetime, timedelta
from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtCharts import (QChart, QChartView, QLineSeries, QDateTimeAxis, 
                              QValueAxis, QAreaSeries, QLegend, QScatterSeries)
from PySide6.QtCore import Qt, QDateTime, QDate, QTime, QPointF, QMargins
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QLinearGradient, QGradient, QBrush

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
        self.view.setStyleSheet("""
            background-color: white; 
            border-radius: 12px; 
            border: 1px solid #eef2f5;
        """)
        layout.addWidget(self.view)

    def _parse_date(self, date_val):
        """تحويل موحد للتاريخ إلى كائن date"""
        if isinstance(date_val, datetime): return date_val.date()
        if isinstance(date_val, date): return date_val
        if isinstance(date_val, str):
            try: return datetime.strptime(date_val, "%Y-%m-%d").date()
            except: pass
        return None

    def _align_and_fill_data(self, consumption_data, reception_data):
        """توحيد الجدول الزمني وملء الفراغات بالأصفار"""
        cons_map = {}
        for x in consumption_data:
            d = self._parse_date(x.get('date'))
            if d: cons_map[d] = float(x.get('daily_cost', 0) or x.get('daily_value', 0))

        rec_map = {}
        for x in reception_data:
            d = self._parse_date(x.get('date'))
            if d: rec_map[d] = float(x.get('daily_cost', 0) or x.get('daily_value', 0))

        all_dates = list(set(list(cons_map.keys()) + list(rec_map.keys())))
        if not all_dates:
            return [], [], 0.0, None, None

        min_date = min(all_dates)
        max_date = max(all_dates)

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

    def _create_label_series(self, points, color_hex, name, overall_duration_ms):
        """
        إنشاء سلسلة نقاط لعرض القيم مع فلترة التداخل.
        overall_duration_ms: المدة الزمنية الكلية للمبيان (لحساب المسافة المناسبة)
        """
        scatter = QScatterSeries()
        scatter.setName(name)
        scatter.setMarkerSize(8) # حجم النقطة
        scatter.setColor(QColor(color_hex))
        scatter.setBorderColor(QColor("white")) # حدود بيضاء للنقطة لجمالية أكثر
        
        # إعداد عرض النصوص
        scatter.setPointLabelsVisible(True)
        scatter.setPointLabelsFormat("@yPoint") # عرض القيمة Y
        scatter.setPointLabelsFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        scatter.setPointLabelsColor(QColor(color_hex))
        
        # منطق الفلترة لمنع التداخل
        # نسمح بعرض التسمية فقط إذا كانت المسافة الزمنية عن السابقة كافية
        # مثلاً: الحد الأدنى هو 6% من عرض المبيان
        min_gap = overall_duration_ms * 0.06 
        
        last_x = -1
        
        for p in points:
            val = p.y()
            # 1. دائماً نعرض النقاط ذات القيمة الكبيرة (Local Peaks) أو تخطي الأصفار إذا أردت
            # هنا سنعرض النقاط بناءً على التباعد
            
            # إذا كانت القيمة 0، قد نفضل عدم عرض الرقم لتخفيف الزحمة، إلا إذا كانت النقاط قليلة
            if val == 0 and len(points) > 10:
                # أضف النقطة للمنحنى لكن بدون نص؟ QScatterSeries لا يدعم نصاً شرطياً لكل نقطة بسهولة
                # لذا سنتخطى إضافة النقطة لسلسلة النصوص تماماً إذا كانت 0 ومزدحمة
                continue 

            if last_x == -1 or (p.x() - last_x) > min_gap:
                scatter.append(p)
                last_x = p.x()
        
        return scatter

    def update_charts(self, consumption_data, reception_data):
        try:
            self.chart.removeAllSeries()
            for ax in self.chart.axes():
                self.chart.removeAxis(ax)

            pts_cons, pts_rec, max_val, start_date, end_date = self._align_and_fill_data(consumption_data, reception_data)

            if not pts_cons and not pts_rec:
                return

            # حساب المدة الزمنية للفلترة
            q_start = QDateTime(start_date, QTime(0,0))
            q_end = QDateTime(end_date, QTime(0,0))
            duration_ms = q_end.toMSecsSinceEpoch() - q_start.toMSecsSinceEpoch()
            if duration_ms == 0: duration_ms = 1 # تجنب القسمة على صفر

            # --- 1. المنحنيات والمساحات (الخلفية) ---
            
            # المصروفات (أزرق)
            series_cons = QLineSeries()
            series_cons.setName("Sorties (Ligne)")
            pen_cons = QPen(QColor("#2980b9")); pen_cons.setWidth(3)
            series_cons.setPen(pen_cons)
            for p in pts_cons: series_cons.append(p)

            area_cons = QAreaSeries(series_cons)
            grad_cons = QLinearGradient(0, 0, 0, 1)
            grad_cons.setCoordinateMode(QGradient.CoordinateMode.ObjectBoundingMode)
            grad_cons.setColorAt(0.0, QColor(41, 128, 185, 80)) 
            grad_cons.setColorAt(1.0, QColor(41, 128, 185, 10))
            area_cons.setBrush(grad_cons)
            area_cons.setPen(QPen(Qt.PenStyle.NoPen))

            # المداخيل (أخضر)
            series_rec = QLineSeries()
            series_rec.setName("Entrées (Ligne)")
            pen_rec = QPen(QColor("#27ae60")); pen_rec.setWidth(3)
            series_rec.setPen(pen_rec)
            for p in pts_rec: series_rec.append(p)

            area_rec = QAreaSeries(series_rec)
            grad_rec = QLinearGradient(0, 0, 0, 1)
            grad_rec.setCoordinateMode(QGradient.CoordinateMode.ObjectBoundingMode)
            grad_rec.setColorAt(0.0, QColor(39, 174, 96, 80))
            grad_rec.setColorAt(1.0, QColor(39, 174, 96, 10))
            area_rec.setBrush(grad_rec)
            area_rec.setPen(QPen(Qt.PenStyle.NoPen))

            # --- 2. نقاط القيم (Scatter Labels) ---
            # ننشئ سلاسل خاصة للنقاط والأرقام فقط (مفلترة لمنع التداخل)
            scatter_cons = self._create_label_series(pts_cons, "#2980b9", "Sorties (Consommation)", duration_ms)
            scatter_rec = self._create_label_series(pts_rec, "#27ae60", "Entrées (Achats)", duration_ms)

            # إضافة السلاسل (الترتيب: مساحات -> خطوط -> نقاط)
            self.chart.addSeries(area_rec)
            self.chart.addSeries(area_cons)
            self.chart.addSeries(series_rec)
            self.chart.addSeries(series_cons)
            self.chart.addSeries(scatter_rec)
            self.chart.addSeries(scatter_cons)

            # إخفاء العناصر الزائدة من وسيلة الإيضاح (Legend)
            # نريد فقط إظهار "Entrées (Achats)" و "Sorties (Consommation)"
            # لذا سنخفي الخطوط والمساحات ونبقي النقاط (لأن النقاط تحمل اللون والاسم الصحيح)
            for marker in self.chart.legend().markers(area_cons): marker.setVisible(False)
            for marker in self.chart.legend().markers(area_rec): marker.setVisible(False)
            for marker in self.chart.legend().markers(series_cons): marker.setVisible(False)
            for marker in self.chart.legend().markers(series_rec): marker.setVisible(False)

            # --- إعداد المحاور ---
            ax_x = QDateTimeAxis()
            ax_x.setFormat("dd MMM")
            ax_x.setTickCount(min(len(pts_cons), 8))
            ax_x.setRange(q_start, q_end)
            ax_x.setLabelsFont(QFont("Segoe UI", 9))
            ax_x.setGridLineColor(QColor("#ecf0f1"))
            self.chart.addAxis(ax_x, Qt.AlignmentFlag.AlignBottom)

            ax_y = QValueAxis()
            ax_y.setLabelFormat("%.0f DA")
            ax_y.setRange(0, max_val * 1.2) # هامش علوي لإفساح المجال للأرقام
            ax_y.setLabelsFont(QFont("Segoe UI", 9))
            ax_y.setGridLineColor(QColor("#ecf0f1"))
            ax_y.setLineVisible(False)
            self.chart.addAxis(ax_y, Qt.AlignmentFlag.AlignLeft)

            # ربط السلاسل بالمحاور
            for s in [series_cons, area_cons, series_rec, area_rec, scatter_cons, scatter_rec]:
                s.attachAxis(ax_x)
                s.attachAxis(ax_y)

        except Exception as e:
            logging.error(f"Error updating charts: {e}")