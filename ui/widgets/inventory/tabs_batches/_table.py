# ui/widgets/inventory/tabs_batches/_table.py
"""
عرض بيانات الجدول: التحميل الكسول، الفرز، تلوين الصفوف
"""

import logging
import json

from PySide6.QtWidgets import QTableWidgetItem, QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont

from ui.formatting import format_money, format_quantity


# ---------------------------------------------------------------------------
# أيقونات مخصصة
# ---------------------------------------------------------------------------
from ui.icons import get_reclamation_icon

# ---------------------------------------------------------------------------
# مساعد بناء خلية والتحقق من الصلاحيات
# ---------------------------------------------------------------------------

def _make_item(val, align=Qt.AlignCenter, color=None, font=None, bg_color=None):
    from PySide6.QtGui import QBrush
    s_val = str(val) if val is not None else ""
    it = QTableWidgetItem(s_val)
    it.setTextAlignment(align)
    if color:
        it.setForeground(color)
    if bg_color:
        it.setBackground(QBrush(bg_color))
    if font:
        it.setFont(font)
    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
    return it


def _can_view_financials(widget):
    """دالة تتحقق مما إذا كان المستخدم يملك صلاحية رؤية القيم المالية بشكل آمن"""
    try:
        # 1. محاولة جلب المستخدم من النافذة الرئيسية مباشرة
        main_window = widget.window()
        user = getattr(main_window, 'current_user', None)
        
        # 2. إذا لم يعثر عليه (الواجهة قيد البناء ولم تدمج بعد بالنافذة)
        # نقوم بالبحث صعوداً في شجرة المكونات الآباء
        if user is None:
            parent = widget.parent()
            while parent:
                if hasattr(parent, 'current_user'):
                    user = parent.current_user
                    break
                parent = parent.parent()
        
        # 3. إذا لم نعثر على المستخدم في أي مكان
        if not user:
            return False
            
        perms = user.get('Permissions', {})
        
        # معالجة الصلاحيات
        if isinstance(perms, str):
            try:
                perms = json.loads(perms)
            except json.JSONDecodeError:
                perms = {}

        if isinstance(perms, list):
            return "tab_inv_financials" in perms
        elif isinstance(perms, dict):
            return perms.get("tab_inv_financials", False)
            
        return False
    except Exception as e:
        logging.error(f"Error checking financial permissions: {e}")
        return False


# ---------------------------------------------------------------------------
# التحميل الكسول (Lazy Loading / Infinite Scroll)
# ---------------------------------------------------------------------------

def on_scroll_value_changed(self, value):
    """تحميل المزيد عند الاقتراب من قاع الجدول"""
    bar = self.table.verticalScrollBar()
    if value >= bar.maximum() - 20:
        load_more_data(self)


def load_more_data(self):
    """إضافة الدفعة التالية من الصفوف للجدول"""
    total = len(self.filtered_data)
    if self.loaded_count >= total:
        return

    start = self.loaded_count
    end   = min(start + self.batch_size, total)
    _append_rows(self, self.filtered_data[start:end])
    self.loaded_count = end
    self.lbl_count_info.setText(f"Affichage: {self.loaded_count} / {total}")


def _append_rows(self, chunk):
    """إضافة chunk من الصفوف إلى نهاية الجدول"""
    hide_fin = not _can_view_financials(self)
    start_row = self.table.rowCount()

    for i, b in enumerate(chunk):
        r = start_row + i
        self.table.insertRow(r)
        _fill_row(self.table, r, b, hide_fin)

    self.table.setColumnHidden(11, hide_fin)
    self.table.setColumnHidden(12, hide_fin)
    self.table.setColumnHidden(13, hide_fin)


# ---------------------------------------------------------------------------
# عرض صفحة كاملة (مع حساب المجموع)
# ---------------------------------------------------------------------------

def populate_table(self, data):
    """عرض شريحة محددة مع حساب المجموع الكلي من filtered_data"""
    self.table.setSortingEnabled(False)
    self.table.setRowCount(0)

    hide_fin = not _can_view_financials(self)

    # حساب المجموع من كامل القائمة المفلترة
    total_value = 0.0
    if not hide_fin:
        for b in self.filtered_data:
            try:
                qty = float(b.get('Quantity_Current', 0))
                if qty > 0:
                    p = float(b.get('Unit_Price_Received', 0))
                    d = float(b.get('Discount_Percent', 0)) / 100.0
                    t = float(b.get('Tax_Rate_Percent', 0)) / 100.0
                    total_value += qty * p * (1 - d) * (1 + t)
            except Exception:
                pass

    for r, b in enumerate(data):
        self.table.insertRow(r)
        _fill_row(self.table, r, b, hide_fin)

    self.table.setSortingEnabled(False)
    self.table.setColumnHidden(11, hide_fin)
    self.table.setColumnHidden(12, hide_fin)
    self.table.setColumnHidden(13, hide_fin)

    if hide_fin:
        self.lbl_total_value.hide()
    else:
        self.lbl_total_value.show()
        self.lbl_total_value.setText(f"💰 Total Filtré : {format_money(total_value)} DA")


def _fill_row(table, r, b, hide_fin):
    """ملء صف واحد بالبيانات"""
    qty = float(b.get('Quantity_Current', 0))
    raw_note = b.get('Reception_Note')
    reclamation = str(raw_note).strip() if raw_note is not None else ""
    if reclamation.lower() == "none":
        reclamation = ""
        
    bg_color = QColor("#ffe4cd") if reclamation else None

    prod_name = b.get('Product_Name', '---')

    prod_item = _make_item(
        prod_name,
        Qt.AlignLeft | Qt.AlignVCenter,
        bg_color=bg_color
    )
    prod_item.setData(Qt.UserRole, b)
    table.setItem(r, 0, prod_item)

    table.setItem(r, 1,  _make_item(b.get('Family_Name', '---'), bg_color=bg_color))
    table.setItem(r, 2,  _make_item(b.get('Manuf_Name', '---'), bg_color=bg_color))
    table.setItem(r, 3,  _make_item(b.get('Automate_Name', '---'), bg_color=bg_color))
    table.setItem(r, 4,  _make_item(b.get('Supplier_Name', '---'), bg_color=bg_color))
    table.setItem(r, 5,  _make_item(
        format_quantity(qty),
        color=QColor("#27ae60"),
        font=QFont("", -1, QFont.Bold),
        bg_color=bg_color
    ))
    table.setItem(r, 6,  _make_item(
        str(b.get('Date_Received') or b.get('Created_At', ''))[:10],
        bg_color=bg_color
    ))
    table.setItem(r, 7,  _make_item(b.get('Lot_Number', '---'), bg_color=bg_color))
    table.setItem(r, 8,  _make_item(str(b.get('Expiry_Date', ''))[:10], bg_color=bg_color))
    table.setItem(r, 9,  _make_item(format_quantity(b.get('Quantity_Initial', 0)), bg_color=bg_color))
    table.setItem(r, 10, _make_item(
        b.get('Internal_Barcode') or b.get('Barcode'),
        bg_color=bg_color
    ))

    # تطبيق الفلتر المالي على الصف
    if not hide_fin:
        p  = float(b.get('Unit_Price_Received', 0))
        d  = float(b.get('Discount_Percent', 0)) / 100.0
        t  = float(b.get('Tax_Rate_Percent', 0)) / 100.0
        p_ttc = p * (1 - d) * (1 + t)
        lv = qty * p_ttc
        table.setItem(r, 11, _make_item(format_money(p), bg_color=bg_color))
        table.setItem(r, 12, _make_item(format_money(p_ttc), bg_color=bg_color))
        table.setItem(r, 13, _make_item(format_money(lv), bg_color=bg_color))
    else:
        table.setItem(r, 11, _make_item("", bg_color=bg_color))
        table.setItem(r, 12, _make_item("", bg_color=bg_color))
        table.setItem(r, 13, _make_item("", bg_color=bg_color))

    table.setItem(r, 14, _make_item(b.get('PO_ID'), bg_color=bg_color))
    table.setItem(r, 15, _make_item(b.get('Location_Name'), bg_color=bg_color))
    table.setItem(r, 16, _make_item(reclamation, bg_color=bg_color))
    
    # تعيين الهيدر العمودي (رقم الصف أو أيقونة شكوى)
    v_header_item = QTableWidgetItem(str(r+1))
    if reclamation:
        v_header_item.setIcon(get_reclamation_icon())
        
    # Ensure text is aligned to the left while icon goes to the right (RTL effect)
    v_header_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    table.setVerticalHeaderItem(r, v_header_item)


# ---------------------------------------------------------------------------
# الفرز
# ---------------------------------------------------------------------------

COL_MAP = {
    0: 'Product_Name',      1: 'Family_Name',
    2: 'Manuf_Name',        3: 'Automate_Name',
    4: 'Supplier_Name',     5: 'Quantity_Current',
    6: 'Date_Received',     7: 'Lot_Number',
    8: 'Expiry_Date',       9: 'Quantity_Initial',
    10: 'Internal_Barcode', 11: 'Unit_Price_Received',
    12: 'Unit_Price_Received_TTC', 13: 'Total_Value',
    14: 'PO_ID',            15: 'Location_Name',
    16: 'Reception_Note'
}

NUMERIC_COLS = {5, 9, 11}
DATE_COLS    = {6, 8}


def _sort_key(col_index, item):
    if col_index == 13:
        try:
            return (float(item.get('Quantity_Current', 0))
                    * float(item.get('Unit_Price_Received', 0)))
        except Exception:
            return 0.0
    elif col_index == 12:
        try:
            qty = float(item.get('Quantity_Current', 0))
            p  = float(item.get('Unit_Price_Received', 0))
            d  = float(item.get('Discount_Percent', 0)) / 100.0
            t  = float(item.get('Tax_Rate_Percent', 0)) / 100.0
            return p * (1 - d) * (1 + t)
        except Exception:
            return 0.0
    elif col_index in NUMERIC_COLS:
        try:
            return float(item.get(COL_MAP.get(col_index), 0))
        except Exception:
            return 0.0

    key_name = COL_MAP.get(col_index)
    val = item.get(key_name)

    if val is None:
        return -1 if col_index in NUMERIC_COLS else ""

    if col_index in NUMERIC_COLS:
        try:
            return float(val)
        except Exception:
            return 0.0
    elif col_index in DATE_COLS:
        return str(val)[:10]
    else:
        return str(val).lower()


def on_header_clicked(self, col_index):
    """عكس الاتجاه أو تعيين عمود جديد ثم تطبيق الفرز"""
    if self.current_sort_col == col_index:
        self.current_sort_asc = not self.current_sort_asc
    else:
        self.current_sort_col = col_index
        self.current_sort_asc = True
    apply_sorting(self)


def apply_sorting(self):
    """فرز filtered_data كاملاً ثم إعادة العرض من الصفر"""
    if self.current_sort_col == -1:
        return

    QApplication.setOverrideCursor(Qt.WaitCursor)
    QApplication.processEvents()

    try:
        col = self.current_sort_col
        asc = self.current_sort_asc

        header = self.table.horizontalHeader()
        header.setSortIndicatorShown(True)
        header.setSortIndicator(
            col,
            Qt.AscendingOrder if asc else Qt.DescendingOrder
        )

        key_name = COL_MAP.get(col)
        if not key_name and col != 12:
            return

        self.filtered_data.sort(
            key=lambda item: _sort_key(col, item),
            reverse=not asc
        )

        # إعادة العرض من الصفر (lazy loading)
        self.table.setRowCount(0)
        self.loaded_count = 0
        load_more_data(self)

    except Exception as e:
        logging.error(f"Sorting Error: {e}")
    finally:
        QApplication.restoreOverrideCursor()
