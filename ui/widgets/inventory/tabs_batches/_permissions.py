# ui/widgets/inventory/tabs_batches/_permissions.py
"""
إدارة الصلاحيات: إخفاء/إظهار العناصر حسب دور المستخدم
"""

import logging
from ._table import _can_view_financials

def apply_role_permissions(self, role=None):
    """إخفاء البيانات المالية تماماً لمن لا يملك الصلاحية"""
    
    # استخدام الدالة الديناميكية للتحقق من صلاحية "tab_inv_financials"
    hide_fin = not _can_view_financials(self)

    self.table.setColumnHidden(6, hide_fin)
    self.table.setColumnHidden(7, hide_fin)
    self.table.setColumnHidden(8, hide_fin)

    if hasattr(self, 'lbl_total_value'):
        if hide_fin:
            self.lbl_total_value.hide()
            self.lbl_total_value.setFixedWidth(0)
        else:
            self.lbl_total_value.show()
            self.lbl_total_value.setFixedWidth(250)

    logging.info(
        f"BatchesTab: Visibility set dynamically based on permissions. "
        f"Financials Hidden: {hide_fin}"
    )