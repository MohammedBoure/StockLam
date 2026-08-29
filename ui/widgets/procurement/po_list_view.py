# ui/views/procurement/po_list_view.py

import logging
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, 
                               QTableWidgetItem, QPushButton, QLabel, QLineEdit, 
                               QComboBox, QHeaderView, QMessageBox, QFrame, QMenu)
from PySide6.QtGui import QAction, QColor, QFont
from PySide6.QtCore import Qt, Signal # [إضافة Signal]

from ui.widgets.procurement.dialogs import PurchaseOrderDialog
from ui.widgets.procurement.reception_dialog import ReceptionDialog
from ui.formatting import format_money

class NumericTableWidgetItem(QTableWidgetItem):
    def __lt__(self, other):
        if other is None:
            return False
        v1 = self.data(Qt.UserRole)
        v2 = other.data(Qt.UserRole)
        if v1 is not None and v2 is not None:
            try:
                return float(v1) < float(v2)
            except (ValueError, TypeError):
                pass
        return super().__lt__(other)

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

                def create_numeric_item(text, numeric_val):
                    item = NumericTableWidgetItem(str(text))
                    item.setTextAlignment(Qt.AlignCenter)
                    item.setData(Qt.UserRole, numeric_val)
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
                
                amt_val = float(po.get('Estimated_Amount_TTC') or po.get('Total_Amount_TTC') or 0)
                if po.get('Is_Partial_Estimate'):
                    amt_display = f"> {format_money(amt_val, 'DA')}" if amt_val > 0 else "---"
                else:
                    amt_display = format_money(amt_val, 'DA') if (amt_val > 0 or po.get('Has_Estimated_Price')) else "---"

                amt_item = create_numeric_item(amt_display, amt_val)
                if po.get('Is_Partial_Estimate'):
                    amt_item.setForeground(QColor("#d35400"))
                    amt_item.setToolTip("Estimation partielle : certains produits n'ont pas encore d'historique de prix en stock.")
                elif po.get('Has_Estimated_Price'):
                    amt_item.setForeground(QColor("#27ae60"))
                    amt_item.setToolTip("Montant estimé calculé d'après les derniers prix d'achat enregistrés dans le stock.")
                else:
                    amt_item.setForeground(QColor("#7f8c8d"))
                    amt_item.setToolTip("Aucun prix d'achat enregistré dans le stock pour ces articles.")

                self.table.setItem(row, 5, amt_item)

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
            dialog.exec()
            if not is_read_only:
                self.refresh_data()
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
