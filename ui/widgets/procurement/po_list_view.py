# ui/views/procurement/po_list_view.py

import logging
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, 
                               QTableWidgetItem, QPushButton, QLabel, QLineEdit, 
                               QComboBox, QHeaderView, QMessageBox, QFrame)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont

# استيراد نوافذ الحوار
from ui.widgets.procurement.dialogs import PurchaseOrderDialog

class PurchaseOrderListView(QWidget):
    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.init_ui()
        self.refresh_data()

    def init_ui(self):
        layout = QVBoxLayout(self)

        filter_layout = QHBoxLayout()
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Rechercher (Fournisseur, ID)...")
        self.search_input.textChanged.connect(self.refresh_data)
        
        self.status_filter = QComboBox()
        self.status_filter.addItems(["Tous", "Brouillon", "Envoyée", "Complétée"])
        self.status_filter.currentTextChanged.connect(self.refresh_data)
        
        filter_layout.addWidget(self.search_input)
        filter_layout.addWidget(QLabel("Statut:"))
        filter_layout.addWidget(self.status_filter)
        
        layout.addLayout(filter_layout)

        self.table = QTableWidget()
        
        columns = ["N°", "Fournisseur", "Date Commande", "Livraison Prévue", "Statut"]
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        
        header = self.table.horizontalHeader()
        self.table.setColumnWidth(0, 120) 

        header.setSectionResizeMode(1, QHeaderView.Stretch)
        for i in range(2, len(columns)):
            header.setSectionResizeMode(i, QHeaderView.ResizeToContents)

        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setSectionsClickable(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.doubleClicked.connect(self.on_table_double_click)
        
        layout.addWidget(self.table)

        # --- 3. Boutons d'actions ---
        actions_layout = QHBoxLayout()
        self.btn_edit = QPushButton("✏️ Modifier la Commande")
        self.btn_edit.clicked.connect(self.edit_selected_po)
        
        self.btn_delete = QPushButton("🗑️ Supprimer la Commande")
        self.btn_delete.setStyleSheet("color: #c0392b;")
        self.btn_delete.clicked.connect(self.delete_selected_po)
        
        actions_layout.addStretch()
        actions_layout.addWidget(self.btn_edit)
        actions_layout.addWidget(self.btn_delete)
        layout.addLayout(actions_layout)

    def refresh_data(self, start_date=None, end_date=None):
        """
        تحديث البيانات مع دعم فلترة التاريخ.
        """
        try:
            self.table.setSortingEnabled(False)
            
            # --- [FIX] التصحيح هنا: تحديد أسماء المتغيرات بدقة ---
            # نرسل months=None لنخبر المدير أننا نريد استخدام التواريخ بدلاً من الأشهر
            all_pos = self.manager.po.get_all_purchase_orders(
                months=None, 
                start_date=start_date, 
                end_date=end_date
            )
            # -----------------------------------------------------
            
            # Mapping Statut → Français
            status_map = {
                'Draft': 'Brouillon',
                'Sent': 'Envoyée',
                'Partial': 'Partielle',
                'Completed': 'Complétée',
                'Cancelled': 'Annulée'
            }
            
            # Mapping couleur
            colors_map = {
                'Draft': 'gray',
                'Sent': 'blue',
                'Partial': 'orange',
                'Completed': 'green',
                'Cancelled': 'red'
            }
            
            search_txt = self.search_input.text().lower()
            status_sel = self.status_filter.currentText()
            
            filtered = []
            for po in all_pos:
                raw_status = po.get('Status', 'Draft')
                display_status = status_map.get(raw_status, raw_status)
                
                if status_sel != "Tous" and display_status != status_sel:
                    continue
                    
                s_name = str(po.get('Supplier_Name', '')).lower()
                po_id = str(po.get('PO_ID', ''))
                if search_txt and (search_txt not in s_name and search_txt not in po_id):
                    continue
                filtered.append((po, raw_status, display_status))
            
            self.table.setRowCount(0)
            for row, (po, raw_status, display_status) in enumerate(filtered):
                self.table.insertRow(row)
                
                def create_centered_item(text):
                    item = QTableWidgetItem(str(text))
                    item.setTextAlignment(Qt.AlignCenter)
                    return item

                # 0. N°
                id_item = create_centered_item(po.get('PO_ID'))
                id_item.setData(Qt.UserRole, po)
                self.table.setItem(row, 0, id_item)
                
                # 1. Fournisseur
                self.table.setItem(row, 1, create_centered_item(po.get('Supplier_Name')))
                
                # 2. Date Commande
                self.table.setItem(row, 2, create_centered_item(po.get('Order_Date')))
                
                # 3. Livraison Prévue
                del_date = po.get('Expected_Delivery_Date') or '---'
                self.table.setItem(row, 3, create_centered_item(del_date))
                
                # 4. Statut (بالفرنسية)
                status_item = create_centered_item(display_status)
                font = QFont()
                font.setBold(True)
                status_item.setFont(font)
                status_item.setForeground(QColor(colors_map.get(raw_status, 'black')))
                self.table.setItem(row, 4, status_item)
                
                # 5. Montant TTC
                amt = float(po.get('Total_Amount_TTC') or 0)
                self.table.setItem(row, 5, create_centered_item(f"{amt:,.2f} DA"))

            self.table.setSortingEnabled(True)

        except Exception as e:
            logging.error(f"Error loading PO list: {e}")

    def get_selected_order(self):
        """جلب البيانات من العمود 0 (عمود ID الجديد) لأنه هو من يحمل الـ UserRole حالياً."""
        row = self.table.currentRow()
        if row < 0:
            return None
        # تأكدنا هنا أننا نقرأ من العمود 0 حيث خزنّا البيانات في دالة refresh_data
        item = self.table.item(row, 0)
        return item.data(Qt.UserRole) if item else None

    # باقي الدوال (on_table_double_click, edit_selected_po, delete_selected_po) تبقى كما هي.
    def on_table_double_click(self, index):
        self.edit_selected_po()

    def edit_selected_po(self):
        po_data = self.get_selected_order()
        if not po_data:
            QMessageBox.warning(self, "Attention", "Veuillez sélectionner une commande.")
            return
            
        po_id = po_data['PO_ID']
        status = po_data.get('Status')
        is_read_only = (status in ['Completed', 'Cancelled'])

        try:
            suppliers = self.manager.suppliers.get_all_suppliers()
            products = self.manager.products.get_all_products()
            full_po = self.manager.po.get_full_order_details(po_id)
            
            dialog = PurchaseOrderDialog(suppliers, products, parent=self, data=full_po, read_only=is_read_only)
            if not is_read_only and dialog.exec():
                new_data = dialog.get_data()
                if new_data:
                    self.manager.po.update_full_order(po_id, new_data)
                    self.refresh_data()
            elif is_read_only:
                dialog.exec()
        except Exception as e:
            logging.error(f"Error editing PO: {e}")

    def delete_selected_po(self):
        po_data = self.get_selected_order()
        if not po_data:
            QMessageBox.warning(self, "Attention", "Veuillez sélectionner une commande.")
            return
        po_id = po_data['PO_ID']
        if po_data.get('Status') not in ['Draft', 'Cancelled']:
            QMessageBox.warning(self, "Interdit", "Seules les commandes 'Draft' ou 'Cancelled' peuvent être supprimées.")
            return
        confirm = QMessageBox.question(self, "Confirmation", f"Voulez-vous supprimer la commande #{po_id} ?",
                                       QMessageBox.Yes | QMessageBox.No)
        if confirm == QMessageBox.Yes:
            try:
                if hasattr(self.manager.po, 'delete_purchase_order') and self.manager.po.delete_purchase_order(po_id):
                    self.refresh_data()
                    QMessageBox.information(self, "Succès", "Commande supprimée.")
            except Exception as e:
                logging.error(f"Error deleting PO: {e}")