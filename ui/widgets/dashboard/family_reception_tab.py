# ui/widgets/dashboard/family_reception_tab.py

import logging
import os
import pandas as pd
from datetime import datetime
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, 
                               QTableWidgetItem, QHeaderView, QComboBox, 
                               QLabel, QPushButton, QFrame, QDateEdit, 
                               QAbstractItemView, QFileDialog, QMessageBox)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QColor, QFont, QIcon
import qtawesome as qta

# مكتبات التصدير PDF
from reportlab.lib.pagesizes import landscape, A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle, SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

class FamilyReceptionTab(QWidget):
    def __init__(self, data_manager):
        super().__init__()
        self.first_load_done = False
        self.data_manager = data_manager
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # --- 1. شريط الفلاتر ---
        filter_frame = QFrame()
        filter_frame.setStyleSheet("background-color: white; border-radius: 5px; border: 1px solid #ddd;")
        filter_layout = QHBoxLayout(filter_frame)
        
        self.combo_family = QComboBox()
        self.combo_family.addItem("Toutes les familles", None)
        self.populate_families()
        
        # التاريخ: السنة الحالية
        current_year = QDate.currentDate().year()
        self.date_from = QDateEdit(QDate(current_year, 1, 1))
        self.date_to = QDateEdit(QDate(current_year, 12, 31))
        
        for d in [self.date_from, self.date_to]:
            d.setCalendarPopup(True)
            d.setDisplayFormat("yyyy-MM-dd")
            
        self.combo_unit = QComboBox()
        self.combo_unit.addItems([
            "📦 Unité de Stockage (Défaut)", 
            "🚚 Unité de Commande (Achat)", 
            "🧪 Unité d'Usage (Test/Unitaire)"
        ])
        self.combo_unit.setItemData(0, "stock")
        self.combo_unit.setItemData(1, "order")
        self.combo_unit.setItemData(2, "usage")
        self.combo_unit.setFixedWidth(220)

        btn_refresh = QPushButton("Afficher Rapport")
        btn_refresh.setCursor(Qt.PointingHandCursor)
        btn_refresh.setStyleSheet("background-color: #2980b9; color: white; font-weight: bold; padding: 5px 15px;")
        btn_refresh.clicked.connect(self.load_data)
        
        # أزرار التصدير
        btn_excel = QPushButton("Excel")
        btn_excel.setIcon(qta.icon('fa5s.file-excel', color='white'))
        btn_excel.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; padding: 5px 10px;")
        btn_excel.clicked.connect(self.export_to_excel)

        btn_pdf = QPushButton("PDF")
        btn_pdf.setIcon(qta.icon('fa5s.file-pdf', color='white'))
        btn_pdf.setStyleSheet("background-color: #c0392b; color: white; font-weight: bold; padding: 5px 10px;")
        btn_pdf.clicked.connect(self.export_to_pdf)

        filter_layout.addWidget(QLabel("Famille:"))
        filter_layout.addWidget(self.combo_family, 1)
        filter_layout.addWidget(QLabel("Afficher en:"))
        filter_layout.addWidget(self.combo_unit)
        filter_layout.addWidget(QLabel("Du:"))
        filter_layout.addWidget(self.date_from)
        filter_layout.addWidget(QLabel("Au:"))
        filter_layout.addWidget(self.date_to)
        filter_layout.addWidget(btn_refresh)
        filter_layout.addSpacing(10)
        filter_layout.addWidget(btn_excel)
        filter_layout.addWidget(btn_pdf)
        
        layout.addWidget(filter_frame)
        
        # --- 2. ملخص إجمالي ---
        self.lbl_summary = QLabel("Total Reçu: 0")
        self.lbl_summary.setStyleSheet("font-size: 16px; font-weight: bold; color: #27ae60; margin: 10px 0;")
        self.lbl_summary.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_summary)

        # --- 3. الجدول الديناميكي ---
        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        
        self.table.setStyleSheet("""
            QTableWidget { gridline-color: #ecf0f1; } 
            QHeaderView::section { background-color: #f8f9fa; font-weight: bold; padding: 5px; }
        """)
        layout.addWidget(self.table)

    def showEvent(self, event):
        super().showEvent(event)
        if not self.first_load_done:
            self.load_data()
            self.first_load_done = True

    def populate_families(self):
        try:
            if hasattr(self.data_manager, 'families'):
                families = self.data_manager.families.get_all_families()
                for f in families:
                    self.combo_family.addItem(f['Family_Name'], f['Family_ID'])
        except: pass

    def get_month_list(self, start_date, end_date):
        months = []
        current = datetime(start_date.year, start_date.month, 1)
        end = datetime(end_date.year, end_date.month, 1)
        while current <= end:
            months.append(current.strftime("%Y-%m"))
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1)
            else:
                current = current.replace(month=current.month + 1)
        return months

    def load_data(self):
        try:
            # 1. تحضير المعطيات
            fam_id = self.combo_family.currentData()
            unit_mode = self.combo_unit.currentData()
            
            d_start_py = self.date_from.date().toPython()
            d_end_py = self.date_to.date().toPython()
            
            # 2. جلب البيانات
            raw_data = self.data_manager.stats.get_reception_matrix_data(fam_id, d_start_py, d_end_py)
            
            matrix = {} 
            products_info = {} 
            products_set = set()
            self.grand_total_all = 0.0 
            
            # --- متغير للتأكد من طباعة التشخيص مرة واحدة فقط ---
            debug_printed = False 

            for row in raw_data:
                p_name = row['Product_Name']
                
                # ============================================================
                # 🕵️‍♂️ منطقة التشخيص: سنراقب المنتج الذي فيه المشكلة
                # ============================================================
                if "ACIDE URIQUE" in str(p_name).upper() and not debug_printed:
                    print("\n" + "!"*50)
                    print(f"🕵️ SPY REPORT FOR: {p_name}")
                    print(f"1. Current Mode Selected: '{unit_mode}'")
                    print(f"2. Raw Database Keys: {list(row.keys())}")
                    print(f"3. Raw Database Values:")
                    print(f"   -> Stock_Unit: '{row.get('Stock_Unit')}'")
                    print(f"   -> Ordering_Unit: '{row.get('Ordering_Unit')}'")
                    print(f"   -> Usage_Unit: '{row.get('Usage_Unit')}'")
                    print("!"*50 + "\n")
                    debug_printed = True # لكي لا يكرر الطباعة
                # ============================================================

                month = str(row['Month_Year']) 
                qty_stock = float(row.get('Total_Stock_Qty') or 0)
                
                final_qty = 0.0
                unit_label = "N/A"
                
                # منطق التحويل
                if unit_mode == 'order':
                    factor = float(row.get('Stock_Qty_Per_Order_Unit') or 1)
                    if factor == 0: factor = 1
                    final_qty = qty_stock / factor
                    # نستخدم .get لضمان عدم حدوث خطأ إذا المفتاح غير موجود
                    unit_label = row.get('Ordering_Unit')
                    
                elif unit_mode == 'usage':
                    factor = float(row.get('Usage_Qty_Per_Stock_Unit') or 1)
                    final_qty = qty_stock * factor
                    unit_label = row.get('Usage_Unit')
                    
                else: 
                    final_qty = qty_stock
                    unit_label = row.get('Stock_Unit')

                # تنظيف النص (إزالة المسافات الزائدة)
                if unit_label:
                    unit_label = str(unit_label).strip()
                
                # التخزين
                if p_name not in matrix: matrix[p_name] = {}
                current_val = matrix[p_name].get(month, 0.0)
                matrix[p_name][month] = current_val + final_qty
                
                products_set.add(p_name)
                
                # تحديث الوحدة بذكاء
                # إذا لم تكن مسجلة، أو كانت N/A، والجديدة صالحة -> سجلها
                current_saved_unit = products_info.get(p_name, "N/A")
                if current_saved_unit in ["N/A", "", "None"] and unit_label and unit_label not in ["N/A", "", "None"]:
                    products_info[p_name] = unit_label
                elif p_name not in products_info:
                    products_info[p_name] = "N/A"

                self.grand_total_all += final_qty

            # ... (باقي كود رسم الجدول يبقى كما هو دون تغيير) ...
            # (قم بنسخ الجزء الخاص برسم الجدول من الكود السابق هنا)
            
            # --- تكملة الكود (نسخ لصق للتبسيط) ---
            self.lbl_summary.setText(f"📦 Total Reçu ({self.combo_unit.currentText()}) : {self.grand_total_all:,.2f}")
            dt_start = datetime(d_start_py.year, d_start_py.month, 1)
            dt_end = datetime(d_end_py.year, d_end_py.month, 1)
            months_list = self.get_month_list(dt_start, dt_end)
            columns = ["Produit", "Unité"] + months_list + ["TOTAL"]
            self.table.setColumnCount(len(columns))
            self.table.setHorizontalHeaderLabels(columns)
            self.table.setRowCount(len(products_set) + 1)
            sorted_products = sorted(list(products_set))
            column_totals = {m: 0.0 for m in months_list}
            for r, p_name in enumerate(sorted_products):
                item_name = QTableWidgetItem(p_name)
                item_name.setFont(QFont("Arial", 9, QFont.Bold))
                self.table.setItem(r, 0, item_name)
                u_lbl = products_info.get(p_name, "")
                item_unit = QTableWidgetItem(str(u_lbl))
                item_unit.setTextAlignment(Qt.AlignCenter); item_unit.setForeground(QColor("#7f8c8d"))
                self.table.setItem(r, 1, item_unit)
                row_total = 0.0
                for c, month in enumerate(months_list):
                    qty = matrix.get(p_name, {}).get(month, 0.0)
                    row_total += qty
                    column_totals[month] += qty
                    txt = self._format_qty(qty)
                    item_qty = QTableWidgetItem(txt)
                    item_qty.setTextAlignment(Qt.AlignCenter)
                    if qty > 0: item_qty.setForeground(QColor("#27ae60")); item_qty.setBackground(QColor("#e8f8f5"))
                    else: item_qty.setForeground(QColor("#bdc3c7"))
                    self.table.setItem(r, c + 2, item_qty)
                t_txt = self._format_qty(row_total)
                item_total = QTableWidgetItem(t_txt)
                item_total.setTextAlignment(Qt.AlignCenter); item_total.setFont(QFont("Arial", 9, QFont.Bold)); item_total.setBackground(QColor("#f4f6f7"))
                self.table.setItem(r, len(months_list) + 2, item_total)
            self.table.resizeColumnsToContents()

        except Exception as e:
            logging.error(f"Error in load_data: {e}", exc_info=True)
            QMessageBox.critical(self, "Erreur", f"Erreur: {str(e)}")
    def _format_qty(self, qty):
        if qty == 0: return "-"
        if qty.is_integer(): return f"{int(qty)}"
        return f"{qty:.2f}"

    def export_to_excel(self):
        if self.table.rowCount() == 0:
            QMessageBox.warning(self, "Attention", "Aucune donnée à exporter.")
            return

        path, _ = QFileDialog.getSaveFileName(self, "Exporter Excel", "Rapport_Reception.xlsx", "Excel Files (*.xlsx)")
        if not path: return

        try:
            columns = [self.table.horizontalHeaderItem(i).text() for i in range(self.table.columnCount())]
            data = []
            
            for r in range(self.table.rowCount()):
                row_data = []
                for c in range(self.table.columnCount()):
                    # معالجة الخلايا المدمجة
                    if self.table.columnSpan(r, c) > 1:
                        item = self.table.item(r, c)
                        row_data.append(item.text() if item else "")
                        row_data.append("")
                        continue
                    
                    if r == self.table.rowCount() - 1 and c == 1: continue

                    item = self.table.item(r, c)
                    val = item.text() if item else ""
                    
                    if val and val != "-" and val.replace('.', '', 1).isdigit():
                        try: row_data.append(float(val))
                        except: row_data.append(val)
                    else:
                        row_data.append(val)
                data.append(row_data)

            df = pd.DataFrame(data, columns=columns)
            
            with pd.ExcelWriter(path, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Rapport')
                workbook = writer.book
                worksheet = writer.sheets['Rapport']
                
                last_row = len(data) + 1 
                worksheet.merge_cells(start_row=last_row, start_column=1, end_row=last_row, end_column=2)
                worksheet.column_dimensions['A'].width = 30

            QMessageBox.information(self, "Succès", "Export Excel réussi !")
            
        except Exception as e:
            logging.error(f"Excel Export Error: {e}", exc_info=True)
            QMessageBox.critical(self, "Erreur", f"Erreur export Excel: {e}")

    def export_to_pdf(self):
        if self.table.rowCount() == 0:
            QMessageBox.warning(self, "Attention", "Aucune donnée à exporter.")
            return

        path, _ = QFileDialog.getSaveFileName(self, "Exporter PDF", "Rapport_Reception.pdf", "PDF Files (*.pdf)")
        if not path: return

        try:
            doc = SimpleDocTemplate(path, pagesize=landscape(A4), rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=20)
            elements = []
            styles = getSampleStyleSheet()

            title = Paragraph(f"Rapport de Réception - {self.combo_unit.currentText()}", styles['Title'])
            elements.append(title)
            
            d_from = self.date_from.text()
            d_to = self.date_to.text()
            info_text = f"<b>Période:</b> {d_from} au {d_to} | <b>Famille:</b> {self.combo_family.currentText()}"
            elements.append(Paragraph(info_text, styles['Normal']))
            elements.append(Spacer(1, 15))

            headers = [self.table.horizontalHeaderItem(i).text() for i in range(self.table.columnCount())]
            data = [headers]

            for r in range(self.table.rowCount()):
                row_data = []
                for c in range(self.table.columnCount()):
                    if r == self.table.rowCount() - 1:
                        if c == 0:
                            item = self.table.item(r, c)
                            row_data.append(item.text() if item else "")
                            continue
                        if c == 1:
                            row_data.append("")
                            continue
                    
                    item = self.table.item(r, c)
                    text = item.text() if item else ""
                    if c == 0: 
                        text = Paragraph(text, styles['Normal'])
                    row_data.append(text)
                data.append(row_data)

            total_page_width = 800
            fixed_cols_width = 200 
            num_dynamic_cols = len(headers) - 2 
            
            if num_dynamic_cols > 0:
                month_col_width = (total_page_width - fixed_cols_width) / num_dynamic_cols
                if month_col_width < 35: month_col_width = 35 
            else:
                month_col_width = 50

            col_widths = [140, 60] + [month_col_width] * (num_dynamic_cols)

            pdf_table = Table(data, colWidths=col_widths, repeatRows=1)
            
            style = TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('ALIGN', (0, 1), (0, -1), 'LEFT'),
                ('BACKGROUND', (0, -1), (-1, -1), colors.beige),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                ('SPAN', (0, -1), (1, -1)), 
            ])
            pdf_table.setStyle(style)
            elements.append(pdf_table)
            
            doc.build(elements)
            QMessageBox.information(self, "Succès", "Export PDF réussi !")

        except Exception as e:
            logging.error(f"PDF Export Error: {e}", exc_info=True)
            QMessageBox.critical(self, "Erreur", f"Erreur export PDF: {str(e)}")