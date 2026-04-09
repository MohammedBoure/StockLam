# ui/widgets/inventory/tabs_batches.py

import logging
import csv
from datetime import datetime, date

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QHeaderView,QTabWidget,
    QFrame, QLabel, QLineEdit, QPushButton, QHBoxLayout, 
    QGroupBox, QMessageBox, QComboBox, QStyle, QInputDialog,
    QDateEdit, QCheckBox, QTableWidgetItem,QApplication,
    QAbstractItemView, QMenu, QFileDialog
)
from PySide6.QtCore import Qt, Signal, QDate, QMarginsF
from PySide6.QtGui import (
    QColor, QAction, QFont, QPageLayout, QPageSize, 
    QTextDocument
)
from PySide6.QtPrintSupport import QPrinter

try:
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT, TA_CENTER
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

from .dialogs import AdjustmentDialog, WasteDialog, BatchDetailsDialog 
from .location_tree_combo import LocationTreeComboBox
from ui.widgets.procurement.reception_dialog import ReceptionDialog

from .quick_actions import QuickTransferDialog, QuickConsumeDialog

class BatchesTab(QWidget):
    data_changed = Signal()
    request_open_reception = Signal(int) 
    request_product_history = Signal(str) 

    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self.all_data = [] 
        
        self.loaded_count = 0      # عدد الصفوف المعروضة حالياً
        self.batch_size = 50       # عدد الصفوف التي يتم تحميلها في كل دفعة
        self.filtered_data = []    # القائمة الكاملة بعد الفلترة (في الذاكرة)

        self.current_sort_col = -1 
        self.current_sort_asc = True 
        
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(5)
        layout.setContentsMargins(5, 5, 5, 5)
        
        filter_group = QGroupBox("🔍 Recherche & Filtres Avancés")
        filter_group.setStyleSheet("""
            QGroupBox { font-weight: bold; color: #2c3e50; border: 1px solid #bdc3c7; border-radius: 6px; margin-top: 6px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 3px; }
        """)
        
        main_filter_layout = QHBoxLayout(filter_group)
        main_filter_layout.setContentsMargins(10, 15, 10, 10)
        
        left_layout = QVBoxLayout()
        left_layout.setSpacing(8)
        
        row1 = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔎 Produit, Code-barres, Lot...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.returnPressed.connect(self.load_data) 
        self.search_input.textChanged.connect(self.apply_filters_local)

        self.loc_filter = LocationTreeComboBox(self.manager.locations)
        self.loc_filter.setPlaceholderText("📍 Emplacement")
        self.loc_filter.setFixedWidth(180)
        self.loc_filter.currentIndexChanged.connect(self.apply_filters_local)
        
        row1.addWidget(self.search_input)
        row1.addWidget(self.loc_filter)
        left_layout.addLayout(row1)
        
        row2 = QHBoxLayout()
        self.combo_family = QComboBox()
        self.combo_family.addItem("📁 Familles", None)
        self.combo_family.setFixedWidth(130)
        self.populate_families()
        self.combo_family.currentIndexChanged.connect(self.apply_filters_local)

        self.combo_manuf = QComboBox()
        self.combo_manuf.addItem("🏭 Marques", None)
        self.combo_manuf.setFixedWidth(130)
        self.populate_manufacturers()
        self.combo_manuf.currentIndexChanged.connect(self.apply_filters_local)

        self.combo_automate = QComboBox()
        self.combo_automate.addItem("⚙️ Automates", None)
        self.combo_automate.setFixedWidth(130)
        self.populate_automates()
        self.combo_automate.currentIndexChanged.connect(self.apply_filters_local)

        self.combo_status = QComboBox()
        self.combo_status.addItems([
            "📋 Tous (>0)", "✅ En Stock", "⚠️ Faible (Seuil)", 
            "❌ Périmés", "🕒 Bientôt Exp.", "⭕ Épuisé (Qté=0)"
        ])
        self.combo_status.setFixedWidth(130)
        self.combo_status.setCurrentIndex(1) 
        self.combo_status.currentIndexChanged.connect(self.load_data)

        row2.addWidget(self.combo_family)
        row2.addWidget(self.combo_manuf)
        row2.addWidget(self.combo_automate)
        row2.addWidget(self.combo_status)
        left_layout.addLayout(row2)
        
        main_filter_layout.addLayout(left_layout, 2)

        line = QFrame()
        line.setFrameShape(QFrame.VLine)
        line.setFrameShadow(QFrame.Sunken)
        main_filter_layout.addWidget(line)

        right_layout = QVBoxLayout()
        right_layout.setSpacing(5)
        
        exp_layout = QHBoxLayout()
        self.chk_date_filter = QCheckBox("Date Expiration:")
        self.chk_date_filter.setStyleSheet("font-weight: bold; color: #c0392b;")
        self.chk_date_filter.setChecked(False) 
        self.chk_date_filter.stateChanged.connect(self.toggle_date_filter)
        
        self.date_from = QDateEdit(QDate.currentDate())
        self.date_from.setCalendarPopup(True)
        self.date_from.setEnabled(False)
        self.date_from.dateChanged.connect(self.apply_filters_local)

        self.date_to = QDateEdit(QDate.currentDate().addYears(1))
        self.date_to.setCalendarPopup(True)
        self.date_to.setEnabled(False)
        self.date_to.dateChanged.connect(self.apply_filters_local)
        
        exp_layout.addWidget(self.chk_date_filter)
        exp_layout.addStretch()
        exp_layout.addWidget(QLabel("Du:"))
        exp_layout.addWidget(self.date_from)
        exp_layout.addWidget(QLabel("Au:"))
        exp_layout.addWidget(self.date_to)
        
        ent_layout = QHBoxLayout()
        self.chk_entry_filter = QCheckBox("Date Entrée:")
        self.chk_entry_filter.setStyleSheet("font-weight: bold; color: #2980b9;")
        self.chk_entry_filter.setChecked(False)
        self.chk_entry_filter.stateChanged.connect(self.toggle_entry_filter)

        self.date_in_from = QDateEdit(QDate.currentDate().addMonths(-1))
        self.date_in_from.setCalendarPopup(True)
        self.date_in_from.setEnabled(False)
        self.date_in_from.dateChanged.connect(self.apply_filters_local)

        self.date_in_to = QDateEdit(QDate.currentDate())
        self.date_in_to.setCalendarPopup(True)
        self.date_in_to.setEnabled(False)
        self.date_in_to.dateChanged.connect(self.apply_filters_local)
        
        ent_layout.addWidget(self.chk_entry_filter)
        ent_layout.addStretch()
        ent_layout.addWidget(QLabel("Du:"))
        ent_layout.addWidget(self.date_in_from)
        ent_layout.addWidget(QLabel("Au:"))
        ent_layout.addWidget(self.date_in_to)

        right_layout.addLayout(exp_layout)
        right_layout.addLayout(ent_layout)

        reset_layout = QHBoxLayout()
        reset_layout.addStretch()
        btn_refresh = QPushButton("Actualiser")
        btn_refresh.setFixedWidth(100)
        btn_refresh.setStyleSheet("background-color: #2980b9; color: white; border-radius: 3px; padding: 2px;")
        btn_refresh.clicked.connect(self.load_data)

        btn_reset = QPushButton("Réinitialiser")
        btn_reset.setFixedWidth(100)
        btn_reset.setStyleSheet("background-color: #95a5a6; color: white; border-radius: 3px; padding: 2px;")
        btn_reset.clicked.connect(self.reset_filters)
        
        reset_layout.addWidget(btn_refresh)
        reset_layout.addWidget(btn_reset)
        right_layout.addLayout(reset_layout)

        main_filter_layout.addLayout(right_layout, 1)
        layout.addWidget(filter_group)

        self.table = QTableWidget()
        self.table.verticalHeader().setDefaultSectionSize(30) 
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        cols = [
            "Désignation Produit", "Famille", "Marque", "Automate", 
            "Fournisseur", "Stock (Actuel)", "Date Entrée", "N° Lot", 
            "Date Exp.", "Qté Init.", "Code-Barres", "Prix U.", 
            "Valeur (DA)", "Ref PO", "Emplacement"
        ]
        
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        for c in range(1, 15):
            header.setSectionResizeMode(c, QHeaderView.ResizeToContents)

        self.table.setWordWrap(True)
        self.table.setSortingEnabled(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("QTableWidget { gridline-color: #ecf0f1; font-size: 12px; }")
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)

        header.setSectionsClickable(True)
        header.setSortIndicatorShown(False)
        header.sectionClicked.connect(self.on_header_clicked) 

        self.table.verticalScrollBar().valueChanged.connect(self.on_scroll_value_changed)

        layout.addWidget(self.table)

        bottom_bar = QHBoxLayout()
        bottom_bar.setContentsMargins(5, 5, 5, 5)

        self.lbl_total_value = QLabel("Valeur Totale : 0.00 DA")
        self.lbl_total_value.setFont(QFont("Arial", 11, QFont.Bold))
        self.lbl_total_value.setStyleSheet("""
            QLabel { 
                color: #2c3e50; 
                border: 1px solid #95a5a6; 
                border-radius: 4px; 
                padding: 6px; 
                background-color: #ecf0f1; 
            }
        """)
        bottom_bar.addWidget(self.lbl_total_value)

        self.lbl_count_info = QLabel("0 éléments")
        self.lbl_count_info.setStyleSheet("color: #7f8c8d; font-weight: bold; margin-left: 10px;")
        bottom_bar.addWidget(self.lbl_count_info)
        
        bottom_bar.addStretch() 

        btn_style = "QPushButton { font-weight: bold; border-radius: 4px; padding: 6px 12px; font-size: 12px; }"
        
        btn_direct_use = QPushButton("⚡ Sortie")
        btn_direct_use.setStyleSheet(btn_style + "background-color: #27ae60; color: white;")
        btn_direct_use.clicked.connect(self.direct_use_process)
        bottom_bar.addWidget(btn_direct_use)

        btn_adjust = QPushButton("✏️ Ajustement")
        btn_adjust.setStyleSheet(btn_style + "background-color: #f39c12; color: white;")
        btn_adjust.clicked.connect(self.adjust_stock)
        bottom_bar.addWidget(btn_adjust)

        btn_waste = QPushButton("🗑️ Rebut")
        btn_waste.setStyleSheet(btn_style + "background-color: #c0392b; color: white;")
        btn_waste.clicked.connect(self.waste_batch)
        bottom_bar.addWidget(btn_waste)

        btn_print = QPushButton("🖨️ Étiquette")
        btn_print.setStyleSheet(btn_style + "background-color: #34495e; color: white;")
        btn_print.clicked.connect(self.print_batch_label)
        bottom_bar.addWidget(btn_print)

        line_sep = QFrame()
        line_sep.setFrameShape(QFrame.VLine)
        line_sep.setFrameShadow(QFrame.Sunken)
        bottom_bar.addWidget(line_sep)

        btn_export_excel = QPushButton("📗 Excel")
        btn_export_excel.setToolTip("Exporter en Excel")
        btn_export_excel.setStyleSheet(btn_style + "background-color: #217346; color: white;")
        btn_export_excel.clicked.connect(self.export_to_excel)
        bottom_bar.addWidget(btn_export_excel)

        btn_export_pdf = QPushButton("📕 PDF")
        btn_export_pdf.setToolTip("Exporter en PDF (Paysage)")
        btn_export_pdf.setStyleSheet(btn_style + "background-color: #e74c3c; color: white;")
        btn_export_pdf.clicked.connect(self.export_to_pdf)
        bottom_bar.addWidget(btn_export_pdf)

        layout.addLayout(bottom_bar)

        self.load_data()
        self.table.doubleClicked.connect(self.show_batch_details)


    def showEvent(self, event):
        """يتم استدعاؤها في كل مرة تظهر فيها الصفحة"""
        super().showEvent(event)
        try:
            # محاولة جلب الدور من النافذة الرئيسية
            main_win = self.window()
            if hasattr(main_win, 'current_user'):
                role = main_win.current_user.get('Role', 'Technician')
                self.apply_role_permissions(role)
        except Exception as e:
            logging.error(f"Error applying permissions in showEvent: {e}")
        
        self.load_data()


    def update_pagination_controls(self):
        """تحديث النصوص وحالة الأزرار بناءً على الصفحة الحالية"""
        total_rows = len(self.filtered_data)
        if total_rows == 0:
            self.lbl_page_info.setText("Aucun résultat")
            self.btn_prev_page.setEnabled(False)
            self.btn_next_page.setEnabled(False)
            return

        total_pages = (total_rows + self.rows_per_page - 1) // self.rows_per_page
        
        # تصحيح الصفحة الحالية لضمان عدم الخروج عن النطاق
        self.current_page = max(0, min(self.current_page, total_pages - 1))
        
        display_page = self.current_page + 1
        self.lbl_page_info.setText(f"Page {display_page} / {total_pages} (Total: {total_rows})")
        
        self.btn_prev_page.setEnabled(self.current_page > 0)
        self.btn_next_page.setEnabled(self.current_page < total_pages - 1)

    def next_page(self):
        self.current_page += 1
        self._render_current_page()

    def prev_page(self):
        self.current_page -= 1
        self._render_current_page()

    def _render_current_page(self):
        """تقطيع البيانات وعرض الجزء المطلوب فقط"""
        start_idx = self.current_page * self.rows_per_page
        end_idx = start_idx + self.rows_per_page
        
        # أخذ شريحة (Slice) من البيانات
        page_data = self.filtered_data[start_idx:end_idx]
        
        self.update_pagination_controls()
        self._populate_table(page_data)

    def showEvent(self, event):
        super().showEvent(event)
        self.load_data()

    
    def apply_sorting(self):
        """تطبيق الترتيب ثم إعادة تعيين العرض للبدء من جديد"""
        if self.current_sort_col == -1: return

        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            col_index = self.current_sort_col
            is_asc = self.current_sort_asc

            self.table.horizontalHeader().setSortIndicatorShown(True)
            self.table.horizontalHeader().setSortIndicator(
                col_index, 
                Qt.AscendingOrder if is_asc else Qt.DescendingOrder
            )

            # خريطة الترتيب
            col_map = {
                0: 'Product_Name', 1: 'Family_Name', 2: 'Manuf_Name',
                3: 'Automate_Name', 4: 'Supplier_Name', 
                5: 'Quantity_Current', 6: 'Date_Received', 7: 'Lot_Number',
                8: 'Expiry_Date', 9: 'Quantity_Initial', 10: 'Internal_Barcode',
                11: 'Unit_Price_Received', 12: 'Total_Value', 
                13: 'PO_ID', 14: 'Location_Name'
            }

            key_name = col_map.get(col_index)
            if not key_name and col_index != 12: return

            def sort_key(item):
                if col_index == 12:
                    try: return float(item.get('Quantity_Current',0)) * float(item.get('Unit_Price_Received',0))
                    except: return 0.0
                
                val = item.get(key_name)
                if val is None: return -1 if col_index in [5,9,11] else ""

                if col_index in [5, 9, 11]: 
                    try: return float(val)
                    except: return 0.0
                elif col_index in [6, 8]: 
                    return str(val)[:10]
                else: 
                    return str(val).lower()

            self.filtered_data.sort(key=sort_key, reverse=not is_asc)

            # إعادة التحميل من البداية
            self.table.setRowCount(0)
            self.loaded_count = 0
            self.load_more_data()

        except Exception as e:
            logging.error(f"Sorting Error: {e}")
        finally:
            QApplication.restoreOverrideCursor()

    def on_scroll_value_changed(self, value):
        """التحقق مما إذا وصل المستخدم إلى أسفل الجدول لتحميل المزيد"""
        bar = self.table.verticalScrollBar()
        # إذا بقي 20 بكسل أو أقل للوصول للقاع، حمل المزيد
        if value >= bar.maximum() - 20: 
            self.load_more_data()

    def load_more_data(self):
        """تحميل الدفعة التالية من البيانات وإضافتها للجدول"""
        total_records = len(self.filtered_data)
        if self.loaded_count >= total_records:
            return  # تم تحميل كل شيء

        # تحديد الشريحة (Slice) التالية
        start_idx = self.loaded_count
        end_idx = min(start_idx + self.batch_size, total_records)
        
        chunk = self.filtered_data[start_idx:end_idx]
        self._append_rows_to_table(chunk)
        
        self.loaded_count = end_idx
        self.lbl_count_info.setText(f"Affichage: {self.loaded_count} / {total_records}")


    def _append_rows_to_table(self, data_chunk):
        """إضافة صفوف جديدة للجدول (هذه الدالة بديلة لـ _populate_table)"""
        
        try:
            role = self.window().current_user.get('Role', 'Technician')
        except: role = 'Technician'
        is_tech = (role == 'Technician')

        def make_item(val, align=Qt.AlignCenter, color=None, font=None):
            s_val = str(val) if val is not None else ""
            it = QTableWidgetItem(s_val)
            it.setTextAlignment(align)
            if color: it.setForeground(color)
            if font: it.setFont(font)
            it.setFlags(it.flags() & ~Qt.ItemIsEditable)
            return it

        start_row = self.table.rowCount()
        
        for i, b in enumerate(data_chunk):
            r = start_row + i
            self.table.insertRow(r)
            
            qty = float(b.get('Quantity_Current', 0))
            
            # تعبئة الأعمدة
            prod_item = make_item(b.get('Product_Name', '---'), Qt.AlignLeft | Qt.AlignVCenter)
            prod_item.setData(Qt.UserRole, b)
            self.table.setItem(r, 0, prod_item)
            self.table.setItem(r, 1, make_item(b.get('Family_Name', '---')))
            self.table.setItem(r, 2, make_item(b.get('Manuf_Name', '---')))
            self.table.setItem(r, 3, make_item(b.get('Automate_Name', '---')))
            self.table.setItem(r, 4, make_item(b.get('Supplier_Name', '---')))
            self.table.setItem(r, 5, make_item(f"{qty:g}", color=QColor("#27ae60"), font=QFont("", -1, QFont.Bold)))
            self.table.setItem(r, 6, make_item(str(b.get('Date_Received') or b.get('Created_At', ''))[:10]))
            self.table.setItem(r, 7, make_item(b.get('Lot_Number', '---')))
            self.table.setItem(r, 8, make_item(str(b.get('Expiry_Date', ''))[:10]))
            self.table.setItem(r, 9, make_item(f"{float(b.get('Quantity_Initial',0)):g}"))
            self.table.setItem(r, 10, make_item(b.get('Internal_Barcode') or b.get('Barcode')))
            
            # الأعمدة المالية
            if not is_tech:
                price_u = float(b.get('Unit_Price_Received', 0))
                discount = float(b.get('Discount_Percent', 0)) / 100.0
                tax = float(b.get('Tax_Rate_Percent', 0)) / 100.0
                line_val = qty * price_u * (1 - discount) * (1 + tax)
                
                self.table.setItem(r, 11, make_item(f"{price_u:,.2f}"))
                self.table.setItem(r, 12, make_item(f"{line_val:,.2f}"))
            else:
                self.table.setItem(r, 11, QTableWidgetItem(""))
                self.table.setItem(r, 12, QTableWidgetItem(""))

            self.table.setItem(r, 13, make_item(b.get('PO_ID')))
            self.table.setItem(r, 14, make_item(b.get('Location_Name')))
        
        self.table.setColumnHidden(11, is_tech)
        self.table.setColumnHidden(12, is_tech)

    def on_header_clicked(self, col_index):
        """يتم استدعاؤها فقط عند ضغط المستخدم على رأس العمود"""
        if self.current_sort_col == col_index:
            # إذا ضغط نفس العمود، اعكس الاتجاه
            self.current_sort_asc = not self.current_sort_asc
        else:
            # إذا ضغط عمود جديد، ابدأ تصاعدياً
            self.current_sort_col = col_index
            self.current_sort_asc = True
        
        # الآن نفذ الفرز
        self.apply_sorting()

    def _populate_table(self, data):
        """عرض البيانات في الجدول (يستقبل شريحة صغيرة فقط 50 صف)"""
        
        # تعطيل الفرز التلقائي لمنع Qt من إعادة ترتيب الـ 50 صف فقط
        self.table.setSortingEnabled(False)
        
        # [تم حذف] أسطر ربط وفصل الإشارات من هنا لأن مكانها الصحيح في init_ui

        self.table.setRowCount(0)
        
        # 1. التحقق من الصلاحيات لحساب الإجمالي
        try:
            role = self.window().current_user.get('Role', 'Technician')
        except: role = 'Technician'
        is_tech = (role == 'Technician')

        # [جديد] حساب المجموع الكلي من القائمة الكاملة (filtered_data) وليس المعروضة فقط
        total_value_filtered = 0.0
        if not is_tech:
            for b in self.filtered_data: # لاحظ استخدام filtered_data هنا
                try:
                    qty = float(b.get('Quantity_Current', 0))
                    if qty > 0:
                        price_u = float(b.get('Unit_Price_Received', 0))
                        discount = float(b.get('Discount_Percent', 0)) / 100.0
                        tax = float(b.get('Tax_Rate_Percent', 0)) / 100.0
                        line_val = qty * price_u * (1 - discount) * (1 + tax)
                        total_value_filtered += line_val
                except: pass

        def make_item(val, align=Qt.AlignCenter, color=None, font=None):
            s_val = str(val) if val is not None else ""
            it = QTableWidgetItem(s_val)
            it.setTextAlignment(align)
            if color: it.setForeground(color)
            if font: it.setFont(font)
            it.setFlags(it.flags() & ~Qt.ItemIsEditable)
            return it

        # 2. رسم الصفوف (للبيانات المعروضة فقط - data)
        for r, b in enumerate(data):
            self.table.insertRow(r)
            qty = float(b.get('Quantity_Current', 0))
            
            # تعبئة البيانات العامة (0-10)
            prod_item = make_item(b.get('Product_Name', '---'), Qt.AlignLeft | Qt.AlignVCenter)
            prod_item.setData(Qt.UserRole, b)
            self.table.setItem(r, 0, prod_item)
            self.table.setItem(r, 1, make_item(b.get('Family_Name', '---')))
            self.table.setItem(r, 2, make_item(b.get('Manuf_Name', '---')))
            self.table.setItem(r, 3, make_item(b.get('Automate_Name', '---')))
            self.table.setItem(r, 4, make_item(b.get('Supplier_Name', '---')))
            self.table.setItem(r, 5, make_item(f"{qty:g}", color=QColor("#27ae60"), font=QFont("", -1, QFont.Bold)))
            self.table.setItem(r, 6, make_item(str(b.get('Date_Received') or b.get('Created_At', ''))[:10]))
            self.table.setItem(r, 7, make_item(b.get('Lot_Number', '---')))
            self.table.setItem(r, 8, make_item(str(b.get('Expiry_Date', ''))[:10]))
            self.table.setItem(r, 9, make_item(f"{float(b.get('Quantity_Initial',0)):g}"))
            self.table.setItem(r, 10, make_item(b.get('Internal_Barcode') or b.get('Barcode')))
            
            # 11-12: البيانات المالية (حساب للصف المعروض)
            if not is_tech:
                price_u = float(b.get('Unit_Price_Received', 0))
                discount = float(b.get('Discount_Percent', 0)) / 100.0
                tax = float(b.get('Tax_Rate_Percent', 0)) / 100.0
                line_val = qty * price_u * (1 - discount) * (1 + tax)
                
                self.table.setItem(r, 11, make_item(f"{price_u:,.2f}"))
                self.table.setItem(r, 12, make_item(f"{line_val:,.2f}"))
            else:
                self.table.setItem(r, 11, QTableWidgetItem(""))
                self.table.setItem(r, 12, QTableWidgetItem(""))

            self.table.setItem(r, 13, make_item(b.get('PO_ID')))
            self.table.setItem(r, 14, make_item(b.get('Location_Name')))

        # تأكيد تعطيل الفرز مرة أخرى بعد الرسم
        self.table.setSortingEnabled(False)
        
        # الإخفاء والتحكم في الليبل السفلي والأعمدة حسب الصلاحيات
        self.table.setColumnHidden(11, is_tech)
        self.table.setColumnHidden(12, is_tech)

        if is_tech:
            self.lbl_total_value.hide()
        else:
            self.lbl_total_value.show()
            self.lbl_total_value.setText(f"💰 Total Filtré : {total_value_filtered:,.2f} DA")

    def sort_by_column(self, col_index):
        """
        ترتيب البيانات كاملة مع إظهار مؤشر تحميل وسهم الاتجاه
        """
        # 1. إظهار مؤشر التحميل (Loading Cursor)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        QApplication.processEvents() # إجبار الواجهة على تحديث شكل الماوس فوراً

        try:
            # 2. منطق عكس الترتيب (Toggle)
            if self.current_sort_col == col_index:
                self.current_sort_asc = not self.current_sort_asc
            else:
                self.current_sort_col = col_index
                self.current_sort_asc = True # افتراضي تصاعدي عند تغيير العمود

            # 3. تحديث سهم الاتجاه في الهيدر
            header = self.table.horizontalHeader()
            header.setSortIndicatorShown(True)
            direction = Qt.AscendingOrder if self.current_sort_asc else Qt.DescendingOrder
            header.setSortIndicator(col_index, direction)

            # 4. خريطة الأعمدة (Mapping)
            # هذه الخريطة تربط رقم العمود باسم الحقل في قاعدة البيانات
            col_map = {
                0: 'Product_Name',
                1: 'Family_Name',
                2: 'Manuf_Name',
                3: 'Automate_Name',
                4: 'Supplier_Name',
                5: 'Quantity_Current',     # رقم
                6: 'Date_Received',        # تاريخ
                7: 'Lot_Number',
                8: 'Expiry_Date',          # تاريخ
                9: 'Quantity_Initial',     # رقم
                10: 'Internal_Barcode',
                11: 'Unit_Price_Received', # رقم
                12: 'Total_Value',         # حسابي
                13: 'PO_ID',
                14: 'Location_Name'
            }

            key_name = col_map.get(col_index)
            
            # إذا ضغط المستخدم على عمود غير معرف أو لا يحتوي بيانات للترتيب
            if not key_name and col_index != 12: 
                return

            # 5. دالة استخراج القيمة للترتيب (Sorting Key)
            def sort_key(item):
                # معالجة خاصة لعمود "القيمة الإجمالية"
                if col_index == 12: 
                    try:
                        q = float(item.get('Quantity_Current', 0))
                        p = float(item.get('Unit_Price_Received', 0))
                        return q * p 
                    except: return 0.0

                val = item.get(key_name)
                
                # التعامل مع القيم الفارغة (تظهر في البداية أو النهاية)
                if val is None:
                    # للأرقام نعيد -1، للنصوص نعيد نص فارغ
                    return -1 if col_index in [5, 9, 11] else ""

                # تحويل الأنواع للترتيب الصحيح
                if col_index in [5, 9, 11]: # أرقام
                    try: return float(val)
                    except: return 0.0
                
                elif col_index in [6, 8]: # تواريخ
                    # نحول التاريخ لنص YYYY-MM-DD لضمان الترتيب الزمني
                    return str(val)[:10]
                
                else: # نصوص
                    return str(val).lower() # تحويل لأحرف صغيرة لتجاهل حالة الأحرف

            # 6. تنفيذ الترتيب على القائمة الكبيرة (في الذاكرة)
            self.filtered_data.sort(key=sort_key, reverse=not self.current_sort_asc)

            # 7. إعادة العرض من الصفحة الأولى
            self.current_page = 0
            self._render_current_page()

        except Exception as e:
            logging.error(f"Error Sorting: {e}")
            QMessageBox.warning(self, "Erreur", f"Erreur de tri : {e}")
        
        finally:
            # 8. إخفاء مؤشر التحميل في جميع الأحوال
            QApplication.restoreOverrideCursor()

    def update_header_indicator(self, col_index):
        """تحديث أيقونة السهم في رأس الجدول"""
        header = self.table.horizontalHeader()
        for i in range(self.table.columnCount()):
            # مسح الأيقونات القديمة
            self.table.model().setHeaderData(i, Qt.Horizontal, None, Qt.DecorationRole)
        
        # وضع الأيقونة الجديدة (يمكنك استخدام أيقونات مخصصة أو نصوص)
        # هنا سنعتمد على مؤشر الفرز الافتراضي الخاص بـ Qt
        header.setSortIndicatorShown(True)
        order = Qt.AscendingOrder if self.current_sort_asc else Qt.DescendingOrder
        header.setSortIndicator(col_index, order)

    def print_batch_label(self):
        """طباعة الملصقات لجميع الصفوف المحددة"""
        selected_rows = self.table.selectionModel().selectedRows()
        
        if not selected_rows:
            # إذا لم يتم تحديد صف كامل، نتحقق من الخلية الحالية
            current_idx = self.table.currentIndex()
            if current_idx.isValid():
                selected_rows = [current_idx]
            else:
                QMessageBox.warning(self, "Attention", "Veuillez sélectionner au moins un lot.")
                return

        # تكرار العملية لكل صف محدد
        for index in selected_rows:
            # الحصول على بيانات الصف
            row = index.row()
            item = self.table.item(row, 0)
            if not item: continue
            
            data = item.data(Qt.UserRole)
            if not data: continue

            product_name = data.get('Product_Name', 'Produit')
            lot_number = data.get('Lot_Number', '')
            
            # إظهار نافذة الكمية (مع توضيح اسم المنتج الحالي في العنوان)
            current_qty = float(data.get('Quantity_Current', 0))
            default_copies = int(current_qty) if current_qty >= 1 else 1

            qty, ok = QInputDialog.getInt(
                self, 
                f"Étiquette : {product_name}",  # عنوان النافذة يحتوي على اسم المنتج
                f"Nombre de copies pour le lot {lot_number}:", 
                default_copies, 
                1, 9999
            )
            
            if ok:
                self.manager.printer.print_label(
                    product_name, 
                    data.get('Internal_Barcode'), 
                    lot_number, 
                    data.get('Expiry_Date'), 
                    qty
                )
            else:
                # إذا ضغط المستخدم Cancel، هل نوقف الباقي؟ 
                # عادة نعم، ولكن يمكن الاستمرار. هنا سأقوم بكسر الحلقة (إيقاف).
                break

    def export_to_excel(self):
        """تصدير الجدول الحالي إلى Excel"""
        cols, rows = self.get_table_data()
        if not rows:
            QMessageBox.warning(self, "Export", "Aucune donnée à exporter.")
            return

        filename, _ = QFileDialog.getSaveFileName(
            self, "Exporter Excel", 
            f"Stock_Lots_{date.today()}.xlsx", 
            "Fichiers Excel (*.xlsx);;Fichiers CSV (*.csv)"
        )
        if not filename: return

        try:
            if filename.endswith('.xlsx') and HAS_PANDAS:
                df = pd.DataFrame(rows, columns=cols)
                for col_name in ['Stock (Actuel)', 'Qté Init.', 'Prix U.', 'Valeur (DA)']:
                    if col_name in df.columns:
                        df[col_name] = df[col_name].astype(str).str.replace(r'[^\d\.\-]', '', regex=True)
                        df[col_name] = pd.to_numeric(df[col_name], errors='coerce').fillna(0)
                
                with pd.ExcelWriter(filename, engine='xlsxwriter') as writer:
                    df.to_excel(writer, sheet_name='Stock', index=False)
                    worksheet = writer.sheets['Stock']
                    for idx, col in enumerate(df.columns):
                        max_len = max(df[col].astype(str).map(len).max(), len(col)) + 2
                        worksheet.set_column(idx, idx, max_len)
            else:
                if not filename.endswith('.csv'): filename += ".csv"
                with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f, delimiter=';')
                    writer.writerow(cols)
                    writer.writerows(rows)
            
        except Exception as e:
            logging.error(f"Erreur Export Excel: {e}")
            QMessageBox.critical(self, "Erreur", f"Échec: {str(e)}")

    def export_to_pdf(self):
        """
        تصدير PDF مع حل مشكلة تداخل النصوص الطويلة
        يتم ذلك عبر تصغير الخط واستخدام Paragraph لكل الخلايا النصية
        """
        if self.table.rowCount() == 0:
            QMessageBox.warning(self, "Attention", "Aucune donnée à exporter.")
            return

        # اختيار مسار الحفظ
        filename, _ = QFileDialog.getSaveFileName(
            self, "Exporter PDF", 
            f"Etat_Stock_{date.today().strftime('%Y-%m-%d')}.pdf", 
            "PDF Files (*.pdf)"
        )
        if not filename: return

        try:
            # إعداد الصفحة: A4 Landscape مع هوامش ضيقة لاستغلال المساحة
            # العرض الكلي لـ A4 Landscape هو حوالي 842 نقطة
            doc = SimpleDocTemplate(
                filename, 
                pagesize=landscape(A4), 
                rightMargin=10, leftMargin=10, topMargin=10, bottomMargin=10
            )
            
            elements = []
            styles = getSampleStyleSheet()

            # --- تعريف ستايل خاص للخلايا الصغيرة ---
            # fontSize=6: تصغير الخط ليناسب 15 عمود
            # leading=7: المسافة بين الأسطر
            # splitLongWords=1: إجبار الكلمات الطويلة جداً على الانقسام للسطر التالي
            style_cell_text = ParagraphStyle(
                'CellText', 
                parent=styles['Normal'], 
                fontName='Helvetica', 
                fontSize=6, 
                leading=7, 
                alignment=TA_LEFT,
                splitLongWords=1,
                wordWrap='CJK'  # يساعد في التفاف النصوص
            )
            
            style_cell_center = ParagraphStyle(
                'CellCenter', 
                parent=styles['Normal'], 
                fontName='Helvetica', 
                fontSize=6, 
                leading=7, 
                alignment=TA_CENTER
            )

            # --- العنوان ---
            title = Paragraph(f"État du Stock par Lot - {date.today().strftime('%d/%m/%Y')}", styles['Title'])
            elements.append(title)
            
            # معلومات الفلتر
            total_val = self.lbl_total_value.text()
            fam_txt = self.combo_family.currentText()
            filter_info = f"<b>{total_val}</b> | Famille: {fam_txt}"
            elements.append(Paragraph(filter_info, styles['Normal']))
            elements.append(Spacer(1, 10))

            # --- تحضير البيانات ---
            # العناوين (Headers)
            headers = [self.table.horizontalHeaderItem(i).text() for i in range(self.table.columnCount())]
            
            # تحويل العناوين أيضاً إلى Paragraph لتصغير خطها وتفادي التداخل
            header_row = [Paragraph(f"<b>{h}</b>", style_cell_center) for h in headers]
            data = [header_row]

            # تكرار الصفوف
            for r in range(self.table.rowCount()):
                if self.table.isRowHidden(r): continue
                
                row_data = []
                for c in range(self.table.columnCount()):
                    item = self.table.item(r, c)
                    text = item.text() if item else ""
                    
                    # تحديد أي الأعمدة تحتوي نصوصاً طويلة وأيها أرقام/تواريخ
                    # الأعمدة النصية العريضة: 0 (Désignation), 1 (Famille), 2 (Marque), 4 (Fournisseur), 14 (Emplacement)
                    # بقية الأعمدة عادة أرقام أو تواريخ قصيرة
                    
                    if c in [0, 1, 2, 3, 4, 10, 13, 14]: 
                        # استخدام محاذاة لليسار للنصوص
                        p = Paragraph(text, style_cell_text)
                    else:
                        # استخدام محاذاة للوسط للأرقام والتواريخ
                        p = Paragraph(text, style_cell_center)
                        
                    row_data.append(p)
                    
                data.append(row_data)

            # إضافة صف أخير للمجاميع (للتجميل فقط كما في طلبك)
            # نضع نصوصاً فارغة للحفاظ على التنسيق
            footer_row = [Paragraph("<b>TOTAL</b>", style_cell_text)] + [""] * 14
            data.append(footer_row)

            # --- حساب عرض الأعمدة (توزيع دقيق لـ 820 نقطة) ---
            # المجموع = 822 تقريباً
            col_widths = [
                140, # 0: Désignation (الأعرض)
                45,  # 1: Famille
                45,  # 2: Marque
                40,  # 3: Auto
                45,  # 4: Fourn
                35,  # 5: Stock
                45,  # 6: Date Ent.
                40,  # 7: Lot
                45,  # 8: Exp
                32,  # 9: Qté Init
                50,  # 10: Code
                35,  # 11: Prix
                45,  # 12: Valeur
                35,  # 13: Ref PO
                45   # 14: Emplacement
            ]

            # إنشاء الجدول
            # repeatRows=1 : تكرار صف العناوين إذا امتد الجدول لعدة صفحات
            pdf_table = Table(data, colWidths=col_widths, repeatRows=1)

            # --- تنسيق الجدول ---
            style = TableStyle([
                # الخلفية والخط للرأس
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'), # محاذاة للأعلى (مهم جداً عند التفاف النص)
                
                # خطوط الشبكة
                ('GRID', (0, 0), (-1, -1), 0.25, colors.black),
                ('box', (0, 0), (-1, -1), 0.5, colors.black),

                # تقليل الحشوة (Padding) داخل الخلايا لتوفير المساحة
                ('LEFTPADDING', (0, 0), (-1, -1), 2),
                ('RIGHTPADDING', (0, 0), (-1, -1), 2),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),

                # تلوين الصف الأخير (Footer)
                ('BACKGROUND', (0, -1), (-1, -1), colors.beige),
                ('SPAN', (0, -1), (4, -1)), # دمج أول خلايا في الأسفل
            ])
            
            # تلوين الصفوف بالتناوب (Zebra Striping) لقراءة أسهل
            for i in range(1, len(data)-1):
                if i % 2 == 0:
                    style.add('BACKGROUND', (0, i), (-1, i), colors.whitesmoke)

            pdf_table.setStyle(style)
            elements.append(pdf_table)

            # بناء الملف
            doc.build(elements)

        except Exception as e:
            logging.error(f"PDF Export Error: {e}", exc_info=True)
            QMessageBox.critical(self, "Erreur", f"Erreur export PDF: {str(e)}")

    def apply_role_permissions(self, role):
        """إخفاء المبالغ المالية تماماً للتقني"""
        is_tech = (role == 'Technician')
        
        # 1. إخفاء أعمدة الجدول (11 و 12)
        self.table.setColumnHidden(11, is_tech)
        self.table.setColumnHidden(12, is_tech)
        
        # 2. إخفاء ملصق القيمة الإجمالية في الأسفل بشكل قاطع
        if hasattr(self, 'lbl_total_value'):
            if is_tech:
                self.lbl_total_value.hide() # إخفاء تماماً
                self.lbl_total_value.setFixedWidth(0) # للتأكد من عدم حجز مساحة
            else:
                self.lbl_total_value.show() # إظهار للأدمن والمدير
                self.lbl_total_value.setFixedWidth(250) # إعادة العرض الطبيعي
                
        logging.info(f"BatchesTab: Visibility set for {role}. Total Label Hidden: {is_tech}")

    def get_table_data(self):
        """استخراج البيانات للتصدير مع استبعاد الأعمدة المالية تماماً للتقني"""
        try:
            role = self.window().current_user.get('Role', 'Technician')
        except:
            role = 'Technician'
        
        is_tech = (role == 'Technician')
        
        columns = []
        for c in range(self.table.columnCount()):
            if is_tech and c in [11, 12]: continue # حذف الأعمدة 11 و 12 تماماً من القائمة
            item = self.table.horizontalHeaderItem(c)
            columns.append(item.text() if item else f"Col {c}")
            
        rows = []
        for r in range(self.table.rowCount()):
            if self.table.isRowHidden(r): continue
            row_data = []
            for c in range(self.table.columnCount()):
                if is_tech and c in [11, 12]: continue # حذف خلايا الأعمدة 11 و 12 تماماً من الصفوف
                item = self.table.item(r, c)
                row_data.append(item.text() if item else "")
            rows.append(row_data)
            
        return columns, rows
    
    def toggle_date_filter(self, state):
        enabled = (state == 2) 
        self.date_from.setEnabled(enabled)
        self.date_to.setEnabled(enabled)
        self.apply_filters_local()

    def toggle_entry_filter(self, state):
        enabled = (state == 2) 
        self.date_in_from.setEnabled(enabled)
        self.date_in_to.setEnabled(enabled)
        self.apply_filters_local()

    def reset_filters(self):
        self.search_input.clear()
        self.loc_filter.setCurrentIndex(0)
        self.combo_family.setCurrentIndex(0)
        self.combo_manuf.setCurrentIndex(0)
        self.combo_automate.setCurrentIndex(0)
        self.combo_status.setCurrentIndex(1) 
        self.chk_date_filter.setChecked(False)
        self.toggle_date_filter(0)
        self.chk_entry_filter.setChecked(False)
        self.toggle_entry_filter(0)
        self.load_data()

    def load_data(self):
        try:
            status_idx = self.combo_status.currentIndex()
            search_text = self.search_input.text().strip()
            fetch_zero = (status_idx == 5) or (len(search_text) > 0)
            
            selected_batch_id = None
            if self.table.currentRow() >= 0:
                item = self.table.item(self.table.currentRow(), 0)
                if item:
                    data = item.data(Qt.UserRole)
                    if data: selected_batch_id = data.get('Batch_ID')

            self.all_data = self.manager.batches.get_all_batches_with_details(include_zero_stock=fetch_zero)
            self.apply_filters_local() 

            if selected_batch_id:
                for r in range(self.table.rowCount()):
                    item = self.table.item(r, 0)
                    if item:
                        b_data = item.data(Qt.UserRole)
                        if b_data and b_data.get('Batch_ID') == selected_batch_id:
                            self.table.selectRow(r); break
        except Exception as e:
            logging.error(f"Erreur load_data: {e}")

    def apply_filters_local(self):
        """تطبيق الفلترة، حساب المجموع، ثم بدء التحميل الكسول"""
        try:
            # 1. جمع معايير البحث
            search_txt = self.search_input.text().lower().strip()
            loc_id = self.loc_filter.get_current_location_id()
            family_id = self.combo_family.currentData()
            manuf_id = self.combo_manuf.currentData()
            automate_id = self.combo_automate.currentData()
            status_idx = self.combo_status.currentIndex()
            
            use_exp_date = self.chk_date_filter.isChecked()
            exp_from = self.date_from.date().toPython()
            exp_to = self.date_to.date().toPython()
            
            use_entry_date = self.chk_entry_filter.isChecked()
            ent_from = self.date_in_from.date().toPython()
            ent_to = self.date_in_to.date().toPython()
            current_date = date.today()

            temp_filtered = []
            
            # 2. حلقة الفلترة
            for row in self.all_data:
                qty = float(row.get('Quantity_Current', 0))
                
                # الحالة
                if status_idx in [0, 1, 2, 3, 4] and qty <= 0: continue 
                elif status_idx == 5 and qty > 0: continue

                # النص
                bc_internal = str(row.get('Internal_Barcode', '')).lower()
                bc_manuf = str(row.get('Barcode', '')).lower()
                if search_txt:
                    full_text = f"{row.get('Product_Name','')} {row.get('Lot_Number','')} {bc_internal} {bc_manuf} {row.get('PO_ID','')}".lower()
                    if search_txt not in full_text: continue

                # القوائم
                if loc_id and row.get('Location_ID') != loc_id: continue
                if family_id and row.get('Family_ID') != family_id: continue
                if manuf_id and row.get('Manuf_ID') != manuf_id: continue
                if automate_id and row.get('Preferred_Automate_ID') != automate_id: continue

                # التواريخ
                min_threshold = float(row.get('Minimum_Stock_Level') or 5) 
                alert_days = int(row.get('Alert_Before_Expiry_Days') or 30)
                
                exp_date_obj = None
                raw_exp = row.get('Expiry_Date')
                if raw_exp:
                    if isinstance(raw_exp, datetime): exp_date_obj = raw_exp.date()
                    elif isinstance(raw_exp, date): exp_date_obj = raw_exp
                    elif isinstance(raw_exp, str):
                        try: exp_date_obj = datetime.strptime(raw_exp[:10], "%Y-%m-%d").date()
                        except: pass

                if status_idx == 2 and qty > min_threshold: continue
                elif status_idx == 3 and (not exp_date_obj or exp_date_obj >= current_date): continue
                elif status_idx == 4:
                    if not exp_date_obj: continue
                    days_left = (exp_date_obj - current_date).days
                    if not (0 <= days_left <= alert_days): continue
                
                if use_exp_date:
                    if not exp_date_obj or not (exp_from <= exp_date_obj <= exp_to): continue

                if use_entry_date:
                    entry_date_val = row.get('Date_Received') or row.get('Created_At')
                    e_date_obj = None
                    if isinstance(entry_date_val, (datetime, date)): 
                        e_date_obj = entry_date_val if isinstance(entry_date_val, date) else entry_date_val.date()
                    elif isinstance(entry_date_val, str):
                        try: e_date_obj = datetime.strptime(str(entry_date_val)[:10], "%Y-%m-%d").date()
                        except: pass
                    if not e_date_obj or not (ent_from <= e_date_obj <= ent_to): continue

                temp_filtered.append(row)
            
            self.filtered_data = temp_filtered

            # 3. حساب القيمة الإجمالية (للكل وليس للمعروض فقط)
            try:
                role = self.window().current_user.get('Role', 'Technician')
            except: role = 'Technician'
            
            if role != 'Technician':
                total_value = 0.0
                for b in self.filtered_data:
                    try:
                        q = float(b.get('Quantity_Current', 0))
                        if q > 0:
                            p = float(b.get('Unit_Price_Received', 0))
                            d = float(b.get('Discount_Percent', 0)) / 100.0
                            t = float(b.get('Tax_Rate_Percent', 0)) / 100.0
                            total_value += q * p * (1 - d) * (1 + t)
                    except: pass
                self.lbl_total_value.setText(f"💰 Total Filtré : {total_value:,.2f} DA")
                self.lbl_total_value.show()
            else:
                self.lbl_total_value.hide()

            # 4. إعادة تعيين الجدول وبدء التحميل من الصفر
            self.table.setRowCount(0)
            self.loaded_count = 0
            
            if self.current_sort_col != -1:
                self.apply_sorting()
            else:
                self.load_more_data()

        except Exception as e:
            logging.error(f"Erreur filters: {e}", exc_info=True)

    def check_fefo_compliance(self, current_batch):
        current_expiry = current_batch.get('Expiry_Date')
        product_id = current_batch.get('Product_ID')
        if not current_expiry: return True
        if isinstance(current_expiry, datetime): curr_date = current_expiry.date()
        elif isinstance(current_expiry, date): curr_date = current_expiry
        elif isinstance(current_expiry, str):
            try: curr_date = datetime.strptime(current_expiry[:10], "%Y-%m-%d").date()
            except: return True
        else: return True

        older_batches = []
        for batch in self.all_data:
            if batch.get('Batch_ID') == current_batch.get('Batch_ID'): continue
            if batch.get('Product_ID') != product_id: continue
            if float(batch.get('Quantity_Current', 0)) <= 0: continue
            other_expiry = batch.get('Expiry_Date')
            if not other_expiry: continue
            other_date = None
            if isinstance(other_expiry, datetime): other_date = other_expiry.date()
            elif isinstance(other_expiry, date): other_date = other_expiry
            elif isinstance(other_expiry, str):
                try: other_date = datetime.strptime(other_expiry[:10], "%Y-%m-%d").date()
                except: continue
            if other_date and other_date < curr_date:
                older_batches.append(batch)

        if older_batches:
            older_batches.sort(key=lambda x: str(x.get('Expiry_Date', '')))
            msg = "⚠️ <b>Attention : Non-Respect du FEFO</b><br><br>Des lots plus anciens existent :"
            for b in older_batches[:3]:
                d_str = str(b.get('Expiry_Date'))[:10]
                lot = b.get('Lot_Number', 'N/A')
                msg += f"<br>• Lot: {lot} | Exp: {d_str}"
            reply = QMessageBox.question(self, "Alerte FEFO", msg, QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.No: return False
        return True

    def get_current_user_id(self):
        try: return self.window().current_user.get('User_ID')
        except: return None

    def direct_use_process(self):
        row_idx = self.table.currentRow()
        if row_idx < 0: 
            QMessageBox.warning(self, "Sélection", "Veuillez sélectionner un lot.")
            return
        batch_data = self.table.item(row_idx, 0).data(Qt.UserRole)
        if not self.check_fefo_compliance(batch_data): return
        max_qty = float(batch_data.get('Quantity_Current', 0))
        if max_qty <= 0: return
        qty, ok = QInputDialog.getDouble(self, "Sortie", f"Quantité (Max: {max_qty:g}):", 1.0, 0.01, max_qty, 2)
        if ok:
            u_id = self.get_current_user_id()
            if self.manager.batches.direct_consume_batch_unit(batch_data['Batch_ID'], qty, user_id=u_id):
                self.load_data()
                self.data_changed.emit()

    def handle_barcode_scan(self):
        txt = self.search_input.text().strip().lower()
        if not txt: return
        found_rows = []
        for r in range(self.table.rowCount()):
            data = self.table.item(r, 0).data(Qt.UserRole)
            bc1 = str(data.get('Internal_Barcode','')).lower()
            bc2 = str(data.get('Barcode','')).lower()
            if txt == bc1 or txt == bc2: found_rows.append(r)
        if len(found_rows) == 1:
            self.table.selectRow(found_rows[0])
            self.table.scrollToItem(self.table.item(found_rows[0], 0))
            self.search_input.selectAll()

    def adjust_stock(self):
        row = self.table.currentRow()
        if row < 0: return
        data = self.table.item(row, 0).data(Qt.UserRole)
        dlg = AdjustmentDialog(data, self.manager.waste_reasons.get_all_reasons(), self)
        if dlg.exec():
            d = dlg.get_data()
            if self.manager.batches.adjust_batch_quantity(d['Batch_ID'], d['Qty_Change'], 'Adjustment', d['Reason_ID'], self.get_current_user_id()):
                self.load_data()
                self.data_changed.emit()

    def waste_batch(self):
        row = self.table.currentRow()
        if row < 0: return
        data = self.table.item(row, 0).data(Qt.UserRole)
        dlg = WasteDialog(data, self.manager.waste_reasons.get_all_reasons(), 'Batch', self)
        if dlg.exec():
            d = dlg.get_data()
            if self.manager.batches.adjust_batch_quantity(d['Source_ID'], -abs(float(d['Qty_Wasted'])), 'Waste', d['Reason_ID'], self.get_current_user_id()):
                self.load_data()
                self.data_changed.emit()

    def show_batch_details(self):
        row = self.table.currentRow()
        if row < 0: return
        batch_data = self.table.item(row, 0).data(Qt.UserRole)
        if batch_data:
            from .dialogs import BatchDetailsDialog
            dialog = BatchDetailsDialog(batch_data, self)
            dialog.exec()


    def open_history_via_barcode(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Sélection", "Veuillez sélectionner un produit.")
            return
            
        item = self.table.item(row, 0)
        if not item: return

        batch_data = item.data(Qt.UserRole)
        if not batch_data: return

        search_term = batch_data.get('Internal_Barcode') or batch_data.get('Barcode') or batch_data.get('Product_Name')
        
        if search_term:
            self.request_product_history.emit(str(search_term))
        else:
            QMessageBox.warning(self, "Erreur", "Aucune donnée (Code/Nom) trouvée pour la recherche.")
            

    def go_to_history(self, product_name):
        if product_name:
            self.request_product_history.emit(str(product_name))

    
    def open_quick_transfer(self, batch_data):
        """فتح نافذة التحويل الصغيرة وتنفيذ العملية"""
        # نمرر مدير المواقع (self.manager.locations) لتعبئة القائمة
        dialog = QuickTransferDialog(batch_data, self.manager.locations, self)
        
        if dialog.exec():
            data = dialog.get_data()
            dest_id = data['dest_id']
            qty = data['qty']

            # تحققات بسيطة
            if not dest_id:
                QMessageBox.warning(self, "Erreur", "Veuillez sélectionner une destination.")
                return
            if str(dest_id) == str(batch_data.get('Location_ID')):
                QMessageBox.warning(self, "Erreur", "La destination est la même que l'emplacement actuel.")
                return

            # التنفيذ عبر المدير (Manager)
            try:
                # نستخدم user_id إذا كان متاحاً
                u_id = self.get_current_user_id()
                success = self.manager.batches.transfer_batch_location(
                    batch_data['Batch_ID'], dest_id, qty, user_id=u_id
                )
                
                if success:
                    self.load_data() # تحديث الجدول
                    self.data_changed.emit() # إشعار باقي التبويبات
                else:
                    QMessageBox.critical(self, "Erreur", "Échec de l'opération dans la base de données.")
            except Exception as e:
                logging.error(f"Quick Transfer Error: {e}")
                QMessageBox.critical(self, "Erreur", f"Erreur technique : {e}")

    def open_quick_consume(self, batch_data):
        """فتح نافذة الاستهلاك الصغيرة وتنفيذ العملية"""
        dialog = QuickConsumeDialog(batch_data, self)
        
        if dialog.exec():
            qty = dialog.get_qty()
            
            try:
                # تحقق من FEFO (اختياري، إذا كنت تريد تطبيقه هنا أيضاً)
                if not self.check_fefo_compliance(batch_data):
                    return

                u_id = self.get_current_user_id()
                success = self.manager.batches.direct_consume_batch_unit(
                    batch_data['Batch_ID'], qty, user_id=u_id
                )
                
                if success:
                    self.load_data()
                    self.data_changed.emit()
                else:
                    QMessageBox.critical(self, "Erreur", "Échec de l'opération.")
            except Exception as e:
                logging.error(f"Quick Consume Error: {e}")
                QMessageBox.critical(self, "Erreur", f"Erreur technique : {e}")

    def show_context_menu(self, pos):
        index = self.table.indexAt(pos)
        if not index.isValid(): return
        
        item = self.table.item(index.row(), 0)
        batch_data = item.data(Qt.UserRole)
        if not batch_data: return
        
        menu = QMenu(self)

        # 1. خيارات الاستهلاك والتحويل (متاحة للجميع)
        action_consume = QAction("📉 Consommation Rapide", self)
        action_consume.triggered.connect(lambda: self.open_quick_consume(batch_data))
        menu.addAction(action_consume)

        action_transfer = QAction("🚚 Transfert vers...", self)
        action_transfer.triggered.connect(lambda: self.open_quick_transfer(batch_data))
        menu.addAction(action_transfer)
        
        menu.addSeparator()

        # --- تحديد دور المستخدم ---
        role = 'Technician' # الافتراضي
        try:
            main_win = self.window()
            if hasattr(main_win, 'current_user') and main_win.current_user:
                role = main_win.current_user.get('Role', 'Technician')
        except Exception: 
            pass

        # 2. خيار السجل (للـ Admin فقط)
        if role == 'Admin':
            search_term = batch_data.get('Internal_Barcode') or batch_data.get('Barcode') or batch_data.get('Product_Name')
            action_history = QAction("📜 Voir Historique (Code-Barres)", self)
            action_history.triggered.connect(lambda: self.go_to_history(search_term))
            menu.addAction(action_history)
        
        # 3. خيار التفاصيل (للجميع)
        action_details = QAction("🔍 Détails du lot", self)
        action_details.triggered.connect(self.show_batch_details)
        menu.addAction(action_details)
        
        # 4. خيار وصل الاستلام (إخفاؤه عن التقني)
        # [تعديل] الشرط: أن يوجد رقم وصل (BR_ID) وأن لا يكون المستخدم 'Technician'
        if batch_data.get('BR_ID') and role != 'Technician':
            action_goto_br = QAction("📄 Voir Bon de Réception", self)
            action_goto_br.triggered.connect(lambda: self.go_to_reception(batch_data['BR_ID'], batch_data.get('Batch_ID')))
            menu.addAction(action_goto_br)
            
        menu.addSeparator()
        
        # 5. الطباعة (للجميع)
        action_print = QAction("🖨️ Imprimer Étiquette", self)
        action_print.triggered.connect(self.print_batch_label)
        menu.addAction(action_print)
        
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def go_to_reception(self, br_id, target_batch_id=None):
        try:
            reception_data = self.manager.reception.get_reception_full_details(br_id)
            if not reception_data or not reception_data.get('Header'):
                QMessageBox.warning(self, "Erreur", "Données de réception introuvables.")
                return
            header = reception_data['Header']
            po_data = {
                'PO_ID': header.get('PO_ID'), 
                'Supplier_ID': header.get('Supplier_ID'), 
                'Supplier_Name': header.get('Supplier_Name', 'Fournisseur Inconnu')
            }
            locations_list = self.manager.locations.get_all_locations()
            
            dialog = ReceptionDialog(
                po_data=po_data, 
                locations_list=locations_list, 
                location_manager=self.manager.locations, 
                manager=self.manager, 
                printer_manager=self.manager.printer, 
                parent=self, 
                edit_mode=True, 
                reception_data=reception_data, 
                target_batch_id=target_batch_id
            )
            dialog.exec()
            try:
                if hasattr(self.manager.db, 'get_raw_connection'):
                    self.manager.db.get_raw_connection().commit()
            except: pass
            self.load_data()
        except Exception as e:
            logging.error(f"Erreur go_to_reception: {e}")
            QMessageBox.critical(self, "Erreur", f"Technique: {str(e)}")

    def populate_manufacturers(self):
        self.combo_manuf.clear()
        self.combo_manuf.addItem("🏭 Marques", None)
        try:
            if hasattr(self.manager, 'manufacturers'):
                for m in self.manager.manufacturers.get_all_manufacturers():
                    self.combo_manuf.addItem(m['Manuf_Name'], m['Manuf_ID'])
            self._adjust_combo_view_width(self.combo_manuf)
        except: pass

    def populate_automates(self):
        self.combo_automate.clear()
        self.combo_automate.addItem("⚙️ Automates", None)
        try:
            if hasattr(self.manager, 'automates'):
                for a in self.manager.automates.get_all_automates():
                    self.combo_automate.addItem(a['Automate_Name'], a['Automate_ID'])
            self._adjust_combo_view_width(self.combo_automate)
        except: pass
    
    def _adjust_combo_view_width(self, combo):
        width = combo.width()
        fm = combo.fontMetrics()
        count = combo.count()
        for i in range(count):
            text_width = fm.horizontalAdvance(combo.itemText(i)) + 30
            if text_width > width:
                width = text_width
        combo.view().setMinimumWidth(width)

    def populate_families(self):
        self.combo_family.clear()
        self.combo_family.addItem("📁 Familles", None)
        try:
            if hasattr(self.manager, 'families'):
                for f in self.manager.families.get_all_families():
                    self.combo_family.addItem(f['Family_Name'], f['Family_ID'])
            self._adjust_combo_view_width(self.combo_family)
        except: pass