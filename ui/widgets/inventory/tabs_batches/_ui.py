# ui/widgets/inventory/tabs_batches/_ui.py
"""
بناء واجهة المستخدم: فلاتر، الجدول، شريط الأدوات السفلي
"""

from PySide6.QtWidgets import (
    QVBoxLayout, QTableWidget, QHeaderView,
    QFrame, QLabel, QLineEdit, QPushButton, QHBoxLayout,
    QGroupBox, QComboBox, QDateEdit, QCheckBox, QAbstractItemView
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QFont

from ..location_tree_combo import LocationTreeComboBox


def build_ui(self):
    """تهيئة كامل الواجهة وربطها بـ self"""
    layout = QVBoxLayout(self)
    layout.setSpacing(5)
    layout.setContentsMargins(5, 5, 5, 5)

    layout.addWidget(_build_filter_group(self))
    layout.addWidget(_build_table(self))
    layout.addLayout(_build_bottom_bar(self))

    self.table.doubleClicked.connect(self.show_batch_details)


# ---------------------------------------------------------------------------
# منطقة الفلاتر
# ---------------------------------------------------------------------------

def _build_filter_group(self):
    filter_group = QGroupBox("🔍 Recherche & Filtres Avancés")
    filter_group.setStyleSheet("""
        QGroupBox { font-weight: bold; color: #2c3e50; border: 1px solid #bdc3c7;
                    border-radius: 6px; margin-top: 6px; }
        QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 3px; }
    """)

    main_filter_layout = QHBoxLayout(filter_group)
    main_filter_layout.setContentsMargins(10, 15, 10, 10)

    left_layout = _build_left_filters(self)
    main_filter_layout.addLayout(left_layout, 2)

    line = QFrame()
    line.setFrameShape(QFrame.VLine)
    line.setFrameShadow(QFrame.Sunken)
    main_filter_layout.addWidget(line)

    right_layout = _build_right_filters(self)
    main_filter_layout.addLayout(right_layout, 1)

    return filter_group


def _build_left_filters(self):
    left_layout = QVBoxLayout()
    left_layout.setSpacing(8)

    # الصف 1: بحث نصي + موقع
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

    # الصف 2: القوائم المنسدلة
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

    return left_layout


def _build_right_filters(self):
    right_layout = QVBoxLayout()
    right_layout.setSpacing(5)

    # فلتر تاريخ الانتهاء
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

    # فلتر تاريخ الدخول
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

    # أزرار الإجراءات
    reset_layout = QHBoxLayout()
    reset_layout.addStretch()

    btn_refresh = QPushButton("Actualiser")
    btn_refresh.setFixedWidth(100)
    btn_refresh.setStyleSheet(
        "background-color: #2980b9; color: white; border-radius: 3px; padding: 2px;"
    )
    btn_refresh.clicked.connect(self.load_data)

    btn_reset = QPushButton("Réinitialiser")
    btn_reset.setFixedWidth(100)
    btn_reset.setStyleSheet(
        "background-color: #95a5a6; color: white; border-radius: 3px; padding: 2px;"
    )
    btn_reset.clicked.connect(self.reset_filters)

    reset_layout.addWidget(btn_refresh)
    reset_layout.addWidget(btn_reset)
    right_layout.addLayout(reset_layout)

    return right_layout


# ---------------------------------------------------------------------------
# الجدول
# ---------------------------------------------------------------------------

def _build_table(self):
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
    for c in range(len(cols)):
        header.setSectionResizeMode(c, QHeaderView.ResizeToContents)

    self.table.setWordWrap(True)
    self.table.setSortingEnabled(False)
    self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
    self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
    self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    self.table.setAlternatingRowColors(True)
    self.table.setStyleSheet(
        "QTableWidget { gridline-color: #ecf0f1; font-size: 12px; }"
    )
    self.table.setContextMenuPolicy(Qt.CustomContextMenu)
    self.table.customContextMenuRequested.connect(self.show_context_menu)

    header.setSectionsClickable(True)
    header.setSortIndicatorShown(False)
    header.sectionClicked.connect(self.on_header_clicked)

    self.table.verticalScrollBar().valueChanged.connect(self.on_scroll_value_changed)

    return self.table


# ---------------------------------------------------------------------------
# الشريط السفلي
# ---------------------------------------------------------------------------

def _build_bottom_bar(self):
    bottom_bar = QHBoxLayout()
    bottom_bar.setContentsMargins(5, 5, 5, 5)

    self.lbl_total_value = QLabel("Valeur Totale : 0.00 DA")
    self.lbl_total_value.setFont(QFont("Arial", 11, QFont.Bold))
    self.lbl_total_value.setStyleSheet("""
        QLabel {
            color: #2c3e50; border: 1px solid #95a5a6; border-radius: 4px;
            padding: 6px; background-color: #ecf0f1;
        }
    """)
    bottom_bar.addWidget(self.lbl_total_value)

    self.lbl_count_info = QLabel("0 éléments")
    self.lbl_count_info.setStyleSheet(
        "color: #7f8c8d; font-weight: bold; margin-left: 10px;"
    )
    bottom_bar.addWidget(self.lbl_count_info)
    bottom_bar.addStretch()

    btn_style = (
        "QPushButton { font-weight: bold; border-radius: 4px; "
        "padding: 6px 12px; font-size: 12px; }"
    )

    def _btn(label, color, slot):
        b = QPushButton(label)
        b.setStyleSheet(btn_style + f"background-color: {color}; color: white;")
        b.clicked.connect(slot)
        return b

    bottom_bar.addWidget(_btn("⚡ Sortie",      "#27ae60", self.direct_use_process))
    bottom_bar.addWidget(_btn("✏️ Ajustement",  "#f39c12", self.adjust_stock))
    bottom_bar.addWidget(_btn("🗑️ Rebut",       "#c0392b", self.waste_batch))
    bottom_bar.addWidget(_btn("🖨️ Étiquette",   "#34495e", self.print_batch_label))

    line_sep = QFrame()
    line_sep.setFrameShape(QFrame.VLine)
    line_sep.setFrameShadow(QFrame.Sunken)
    bottom_bar.addWidget(line_sep)

    bottom_bar.addWidget(_btn("📗 Excel", "#217346", self.export_to_excel))
    bottom_bar.addWidget(_btn("📕 PDF",   "#e74c3c", self.export_to_pdf))

    return bottom_bar
