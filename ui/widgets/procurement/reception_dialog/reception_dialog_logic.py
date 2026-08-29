"""
reception_dialog_logic.py
--------------------------
Mixin يحتوي على كل المنطق الوظيفي لـ ReceptionDialog:
  - حساب المجاميع
  - التحقق من الرأس
  - إضافة / تعديل / حذف السطور
  - توليد الباركود
  - تحميل البيانات
  - إدارة حالة الحقول
"""
import logging
import random

from PySide6.QtWidgets import QMessageBox, QInputDialog
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QColor

from ..bulk_barcode_selection_dialog import BulkBarcodeSelectionDialog
from ui.formatting import format_money, format_quantity, quantity_to_int


class ReceptionDialogLogicMixin:
    """Mixin يُضاف إلى ReceptionDialog لإدارة المنطق الوظيفي."""

    # ------------------------------------------------------------------ #
    #  إعداد الاتصالات                                                    #
    # ------------------------------------------------------------------ #
    def setup_connections(self):
        self.cb_product.currentIndexChanged.connect(self.on_product_selected)

        for w in [self.inp_qty, self.inp_remise]:
            w.valueChanged.connect(self.calculate_live_item_ttc)
        self.cb_remise_type.currentIndexChanged.connect(self.calculate_live_item_ttc)
        
        self.inp_price.valueChanged.connect(self.on_ht_changed)
        self.inp_price_ttc.valueChanged.connect(self.on_ttc_changed)
        self.chk_tva.stateChanged.connect(self.on_tva_toggled)

        self.btn_validate_ref.clicked.connect(self.validate_header_and_create)
        self.btn_unlock_header.clicked.connect(self.enable_header_editing)

        self.btn_add.clicked.connect(self.add_item_to_table)
        self.btn_modify.clicked.connect(self.load_item_for_edit)
        self.btn_delete.clicked.connect(self.delete_selected_row)
        self.btn_print.clicked.connect(self.print_selected_labels)
        self.btn_print_all.clicked.connect(self.open_bulk_print_dialog)

        self.table_items.cellDoubleClicked.connect(self.load_item_for_edit)

    # ------------------------------------------------------------------ #
    #  اختيار المنتج & الحساب الفوري                                     #
    # ------------------------------------------------------------------ #
    def on_product_selected(self):
        p = self.cb_product.currentData()
        self.cb_unit_type.clear()
        if not p:
            return
        self.cb_unit_type.addItem(p.get('Stock_Unit', 'U'), 1.0)
        if p.get('Ordering_Unit') and p['Ordering_Unit'] != p.get('Stock_Unit'):
            self.cb_unit_type.addItem(p['Ordering_Unit'], float(p.get('Stock_Qty_Per_Order_Unit', 1.0)))

    def on_ht_changed(self):
        try:
            self.inp_price_ttc.blockSignals(True)
            tva_rate = 0.19 if hasattr(self, 'chk_tva') and self.chk_tva.isChecked() else 0.0
            ttc = self.inp_price.value() * (1 + tva_rate)
            self.inp_price_ttc.setValue(ttc)
        finally:
            self.inp_price_ttc.blockSignals(False)
        self.calculate_live_item_ttc()

    def on_ttc_changed(self):
        try:
            self.inp_price.blockSignals(True)
            tva_rate = 0.19 if hasattr(self, 'chk_tva') and self.chk_tva.isChecked() else 0.0
            ht = self.inp_price_ttc.value() / (1 + tva_rate)
            self.inp_price.setValue(ht)
        finally:
            self.inp_price.blockSignals(False)
        self.calculate_live_item_ttc()
        
    def on_tva_toggled(self):
        self.on_ht_changed()

    def calculate_live_item_ttc(self):
        try:
            if not hasattr(self, 'inp_qty') or not self.inp_qty:
                return
            qty      = float(self.inp_qty.value())
            price    = self.inp_price.value()
            rem_val  = self.inp_remise.value()
            rem_type = self.cb_remise_type.currentText()
            factor   = float(self.cb_unit_type.currentData() or 1.0)

            base_ht = qty * factor * price
            rem_amt = base_ht * (rem_val / 100) if rem_type == "%" else rem_val
            net_ht  = base_ht - rem_amt
            tax     = net_ht * 0.19 if self.chk_tva.isChecked() else 0
            ttc     = net_ht + tax

            self.lbl_item_ttc.setText(f"TTC : {format_money(ttc, 'DA')}")

            if factor > 1:
                p_data  = self.cb_product.currentData()
                stock_u = p_data.get('Stock_Unit', 'U') if p_data else 'U'
                self.lbl_conversion_logic.setText(
                    f"💡 {format_quantity(qty)} {self.cb_unit_type.currentText()} = {format_quantity(qty * factor)} {stock_u} en stock."
                )
            else:
                self.lbl_conversion_logic.setText("💡 Saisie directe en unité de stockage.")
        except RuntimeError:
            pass

    # ------------------------------------------------------------------ #
    #  إدارة رأس الفاتورة                                                 #
    # ------------------------------------------------------------------ #
    def enable_header_editing(self):
        """إعادة فتح حقول الرأس للتعديل."""
        self.invoice_ref.setReadOnly(False)
        self.bl_ref.setReadOnly(False)
        self.reception_date.setReadOnly(False)

        self.btn_validate_ref.setText(" Enregistrer")
        self.btn_validate_ref.setEnabled(True)
        self.btn_validate_ref.setStyleSheet("""
            QPushButton {
                background-color: #2980b9;
                color: white;
                font-weight: bold;
                padding: 6px 15px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #3498db; }
        """)
        self.btn_unlock_header.setVisible(False)
        self.toggle_inputs_state(False)
        self.invoice_ref.setFocus()

    def validate_header_and_create(self):
        """التحقق من الرأس، الحفظ، ثم فتح حقول المنتجات."""
        inv_ref = self.invoice_ref.text().strip()
        bl_ref  = self.bl_ref.text().strip()

        if not inv_ref and not bl_ref:
            QMessageBox.warning(
                self, "Données manquantes",
                "Veuillez saisir au moins une référence (Facture ou BL) avant de valider."
            )
            self.invoice_ref.setFocus()
            return False

        try:
            self.btn_validate_ref.setEnabled(False)
            self.btn_validate_ref.repaint()

            u_id = self.get_current_user_id()
            mgr  = self.manager.reception if hasattr(self.manager, 'reception') else self.manager

            header_data = {
                "PO_ID":                self.po_data.get('PO_ID'),
                "Supplier_ID":          self.po_data.get('Supplier_ID'),
                "Supplier_Invoice_Ref": inv_ref,
                "Supplier_BL_Ref":      bl_ref,
                "Reception_Date":       self.reception_date.date().toPyDate(),
                "Created_By":           u_id
            }

            if not self.br_id:
                new_id = mgr.create_new_reception_header(header_data)
                if not new_id:
                    self.btn_validate_ref.setEnabled(True)
                    QMessageBox.critical(self, "Erreur Doublon", "Cette référence existe déjà.")
                    return False
                self.br_id = new_id
            else:
                mgr.update_reception_header_info(self.br_id, header_data)

            # تحديث حالة PO
            self.invoice_ref.setReadOnly(True)
            self.bl_ref.setReadOnly(True)
            self.reception_date.setReadOnly(True)

            self.btn_validate_ref.setText(" Validé")
            self.btn_validate_ref.setStyleSheet(
                "background-color: #27ae60; color: white; font-weight: bold; border: none;"
            )
            self.btn_unlock_header.setVisible(True)
            self.toggle_inputs_state(True)
            self.cb_product.setFocus()
            return True

        except Exception as e:
            logging.error(f"Validation error: {e}")
            self.btn_validate_ref.setEnabled(True)
            QMessageBox.critical(self, "Erreur Système", str(e))
            return False

    # ------------------------------------------------------------------ #
    #  إدارة حالة الحقول                                                  #
    # ------------------------------------------------------------------ #
    def toggle_inputs_state(self, enabled: bool):
        for w in [
            self.cb_product, self.cb_unit_type, self.inp_qty,
            self.inp_lot, self.inp_expiry, self.cb_location,
            self.inp_price, self.inp_price_ttc, self.inp_remise, self.cb_remise_type,
            self.chk_tva, self.inp_observation,
            self.btn_add, self.btn_modify, self.btn_delete, self.btn_print,
            self.table_items,
        ]:
            w.setEnabled(enabled)

    # ------------------------------------------------------------------ #
    #  المجاميع                                                            #
    # ------------------------------------------------------------------ #
    def update_totals(self):
        self.total_ht_val    = 0.0
        self.total_tva_val   = 0.0
        self.total_remise_val= 0.0
        self.total_ttc_val   = 0.0

        for r in range(self.table_items.rowCount()):
            item = self.table_items.item(r, 0)
            if not item:
                continue
            meta = item.data(Qt.UserRole)
            if not meta:
                continue

            qty      = float(meta.get('Qty_Received', 0))
            price    = float(meta.get('Unit_Price_Received', 0.0))
            disc_amt = float(meta.get('Discount_Val', 0.0))
            tax_rate = float(meta.get('Tax_Rate_Percent', 0)) / 100.0

            line_ht     = qty * price
            line_net_ht = line_ht - disc_amt
            line_tva    = line_net_ht * tax_rate
            line_ttc    = line_net_ht + line_tva

            self.total_ht_val     += line_ht
            self.total_remise_val += disc_amt
            self.total_tva_val    += line_tva
            self.total_ttc_val    += line_ttc

        self.lbl_total_ht.setText(format_money(self.total_ht_val, 'DA'))
        self.lbl_total_remise.setText(format_money(self.total_remise_val, 'DA'))
        self.lbl_total_tva.setText(format_money(self.total_tva_val, 'DA'))
        self.lbl_total_ttc.setText(format_money(self.total_ttc_val, 'DA'))

    # ------------------------------------------------------------------ #
    #  تحميل البيانات (وضع التعديل)                                      #
    # ------------------------------------------------------------------ #
    def load_reception_data(self):
        """تحميل بيانات الاستقبال في وضع التعديل."""
        if not self.reception_data or not self.reception_data.get('Header'):
            return

        if self.br_id:
            self.invoice_ref.setReadOnly(True)
            self.bl_ref.setReadOnly(True)
            self.reception_date.setReadOnly(True)

            self.btn_validate_ref.setText(" Validé")
            self.btn_validate_ref.setEnabled(False)
            self.btn_validate_ref.setStyleSheet(
                "background-color: #27ae60; color: white; font-weight: bold; border: none;"
            )
            self.btn_unlock_header.setVisible(True)

        self.table_items.setSortingEnabled(False)

        header  = self.reception_data['Header']
        inv_ref = header.get('Supplier_Invoice_Ref') or ''
        self.invoice_ref.setText(inv_ref)
        self.bl_ref.setText(header.get('Supplier_BL_Ref') or '')

        if header.get('Reception_Date'):
            r_date = header['Reception_Date']
            try:
                if isinstance(r_date, str):
                    qdate = QDate.fromString(r_date[:10], "yyyy-MM-dd")
                    if qdate.isValid():
                        self.reception_date.setDate(qdate)
                elif hasattr(r_date, 'year'):
                    self.reception_date.setDate(QDate(r_date.year, r_date.month, r_date.day))
            except Exception:
                pass

        self.table_items.setRowCount(0)

        for batch in self.reception_data.get('Batches', []):
            row = self.table_items.rowCount()
            self.table_items.insertRow(row)

            qty      = float(batch.get('Quantity_Initial', 0))
            price    = float(batch.get('Unit_Price_Received', 0))
            tax_pct  = float(batch.get('Tax_Rate_Percent', 0))
            disc_pct = float(batch.get('Discount_Percent', 0))

            base_ht   = qty * price
            disc_amt  = base_ht * (disc_pct / 100)
            net_ht    = base_ht - disc_amt
            tva_amt   = net_ht * (tax_pct / 100)
            total_ttc = net_ht + tva_amt
            pu_ttc    = (total_ttc / qty) if qty > 0 else 0

            meta = {
                'Batch_ID':             batch.get('Batch_ID'),
                'Product_ID':           batch.get('Product_ID'),
                'Location_ID':          batch.get('Location_ID'),
                'Location_Name':        batch.get('Location_Name', '---'),
                'Lot_Number':           batch.get('Lot_Number', 'N/A'),
                'Expiry_Date':          str(batch.get('Expiry_Date', '')),
                'Qty_Received':         qty,
                'Unit_Price_Received':  price,
                'Discount_Val':         disc_amt,
                'Discount_Percent':     disc_pct,
                'Tax_Rate_Percent':     tax_pct,
                'Internal_Barcode':     batch.get('Internal_Barcode', '---'),
                'Line_Note':            batch.get('Reception_Note', ''),
                'Unit_Label':           batch.get('Stock_Unit', 'U'),
                'factor':               1.0
            }

            display_values = [
                batch.get('Product_Name', '---'),
                batch.get('Internal_Barcode', '---'),
                batch.get('Stock_Unit', 'U'),
                format_quantity(qty),
                meta['Lot_Number'],
                meta['Expiry_Date'],
                batch.get('Location_Name', '---'),
                format_money(price, 'DA'),
                format_money(disc_amt, 'DA'),
                format_money(net_ht, 'DA'),
                format_money(tva_amt, 'DA'),
                format_money(pu_ttc, 'DA'),
                format_money(total_ttc, 'DA')
            ]

            from PySide6.QtWidgets import QTableWidgetItem
            for col, value in enumerate(display_values):
                cell = QTableWidgetItem(str(value))
                cell.setTextAlignment(Qt.AlignCenter)
                self.table_items.setItem(row, col, cell)

            self.table_items.item(row, 0).setData(Qt.UserRole, meta)

        self.update_totals()
        self.table_items.setSortingEnabled(True)

    def load_items_from_db(self):
        """تحديث الجدول من قاعدة البيانات مباشرة لضمان المزامنة."""
        if not hasattr(self, 'br_id') or not self.br_id:
            return
        reception_mgr = self.manager.reception if hasattr(self.manager, 'reception') else self.manager
        details = reception_mgr.get_reception_full_details(self.br_id)
        if details:
            self.reception_data = details
            self.load_reception_data()

    # ------------------------------------------------------------------ #
    #  إضافة / تعديل / حذف                                               #
    # ------------------------------------------------------------------ #
    def add_item_to_table(self):
        """إضافة أو تعديل سطر في الجدول وقاعدة البيانات."""
        try:
            if not self.br_id:
                QMessageBox.warning(
                    self, "Action Requise",
                    "Veuillez valider l'en-tête (Bouton Valider) avant d'ajouter des produits."
                )
                self.invoice_ref.setFocus()
                return

            p_data = self.cb_product.currentData()
            loc_id = self.cb_location.get_current_location_id()

            if not p_data or loc_id is None:
                QMessageBox.warning(self, "Attention", "Veuillez sélectionner un produit et un emplacement.")
                return

            u_id   = self.get_current_user_id()
            mgr    = self.manager.reception if hasattr(self.manager, 'reception') else self.manager

            qty          = float(self.inp_qty.value())
            factor       = float(self.cb_unit_type.currentData() or 1.0)
            effective_qty= qty * factor

            if self.current_editing_row != -1:
                old_meta       = self.table_items.item(self.current_editing_row, 0).data(Qt.UserRole)
                barcode_to_save= old_meta.get('Internal_Barcode')
            else:
                barcode_to_save= self.generate_internal_barcode()

            current_po_id = self.po_data.get('PO_ID')

            line_data = {
                "BR_ID":               self.br_id,
                "PO_ID":               current_po_id,
                "Product_ID":          p_data['Product_ID'],
                "Location_ID":         loc_id,
                "Quantity_Initial":    effective_qty,
                "Quantity_Current":    effective_qty,
                "Unit_Price_Received": self.inp_price.value(),
                "Tax_Rate_Percent":    19.0 if self.chk_tva.isChecked() else 0.0,
                "Discount_Percent":    self.inp_remise.value() if self.cb_remise_type.currentText() == "%" else 0,
                "Lot_Number":          self.inp_lot.text() or "N/A",
                "Expiry_Date":         self.inp_expiry.date().toPyDate(),
                "Batch_Note":          self.inp_observation.text().strip(),
                "Internal_Barcode":    barcode_to_save,
                "Created_By":          u_id
            }

            if self.current_editing_row != -1:
                meta = self.table_items.item(self.current_editing_row, 0).data(Qt.UserRole)
                success, msg = mgr.update_reception_line(meta['Batch_ID'], line_data)
            else:
                success, msg = mgr.add_reception_line(line_data)

            if success:
                mgr._recalculate_reception_totals(self.br_id)
                self.load_items_from_db()
                self.clear_inputs()
            else:
                QMessageBox.critical(self, "Erreur", msg)

        except Exception as e:
            QMessageBox.critical(self, "Erreur", str(e))

    def load_item_for_edit(self):
        try:
            row = self.table_items.currentRow()
            if row < 0:
                QMessageBox.warning(self, "Attention", "Veuillez sélectionner une ligne.")
                return

            item_0 = self.table_items.item(row, 0)
            if not item_0:
                return
            meta = item_0.data(Qt.UserRole)
            if not meta:
                return

            p_id = meta.get('Product_ID')
            for i in range(self.cb_product.count()):
                p_data = self.cb_product.itemData(i)
                if p_data and p_data.get('Product_ID') == p_id:
                    self.cb_product.setCurrentIndex(i)
                    break

            factor      = float(meta.get('factor', 1.0))
            qty_display = quantity_to_int(float(meta.get('Qty_Received', 0)) / factor)
            self.inp_qty.setValue(qty_display)

            idx_unit = self.cb_unit_type.findText(meta.get('Unit_Label', ''))
            if idx_unit >= 0:
                self.cb_unit_type.setCurrentIndex(idx_unit)

            self.chk_tva.setChecked(float(meta.get('Tax_Rate_Percent', 0)) > 0)
            self.inp_price.setValue(float(meta.get('Unit_Price_Received', 0.0)))

            if float(meta.get('Discount_Percent', 0)) > 0:
                self.cb_remise_type.setCurrentText("%")
                self.inp_remise.setValue(float(meta['Discount_Percent']))
            else:
                self.cb_remise_type.setCurrentText("DZD")
                self.inp_remise.setValue(float(meta.get('Discount_Val', 0.0)))

            self.inp_lot.setText(str(meta.get('Lot_Number', '')))
            exp_date_str = str(meta.get('Expiry_Date', ''))
            if exp_date_str and exp_date_str not in ['None', 'N/A', '']:
                q_date = QDate.fromString(exp_date_str, "yyyy-MM-dd")
                if q_date.isValid():
                    self.inp_expiry.setDate(q_date)

            location_name = meta.get('Location_Name', '---')
            if meta.get('Location_ID'):
                if not self.select_location_id(meta['Location_ID']):
                    self.cb_location.setCurrentText(location_name)
            else:
                self.cb_location.setCurrentText(location_name)

            self.inp_observation.setText(str(meta.get('Line_Note', '')))

            self.current_editing_row = row
            self.btn_add.setText("💾 Enregistrer Modif.")
            self.btn_add.setStyleSheet("background-color: #f39c12; color: white; font-weight: bold;")
            self.calculate_live_item_ttc()

        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur de chargement: {str(e)}")

    def delete_selected_row(self):
        row = self.table_items.currentRow()
        if row < 0:
            return

        item_0 = self.table_items.item(row, 0)
        meta   = item_0.data(Qt.UserRole)
        batch_id = meta.get('Batch_ID')
        if not batch_id:
            return

        if QMessageBox.question(
            self, "Confirmation",
            "Supprimer définitivement ce produit du stock ?",
            QMessageBox.Yes | QMessageBox.No
        ) == QMessageBox.Yes:
            mgr = self.get_reception_mgr()
            success, msg = mgr.delete_reception_line(batch_id)
            if success:
                mgr._recalculate_reception_totals(self.br_id)
                self.load_items_from_db()
            else:
                QMessageBox.warning(self, "Action Impossible", msg)

    # ------------------------------------------------------------------ #
    #  الطباعة                                                             #
    # ------------------------------------------------------------------ #
    def print_selected_labels(self):
        rows = set(index.row() for index in self.table_items.selectedIndexes())
        if not rows:
            return
        for row in rows:
            meta         = self.table_items.item(row, 0).data(Qt.UserRole)
            product_name = self.table_items.item(row, 0).text()
            barcode_val  = self.table_items.item(row, 1).text()
            lot          = self.table_items.item(row, 4).text()
            expiry       = self.table_items.item(row, 5).text()
            qty          = int(meta.get('Qty_Received', 1))
            copies, ok   = QInputDialog.getInt(self, "Impression", f"Copies pour {product_name}", qty, 1, 1000)
            if ok:
                self.printer.print_label(product_name, barcode_val, lot, expiry, copies)

    def open_bulk_print_dialog(self):
        """فتح نافذة الطباعة الجماعية."""
        if self.table_items.rowCount() == 0:
            QMessageBox.information(self, "Info", "La liste est vide.")
            return

        items_to_process = []
        for row in range(self.table_items.rowCount()):
            item_0 = self.table_items.item(row, 0)
            if not item_0:
                continue
            meta = item_0.data(Qt.UserRole)
            if meta:
                meta['Product_Name'] = item_0.text()
                items_to_process.append(meta)

        dlg = BulkBarcodeSelectionDialog(items_to_process, self)
        if dlg.exec():
            selected     = dlg.get_items_to_print()
            total_labels = 0
            for index, item in enumerate(selected):
                qty    = int(item.get('Qty_Received', 1))
                name   = item.get('Product_Name', 'Inconnu')
                barcode= item.get('Internal_Barcode', '')
                lot    = item.get('Lot_Number', '')
                expiry = str(item.get('Expiry_Date', ''))
                if qty > 0:
                    self.printer.print_label(name, barcode, lot, expiry, qty)
                    total_labels += qty
                if index < len(selected) - 1:
                    self.printer.print_label("----------------", "   ", "---", "---", 1)

            QMessageBox.information(
                self, "Terminé", f"Ordre d'impression envoyé pour {total_labels} étiquettes."
            )

    # ------------------------------------------------------------------ #
    #  مساعدات                                                             #
    # ------------------------------------------------------------------ #
    def select_location_id(self, location_id):
        try:
            if location_id is None:
                return False
            for i in range(self.cb_location.count()):
                if self.cb_location.itemData(i) == location_id:
                    self.cb_location.setCurrentIndex(i)
                    return True
            return False
        except Exception:
            return False

    def get_reception_mgr(self):
        return self.manager.reception if hasattr(self.manager, 'reception') else self.manager

    def get_current_user_id(self):
        u_id          = None
        parent_widget = self.parent()
        while parent_widget:
            if hasattr(parent_widget, 'current_user') and isinstance(parent_widget.current_user, dict):
                u_id = parent_widget.current_user.get('User_ID')
                break
            parent_widget = parent_widget.parent()
        if u_id is None and hasattr(self.manager, 'current_user_id'):
            u_id = self.manager.current_user_id
        return u_id

    def is_barcode_exists_in_table(self, barcode):
        for row in range(self.table_items.rowCount()):
            item = self.table_items.item(row, 1)
            if item and item.text() == barcode:
                return True
            meta_item = self.table_items.item(row, 0)
            if meta_item:
                meta = meta_item.data(Qt.UserRole)
                if meta and meta.get('Internal_Barcode') == barcode:
                    return True
        return False

    def generate_internal_barcode(self):
        batch_mgr = self.manager.batches if hasattr(self.manager, 'batches') else None
        if not batch_mgr:
            from database.inventory_batch_manager import InventoryBatchManager
            batch_mgr = InventoryBatchManager(self.manager.db)

        po_id = self.po_data.get('PO_ID', '0')
        if hasattr(batch_mgr, 'get_barcode_prefix_for_po'):
            base_prefix = batch_mgr.get_barcode_prefix_for_po(po_id)
        else:
            base_prefix = str(po_id)

        if self.br_id and hasattr(batch_mgr, 'get_next_reception_barcode'):
            next_barcode = batch_mgr.get_next_reception_barcode(self.br_id, po_id=po_id)
        else:
            next_barcode = batch_mgr.get_next_smart_barcode(po_id)

        if hasattr(batch_mgr, 'extract_smart_barcode_serial'):
            serial = batch_mgr.extract_smart_barcode_serial(next_barcode, base_prefix) or 0
        else:
            serial = int(str(next_barcode)[len(base_prefix):])

        while self.is_barcode_exists_in_table(next_barcode):
            serial      += 1
            next_barcode = f"{base_prefix}{str(serial).zfill(3)}"
        return next_barcode

    def clear_inputs(self):
        self.cb_product.setCurrentIndex(0)
        self.cb_unit_type.clear()
        self.cb_location.setCurrentIndex(0)
        self.inp_lot.clear()
        self.inp_qty.setValue(1)
        self.inp_price.setValue(0.0)
        self.inp_price_ttc.setValue(0.0)
        self.inp_remise.setValue(0.0)
        self.inp_observation.clear()
        self.inp_expiry.setDate(QDate.currentDate().addYears(2))
        self.current_editing_row = -1
        self.btn_add.setText(" Ajouter")
        self.btn_add.setStyleSheet("")
        self.cb_product.setFocus()

    def is_input_dirty(self):
        return (
            self.cb_product.currentIndex() > 0 or
            self.inp_lot.text().strip() != "" or
            self.inp_price.value() > 0
        )

    def get_reception_data(self):
        if self.table_items.rowCount() == 0:
            return None

        invoice_ref = self.invoice_ref.text().strip()
        bl_ref      = self.bl_ref.text().strip()

        doc_type = "None"
        if invoice_ref and bl_ref: doc_type = "Both"
        elif invoice_ref:          doc_type = "Facture"
        elif bl_ref:               doc_type = "BL"

        items = []
        for r in range(self.table_items.rowCount()):
            meta = self.table_items.item(r, 0).data(Qt.UserRole)
            if meta:
                items.append(meta)

        self.update_totals()

        header_data = {
            "BR_ID":               self.br_id,
            "PO_ID":               self.po_data.get('PO_ID'),
            "Supplier_ID":         self.po_data.get('Supplier_ID'),
            "Supplier_Invoice_Ref":invoice_ref or None,
            "Supplier_BL_Ref":     bl_ref or None,
            "Document_Type":       doc_type,
            "Reception_Date":      self.reception_date.date().toPyDate(),
            "Invoice_Total_HT":    round(self.total_ht_val, 2),
            "Invoice_Total_TVA":   round(self.total_tva_val, 2),
            "Invoice_Total_TTC":   round(self.total_ttc_val, 2),
            "Total_Discount":      round(self.total_remise_val, 2)
        }
        return header_data, items

    def highlight_target_row(self):
        if not self.target_batch_id:
            return
        found_row = -1
        for row in range(self.table_items.rowCount()):
            item = self.table_items.item(row, 0)
            if not item:
                continue
            meta = item.data(Qt.UserRole)
            if meta and meta.get('Batch_ID') == self.target_batch_id:
                found_row = row
                break

        if found_row != -1:
            from PySide6.QtWidgets import QAbstractItemView
            self.table_items.selectRow(found_row)
            self.table_items.scrollToItem(
                self.table_items.item(found_row, 0),
                QAbstractItemView.PositionAtCenter
            )
            green_brush = QColor("#d4edda")
            for col in range(self.table_items.columnCount()):
                cell = self.table_items.item(found_row, col)
                if cell:
                    cell.setBackground(green_brush)
                    f = cell.font()
                    f.setBold(True)
                    cell.setFont(f)
