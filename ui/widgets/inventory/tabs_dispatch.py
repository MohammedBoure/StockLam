# ui/widgets/inventory/tabs_dispatch.py

import logging
from datetime import datetime, date
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QAbstractItemView,QMenu,
    QTableWidgetItem, QPushButton, QHeaderView, QGroupBox, QFrame, 
    QLabel, QMessageBox, QLineEdit, QSpinBox, QComboBox, QCompleter, QDialog
)
from PySide6.QtCore import Qt, Signal, QTimer, QStringListModel
from PySide6.QtGui import QColor, QFont,QAction

from ui.formatting import format_quantity, quantity_to_int

try:
    from .location_tree_combo import LocationTreeComboBox
except ImportError:
    from PySide6.QtWidgets import QComboBox as LocationTreeComboBox

# ==============================================================================
# Classes Utilitaires
# ==============================================================================

class BarcodeLineEdit(QLineEdit):
    def keyPressEvent(self, event):
        azerty_map = {
            Qt.Key_Ampersand: "1", Qt.Key_Eacute: "2", Qt.Key_QuoteDbl: "3",
            Qt.Key_QuoteLeft: "4", Qt.Key_ParenLeft: "5", Qt.Key_Minus: "6",
            Qt.Key_Egrave: "7", Qt.Key_Underscore: "8", Qt.Key_Ccedilla: "9",
            Qt.Key_Agrave: "0"
        }
        if event.key() in azerty_map:
            self.insert(azerty_map[event.key()])
            event.accept()
        else:
            super().keyPressEvent(event)

class NumericSpinBox(QSpinBox):
    def keyPressEvent(self, event):
        azerty_map = {
            Qt.Key_Ampersand: "1", Qt.Key_Eacute: "2", Qt.Key_QuoteDbl: "3",
            Qt.Key_QuoteLeft: "4", Qt.Key_ParenLeft: "5", Qt.Key_Minus: "6",
            Qt.Key_Egrave: "7", Qt.Key_Underscore: "8", Qt.Key_Ccedilla: "9",
            Qt.Key_Agrave: "0"
        }
        if event.key() in azerty_map:
            self.lineEdit().insert(azerty_map[event.key()])
            event.accept()
        else:
            super().keyPressEvent(event)

    def focusInEvent(self, event):
        super().focusInEvent(event)
        QTimer.singleShot(0, self.selectAll)

# ==============================================================================
# FEFO Selection Dialog (النافذة الجديدة لاختيار الدفعة)
# ==============================================================================

class FEFOSelectionDialog(QDialog):
    def __init__(self, product_name, batches_list, recommended_batch, current_scanned_batch, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"⚠️ Respect du FEFO - {product_name}")
        self.resize(1100, 550)
        
        self.selected_batch = None
        self.product_name = product_name
        self.batches_list = batches_list
        self.recommended_batch = recommended_batch
        self.current_scanned_batch = current_scanned_batch
        
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # 1. Header Message With Product Name
        header_frame = QFrame()
        header_frame.setStyleSheet("background-color: #fff3cd; border: 1px solid #ffeeba; border-radius: 5px;")
        header_layout = QVBoxLayout(header_frame)
        
        lbl_title = QLabel(f"📦 Produit : {self.product_name}")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #856404;")
        
        lbl_desc = QLabel(
            "⚠️ <b>Alerte FEFO :</b> Vous avez sélectionné un lot récent, mais des lots plus anciens sont disponibles.<br>"
            "Veuillez choisir ci-dessous le lot à consommer (Le lot recommandé est surligné en vert)."
        )
        lbl_desc.setStyleSheet("color: #856404; font-size: 13px;")
        
        header_layout.addWidget(lbl_title)
        header_layout.addWidget(lbl_desc)
        layout.addWidget(header_frame)

        # 2. Table
        self.table = QTableWidget()

        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)

        cols = [
            "État", "Produit", "N° Lot", "Date Exp.", "Qté Dispo", 
            "Emplacement", "Marque", "Date Réception"
        ]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        
        # تنسيق الأعمدة
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch) # Product Name Stretch
        
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSortingEnabled(False)
        layout.addWidget(self.table)

        self.populate_table()

        # 3. Buttons
        btn_box = QHBoxLayout()
        
        btn_cancel = QPushButton("Annuler l'opération")
        btn_cancel.setStyleSheet("background-color: #95a5a6; color: white; padding: 8px;")
        btn_cancel.clicked.connect(self.reject)
        
        btn_confirm = QPushButton("✅ Confirmer le lot sélectionné")
        btn_confirm.setCursor(Qt.PointingHandCursor)
        btn_confirm.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; padding: 10px 20px; font-size: 14px; border-radius: 5px;")
        btn_confirm.clicked.connect(self.confirm_selection)

        btn_box.addStretch()
        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(btn_confirm)
        layout.addLayout(btn_box)


    def show_context_menu(self, pos):
        """إظهار القائمة عند النقر بالزر الأيمن"""
        index = self.table.indexAt(pos)
        if not index.isValid(): return

        menu = QMenu(self)
        
        action_history = QAction("📜 Voir Historique du Produit", self)
        action_history.triggered.connect(self.open_history_via_barcode)
        menu.addAction(action_history)
        
        # خيار حذف من السلة (مفيد أيضاً)
        action_remove = QAction("🗑️ Retirer de la liste", self)
        action_remove.triggered.connect(self.remove_selected_row)
        menu.addAction(action_remove)

        menu.exec(self.table.viewport().mapToGlobal(pos))

    def remove_selected_row(self):
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)

    def open_history_via_barcode(self):
        """الانتقال المباشر لصفحة السجل (ID = 6)."""
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Sélection", "Veuillez sélectionner un produit.")
            return

        item = self.table.item(row, 0)
        if not item: return
        
        batch_data = item.data(Qt.UserRole)
        if not batch_data: return

        # 1. تحديد ما سنبحث عنه (الباركود هو الأفضل)
        search_term = batch_data.get('Internal_Barcode') or batch_data.get('Barcode') or batch_data.get('Product_Name')

        # 2. الوصول للنافذة الرئيسية
        main_win = self.window()
        
        # التأكد من أننا في النافذة الرئيسية الصحيحة
        if hasattr(main_win, 'switch_page') and hasattr(main_win, 'nav_group'):
            
            # رقم صفحة السجل هو 6 (بناءً على ملف main_window.py)
            HISTORY_PAGE_ID = 6
            
            # تفعيل الزر في القائمة الجانبية (للمظهر)
            btn = main_win.nav_group.button(HISTORY_PAGE_ID)
            if btn:
                btn.setChecked(True)
                
            # الانتقال الفعلي للصفحة (سيقوم بتحميلها إذا لم تكن مفتوحة)
            main_win.switch_page(HISTORY_PAGE_ID)
            
            # 3. وضع النص في خانة البحث (نستخدم Timer بسيط لضمان اكتمال تحميل الصفحة)
            from PySide6.QtCore import QTimer
            
            def apply_search_filter():
                # الصفحة تخزن في main_win.pages بعد تحميلها
                if hasattr(main_win, 'pages') and HISTORY_PAGE_ID in main_win.pages:
                    history_page = main_win.pages[HISTORY_PAGE_ID]
                    
                    # البحث عن خانة الإدخال ووضع النص
                    if hasattr(history_page, 'search_input'):
                        history_page.search_input.setText(str(search_term))
                        
                        # تشغيل الفلتر تلقائياً
                        if hasattr(history_page, 'filter_data'):
                            history_page.filter_data()
            
            # تنفيذ البحث بعد 50 ميلي ثانية (لضمان أن الواجهة جاهزة)
            QTimer.singleShot(50, apply_search_filter)
            
        else:
            QMessageBox.warning(self, "Erreur", "Impossible de localiser la fenêtre principale (MainWindow).")

    def populate_table(self):
        self.table.setRowCount(0)
        
        for batch in self.batches_list:
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            # المقارنة بالـ ID لضمان الدقة
            is_recommended = (str(batch['Batch_ID']) == str(self.recommended_batch['Batch_ID']))
            is_scanned = (str(batch['Batch_ID']) == str(self.current_scanned_batch['Batch_ID']))
            
            # 0. État (Status)
            status_text = ""
            if is_recommended: status_text = "⭐ RECOMMANDÉ"
            elif is_scanned: status_text = "✋ SÉLECTIONNÉ"
            
            item_status = QTableWidgetItem(status_text)
            item_status.setTextAlignment(Qt.AlignCenter)
            if is_recommended:
                item_status.setForeground(QColor("#155724"))
                item_status.setFont(QFont("Arial", 9, QFont.Bold))
            elif is_scanned:
                item_status.setForeground(QColor("#c0392b"))
            self.table.setItem(row, 0, item_status)

            # 1. Produit
            self.table.setItem(row, 1, QTableWidgetItem(str(batch.get('Product_Name', ''))))

            # 2. N° Lot
            self.table.setItem(row, 2, QTableWidgetItem(str(batch.get('Lot_Number', ''))))
            
            # 3. Date Exp
            exp_date = str(batch.get('Expiry_Date', ''))[:10]
            item_exp = QTableWidgetItem(exp_date)
            item_exp.setTextAlignment(Qt.AlignCenter)
            if is_recommended:
                item_exp.setFont(QFont("Arial", 10, QFont.Bold))
                item_exp.setForeground(QColor("#c0392b")) # تاريخ أحمر للموصى به
            self.table.setItem(row, 3, item_exp)

            # 4. Qté
            qty_item = QTableWidgetItem(format_quantity(batch.get('Quantity_Current', 0)))
            qty_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 4, qty_item)
            
            # 5. Emplacement
            self.table.setItem(row, 5, QTableWidgetItem(str(batch.get('Location_Name', '-'))))
            
            # 6. Marque
            self.table.setItem(row, 6, QTableWidgetItem(str(batch.get('Manuf_Name', '-'))))
            
            # 7. Date Réception
            rec_date = str(batch.get('Date_Received', ''))[:10]
            self.table.setItem(row, 7, QTableWidgetItem(rec_date))
            
            # تلوين الصفوف
            if is_recommended:
                for c in range(self.table.columnCount()):
                    if self.table.item(row, c):
                        self.table.item(row, c).setBackground(QColor("#d4edda")) # أخضر فاتح
            elif is_scanned:
                for c in range(self.table.columnCount()):
                    if self.table.item(row, c):
                        self.table.item(row, c).setBackground(QColor("#f8d7da")) # أحمر فاتح

            # تخزين البيانات
            self.table.item(row, 0).setData(Qt.UserRole, batch)
            
            # تحديد الصف الموصى به تلقائياً
            if is_recommended:
                self.table.selectRow(row)

    def confirm_selection(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Sélection", "Veuillez sélectionner une ligne.")
            return
        
        self.selected_batch = self.table.item(row, 0).data(Qt.UserRole)
        self.accept()

# ==============================================================================
# Main Class: DispatchTab
# ==============================================================================

class DispatchTab(QWidget):
    data_changed = Signal()

    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self.all_inventory_pool = [] 
        self.search_map = {} 
        
        self.scan_timer = QTimer()
        self.scan_timer.setSingleShot(True)
        self.scan_timer.timeout.connect(self.process_scan_buffer)

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)

        # --- Scan Area ---
        scan_group = QGroupBox("")
        scan_group.setStyleSheet("""
            QGroupBox { font-weight: bold; font-size: 14px; color: #2c3e50; border: 2px solid #2980b9; border-radius: 10px; padding-top: 25px; margin-top: 10px; }
            QGroupBox::title { subcontrol-origin: margin; left: 15px; top: -10px; padding: 0 5px; background-color: white; }
        """)
        scan_layout = QHBoxLayout(scan_group)
        scan_layout.setContentsMargins(10, 10, 10, 10)

        self.barcode_input = BarcodeLineEdit()
        self.barcode_input.setPlaceholderText("🔴 Scannez (Code-Barres) ou Écrivez (Nom/Lot)...")
        self.barcode_input.setMinimumHeight(60)
        self.barcode_input.setStyleSheet("""
            QLineEdit { 
                font-size: 18px; font-weight: bold; background-color: #f1f2f6; 
                border: 2px solid #bdc3c7; border-radius: 8px; padding-left: 15px; color: #2c3e50;
            }
            QLineEdit:focus { border: 2px solid #2980b9; background-color: #ffffff; }
        """)

        self.completer = QCompleter(self)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchContains)
        self.completer.setCompletionMode(QCompleter.PopupCompletion)
        self.barcode_input.setCompleter(self.completer)

        self.completer.activated.connect(self.on_completer_activated)
        self.barcode_input.textChanged.connect(self.on_text_changed)
        self.barcode_input.returnPressed.connect(self.process_scan_buffer)
        
        scan_layout.addWidget(self.barcode_input)
        layout.addWidget(scan_group)

        # --- Table ---
        self.table = QTableWidget()
        cols = ["Produit", "N° Lot", "Source (Lieu Actuel)", "Destination", "Qté", "Suppr."]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        
        self.table.verticalHeader().setDefaultSectionSize(50)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        
        self.table.setStyleSheet("""
            QTableWidget { background-color: white; border: 1px solid #dcdde1; border-radius: 5px; font-size: 13px; }
            QHeaderView::section { background-color: #ecf0f1; padding: 5px; font-weight: bold; border: none; }
            QTableWidget::item { padding: 5px; }
            QComboBox { padding: 5px; border: 1px solid #bdc3c7; border-radius: 3px; }
        """)
        layout.addWidget(self.table)

        # --- Buttons ---
        btns_frame = QFrame()
        btns_frame.setStyleSheet("QFrame { background-color: #f8f9fa; border-top: 1px solid #dcdde1; }")
        btns_layout = QHBoxLayout(btns_frame)
        btns_layout.setContentsMargins(10, 10, 10, 10)

        self.btn_clear = QPushButton("Vider la liste")
        self.btn_clear.setFixedWidth(120)
        self.btn_clear.setMinimumHeight(45)
        self.btn_clear.setStyleSheet("background-color: #95a5a6; color: white; font-weight: bold; border-radius: 5px;")
        self.btn_clear.clicked.connect(lambda: self.table.setRowCount(0))

        self.btn_consume = QPushButton("📉 CONSOMMATION")
        self.btn_consume.setMinimumHeight(55)
        self.btn_consume.setStyleSheet("QPushButton { background-color: #c0392b; color: white; font-weight: bold; font-size: 16px; border-radius: 8px; } QPushButton:hover { background-color: #e74c3c; }")
        self.btn_consume.clicked.connect(lambda: self.execute_bulk_action("consume"))

        self.btn_transfer = QPushButton("🚚 TRANSFERT")
        self.btn_transfer.setMinimumHeight(55)
        self.btn_transfer.setStyleSheet("QPushButton { background-color: #2980b9; color: white; font-weight: bold; font-size: 16px; border-radius: 8px; } QPushButton:hover { background-color: #3498db; }")
        self.btn_transfer.clicked.connect(lambda: self.execute_bulk_action("transfer"))

        btns_layout.addWidget(self.btn_clear)
        btns_layout.addStretch()
        btns_layout.addWidget(self.btn_consume)
        btns_layout.addSpacing(15)
        btns_layout.addWidget(self.btn_transfer)
        
        layout.addWidget(btns_frame)

        self.load_inventory_data()

    def load_inventory_data(self):
        try:
            self.all_inventory_pool = self.manager.batches.get_all_batches_with_details()
            
            suggestions = []
            self.search_map = {}
            
            for b in self.all_inventory_pool:
                qty = quantity_to_int(b.get('Quantity_Current', 0))
                if qty <= 0: continue
                
                loc_name = b.get('Location_Name', '---')
                display_text = f"{b['Product_Name']} | Lot: {b['Lot_Number']} | 📍 {loc_name} (Qté: {format_quantity(qty)})"
                
                suggestions.append(display_text)
                self.search_map[display_text] = b
            
            model = QStringListModel(suggestions)
            self.completer.setModel(model)
            
        except Exception as e:
            logging.error(f"DispatchTab: Erreur pool load: {e}", exc_info=True)

    def on_text_changed(self, text):
        if not text.strip(): return
        self.scan_timer.start(200)

    def on_completer_activated(self, text):
        batch = self.search_map.get(text)
        if batch:
            self.add_to_table([batch])
            self.flash_input("#dff9fb")
            QTimer.singleShot(0, self.barcode_input.clear)
            self.barcode_input.setFocus()

    def process_scan_buffer(self):
        if self.completer.popup().isVisible():
            return

        raw_text = self.barcode_input.text().strip().lower()
        if not raw_text: return

        found_batches = []
        clean_input = raw_text.replace("-", "")

        for b in self.all_inventory_pool:
            if quantity_to_int(b.get('Quantity_Current', 0)) <= 0: continue

            internal = str(b.get('Internal_Barcode', '')).strip().lower()
            manuf = str(b.get('Barcode', '')).strip().lower()
            
            clean_internal = internal.replace("-", "")
            clean_manuf = manuf.replace("-", "")
            
            if clean_input == clean_internal or clean_input == clean_manuf:
                found_batches.append(b)

        if found_batches:
            self.add_to_table(found_batches)
            self.flash_input("#dff9fb")
            self.barcode_input.clear()
        else:
            self.flash_input("#fab1a0")
        
        self.barcode_input.setFocus()

    def flash_input(self, color_hex):
        original_style = self.barcode_input.styleSheet()
        temp_style = f"background-color: {color_hex};"
        self.barcode_input.setStyleSheet(temp_style)
        QTimer.singleShot(300, lambda: self.barcode_input.setStyleSheet(original_style))

    def add_to_table(self, batches_list):
        if not batches_list: return

        primary_batch = batches_list[0]
        row = self.table.rowCount()
        self.table.insertRow(row)

        # 0. Product Name
        name_str = f"{primary_batch['Product_Name']}\n(BC: {primary_batch.get('Internal_Barcode', '-')})"
        name_item = QTableWidgetItem(name_str)
        name_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.table.setItem(row, 0, name_item)

        # 1. Lot
        lot_item = QTableWidgetItem(str(primary_batch['Lot_Number']))
        lot_item.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(row, 1, lot_item)

        # 2. Source Combo
        cb_source = QComboBox()
        cb_source.setStyleSheet("font-weight: bold; color: #2c3e50;")
        
        for b in batches_list:
            loc_name = b.get('Location_Name', 'Inconnu')
            qty = quantity_to_int(b.get('Quantity_Current', 0))
            item_text = f"{loc_name} (Dispo: {format_quantity(qty)})"
            cb_source.addItem(item_text, b)
        
        self.table.setCellWidget(row, 2, cb_source)

        # 3. Dest
        dest_picker = LocationTreeComboBox(self.manager.locations)
        dest_picker.setPlaceholderText("📍 Destination...")
        self.table.setCellWidget(row, 3, dest_picker)

        # 4. Qty
        qty_input = NumericSpinBox()
        qty_input.setMinimumHeight(35)
        qty_input.lineEdit().setAlignment(Qt.AlignCenter)
        qty_input.lineEdit().returnPressed.connect(self.barcode_input.setFocus)
        self.table.setCellWidget(row, 4, qty_input)

        # 5. Delete
        btn_del = QPushButton("✕")
        btn_del.setCursor(Qt.PointingHandCursor)
        btn_del.setStyleSheet("color: #e74c3c; font-weight: bold; border: none; font-size: 18px; background: transparent;")
        btn_del.clicked.connect(self.remove_clicked_row) # Updated connection
        self.table.setCellWidget(row, 5, btn_del)
        

        def update_row_context(index):
            selected_batch = cb_source.itemData(index)
            if not selected_batch: return
            name_item.setData(Qt.UserRole, selected_batch)
            max_qty = quantity_to_int(selected_batch.get('Quantity_Current', 0))
            qty_input.setRange(1, max_qty if max_qty > 0 else 1)
            qty_input.setValue(1)
            
            if max_qty < 5:
                cb_source.setStyleSheet("font-weight: bold; color: #c0392b;")
            else:
                cb_source.setStyleSheet("font-weight: bold; color: #27ae60;")

        cb_source.currentIndexChanged.connect(update_row_context)
        cb_source.setCurrentIndex(0)
        update_row_context(0)

        self.table.scrollToBottom()
        self.table.selectRow(row)

    def remove_clicked_row(self):
        # 1. Identify the button that triggered the event
        button = self.sender()
        if not button:
            return

        # 2. Get the button's coordinates relative to the table viewport
        pos = button.mapTo(self.table.viewport(), button.rect().center())

        # 3. Find the cell index at those coordinates
        index = self.table.indexAt(pos)

        # 4. Remove the exact row
        if index.isValid():
            self.table.removeRow(index.row())

    # ==========================================================================
    # LOGIQUE FEFO (First Expired First Out)
    # ==========================================================================

    def parse_date(self, date_val):
        """تحويل التواريخ بشكل آمن"""
        if not date_val: return None
        if isinstance(date_val, datetime): return date_val.date()
        if isinstance(date_val, date): return date_val
        if isinstance(date_val, str):
            clean = date_val.split(" ")[0].strip()
            try: return datetime.strptime(clean, "%Y-%m-%d").date()
            except: pass
            try: return datetime.strptime(clean, "%d/%m/%Y").date()
            except: pass
        return None

    def get_all_product_batches_sorted(self, product_id):
        """
        جلب الدفعات مرتبة حسب:
        1. تاريخ الانتهاء (FEFO)
        2. تاريخ الاستلام (FIFO) عند تساوي تاريخ الانتهاء
        """
        if not product_id: return []
        
        batches = []
        for b in self.all_inventory_pool:
            if str(b.get('Product_ID')) == str(product_id):
                try:
                    if quantity_to_int(b.get('Quantity_Current', 0)) > 0:
                        batches.append(b)
                except: continue
        
        # دالة مساعدة للترتيب
        def sort_key(batch):
            # المعيار 1: تاريخ الانتهاء
            exp = self.parse_date(batch.get('Expiry_Date')) or date.max
            
            # المعيار 2: تاريخ الاستلام (Created_At/Date_Received)
            # نحوله لنص للمقارنة الآمنة أو نستخدمه مباشرة إذا كان datetime
            rcv = batch.get('Date_Received') 
            if not rcv: rcv = datetime.max # إذا لم يوجد تاريخ نعتبره جديداً جداً
            
            # يتم الترتيب بناءً على (التاريخ، ثم الاستلام)
            return (exp, rcv)

        batches.sort(key=sort_key)
        return batches

    def check_fefo_compliance(self, current_batch):
        """
        التحقق من FEFO + FIFO (عند تساوي التواريخ).
        """
        curr_exp_date = self.parse_date(current_batch.get('Expiry_Date'))
        
        # إذا الدفعة الحالية ليس لها تاريخ انتهاء، نمررها
        if not curr_exp_date: 
            return True, current_batch

        # 1. جلب الدفعات مرتبة (انتهاء -> استلام)
        all_product_batches = self.get_all_product_batches_sorted(current_batch.get('Product_ID'))
        
        if not all_product_batches:
            return True, current_batch
        
        # الدفعة الأولى في القائمة هي "المثالية" (الموصى بها)
        recommended_batch = all_product_batches[0]
        
        # إذا كانت الدفعة الحالية هي نفسها الموصى بها، فكل شيء ممتاز
        if str(current_batch.get('Batch_ID')) == str(recommended_batch.get('Batch_ID')):
            return True, current_batch

        # تجهيز تواريخ المقارنة
        rec_exp_date = self.parse_date(recommended_batch.get('Expiry_Date'))
        
        # تحضير تواريخ الاستلام للمقارنة
        curr_rcv = current_batch.get('Date_Received')
        rec_rcv = recommended_batch.get('Date_Received')
        
        # تحويل تواريخ الاستلام لنصوص لضمان مقارنة صحيحة (في حال اختلاف الأنواع)
        curr_rcv_str = str(curr_rcv) if curr_rcv else "9999"
        rec_rcv_str = str(rec_rcv) if rec_rcv else "9999"

        # === منطق كشف المخالفة ===
        is_violation = False

        # الحالة 1: تاريخ انتهاء الموصى به "أقدم" من الحالي (FEFO Violation)
        if rec_exp_date and rec_exp_date < curr_exp_date:
            is_violation = True
            
        # الحالة 2: تواريخ الانتهاء "متساوية"، لكن الموصى به "دخل المخزن أولاً" (FIFO Violation)
        elif rec_exp_date == curr_exp_date:
            if rec_rcv_str < curr_rcv_str:
                is_violation = True

        if not is_violation:
            return True, current_batch

        # === عرض التنبيه ===
        product_name = current_batch.get('Product_Name', 'Produit')
        
        dialog = FEFOSelectionDialog(
            product_name, 
            all_product_batches, 
            recommended_batch, 
            current_scanned_batch=current_batch,
            parent=self
        )
        
        if dialog.exec() == QDialog.Accepted:
            if dialog.selected_batch:
                return True, dialog.selected_batch
            else:
                return False, None
        else:
            return False, None

    def execute_bulk_action(self, action_type):
        count = self.table.rowCount()
        if count == 0:
            QMessageBox.warning(self, "Vide", "La liste est vide.")
            return

        action_name = "CONSOMMATION" if action_type == "consume" else "TRANSFERT"
        msg = f"Êtes-vous sûr de vouloir valider la <b>{action_name}</b> de {count} ligne(s) ?"
        
        reply = QMessageBox.question(self, "Confirmation", msg, QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.No: return

        main_win = self.window()
        current_user = getattr(main_win, 'current_user', None)
        u_id = current_user['User_ID'] if current_user else None

        success_count = 0
        errors = []
        skipped_count = 0
        swapped_count = 0
        
        # تجميع الصفوف
        rows_to_process = []
        for r in range(self.table.rowCount()):
            cb = self.table.cellWidget(r, 2)
            if not cb: continue
            
            batch = cb.currentData()
            if not batch:
                errors.append(f"Ligne {r+1}: Lot invalide.")
                continue

            qty = self.table.cellWidget(r, 4).value()
            dest_id = None
            if action_type == "transfer":
                dest_widget = self.table.cellWidget(r, 3)
                dest_id = dest_widget.get_current_location_id()
                if not dest_id:
                    errors.append(f"Ligne {r+1} ({batch.get('Product_Name')}): Destination manquante.")
                    continue
            
            rows_to_process.append({
                'row_idx': r,
                'batch': batch,
                'qty': qty,
                'dest_id': dest_id
            })

        if errors:
            QMessageBox.warning(self, "Erreur", "\n".join(errors))
            return

        # تنفيذ العمليات
        for item in rows_to_process:
            batch = item['batch']
            qty = item['qty']
            dest_id = item['dest_id']
            
            try:
                final_batch = batch
                
                # تطبيق FEFO فقط عند الاستهلاك
                if action_type == "consume":
                    should_proceed, target_batch = self.check_fefo_compliance(batch)
                    
                    if not should_proceed:
                        skipped_count += 1
                        continue # تخطي هذا السطر (المستخدم ألغى العملية لهذا المنتج)
                    
                    # هل تم تغيير الدفعة؟
                    if str(target_batch.get('Batch_ID')) != str(batch.get('Batch_ID')):
                        swapped_count += 1
                        final_batch = target_batch
                        
                        avail = quantity_to_int(final_batch.get('Quantity_Current', 0))
                        if qty > avail:
                            errors.append(f"Stock insuffisant sur le lot sélectionné ({avail}) pour {final_batch.get('Product_Name')}")
                            continue

                # التنفيذ
                res = False
                if action_type == "consume":
                    res = self.manager.batches.direct_consume_batch_unit(
                        final_batch['Batch_ID'], qty, user_id=u_id
                    )
                else:
                    res = self.manager.batches.transfer_batch_location(
                        final_batch['Batch_ID'], dest_id, qty, user_id=u_id
                    )
                
                if res: success_count += 1
                else: errors.append(f"Échec DB: {final_batch.get('Product_Name')}")

            except Exception as e:
                errors.append(f"Erreur technique: {str(e)}")

        # التقرير النهائي
        summary = []
        if success_count > 0: summary.append(f"✅ {success_count} opérations réussies.")
        if swapped_count > 0: summary.append(f"🔄 {swapped_count} lots changés (FEFO).")
        if skipped_count > 0: summary.append(f"⛔ {skipped_count} opérations annulées.")
        
        final_msg = "\n".join(summary)
        if errors:
            final_msg += "\n\n❌ Erreurs :\n" + "\n".join(errors[:5])
            QMessageBox.warning(self, "Résultat Partiel", final_msg)
        else:
            if success_count > 0 or skipped_count > 0:
                QMessageBox.information(self, "Succès", final_msg)

        if success_count > 0:
            self.table.setRowCount(0)
            self.load_inventory_data()
            self.data_changed.emit()
            self.barcode_input.setFocus()

    def showEvent(self, event):
        super().showEvent(event)
        self.load_inventory_data()
        self.barcode_input.setFocus()
