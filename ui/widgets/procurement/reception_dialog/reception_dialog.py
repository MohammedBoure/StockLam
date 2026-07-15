"""
reception_dialog.py
-------------------
الكلاس الرئيسي لنافذة الاستقبال.
يرث من:
  - BaseDialog          (PySide6 base)
  - ReceptionDialogUIMixin   (بناء الواجهة)
  - ReceptionDialogLogicMixin (المنطق الوظيفي)
"""
import logging

from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QGuiApplication

from ui.widgets.master_data.dialogs import BaseDialog
from .reception_dialog_ui    import ReceptionDialogUIMixin
from .reception_dialog_logic import ReceptionDialogLogicMixin


class ReceptionDialog(ReceptionDialogUIMixin, ReceptionDialogLogicMixin, BaseDialog):
    def __init__(
        self, po_data, locations_list, location_manager, manager,
        printer_manager, parent=None, edit_mode=False,
        reception_data=None, target_batch_id=None
    ):
        self.po_data          = po_data
        self.locations        = locations_list
        self.location_manager = location_manager
        self.manager          = manager
        self.printer          = printer_manager
        self.edit_mode        = edit_mode
        self.reception_data   = reception_data
        self.target_batch_id  = target_batch_id
        self.current_editing_row = -1

        # متغيرات الحساب
        self.total_ht_val     = 0.0
        self.total_tva_val    = 0.0
        self.total_remise_val = 0.0
        self.total_ttc_val    = 0.0

        # تعريف br_id فوراً
        self.br_id = None
        if self.edit_mode and self.reception_data:
            self.br_id = self.reception_data.get('Header', {}).get('BR_ID')

        title = (
            f"Réception #{po_data.get('PO_ID', 'N/A')} "
            f"- {po_data.get('Supplier_Name', 'N/A')}"
        )
        super().__init__(title, parent)

        if hasattr(self, 'buttons'):
            self.buttons.hide()

        self.adjust_screen_size()

        # 1. إنشاء العناصر
        self.create_widgets()
        # 2. ربط الأحداث
        self.setup_connections()
        # 3. ترتيب الواجهة
        self.init_ui()
        # 4. تعطيل الحقول في البداية
        self.toggle_inputs_state(False)

        if self.edit_mode and self.reception_data:
            self.load_reception_data()
            if self.br_id:
                self.toggle_inputs_state(True)
            if self.target_batch_id:
                QTimer.singleShot(100, self.highlight_target_row)

        self.showMaximized()

    # ------------------------------------------------------------------ #
    #  حجم النافذة                                                         #
    # ------------------------------------------------------------------ #
    def adjust_screen_size(self):
        self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint | Qt.WindowMinimizeButtonHint)
        screen_geo = QGuiApplication.primaryScreen().availableGeometry()
        self.resize(screen_geo.width(), screen_geo.height())
        self.move(screen_geo.topLeft())

    # ------------------------------------------------------------------ #
    #  إغلاق النافذة                                                       #
    # ------------------------------------------------------------------ #
    def accept(self):
        """الحفظ تلقائي — نغلق النافذة فقط."""
        super().accept()

    def reject(self):
        """عند Cancel / ESC: تحقق من بيانات غير محفوظة."""
        if self.is_input_dirty():
            reply = QMessageBox.question(
                self, "Quitter",
                "Il y a des informations saisies non ajoutées à la liste. Voulez-vous vraiment quitter ?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                return
        super().reject()

    def closeEvent(self, event):
        """تأكيد الخروج عند الضغط على X."""
        if self.is_input_dirty():
            reply = QMessageBox.question(
                self, "Données non ajoutées",
                "Vous avez saisi des informations sans les ajouter.\nVoulez-vous vraiment quitter ?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
