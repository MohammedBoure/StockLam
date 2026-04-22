# ui/widgets/inventory/tabs_batches/_context_menu.py
"""
قائمة السياق (Right-Click) مع قواعد الصلاحيات
"""

from PySide6.QtWidgets import QMenu
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction


def show_context_menu(self, pos):
    index = self.table.indexAt(pos)
    if not index.isValid():
        return

    item = self.table.item(index.row(), 0)
    batch_data = item.data(Qt.UserRole) if item else None
    if not batch_data:
        return

    from ._actions import get_current_role
    role = get_current_role(self)

    menu = QMenu(self)

    # --- متاح للجميع ---
    _add_action(menu, "📉 Consommation Rapide",
                lambda: self.open_quick_consume(batch_data))
    _add_action(menu, "🚚 Transfert vers...",
                lambda: self.open_quick_transfer(batch_data))
    menu.addSeparator()

    # --- للـ Admin فقط: سجل الباركود ---
    if role == 'Admin':
        search_term = (
            batch_data.get('Internal_Barcode')
            or batch_data.get('Barcode')
            or batch_data.get('Product_Name')
        )
        _add_action(menu, "📜 Voir Historique (Code-Barres)",
                    lambda: self.go_to_history(search_term))

    # --- تفاصيل اللوط (للجميع) ---
    _add_action(menu, "🔍 Détails du lot", self.show_batch_details)

    # --- وصل الاستلام (ليس للتقني) ---
    if batch_data.get('BR_ID') and role != 'Technician':
        _add_action(
            menu, "📄 Voir Bon de Réception",
            lambda: self.go_to_reception(
                batch_data['BR_ID'], batch_data.get('Batch_ID')
            )
        )

    menu.addSeparator()

    # --- طباعة (للجميع) ---
    _add_action(menu, "🖨️ Imprimer Étiquette", self.print_batch_label)

    menu.exec(self.table.viewport().mapToGlobal(pos))


def _add_action(menu, label, slot):
    action = QAction(label, menu)
    action.triggered.connect(slot)
    menu.addAction(action)
