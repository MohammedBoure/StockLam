# ui/widgets/inventory/inventory_view.py

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QTabWidget)
from .tabs_batches import BatchesTab
from ..history import MovementHistoryTab
from .tabs_dispatch import DispatchTab
import logging

class InventoryTab(QWidget):
    def __init__(self, data_manager):
        super().__init__()
        self.data_manager = data_manager
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        
        # تهيئة الواجهتين الخاصتين بالمخزون فقط
        self.batches_tab = BatchesTab(self.data_manager)
        self.dispatch_tab = DispatchTab(self.data_manager)
        
        # ❌ حذفنا self.history_tab من هنا
        
        # ربط الإشارات الضرورية
        self.dispatch_tab.data_changed.connect(self.batches_tab.load_data)
        self.batches_tab.data_changed.connect(self.dispatch_tab.load_inventory_data)
        
        layout.addWidget(self.tabs)

    def apply_role_permissions(self, role):
        """
        التحكم في ظهور الأزرار والعناصر الداخلية داخل التبويبات بناءً على الدور.
        ملاحظة: إدارة التبويبات نفسها (إظهار/إخفاء السجل) تمت إزالتها من هنا ونقلها إلى main_window.py
        """
        is_technician = (role == 'Technician')
        is_consumer = (role == 'Manager') # المستهلك
        
        # وضع القراءة فقط للمستهلك (إخفاء أزرار الإضافة في BatchesTab)
        if is_consumer:
            if hasattr(self.batches_tab, 'btn_add_batch'):
                self.batches_tab.btn_add_batch.setVisible(False)
            if hasattr(self.batches_tab, 'btn_import'):
                self.batches_tab.btn_import.setVisible(False)
        
        # التقني يرى الأزرار بشكل طبيعي
        elif is_technician:
            if hasattr(self.batches_tab, 'btn_add_batch'):
                self.batches_tab.btn_add_batch.setVisible(True)