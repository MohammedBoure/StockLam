import logging
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QHeaderView, 
    QTableWidgetItem, QLabel, QPushButton, QGroupBox, QFormLayout, 
    QTextEdit, QMessageBox, QAbstractItemView, QInputDialog
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush, QFont
import qtawesome as qta
from ui.formatting import format_quantity

class ReclamationDialog(QDialog):
    """
    نافذة لعرض وتعديل تفاصيل الشكاوى.
    - تعرض فقط المنتجات التي بها مشاكل.
    - تتيح التحديد المتعدد لحذف الملاحظات.
    """
    def __init__(self, reception_data, manager, parent=None):
        super().__init__(parent)
        self.data = reception_data
        self.header = reception_data.get('Header', {})
        self.batches = reception_data.get('Batches', [])
        self.manager = manager 
        self.br_id = self.header.get('BR_ID')
        
        self.setWindowTitle(f"Gestion Réclamation - BR #{self.br_id}")
        self.resize(1000, 750)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # --- 1. Header Info ---
        info_group = QGroupBox("📋 Informations Générales")
        info_group.setStyleSheet("QGroupBox { font-weight: bold; border: 1px solid #bdc3c7; border-radius: 6px; margin-top: 10px; }")
        info_layout = QHBoxLayout(info_group)
        
        form1 = QFormLayout()
        form1.addRow("Fournisseur:", QLabel(str(self.header.get('Supplier_Name', '---'))))
        form1.addRow("Date Réception:", QLabel(str(self.header.get('Reception_Date', '---'))))
        
        form2 = QFormLayout()
        form2.addRow("Réf. Facture:", QLabel(str(self.header.get('Supplier_Invoice_Ref', '---'))))
        form2.addRow("Réf. BL:", QLabel(str(self.header.get('Supplier_BL_Ref', '---'))))
        
        info_layout.addLayout(form1)
        info_layout.addLayout(form2)
        layout.addWidget(info_group)
        
        # --- 2. Edit Note Section (General) ---
        note_group = QGroupBox("📝 Note Générale (Facture / BL)")
        note_group.setStyleSheet("QGroupBox { font-weight: bold; color: #2980b9; border: 1px solid #2980b9; border-radius: 6px; margin-top: 10px; }")
        note_layout = QVBoxLayout(note_group)
        
        self.txt_note = QTextEdit()
        self.txt_note.setPlaceholderText("Note générale sur la réception...")
        self.txt_note.setPlainText(self.header.get('Variance_Notes', ''))
        self.txt_note.setMaximumHeight(60)
        
        btn_save_note = QPushButton("Enregistrer Note Générale")
        btn_save_note.setFixedWidth(200)
        btn_save_note.clicked.connect(self.save_general_note)
        
        note_layout.addWidget(self.txt_note)
        note_layout.addWidget(btn_save_note, alignment=Qt.AlignRight)
        
        layout.addWidget(note_group)

        # --- 3. Products Table ---
        prod_layout = QHBoxLayout()
        lbl_table = QLabel("📦 Produits avec Réclamations (Non-Conformes) :")
        lbl_table.setStyleSheet("font-weight: bold; font-size: 14px; margin-top: 10px;")
        prod_layout.addWidget(lbl_table)
        prod_layout.addStretch()
        
        # زر تعديل ملاحظة المنتج
        btn_edit_prod_note = QPushButton("Modifier Note")
        btn_edit_prod_note.setIcon(qta.icon('fa5s.edit', color='white'))
        btn_edit_prod_note.setStyleSheet("background-color: #f39c12; color: white; font-weight: bold; padding: 5px 10px;")
        btn_edit_prod_note.clicked.connect(self.edit_product_note)
        
        # زر حذف الملاحظة (جديد)
        btn_remove_note = QPushButton("Supprimer Note(s)")
        btn_remove_note.setIcon(qta.icon('fa5s.trash', color='white'))
        btn_remove_note.setStyleSheet("background-color: #c0392b; color: white; font-weight: bold; padding: 5px 10px;")
        btn_remove_note.clicked.connect(self.remove_selected_notes)
        
        prod_layout.addWidget(btn_edit_prod_note)
        prod_layout.addWidget(btn_remove_note)
        
        layout.addLayout(prod_layout)

        self.table = QTableWidget()
        cols = ["ID", "Produit", "Lot", "Qté", "Note / Réclamation"]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents) # Product Name
        self.table.setAlternatingRowColors(True)
        
        # إعدادات التحديد المتعدد ومنع التعديل المباشر
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection) # يسمح باختيار متعدد
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers) # يمنع ظهور حقل الكتابة عند النقر المزدوج
        self.table.setColumnHidden(0, True) # إخفاء عمود ID
        
        self.table.doubleClicked.connect(self.edit_product_note)
        
        self.populate_table()
        layout.addWidget(self.table)

        # --- 4. Close Button ---
        btn_close = QPushButton("Fermer")
        btn_close.setFixedWidth(120)
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close, alignment=Qt.AlignRight)

    def populate_table(self):
        self.table.setRowCount(0)
        
        # الفلترة: عرض المنتجات التي تحتوي على ملاحظة فقط
        problematic_items = [
            b for b in self.batches 
            if b.get('Reception_Note') and str(b.get('Reception_Note')).strip() != ''
        ]

        for row, item in enumerate(problematic_items):
            self.table.insertRow(row)
            
            batch_id = item.get('Batch_ID')
            prod_name = f"{item.get('Product_Name')} (Code: {item.get('Internal_Barcode')})"
            lot = str(item.get('Lot_Number', ''))
            qty = format_quantity(item.get('Quantity_Initial', 0), item.get('Stock_Unit', 'U'))
            note = str(item.get('Reception_Note', ''))
            
            self.table.setItem(row, 0, QTableWidgetItem(str(batch_id)))
            self.table.setItem(row, 1, QTableWidgetItem(prod_name))
            self.table.setItem(row, 2, QTableWidgetItem(lot))
            self.table.setItem(row, 3, QTableWidgetItem(qty))
            
            note_item = QTableWidgetItem(note)
            note_item.setForeground(QBrush(QColor("#c0392b"))) # أحمر
            note_item.setFont(QFont("Segoe UI", 9, QFont.Bold))
            self.table.setItem(row, 4, note_item)

    def save_general_note(self):
        """حفظ الملاحظة العامة للرأس"""
        new_note = self.txt_note.toPlainText().strip()
        if hasattr(self.manager.reception, 'update_variance_note'):
            if self.manager.reception.update_variance_note(self.br_id, new_note):
                QMessageBox.information(self, "Succès", "Note générale mise à jour.")
            else:
                QMessageBox.critical(self, "Erreur", "Échec de la mise à jour.")

    def edit_product_note(self):
        """فتح نافذة لتعديل ملاحظة المنتج المحدد"""
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.warning(self, "Sélection", "Veuillez sélectionner une ligne.")
            return
        
        # نأخذ أول سطر محدد فقط للتعديل النصي
        row = rows[0].row()
        
        batch_id = int(self.table.item(row, 0).text())
        prod_name = self.table.item(row, 1).text()
        current_note = self.table.item(row, 4).text()
        
        text, ok = QInputDialog.getMultiLineText(
            self, 
            "Modifier Note Produit", 
            f"Note pour : {prod_name}", 
            current_note
        )
        
        if ok:
            text = text.strip()
            # إذا مسح النص، نعتبره حذفاً
            if not text:
                self.remove_note_by_id(batch_id)
                return

            if self.manager.reception.update_batch_note(batch_id, text):
                # تحديث الذاكرة
                for b in self.batches:
                    if b.get('Batch_ID') == batch_id:
                        b['Reception_Note'] = text
                        break
                self.populate_table() # إعادة تحميل الجدول
                QMessageBox.information(self, "Succès", "Note mise à jour.")
            else:
                QMessageBox.critical(self, "Erreur", "Échec de la mise à jour.")

    def remove_selected_notes(self):
        """حذف الملاحظات للمنتجات المحددة (تحديد متعدد)"""
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.warning(self, "Sélection", "Veuillez sélectionner un ou plusieurs produits.")
            return

        count = len(rows)
        confirm = QMessageBox.question(
            self, "Confirmation", 
            f"Voulez-vous supprimer la réclamation pour {count} produit(s) ?\n"
            "Ils seront retirés de cette liste.",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if confirm == QMessageBox.Yes:
            success_count = 0
            for index in rows:
                row = index.row()
                batch_id = int(self.table.item(row, 0).text())
                
                # تحديث قاعدة البيانات (جعل الملاحظة فارغة)
                if self.manager.reception.update_batch_note(batch_id, ""):
                    # تحديث الذاكرة
                    for b in self.batches:
                        if b.get('Batch_ID') == batch_id:
                            b['Reception_Note'] = ""
                            break
                    success_count += 1
            
            if success_count > 0:
                self.populate_table() # إعادة تحميل الجدول لإخفاء المنتجات التي تم إصلاحها
                QMessageBox.information(self, "Succès", f"{success_count} réclamation(s) supprimée(s).")

    def remove_note_by_id(self, batch_id):
        """دالة مساعدة لحذف ملاحظة واحدة"""
        if self.manager.reception.update_batch_note(batch_id, ""):
            for b in self.batches:
                if b.get('Batch_ID') == batch_id:
                    b['Reception_Note'] = ""
                    break
            self.populate_table()
            QMessageBox.information(self, "Succès", "Réclamation supprimée.")
