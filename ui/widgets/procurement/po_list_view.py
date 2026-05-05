# ui/views/procurement/po_list_view.py

import logging
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, 
                               QTableWidgetItem, QPushButton, QLabel, QLineEdit, 
                               QComboBox, QHeaderView, QMessageBox, QFrame, QMenu)
from PySide6.QtGui import QAction, QColor, QFont
from PySide6.QtCore import Qt, Signal # [إضافة Signal]

# استيراد نوافذ الحوار
from ui.widgets.procurement.dialogs import PurchaseOrderDialog
from ui.widgets.procurement.reception_dialog import ReceptionDialog

class PurchaseOrderListView(QWidget):
    view_receptions_requested = Signal(int)

    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.init_ui()
        self.refresh_data()

    def init_ui(self):
        layout = QVBoxLayout(self)

        filter_layout = QHBoxLayout()
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Rechercher (ID)...")
        self.search_input.textChanged.connect(self.refresh_data)
        
        filter_layout.addWidget(QLabel("Fournisseur:"))
        self.supplier_filter = QComboBox()
        self.supplier_filter.setMinimumWidth(150)
        self.supplier_filter.addItem("Tous")
        self.load_suppliers() 
        self.supplier_filter.currentTextChanged.connect(self.refresh_data)

        self.status_filter = QComboBox()
        self.status_filter.addItems(["Tous", "Brouillon", "Envoyée", "Partielle", "Complétée"])
        self.status_filter.currentTextChanged.connect(self.refresh_data)
        
        filter_layout.addWidget(self.search_input)
        filter_layout.addWidget(self.supplier_filter) 
        filter_layout.addWidget(QLabel("Statut:"))
        filter_layout.addWidget(self.status_filter)
        
        layout.addLayout(filter_layout)

        self.table = QTableWidget()
        
        columns = ["N°", "Fournisseur", "Date Commande", "Livraison Prévue", "Statut", "Montant TTC"]
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
        
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        
        self.table.doubleClicked.connect(self.on_table_double_click)
        
        layout.addWidget(self.table)

        # --- أزرار الإجراءات ---
        actions_layout = QHBoxLayout()
        
        self.btn_receive = QPushButton("📥 Réceptionner")
        self.btn_receive.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold;")
        self.btn_receive.clicked.connect(self.create_reception_for_selected)

        # [جديد] زر عرض الأرشيف
        self.btn_history = QPushButton("📜 Voir Historique")
        self.btn_history.setStyleSheet("background-color: #3498db; color: white; font-weight: bold;")
        self.btn_history.clicked.connect(self.trigger_view_history)

        self.btn_edit = QPushButton("✏️ Modifier la Commande")
        self.btn_edit.clicked.connect(self.edit_selected_po)
        
        self.btn_delete = QPushButton("🗑️ Supprimer la Commande")
        self.btn_delete.setStyleSheet("color: #c0392b;")
        self.btn_delete.clicked.connect(self.delete_selected_po)
        
        actions_layout.addWidget(self.btn_receive)
        actions_layout.addWidget(self.btn_history) # إضافة الزر الجديد هنا
        actions_layout.addStretch()
        actions_layout.addWidget(self.btn_edit)
        actions_layout.addWidget(self.btn_delete)
        layout.addLayout(actions_layout)

    def load_suppliers(self):
        """تحميل قائمة الموردين في القائمة المنسدلة"""
        try:
            suppliers = self.manager.suppliers.get_all_suppliers()
            for s in suppliers:
                self.supplier_filter.addItem(s['Supplier_Name'], s['Supplier_ID'])
        except Exception as e:
            logging.error(f"Error loading suppliers filter: {e}")

    def show_context_menu(self, pos):
        """عرض القائمة عند النقر بالزر الأيمن"""
        index = self.table.indexAt(pos)
        if not index.isValid():
            return

        menu = QMenu(self)
        
        # 1. خيار إنشاء استلام
        action_receive = QAction("📥 Créer Bon de Réception", self)
        action_receive.triggered.connect(self.create_reception_for_selected)
        menu.addAction(action_receive)
        
        # [جديد] خيار عرض الأرشيف في القائمة
        action_history = QAction("📜 Voir les Réceptions associées", self)
        action_history.triggered.connect(self.trigger_view_history)
        menu.addAction(action_history)

        menu.addSeparator()

        # 2. خيار التعديل
        action_edit = QAction("✏️ Modifier", self)
        action_edit.triggered.connect(self.edit_selected_po)
        menu.addAction(action_edit)

        # 3. خيار الحذف
        action_delete = QAction("🗑️ Supprimer", self)
        action_delete.triggered.connect(self.delete_selected_po)
        menu.addAction(action_delete)

        menu.exec(self.table.viewport().mapToGlobal(pos))

    def trigger_view_history(self):
        """[جديد] دالة إرسال الإشارة لفتح الأرشيف"""
        po_data = self.get_selected_order()
        if not po_data:
            QMessageBox.warning(self, "Attention", "Veuillez sélectionner une commande.")
            return
        
        # إرسال ID الطلب ليتم التقاطه في procurement_tabs.py
        self.view_receptions_requested.emit(po_data['PO_ID'])

    def create_reception_for_selected(self):
        """فتح نافذة الاستلام للطلب المحدد"""
        po_data = self.get_selected_order()
        if not po_data:
            QMessageBox.warning(self, "Attention", "Veuillez sélectionner une commande.")
            return
        
        po_id = po_data['PO_ID']
        status = po_data.get('Status')

        # ---------------------------------------------------------
        # [تعديل] منع إنشاء استلام إذا كانت الحالة Draft أو Cancelled
        # ---------------------------------------------------------
        if status == 'Draft':
            QMessageBox.warning(self, "Action impossible", 
                                "Impossible de créer une réception pour une commande 'Brouillon'.\n"
                                "Veuillez d'abord valider la commande (Statut: Envoyée).")
            return

        if status == 'Cancelled':
            QMessageBox.warning(self, "Action impossible", 
                                "Impossible de créer une réception pour une commande 'Annulée'.")
            return
        # ---------------------------------------------------------

        try:
            full_po_data = self.manager.po.get_full_order_details(po_id)
            if not full_po_data:
                QMessageBox.warning(self, "Erreur", f"Impossible de charger les détails de la commande #{po_id}.")
                return

            locations = self.manager.locations.get_all_locations_flat()

            dialog = ReceptionDialog(
                po_data=full_po_data,
                locations_list=locations,
                location_manager=self.manager.locations,
                manager=self.manager.reception,
                printer_manager=self.manager.printer,
                parent=self
            )
            
            dialog.exec()
            self.refresh_data()

        except Exception as e:
            logging.error(f"Erreur lors de l'ouverture de la réception: {e}")
            QMessageBox.critical(self, "Erreur", f"Une erreur s'est produite: {e}")

    def refresh_data(self, start_date=None, end_date=None):
        """تحديث البيانات مع دعم فلترة التاريخ والموردين."""
        try:
            self.table.setSortingEnabled(False)
            
            all_pos = self.manager.po.get_all_purchase_orders(
                months=None, 
                start_date=start_date, 
                end_date=end_date
            )
            
            status_map = {
                'Draft': 'Brouillon',
                'Sent': 'Envoyée',
                'Partial_Received': 'Partielle',
                'Partial': 'Partielle',
                'Completed': 'Complétée',
                'Cancelled': 'Annulée'
            }
            
            colors_map = {
                'Draft': 'gray', 'Sent': 'blue', 'Partial_Received': 'orange', 'Partial': 'orange',
                'Completed': 'green', 'Cancelled': 'red'
            }
            
            search_txt = self.search_input.text().lower()
            status_sel = self.status_filter.currentText()
            supplier_sel = self.supplier_filter.currentText() 
            
            filtered = []
            for po in all_pos:
                raw_status = po.get('Status', 'Draft')
                display_status = status_map.get(raw_status, raw_status)
                po_supplier = po.get('Supplier_Name', '')

                if status_sel != "Tous" and display_status != status_sel:
                    continue
                
                if supplier_sel != "Tous" and po_supplier != supplier_sel:
                    continue
                    
                po_id = str(po.get('PO_ID', ''))
                if search_txt and (search_txt not in po_id.lower()):
                    continue

                filtered.append((po, raw_status, display_status))
            
            self.table.setRowCount(0)
            for row, (po, raw_status, display_status) in enumerate(filtered):
                self.table.insertRow(row)
                
                def create_centered_item(text):
                    item = QTableWidgetItem(str(text))
                    item.setTextAlignment(Qt.AlignCenter)
                    return item

                id_item = create_centered_item(po.get('PO_ID'))
                id_item.setData(Qt.UserRole, po)
                self.table.setItem(row, 0, id_item)
                
                self.table.setItem(row, 1, create_centered_item(po.get('Supplier_Name')))
                self.table.setItem(row, 2, create_centered_item(po.get('Order_Date')))
                
                del_date = po.get('Expected_Delivery_Date') or '---'
                self.table.setItem(row, 3, create_centered_item(del_date))
                
                status_item = create_centered_item(display_status)
                font = QFont()
                font.setBold(True)
                status_item.setFont(font)
                status_item.setForeground(QColor(colors_map.get(raw_status, 'black')))
                self.table.setItem(row, 4, status_item)
                
                amt = float(po.get('Total_Amount_TTC') or 0)
                self.table.setItem(row, 5, create_centered_item(f"{amt:,.2f} DA"))

            self.table.setSortingEnabled(True)

        except Exception as e:
            logging.error(f"Error loading PO list: {e}")

    def get_selected_order(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return item.data(Qt.UserRole) if item else None

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
            except Exception as e:
                logging.error(f"Error deleting PO: {e}")
