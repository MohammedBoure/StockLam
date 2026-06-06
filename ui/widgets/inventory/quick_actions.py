# ui/widgets/inventory/quick_actions.py

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QDialogButtonBox, 
                               QSpinBox, QLabel, QMessageBox)
from ui.formatting import quantity_to_int
from .location_tree_combo import LocationTreeComboBox # تأكد من المسار الصحيح

class QuickTransferDialog(QDialog):
    """
    نافذة صغيرة للتحويل السريع (Transfert)
    تطلب: الوجهة + الكمية
    """
    def __init__(self, batch_data, location_manager, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🚚 Transfert Rapide")
        self.setModal(True)
        self.resize(350, 200)

        layout = QVBoxLayout(self)

        # 1. عرض معلومات المنتج واللوت
        info_style = "font-size: 12px; color: #2c3e50; margin-bottom: 10px;"
        info_text = (f"<b>Produit :</b> {batch_data.get('Product_Name')}<br>"
                     f"<b>Lot :</b> {batch_data.get('Lot_Number')}<br>"
                     f"<b>Lieu Actuel :</b> {batch_data.get('Location_Name')}")
        layout.addWidget(QLabel(info_text))

        # 2. نموذج الإدخال
        form = QFormLayout()

        # اختيار الوجهة
        self.dest_combo = LocationTreeComboBox(location_manager)
        self.dest_combo.setPlaceholderText("📍 Sélectionner la destination...")
        form.addRow("Vers (Destination):", self.dest_combo)

        # اختيار الكمية
        self.qty_spin = QSpinBox()
        max_qty = quantity_to_int(batch_data.get('Quantity_Current', 0))
        self.qty_spin.setRange(1, max_qty) # لا يمكن تجاوز الكمية المتوفرة
        self.qty_spin.setValue(1)
        self.qty_spin.setSuffix("")
        self.qty_spin.setStyleSheet("font-weight: bold; font-size: 14px;")
        form.addRow("Quantité:", self.qty_spin)

        layout.addLayout(form)

        # 3. الأزرار (OK / Cancel)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_data(self):
        """إرجاع البيانات المدخلة"""
        return {
            'dest_id': self.dest_combo.get_current_location_id(),
            'qty': self.qty_spin.value()
        }

class QuickConsumeDialog(QDialog):
    """
    نافذة صغيرة للاستهلاك السريع (Consommation)
    تطلب: الكمية فقط
    """
    def __init__(self, batch_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📉 Consommation Rapide")
        self.setModal(True)
        self.resize(300, 150)

        layout = QVBoxLayout(self)

        # 1. معلومات
        info_text = (f"<b>Sortie de Stock (Consommation)</b><br>"
                     f"{batch_data.get('Product_Name')} (Lot: {batch_data.get('Lot_Number')})")
        layout.addWidget(QLabel(info_text))

        # 2. الكمية
        form = QFormLayout()
        self.qty_spin = QSpinBox()
        max_qty = quantity_to_int(batch_data.get('Quantity_Current', 0))
        self.qty_spin.setRange(1, max_qty)
        self.qty_spin.setValue(1)
        self.qty_spin.setSuffix("")
        self.qty_spin.setStyleSheet("font-weight: bold; font-size: 14px; color: #c0392b;")
        form.addRow("Quantité à sortir:", self.qty_spin)
        layout.addLayout(form)

        # 3. الأزرار
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_qty(self):
        return self.qty_spin.value()
