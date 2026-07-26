import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QHeaderView, QPushButton,
    QHBoxLayout, QLabel, QTableWidgetItem, QComboBox,
    QDateEdit, QStyle, QDialog, QFormLayout, QGroupBox, QCheckBox,
    QAbstractItemView
)
from PySide6.QtCore import Qt, QDate, QTimer
from PySide6.QtGui import QColor, QBrush, QFont

from .inventory.dialogs import BarcodeLineEdit
from ui.formatting import format_quantity


# ==============================================================================
# نافذة التفاصيل الكاملة (تظهر عند النقر المزدوج)
# ==============================================================================
class MovementDetailsDialog(QDialog):
    def __init__(self, data, parent=None):
        super().__init__(parent)
        self.data = data
        self.setWindowTitle("📄 Détails de l'Opération")
        self.resize(550, 600)
        self.init_ui()

    def init_ui(self):
        self._build_details_view()

    def _build_details_view(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        def value(*keys, default="-"):
            for key in keys:
                val = self.data.get(key)
                if val not in (None, ""):
                    return str(val)
            return default

        def add_row(form, label, text):
            label_widget = QLabel(f"<b>{label}</b>")
            value_widget = QLabel(text)
            value_widget.setWordWrap(True)
            value_widget.setTextInteractionFlags(Qt.TextSelectableByMouse)
            form.addRow(label_widget, value_widget)

        type_map = {
            'Purchase_Receive': 'Reception (Achat)',
            'Patient_Test': 'Consommation',
            'QC_Run': 'QC',
            'Calibration': 'Calibration',
            'Open_Pack': 'Ouverture',
            'Adjustment': 'Ajustement',
            'Waste': 'Perte',
            'Transfer': 'Transfert',
            'External_Transfer': 'Vente/Externe',
            'Transfer_Return': 'Retour Sous-traitant',
            'Return_To_Supplier': 'Retour Fournisseur',
        }

        movement_type = value('Movement_Type')
        qty_raw = self.data.get('Qty_Change')
        try:
            qty_text = format_quantity(qty_raw, value('Unit_Used', default=''))
        except (TypeError, ValueError):
            qty_text = value('Qty_Change')

        main_group = QGroupBox("Operation")
        main_form = QFormLayout(main_group)
        add_row(main_form, "Date :", value('Transaction_Date')[:19])
        add_row(main_form, "Type :", type_map.get(movement_type, movement_type))
        add_row(main_form, "Quantite :", qty_text)
        add_row(main_form, "Stock apres mouvement :", value('Stock_After', 'Batch_Historical_Stock', 'Historical_Stock'))
        add_row(main_form, "Utilisateur :", value('Operator_Name'))
        layout.addWidget(main_group)

        product_group = QGroupBox("Produit et lot")
        product_form = QFormLayout(product_group)
        add_row(product_form, "Produit :", value('Product_Name'))
        add_row(product_form, "Code-barres :", value('Batch_Barcode', 'Product_Barcode'))
        add_row(product_form, "Lot :", value('Lot_Number'))
        add_row(product_form, "Emplacement :", value('Location_Name'))
        add_row(product_form, "Batch ID :", value('Batch_ID'))
        layout.addWidget(product_group)

        notes_group = QGroupBox("Notes")
        notes_form = QFormLayout(notes_group)
        add_row(notes_form, "Raison :", value('Reason_Name'))
        add_row(notes_form, "Notes :", value('Notes'))
        add_row(notes_form, "Mouvement ID :", value('Movement_ID', 'Log_ID'))
        layout.addWidget(notes_group)

        btn_close = QPushButton("Fermer")
        btn_close.clicked.connect(self.accept)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)


# ==============================================================================
# التبويب الرئيسي للسجل مع التحميل التلقائي عند التمرير (Scroll-based Lazy Loading)
# ==============================================================================
class MovementHistoryTab(QWidget):
    def __init__(self, manager):
        super().__init__()
        self.manager = manager

        # متغيرات التحميل التدريجي عبر التمرير (Infinite Scroll Lazy Loading)
        self.current_offset = 0
        self.batch_size = 50
        self.total_records = 0
        self.is_loading = False
        self.has_more_data = True

        # مؤقت للبحث لتفادي كثرة الاستعلامات أثناء الكتابة السريعة
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(300)
        self.search_timer.timeout.connect(self.reset_and_reload)

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(8, 8, 8, 8)

        # --- 1. منطقة الفلاتر (Filter Bar) ---
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(8)

        self.date_from = QDateEdit(QDate.currentDate().addYears(-1))
        self.date_from.setCalendarPopup(True)
        self.date_from.setDisplayFormat("yyyy-MM-dd")
        self.date_from.setFixedWidth(110)
        self.date_from.setEnabled(True)
        self.date_from.dateChanged.connect(self.reset_and_reload)

        self.date_to = QDateEdit(QDate.currentDate())
        self.date_to.setCalendarPopup(True)
        self.date_to.setDisplayFormat("yyyy-MM-dd")
        self.date_to.setFixedWidth(110)
        self.date_to.setEnabled(True)
        self.date_to.dateChanged.connect(self.reset_and_reload)

        # القائمة المنسدلة لأنواع الحركات
        self.combo_type = QComboBox()
        self.combo_type.addItems([
            "📋 Tous les mouvements",
            "📥 Réceptions (Achats)",
            "🧪 Consommations (Patients)",
            "🛡️ Contrôles Qualité (QC)",
            "⚙️ Calibrations",
            "📦 Ouvertures Boîtes",
            "✏️ Ajustements Manuels",
            "🗑️ Rebuts / Pertes",
            "🚚 Transferts Internes",
            "💰 Ventes / Transf. Externes",
            "↩️ Retours Sous-traitants (BR)",
            "↩️ Retours Fournisseurs (Avoirs)"
        ])

        self.combo_type.setItemData(0, None)
        self.combo_type.setItemData(1, "Purchase_Receive")
        self.combo_type.setItemData(2, "Patient_Test")
        self.combo_type.setItemData(3, "QC_Run")
        self.combo_type.setItemData(4, "Calibration")
        self.combo_type.setItemData(5, "Open_Pack")
        self.combo_type.setItemData(6, "Adjustment")
        self.combo_type.setItemData(7, "Waste")
        self.combo_type.setItemData(8, "Transfer")
        self.combo_type.setItemData(9, "External_Transfer")
        self.combo_type.setItemData(10, "Transfer_Return")
        self.combo_type.setItemData(11, "Return_To_Supplier")

        self.combo_type.setMinimumWidth(210)
        self.combo_type.setStyleSheet("QComboBox { padding: 4px; font-size: 13px; }")
        self.combo_type.currentIndexChanged.connect(self.reset_and_reload)

        # حقل البحث السيرفري
        self.search_input = BarcodeLineEdit()
        self.search_input.setPlaceholderText("🔍 Barcode, Produit, Lot, Utilisateur...")
        self.search_input.textChanged.connect(self.on_search_text_changed)

        btn_refresh = QPushButton()
        btn_refresh.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))
        btn_refresh.setFixedSize(32, 32)
        btn_refresh.setToolTip("Recharger")
        btn_refresh.clicked.connect(self.reset_and_reload)

        filter_layout.addWidget(QLabel("Du:"))
        filter_layout.addWidget(self.date_from)
        filter_layout.addWidget(QLabel("Au:"))
        filter_layout.addWidget(self.date_to)
        filter_layout.addWidget(self.combo_type)
        filter_layout.addWidget(self.search_input, stretch=1)
        filter_layout.addWidget(btn_refresh)

        layout.addLayout(filter_layout)

        # --- 2. الجدول الرئيسي ---
        self.table = QTableWidget()
        cols = [
            "Date", "Produit", "Code-Barres", "Lot", "Type",
            "Mvt", "Stock", "Emplacement", "Utilisateur", "Notes"
        ]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)

        f = self.table.font()
        f.setPointSize(9)
        self.table.setFont(f)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(8, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(9, QHeaderView.Stretch)

        self.table.verticalHeader().setDefaultSectionSize(28)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)

        self.table.doubleClicked.connect(self.show_full_details)
        layout.addWidget(self.table)

        # ربط حدث التمرير (Scroll) لجلب المزيد تلقائياً عند الوصول لأسفل الجدول
        self.table.verticalScrollBar().valueChanged.connect(self._on_scroll)

        # --- 3. شريط حالة التمرير والتحميل التدريجي (Scroll-based Status Bar) ---
        status_layout = QHBoxLayout()
        status_layout.setSpacing(8)

        self.lbl_status = QLabel("0/0")
        self.lbl_status.setStyleSheet("font-weight: bold; font-size: 12px; color: #2c3e50;")

        status_layout.addWidget(self.lbl_status, stretch=1)
        layout.addLayout(status_layout)

        # التحميل الأولي
        self.reset_and_reload()

    def on_search_text_changed(self):
        self.search_timer.start()


    def _on_scroll(self, value):
        scroll_bar = self.table.verticalScrollBar()
        # عند وصول شريط التمرير إلى القرب من النهاية السفلى (أقل من 20 بكسل من القاع)
        if scroll_bar.maximum() > 0 and value >= scroll_bar.maximum() - 20:
            self.load_next_batch()

    def reset_and_reload(self):
        self.current_offset = 0
        self.has_more_data = True
        self.table.setRowCount(0)
        self.total_records = 0
        self.load_next_batch()

    def load_data(self):
        """توافقية الدالة للنداءات الخارجية."""
        self.reset_and_reload()

    def filter_by_product(self, product_name):
        if product_name:
            self.search_input.setText(product_name)
            self.reset_and_reload()

    def get_active_filters(self):
        m_type = self.combo_type.currentData()
        txt = self.search_input.text().strip()
        search_text = txt if txt else None

        start_date = self.date_from.date().toString("yyyy-MM-dd")
        end_date = self.date_to.date().toString("yyyy-MM-dd")

        return {
            'movement_type': m_type,
            'search_text': search_text,
            'start_date': start_date,
            'end_date': end_date
        }

    def load_next_batch(self):
        if self.is_loading or not self.has_more_data:
            return

        self.is_loading = True
        self.lbl_status.setText("⏳ Chargement du lot suivant...")

        try:
            filters = self.get_active_filters()

            # جلب العدد الإجمالي فقط في الدفعة الأولى
            if self.current_offset == 0:
                self.total_records = self.manager.movement.get_movements_count(**filters)

            # جلب الدفعة التالية بناءً على offset و batch_size
            movements = self.manager.movement.get_movements_log(
                limit=self.batch_size,
                offset=self.current_offset,
                **filters
            )

            if not movements:
                self.has_more_data = False
            else:
                self._append_rows_to_table(movements)
                self.current_offset += len(movements)
                if len(movements) < self.batch_size:
                    self.has_more_data = False

            self.update_status_ui()
        except Exception as e:
            logging.error(f"Error fetching lazy movement batch: {e}")
            self.lbl_status.setText("⚠️ Erreur lors du chargement des données")
        finally:
            self.is_loading = False

    def update_status_ui(self):
        loaded_count = self.table.rowCount()
        self.lbl_status.setText(f"{loaded_count}/{self.total_records}")

    def _append_rows_to_table(self, data):
        self.table.setSortingEnabled(False)
        start_row = self.table.rowCount()

        type_map = {
            'Purchase_Receive': 'Réception (Achat)',
            'Patient_Test': 'Consommation',
            'QC_Run': 'QC',
            'Calibration': 'Calibration',
            'Open_Pack': 'Ouverture',
            'Adjustment': 'Ajustement',
            'Waste': 'Perte',
            'Transfer': 'Transfert',
            'External_Transfer': 'Vente/Externe',
            'Transfer_Return': 'Retour Sous-traitant',
            'Return_To_Supplier': 'Retour Fourn.'
        }

        for i, mov in enumerate(data):
            r = start_row + i
            self.table.insertRow(r)

            def item(text, align=Qt.AlignCenter, color=None, font=None):
                val = str(text) if text is not None else "-"
                it = QTableWidgetItem(val)
                it.setTextAlignment(align)
                if color:
                    it.setForeground(QBrush(QColor(color)))
                if font:
                    it.setFont(font)
                return it

            # 1. التاريخ
            self.table.setItem(r, 0, item(str(mov.get('Transaction_Date', ''))[:16]))
            self.table.item(r, 0).setData(Qt.UserRole, mov)

            # 2. المنتج
            self.table.setItem(r, 1, item(mov.get('Product_Name', '-'), font=QFont("Segoe UI", 9, QFont.Bold)))

            # 3. الباركود واللوت
            self.table.setItem(r, 2, item(mov.get('Batch_Barcode') or '-'))
            self.table.setItem(r, 3, item(mov.get('Lot_Number') or '-'))

            # 4. نوع الحركة
            raw_type = mov.get('Movement_Type', '')
            t_item = item(type_map.get(raw_type, raw_type))
            if raw_type == 'Purchase_Receive':
                t_item.setBackground(QBrush(QColor("#e8f5e9")))
            elif raw_type == 'Waste':
                t_item.setBackground(QBrush(QColor("#ffebee")))
            elif raw_type in ['Patient_Test', 'QC_Run']:
                t_item.setForeground(QBrush(QColor("#1976d2")))
            self.table.setItem(r, 4, t_item)

            # 5. الكمية
            qty = float(mov.get('Qty_Change', 0))
            self.table.setItem(r, 5, item(format_quantity(qty), Qt.AlignCenter, "#c0392b" if qty < 0 else "#27ae60"))

            # 6. رصيد الباركود (Batch Stock)
            batch_stock = mov.get('Batch_Historical_Stock')
            if batch_stock is None:
                batch_stock = mov.get('Historical_Stock')

            stock_txt = format_quantity(batch_stock) if batch_stock is not None else "?"
            s_item = item(stock_txt, font=QFont("Arial", 9, QFont.Bold))

            if batch_stock is not None and float(batch_stock) <= 0:
                s_item.setForeground(QBrush(QColor("#c0392b")))
            else:
                s_item.setForeground(QBrush(QColor("#2c3e50")))

            self.table.setItem(r, 6, s_item)

            # 7. باقي الأعمدة
            self.table.setItem(r, 7, item(mov.get('Location_Name', '---'), Qt.AlignCenter, "#2980b9"))
            self.table.setItem(r, 8, item(mov.get('Operator_Name') or "Système", Qt.AlignCenter, "#7f8c8d"))

            full_note = f"{mov.get('Reason_Name','') or ''} {mov.get('Notes','') or ''}".strip()
            self.table.setItem(r, 9, item(full_note, Qt.AlignLeft | Qt.AlignVCenter))

        self.table.setSortingEnabled(True)

    def show_full_details(self):
        row = self.table.currentRow()
        if row < 0:
            return
        data = self.table.item(row, 0).data(Qt.UserRole)
        if data:
            dlg = MovementDetailsDialog(data, self)
            dlg.exec()
