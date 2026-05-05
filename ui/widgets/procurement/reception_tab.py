from PySide6.QtWidgets import (QWidget, QVBoxLayout, QTableWidget, QDateEdit,
                               QHeaderView, QPushButton, QHBoxLayout, QMessageBox, 
                               QTableWidgetItem, QLabel, QFrame, QLineEdit, QComboBox)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QColor, QFont
import logging
from .reception_dialog import ReceptionDialog 

class ReceptionTab(QWidget):
    """
    Onglet 'Réception' dans la section Achats.
    """
    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self.init_ui()
        self.load_pending_pos()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # --- Barre d'outils ---
        top_frame = QFrame()
        top_frame.setStyleSheet("QFrame { background-color: #f8f9fa; border: 1px solid #e0e0e0; border-radius: 6px; }")
        top_layout = QHBoxLayout(top_frame)
        top_layout.setContentsMargins(10, 10, 10, 10)
        
        lbl_title = QLabel("📥 Réception des Commandes")
        lbl_title.setStyleSheet("border: none; font-size: 14px; font-weight: bold; color: #2c3e50;")
        
        # مربع البحث
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 ID...")
        self.search_input.setStyleSheet("background: white; border: 1px solid #ccc; padding: 5px; border-radius: 4px;")
        self.search_input.setFixedWidth(150)
        self.search_input.textChanged.connect(self.load_pending_pos)

        # فلتر الموردين (موجود ومفعل)
        self.supplier_filter = QComboBox()
        self.supplier_filter.setStyleSheet("background: white; border: 1px solid #ccc; padding: 5px; border-radius: 4px;")
        self.supplier_filter.setFixedWidth(200)
        self.supplier_filter.addItem("Tous les fournisseurs")
        self.load_suppliers() # تعبئة القائمة
        self.supplier_filter.currentTextChanged.connect(self.load_pending_pos)

        btn_refresh = QPushButton("🔄 Actualiser")
        btn_refresh.setStyleSheet("QPushButton { background-color: #ecf0f1; border: 1px solid #bdc3c7; border-radius: 4px; padding: 6px 12px; } QPushButton:hover { background-color: #dfe6e9; }")
        btn_refresh.clicked.connect(self.load_pending_pos)
        
        btn_receive = QPushButton("📥 Réceptionner")
        btn_receive.setStyleSheet("QPushButton { background-color: #27ae60; color: white; font-weight: bold; border-radius: 4px; padding: 6px 15px; border: none;} QPushButton:hover { background-color: #2ecc71; }")
        btn_receive.clicked.connect(self.open_receive_dialog)

        top_layout.addWidget(lbl_title)
        top_layout.addSpacing(20)
        top_layout.addWidget(self.search_input)
        top_layout.addWidget(self.supplier_filter) # الفلتر مضاف هنا
        top_layout.addStretch()
        top_layout.addWidget(btn_refresh)
        top_layout.addWidget(btn_receive)
        
        layout.addWidget(top_frame)

        # --- Tableau ---
        self.table = QTableWidget()
        columns = ["ID BC", "Fournisseur", "Date Commande", "Date Prévue"]
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setDefaultAlignment(Qt.AlignCenter)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("border: 1px solid #e0e0e0;")
        self.table.doubleClicked.connect(self.open_receive_dialog)
        
        layout.addWidget(self.table)

    def load_suppliers(self):
        """تحميل الموردين من المدير وتعبئة القائمة المنسدلة."""
        try:
            if hasattr(self.manager, 'suppliers'):
                suppliers = self.manager.suppliers.get_all_suppliers()
                for s in suppliers:
                    self.supplier_filter.addItem(s['Supplier_Name'], s['Supplier_ID'])
        except Exception as e:
            logging.error(f"Erreur chargement fournisseurs: {e}")

    def force_close_po(self):
        """إغلاق الطلب يدوياً"""
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Attention", "Veuillez sélectionner une commande à clôturer.")
            return

        po_header = self.table.item(row, 0).data(Qt.UserRole)
        po_id = po_header['PO_ID']
        supplier = po_header.get('Supplier_Name', 'Inconnu')

        reply = QMessageBox.question(
            self, 
            "Confirmation de clôture",
            f"Êtes-vous sûr de vouloir marquer le BC #{po_id} ({supplier}) comme <b>COMPLÉTÉ</b> ?\n\n"
            "Cela signifie que vous ne recevrez plus d'articles pour cette commande.\n"
            "Elle disparaîtra de cette liste.",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                success = self.manager.po.update_status(po_id, 'Completed')
                if success:
                    self.load_pending_pos() 
                    if hasattr(self.parent(), 'on_tab_change'):
                        self.parent().on_tab_change(2)
                else:
                    QMessageBox.critical(self, "Erreur", "Échec de la mise à jour du statut.")
            except Exception as e:
                logging.error(f"Erreur lors de la clôture manuelle du BC {po_id}: {e}")
                QMessageBox.critical(self, "Erreur", f"Une erreur s'est produite: {e}")

    def showEvent(self, event):
        super().showEvent(event)
        self.load_pending_pos()

    def _has_variance_notes(self, po_id: int) -> bool:
        try:
            with self.manager.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = """
                    SELECT COUNT(*) 
                    FROM Inventory_Batches b
                    JOIN Reception_Log rl ON b.BR_ID = rl.BR_ID
                    WHERE rl.PO_ID = %s 
                    AND b.Reception_Note IS NOT NULL 
                    AND b.Reception_Note != ''
                """
                cursor.execute(query, (po_id,))
                count = cursor.fetchone()[0]
                return count > 0
        except Exception as e:
            logging.error(f"Erreur lors de la vérification des notes de variance pour le BC {po_id}: {e}")
            return False

    def load_pending_pos(self):
        try:
            all_pos = self.manager.po.get_all_purchase_orders()
            allowed_statuses = ['Sent', 'Partial_Received', 'Partial', 'Approved']
            
            search_txt = self.search_input.text().lower().strip()
            supplier_sel = self.supplier_filter.currentText() # المورد المختار

            pending_pos = []
            for po in all_pos:
                status = po.get('Status', '')
                if status not in allowed_statuses:
                    continue
                
                po_id_str = str(po.get('PO_ID', '')).lower()
                supp_name = str(po.get('Supplier_Name', '')).lower()
                
                # 1. فلتر المورد
                if supplier_sel != "Tous les fournisseurs" and po.get('Supplier_Name') != supplier_sel:
                    continue

                # 2. البحث النصي (ID فقط)
                if search_txt and (search_txt not in po_id_str):
                    continue
                
                # تم إلغاء استخدام هذا المتغير في التنسيق، لكن أبقيناه للمنطق
                has_notes = self._has_variance_notes(po['PO_ID'])
                pending_pos.append({'po_data': po, 'has_notes': has_notes})
            
            self.table.setRowCount(0)
            for row, item in enumerate(pending_pos):
                po = item['po_data']
                # has_notes = item['has_notes'] # لم نعد نحتاج هذا للتنسيق
                self.table.insertRow(row)
                
                def centered_item(text):
                    item = QTableWidgetItem(str(text))
                    item.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
                    return item
                
                self.table.setItem(row, 0, centered_item(po.get('PO_ID')))
                self.table.setItem(row, 1, centered_item(po.get('Supplier_Name')))
                self.table.setItem(row, 2, centered_item(po.get('Order_Date')))
                self.table.setItem(row, 3, centered_item(po.get('Expected_Delivery_Date') or '---'))
                
                # --- تم إزالة كود التنسيق بالخط العريض والأحمر بناءً على طلبك ---
                # if has_notes:
                #     for col in range(self.table.columnCount()):
                #         it = self.table.item(row, col)
                #         if it:
                #             it.setForeground(QColor("white"))
                #             it.setBackground(QColor("#e74c3c"))
                #             it.setFont(QFont("Arial", 9, QFont.Bold))
                # -------------------------------------------------------------
                
                self.table.item(row, 0).setData(Qt.UserRole, po)
        except Exception as e:
            logging.error(f"Erreur lors du chargement des BC en attente: {e}")

    def open_receive_dialog(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Attention", "Veuillez sélectionner une commande dans le tableau.")
            return
            
        po_header = self.table.item(row, 0).data(Qt.UserRole)
        po_id = po_header['PO_ID']
        
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
            self.load_pending_pos() 
            
            if hasattr(self.parent(), 'on_tab_change'):
                self.parent().on_tab_change(2)

        except Exception as e:
            logging.error(f"Erreur inattendue : {e}", exc_info=True)
            QMessageBox.critical(self, "Erreur Système", "Une erreur s'est produite.")
