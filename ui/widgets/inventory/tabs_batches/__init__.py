# ui/widgets/inventory/tabs_batches/__init__.py
"""
حزمة tabs_batches
-----------------
نقطة الدخول الوحيدة للاستخدام الخارجي:

    from ui.widgets.inventory.tabs_batches import BatchesTab

البنية الداخلية:
    _ui.py           ← بناء الواجهة (فلاتر + جدول + شريط سفلي)
    _filters.py      ← تحميل البيانات والفلترة المحلية
    _table.py        ← عرض الجدول، التحميل الكسول، الفرز
    _actions.py      ← إجراءات المستخدم (استهلاك، تحويل، FEFO ...)
    _export.py       ← طباعة، Excel، PDF
    _combos.py       ← تعبئة القوائم المنسدلة
    _context_menu.py ← قائمة السياق (كليك يمين)
    _permissions.py  ← إدارة الصلاحيات حسب الدور
"""

import logging
import time

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Signal

# استيراد كل الوحدات الداخلية
from ._ui           import build_ui
from ._filters      import (
    load_data, apply_filters_local,
    toggle_date_filter, toggle_entry_filter, reset_filters,
)
from ._table        import (
    on_scroll_value_changed, load_more_data,
    on_header_clicked, apply_sorting, populate_table,
)
from ._actions      import (
    get_current_user_id, check_fefo_compliance,
    direct_use_process, adjust_stock, waste_batch,
    show_batch_details, open_quick_transfer, open_quick_consume,
    go_to_history, open_history_via_barcode, go_to_reception,
    handle_barcode_scan,
)
from ._export       import (
    print_batch_label, export_to_excel, export_to_pdf, get_table_data,
)
from ._combos       import populate_families, populate_manufacturers, populate_automates
from ._context_menu import show_context_menu
from ._permissions  import apply_role_permissions


class BatchesTab(QWidget):
    """تبويب إدارة اللوطات (Batches) في مخزن المستلزمات الطبية"""

    data_changed           = Signal()
    request_open_reception = Signal(int)
    request_product_history = Signal(str)

    def __init__(self, manager):
        super().__init__()
        self.manager = manager

        # بيانات
        self.all_data      = []
        self.filtered_data = []

        # التحميل الكسول
        self.loaded_count = 0
        self.batch_size   = 50

        # الفرز
        self.current_sort_col = -1
        self.current_sort_asc = True
        self._last_load_monotonic = 0.0
        self._auto_reload_interval_seconds = 15.0

        self.init_ui()

    # ------------------------------------------------------------------
    # تهيئة الواجهة
    # ------------------------------------------------------------------

    def init_ui(self):
        build_ui(self)

    def showEvent(self, event):
        super().showEvent(event)
        try:
            main_win = self.window()
            if hasattr(main_win, 'current_user'):
                role = main_win.current_user.get('Role', 'Technician')
                self.apply_role_permissions(role)
        except Exception as e:
            logging.error(f"Error applying permissions in showEvent: {e}")
        now = time.monotonic()
        if not self.all_data or (now - self._last_load_monotonic) >= self._auto_reload_interval_seconds:
            self.load_data()

    # ------------------------------------------------------------------
    # ربط الدوال من الوحدات الخارجية بالكلاس
    # (كل دالة تستقبل self ضمنياً بفضل هذا الربط)
    # ------------------------------------------------------------------

    # الفلاتر والتحميل
    load_data            = load_data
    apply_filters_local  = apply_filters_local
    toggle_date_filter   = toggle_date_filter
    toggle_entry_filter  = toggle_entry_filter
    reset_filters        = reset_filters

    # الجدول والفرز
    on_scroll_value_changed = on_scroll_value_changed
    load_more_data          = load_more_data
    on_header_clicked       = on_header_clicked
    apply_sorting           = apply_sorting
    populate_table          = populate_table

    # الإجراءات
    get_current_user_id     = get_current_user_id
    check_fefo_compliance   = check_fefo_compliance
    direct_use_process      = direct_use_process
    adjust_stock            = adjust_stock
    waste_batch             = waste_batch
    show_batch_details      = show_batch_details
    open_quick_transfer     = open_quick_transfer
    open_quick_consume      = open_quick_consume
    go_to_history           = go_to_history
    open_history_via_barcode = open_history_via_barcode
    go_to_reception         = go_to_reception
    handle_barcode_scan     = handle_barcode_scan

    # التصدير
    print_batch_label = print_batch_label
    export_to_excel   = export_to_excel
    export_to_pdf     = export_to_pdf
    get_table_data    = get_table_data

    # القوائم المنسدلة
    populate_families      = populate_families
    populate_manufacturers = populate_manufacturers
    populate_automates     = populate_automates

    # قائمة السياق
    show_context_menu = show_context_menu

    # الصلاحيات
    apply_role_permissions = apply_role_permissions
