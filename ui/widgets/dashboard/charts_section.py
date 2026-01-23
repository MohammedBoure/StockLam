# ui/widgets/dashboard/charts_section.py

import logging
from datetime import date, datetime
from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtCharts import QChart, QChartView, QLineSeries, QDateTimeAxis, QValueAxis, QAreaSeries
from PySide6.QtCore import Qt, QDateTime, QDate, QTime
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QLinearGradient, QGradient

class ChartsSection(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        self.chart = QChart()
        self.chart.setTitle("💸 Tendance des Coûts Journaliers")
        self.chart.setTitleFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        
        # --- [FIX 1] استخدام NoAnimation مبدئياً لزيادة الاستقرار ---
        # الرسوم المتحركة مع التحديث السريع تسبب Crash
        self.chart.setAnimationOptions(QChart.AnimationOption.NoAnimation)
        
        self.chart.setBackgroundVisible(False)
        self.chart.legend().setVisible(False)

        self.view = QChartView(self.chart)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setStyleSheet("background-color: white; border-radius: 12px; border: 1px solid #eef2f5;")
        layout.addWidget(self.view)

    def update_charts(self, trend_data):
        try:
            # --- [FIX 2] إيقاف الأنيميشن قبل حذف البيانات ---
            self.chart.setAnimationOptions(QChart.AnimationOption.NoAnimation)
            
            # تنظيف السلاسل السابقة
            self.chart.removeAllSeries()
            
            # تنظيف المحاور السابقة بشكل صحيح
            # نقوم بنسخ القائمة لأن الحذف أثناء الدوران يسبب مشاكل
            axes = list(self.chart.axes())
            for ax in axes:
                self.chart.removeAxis(ax)
                # لا نحتاج لـ deleteLater هنا لأن Python wrapper يديرها، ولكن الإزالة من الشارت ضرورية

            if not trend_data:
                return

            upper_series = QLineSeries()
            pen = QPen(QColor("#007572"))
            pen.setWidth(3)
            upper_series.setPen(pen)

            max_val = 0.0
            min_timestamp = None
            max_timestamp = None

            # ترتيب البيانات لضمان رسم الخط بشكل صحيح
            sorted_data = sorted(trend_data, key=lambda x: x['date'])

            for entry in sorted_data:
                try:
                    val = float(entry.get('daily_cost', 0) or entry.get('daily_value', 0))
                    raw_date = entry['date']
                    
                    # --- [FIX 3] تحويل التاريخ الآمن ---
                    q_dt = QDateTime()
                    
                    if isinstance(raw_date, str):
                        # محاولة التعامل مع تنسيقات متعددة إذا لزم الأمر
                        q_dt = QDateTime.fromString(raw_date, "yyyy-MM-dd")
                        if not q_dt.isValid():
                             # محاولة احتياطية لتنسيق آخر
                             q_dt = QDateTime.fromString(raw_date, "dd-MM-yyyy")
                             
                    elif isinstance(raw_date, (date, datetime)):
                        # الطريقة الأضمن للتحويل
                        q_date = QDate(raw_date.year, raw_date.month, raw_date.day)
                        q_dt = QDateTime(q_date, QTime(0, 0, 0))
                    
                    if not q_dt.isValid():
                        continue
                    
                    ms_timestamp = q_dt.toMSecsSinceEpoch()
                    upper_series.append(ms_timestamp, val)
                    
                    if val > max_val: max_val = val
                    
                    if min_timestamp is None or ms_timestamp < min_timestamp:
                        min_timestamp = ms_timestamp
                    if max_timestamp is None or ms_timestamp > max_timestamp:
                        max_timestamp = ms_timestamp
                        
                except ValueError:
                    continue # تجاهل القيم غير الصالحة بصمت لتسريع اللوب

            # إذا لم تكن هناك نقاط صالحة، نخرج
            if upper_series.count() == 0:
                return

            # إعداد التدرج اللوني (Gradient)
            area_series = QAreaSeries(upper_series)
            gradient = QLinearGradient(0, 0, 0, 1)
            gradient.setCoordinateMode(QGradient.CoordinateMode.ObjectBoundingMode)
            gradient.setColorAt(0.0, QColor(0, 117, 114, 120)) 
            gradient.setColorAt(1.0, QColor(0, 117, 114, 10))  
            area_series.setBrush(gradient)
            area_series.setPen(QPen(Qt.PenStyle.NoPen))

            self.chart.addSeries(area_series)
            self.chart.addSeries(upper_series)

            # إعداد محور X (الوقت)
            ax_x = QDateTimeAxis()
            ax_x.setFormat("dd/MM")
            ax_x.setTickCount(8) # تقليل عدد التواريخ لمنع التزاحم
            
            if min_timestamp is not None and max_timestamp is not None:
                if min_timestamp == max_timestamp:
                    min_timestamp -= 86400000 
                    max_timestamp += 86400000
                
                # إضافة هامش بسيط
                ax_x.setRange(QDateTime.fromMSecsSinceEpoch(int(min_timestamp)), 
                              QDateTime.fromMSecsSinceEpoch(int(max_timestamp)))
            
            self.chart.addAxis(ax_x, Qt.AlignmentFlag.AlignBottom)
            upper_series.attachAxis(ax_x)
            area_series.attachAxis(ax_x)
            
            # إعداد محور Y (القيم)
            ax_y = QValueAxis()
            ax_y.setLabelFormat("%.0f DA") # إضافة العملة
            # زيادة الحد الأعلى قليلاً لجمالية الرسم
            top_range = max_val * 1.2 if max_val > 0 else 100
            ax_y.setRange(0, top_range)
            
            self.chart.addAxis(ax_y, Qt.AlignmentFlag.AlignLeft)
            upper_series.attachAxis(ax_y)
            area_series.attachAxis(ax_y)

            # --- [FIX 4] إعادة تفعيل الأنيميشن بحذر (اختياري) ---
            # إذا كنت تريد استقراراً تاماً 100%، اترك السطر التالي معلقاً
            self.chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)

        except Exception as e:
            logging.error(f"Error updating charts: {e}")