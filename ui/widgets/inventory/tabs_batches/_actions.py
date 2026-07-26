# ui/widgets/inventory/tabs_batches/_actions.py
"""
إجراءات المستخدم: استهلاك، تحويل، تعديل، ربط FEFO، ومسح باركود
"""

import logging
from datetime import datetime, date

from PySide6.QtWidgets import QMessageBox, QInputDialog
from PySide6.QtCore import Qt

from ..dialogs import AdjustmentDialog, WasteDialog, BatchDetailsDialog
from ui.widgets.procurement.reception_dialog import ReceptionDialog
from ..quick_actions import QuickTransferDialog, QuickConsumeDialog
from ui.formatting import format_quantity, quantity_to_int


def get_current_user_id(self):
    try:
        return self.window().current_user.get('User_ID')
    except Exception:
        return None


def get_current_role(self):
    try:
        main_win = self.window()
        if hasattr(main_win, 'current_user') and main_win.current_user:
            return main_win.current_user.get('Role', 'Technician')
    except Exception:
        pass
    return 'Technician'


# ---------------------------------------------------------------------------
# FEFO
# ---------------------------------------------------------------------------

def check_fefo_compliance(self, current_batch):
    """التحقق من قاعدة FEFO وتحذير المستخدم عند انتهاكها"""
    current_expiry = current_batch.get('Expiry_Date')
    product_id     = current_batch.get('Product_ID')

    if not current_expiry:
        return True

    curr_date = _to_date(current_expiry)
    if curr_date is None:
        return True

    older_batches = [
        b for b in self.all_data
        if (b.get('Batch_ID') != current_batch.get('Batch_ID')
            and b.get('Product_ID') == product_id
            and quantity_to_int(b.get('Quantity_Current', 0)) > 0
            and _to_date(b.get('Expiry_Date')) is not None
            and _to_date(b.get('Expiry_Date')) < curr_date)
    ]

    if not older_batches:
        return True

    older_batches.sort(key=lambda x: str(x.get('Expiry_Date', '')))
    msg = "⚠️ <b>Attention : Non-Respect du FEFO</b><br><br>Des lots plus anciens existent :"
    for b in older_batches[:3]:
        msg += f"<br>• Lot: {b.get('Lot_Number', 'N/A')} | Exp: {str(b.get('Expiry_Date'))[:10]}"

    reply = QMessageBox.question(
        self, "Alerte FEFO", msg,
        QMessageBox.Yes | QMessageBox.No, QMessageBox.No
    )
    return reply == QMessageBox.Yes


def _to_date(val):
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


# ---------------------------------------------------------------------------
# إجراءات الجدول الرئيسية
# ---------------------------------------------------------------------------

def on_cell_clicked(self, row, col):
    """فتح حوار تعديل الشكوى فقط عند النقر على خلية/أيقونة الشكوى (العمود 16)"""
    if col == 16:
        item = self.table.item(row, 0)
        if item:
            batch_data = item.data(Qt.UserRole)
            if batch_data:
                self.edit_reclamation(batch_data)

def on_vertical_header_clicked(self, logicalIndex):
    """إلغاء فتح الشكوى عند النقر على الهيدر العمودي (رقم الصف)"""
    pass

def edit_reclamation(self, batch_data):
    """تعديل ملاحظة/شكوى الاستلام (Réclamation) للوط"""
    raw_note = batch_data.get('Reception_Note')
    current_note = str(raw_note).strip() if raw_note is not None else ""
    if current_note.lower() == "none":
        current_note = ""
        
    new_note, ok = QInputDialog.getMultiLineText(
        self,
        "Modifier la Réclamation",
        "Texte de la réclamation (laissez vide pour supprimer):",
        current_note
    )
    if ok:
        new_note = new_note.strip()
        batch_id = batch_data.get('Batch_ID')
        if self.manager.batches.update_batch_reception_note(batch_id, new_note):
            self.load_data()
            self.data_changed.emit()
            QMessageBox.information(self, "Succès", "La réclamation a été mise à jour.")
        else:
            QMessageBox.warning(self, "Erreur", "Impossible de mettre à jour la réclamation.")

def direct_use_process(self):
    """سحب مباشر من اللوط المحدد"""
    row_idx = self.table.currentRow()
    if row_idx < 0:
        QMessageBox.warning(self, "Sélection", "Veuillez sélectionner un lot.")
        return

    batch_data = self.table.item(row_idx, 0).data(Qt.UserRole)
    if not check_fefo_compliance(self, batch_data):
        return

    max_qty = quantity_to_int(batch_data.get('Quantity_Current', 0))
    if max_qty <= 0:
        return

    qty, ok = QInputDialog.getInt(
        self, "Sortie",
        f"Quantite (Max: {format_quantity(max_qty)}):", 1, 1, max_qty, 1
    )
    if ok:
        u_id = get_current_user_id(self)
        if self.manager.batches.direct_consume_batch_unit(
            batch_data['Batch_ID'], qty, user_id=u_id
        ):
            self.load_data()
            self.data_changed.emit()


def adjust_stock(self):
    """تعديل كمية اللوط"""
    row = self.table.currentRow()
    if row < 0:
        return
    data = self.table.item(row, 0).data(Qt.UserRole)
    dlg  = AdjustmentDialog(data, self.manager.waste_reasons.get_all_reasons(), self)
    if dlg.exec():
        d = dlg.get_data()
        if self.manager.batches.adjust_batch_quantity(
            d['Batch_ID'], d['Qty_Change'], 'Adjustment',
            d['Reason_ID'], get_current_user_id(self)
        ):
            self.load_data()
            self.data_changed.emit()


def waste_batch(self):
    """إضافة اللوط إلى الفاقد (Rebut)"""
    row = self.table.currentRow()
    if row < 0:
        return
    data = self.table.item(row, 0).data(Qt.UserRole)
    dlg  = WasteDialog(data, self.manager.waste_reasons.get_all_reasons(), 'Batch', self)
    if dlg.exec():
        d = dlg.get_data()
        if self.manager.batches.adjust_batch_quantity(
            d['Source_ID'], -abs(float(d['Qty_Wasted'])),
            'Waste', d['Reason_ID'], get_current_user_id(self)
        ):
            self.load_data()
            self.data_changed.emit()


def show_batch_details(self):
    """عرض نافذة تفاصيل اللوط"""
    row = self.table.currentRow()
    if row < 0:
        return
    batch_data = self.table.item(row, 0).data(Qt.UserRole)
    if batch_data:
        dialog = BatchDetailsDialog(batch_data, self)
        dialog.exec()


# ---------------------------------------------------------------------------
# إجراءات النقل والاستهلاك السريع
# ---------------------------------------------------------------------------

def open_quick_transfer(self, batch_data):
    """فتح نافذة التحويل السريع وتنفيذ العملية"""
    dialog = QuickTransferDialog(batch_data, self.manager.locations, self)

    if not dialog.exec():
        return

    data    = dialog.get_data()
    dest_id = data['dest_id']
    qty     = data['qty']

    if not dest_id:
        QMessageBox.warning(self, "Erreur", "Veuillez sélectionner une destination.")
        return
    if str(dest_id) == str(batch_data.get('Location_ID')):
        QMessageBox.warning(self, "Erreur", "La destination est la même que l'emplacement actuel.")
        return

    try:
        success = self.manager.batches.transfer_batch_location(
            batch_data['Batch_ID'], dest_id, qty,
            user_id=get_current_user_id(self)
        )
        if success:
            self.load_data()
            self.data_changed.emit()
        else:
            QMessageBox.critical(self, "Erreur", "Échec de l'opération dans la base de données.")
    except Exception as e:
        logging.error(f"Quick Transfer Error: {e}")
        QMessageBox.critical(self, "Erreur", f"Erreur technique : {e}")


def open_quick_consume(self, batch_data):
    """فتح نافذة الاستهلاك السريع وتنفيذ العملية"""
    dialog = QuickConsumeDialog(batch_data, self)

    if not dialog.exec():
        return

    qty = dialog.get_qty()
    try:
        if not check_fefo_compliance(self, batch_data):
            return
        success = self.manager.batches.direct_consume_batch_unit(
            batch_data['Batch_ID'], qty,
            user_id=get_current_user_id(self)
        )
        if success:
            self.load_data()
            self.data_changed.emit()
        else:
            QMessageBox.critical(self, "Erreur", "Échec de l'opération.")
    except Exception as e:
        logging.error(f"Quick Consume Error: {e}")
        QMessageBox.critical(self, "Erreur", f"Erreur technique : {e}")


# ---------------------------------------------------------------------------
# التاريخ والسجل
# ---------------------------------------------------------------------------

def go_to_history(self, product_name):
    if product_name:
        self.request_product_history.emit(str(product_name))


def open_history_via_barcode(self):
    row = self.table.currentRow()
    if row < 0:
        QMessageBox.warning(self, "Sélection", "Veuillez sélectionner un produit.")
        return

    item = self.table.item(row, 0)
    if not item:
        return
    batch_data = item.data(Qt.UserRole)
    if not batch_data:
        return

    search_term = (
        batch_data.get('Internal_Barcode')
        or batch_data.get('Barcode')
        or batch_data.get('Product_Name')
    )
    if search_term:
        self.request_product_history.emit(str(search_term))
    else:
        QMessageBox.warning(self, "Erreur", "Aucune donnée (Code/Nom) trouvée pour la recherche.")


def go_to_reception(self, br_id, target_batch_id=None):
    """فتح وصل الاستلام المرتبط باللوط وتحديد السطر الصحيح"""
    try:
        reception_data = self.manager.reception.get_reception_full_details(br_id)
        if not reception_data or not reception_data.get('Header'):
            QMessageBox.warning(self, "Erreur", "Données de réception introuvables.")
            return

        # --- بداية التعديل الذكي للبحث عن السطر الأصلي ---
        if target_batch_id:
            # التحقق مما إذا كان اللوط موجوداً ضمن اللوطات الأصلية للوصل
            valid_ids = [b['Batch_ID'] for b in reception_data.get('Batches', [])]
            
            if target_batch_id not in valid_ids:
                # إذا لم يكن موجوداً (يعني أنه منتج محول)، نجلبه من بيانات الجدول الحالية
                clicked_batch = next((b for b in self.all_data if b.get('Batch_ID') == target_batch_id), None)
                
                if clicked_batch:
                    clicked_barcode = str(clicked_batch.get('Internal_Barcode') or '').strip()
                    clicked_lot = str(clicked_batch.get('Lot_Number') or '').strip()

                    if clicked_barcode:
                        parent_batch = next(
                            (b for b in reception_data.get('Batches', [])
                             if b['Product_ID'] == clicked_batch['Product_ID']
                             and str(b.get('Internal_Barcode') or '').strip() == clicked_barcode),
                            None
                        )
                    else:
                        parent_batch = next(
                            (b for b in reception_data.get('Batches', [])
                             if b['Product_ID'] == clicked_batch['Product_ID']
                             and clicked_lot
                             and str(b.get('Lot_Number') or '').strip() == clicked_lot),
                            None
                        )
                    
                    if parent_batch:
                        # استبدال المعرف بمعرف اللوط الأصلي ليتم تلوينه في الواجهة
                        target_batch_id = parent_batch['Batch_ID']
        # --- نهاية التعديل ---

        header = reception_data['Header']
        po_data = {
            'PO_ID':        header.get('PO_ID'),
            'Supplier_ID':  header.get('Supplier_ID'),
            'Supplier_Name': header.get('Supplier_Name', 'Fournisseur Inconnu'),
        }

        dialog = ReceptionDialog(
            po_data=po_data,
            locations_list=self.manager.locations.get_all_locations(),
            location_manager=self.manager.locations,
            manager=self.manager,
            printer_manager=self.manager.printer,
            parent=self,
            edit_mode=True,
            reception_data=reception_data,
            target_batch_id=target_batch_id, # سيتم تمرير المعرف الأصلي الآن إذا كان المنتج محولاً
        )
        dialog.exec()

        try:
            if hasattr(self.manager.db, 'get_raw_connection'):
                self.manager.db.get_raw_connection().commit()
        except Exception:
            pass

        self.load_data()

    except Exception as e:
        logging.error(f"Erreur go_to_reception: {e}")
        QMessageBox.critical(self, "Erreur", f"Technique: {str(e)}")

# ---------------------------------------------------------------------------
# مسح الباركود
# ---------------------------------------------------------------------------

def handle_barcode_scan(self):
    txt = self.search_input.text().strip().lower()
    if not txt:
        return
    found_rows = []
    for r in range(self.table.rowCount()):
        data = self.table.item(r, 0).data(Qt.UserRole)
        bc1  = str(data.get('Internal_Barcode', '')).lower()
        bc2  = str(data.get('Barcode', '')).lower()
        if txt in (bc1, bc2):
            found_rows.append(r)

    if len(found_rows) == 1:
        self.table.selectRow(found_rows[0])
        self.table.scrollToItem(self.table.item(found_rows[0], 0))
        self.search_input.selectAll()
