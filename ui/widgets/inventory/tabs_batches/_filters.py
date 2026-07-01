# ui/widgets/inventory/tabs_batches/_filters.py
"""
تحميل البيانات من قاعدة البيانات وتطبيق الفلاتر المحلية
"""

import logging
import time
from datetime import datetime, date

from ui.formatting import format_money


# ---------------------------------------------------------------------------
# تحميل البيانات
# ---------------------------------------------------------------------------

def load_data(self):
    """جلب كامل البيانات من قاعدة البيانات ثم تطبيق الفلاتر"""
    try:
        status_idx  = self.combo_status.currentIndex()
        search_text = self.search_input.text().strip()
        fetch_zero  = (status_idx == 5) or (len(search_text) > 0)

        # حفظ الصف المحدد حالياً للعودة إليه بعد التحديث
        selected_batch_id = None
        if self.table.currentRow() >= 0:
            item = self.table.item(self.table.currentRow(), 0)
            if item:
                data = item.data(0x0100)  # Qt.UserRole
                if data:
                    selected_batch_id = data.get('Batch_ID')

        self.all_data = self.manager.batches.get_all_batches_with_details(
            include_zero_stock=fetch_zero
        )
        apply_filters_local(self)
        self._last_load_monotonic = time.monotonic()

        # استعادة التحديد السابق
        if selected_batch_id:
            from PySide6.QtCore import Qt
            for r in range(self.table.rowCount()):
                item = self.table.item(r, 0)
                if item:
                    b_data = item.data(Qt.UserRole)
                    if b_data and b_data.get('Batch_ID') == selected_batch_id:
                        self.table.selectRow(r)
                        break

    except Exception as e:
        logging.error(f"Erreur load_data: {e}")


# ---------------------------------------------------------------------------
# الفلترة المحلية (في الذاكرة)
# ---------------------------------------------------------------------------

def apply_filters_local(self):
    """تطبيق كل الفلاتر على self.all_data وتحديث الجدول"""
    try:
        search_txt   = self.search_input.text().lower().strip()
        loc_id       = self.loc_filter.get_current_location_id()
        family_id    = self.combo_family.currentData()
        manuf_id     = self.combo_manuf.currentData()
        automate_id  = self.combo_automate.currentData()
        status_idx   = self.combo_status.currentIndex()

        use_exp_date  = self.chk_date_filter.isChecked()
        exp_from      = self.date_from.date().toPython()
        exp_to        = self.date_to.date().toPython()

        use_entry_date = self.chk_entry_filter.isChecked()
        ent_from       = self.date_in_from.date().toPython()
        ent_to         = self.date_in_to.date().toPython()
        current_date   = date.today()

        temp_filtered = []

        for row in self.all_data:
            qty = float(row.get('Quantity_Current', 0))

            # --- فلتر الحالة ---
            if status_idx in [0, 1, 2, 3, 4] and qty <= 0:
                continue
            elif status_idx == 5 and qty > 0:
                continue

            # --- البحث النصي ---
            if search_txt:
                bc_int = str(row.get('Internal_Barcode', '')).lower()
                bc_man = str(row.get('Barcode', '')).lower()
                full   = (
                    f"{row.get('Product_Name', '')} "
                    f"{row.get('Lot_Number', '')} "
                    f"{bc_int} {bc_man} "
                    f"{row.get('PO_ID', '')}"
                ).lower()
                if search_txt not in full:
                    continue

            # --- فلاتر القوائم ---
            if loc_id      and row.get('Location_ID')            != loc_id:      continue
            if family_id   and row.get('Family_ID')              != family_id:   continue
            if manuf_id    and row.get('Manuf_ID')               != manuf_id:    continue
            if automate_id and row.get('Preferred_Automate_ID')  != automate_id: continue

            # --- فلتر الحالة المتقدمة (Seuil / Périmés / Bientôt Exp.) ---
            min_threshold = float(row.get('Minimum_Stock_Level') or 5)
            alert_days    = int(row.get('Alert_Before_Expiry_Days') or 30)

            exp_date_obj = _parse_date(row.get('Expiry_Date'))

            if status_idx == 2 and qty > min_threshold:
                continue
            elif status_idx == 3 and (not exp_date_obj or exp_date_obj >= current_date):
                continue
            elif status_idx == 4:
                if not exp_date_obj:
                    continue
                days_left = (exp_date_obj - current_date).days
                if not (0 <= days_left <= alert_days):
                    continue

            # --- فلتر تاريخ الانتهاء ---
            if use_exp_date:
                if not exp_date_obj or not (exp_from <= exp_date_obj <= exp_to):
                    continue

            # --- فلتر تاريخ الدخول ---
            if use_entry_date:
                entry_val = row.get('Date_Received') or row.get('Created_At')
                e_date    = _parse_date(entry_val)
                if not e_date or not (ent_from <= e_date <= ent_to):
                    continue

            temp_filtered.append(row)

        self.filtered_data = temp_filtered

        # --- حساب المجموع الكلي ---
        _update_total_label(self)

        # --- إعادة التحميل ---
        self.table.setRowCount(0)
        self.loaded_count = 0

        if self.current_sort_col != -1:
            from ._table import apply_sorting
            apply_sorting(self)
        else:
            from ._table import load_more_data
            load_more_data(self)

    except Exception as e:
        logging.error(f"Erreur filters: {e}", exc_info=True)


# ---------------------------------------------------------------------------
# مساعدات داخلية
# ---------------------------------------------------------------------------

def _parse_date(val):
    """تحويل قيمة تاريخ متعددة الأنواع إلى date أو None"""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    if isinstance(val, str):
        try:
            return datetime.strptime(val[:10], "%Y-%m-%d").date()
        except Exception:
            return None
    return None


def _update_total_label(self):
    """تحديث ملصق القيمة الإجمالية أو إخفاؤه حسب دور المستخدم"""
    try:
        role = self.window().current_user.get('Role', 'Technician')
    except Exception:
        role = 'Technician'

    if role == 'Technician':
        self.lbl_total_value.hide()
        return

    total = 0.0
    for b in self.filtered_data:
        try:
            q = float(b.get('Quantity_Current', 0))
            if q > 0:
                p = float(b.get('Unit_Price_Received', 0))
                d = float(b.get('Discount_Percent', 0)) / 100.0
                t = float(b.get('Tax_Rate_Percent', 0)) / 100.0
                total += q * p * (1 - d) * (1 + t)
        except Exception:
            pass

    self.lbl_total_value.setText(f"💰 Total Filtré : {format_money(total)} DA")
    self.lbl_total_value.show()


# ---------------------------------------------------------------------------
# أدوات الفلترة (مرتبطة بـ checkboxes وزر Reset)
# ---------------------------------------------------------------------------

def toggle_date_filter(self, state):
    enabled = (state == 2)
    self.date_from.setEnabled(enabled)
    self.date_to.setEnabled(enabled)
    apply_filters_local(self)


def toggle_entry_filter(self, state):
    enabled = (state == 2)
    self.date_in_from.setEnabled(enabled)
    self.date_in_to.setEnabled(enabled)
    apply_filters_local(self)


def reset_filters(self):
    self.search_input.clear()
    self.loc_filter.setCurrentIndex(0)
    self.combo_family.setCurrentIndex(0)
    self.combo_manuf.setCurrentIndex(0)
    self.combo_automate.setCurrentIndex(0)
    self.combo_status.setCurrentIndex(1)
    self.chk_date_filter.setChecked(False)
    toggle_date_filter(self, 0)
    self.chk_entry_filter.setChecked(False)
    toggle_entry_filter(self, 0)
    load_data(self)
