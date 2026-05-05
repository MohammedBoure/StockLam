# ui\widgets\supplier\supplier_stats_tab.py

import logging
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, 
    QHeaderView, QPushButton, QLabel, QComboBox, QDateEdit, QFrame, 
    QMessageBox, QDialog, QFormLayout, QLineEdit, QDoubleSpinBox, QCheckBox
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QColor, QFont, QBrush
import qtawesome as qta
from database.system_logger import active_user_id

# --- ReportLab PDF ---
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.units import cm
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False

# ==============================================================================
# النافذة المنبثقة لإضافة دفعة (مع ميزة الربط بالفاتورة)
# ==============================================================================
class AddPaymentDialog(QDialog):
    def __init__(self, supplier_id, manager, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ajouter un Versement")
        self.resize(500, 400)
        self.supplier_id = supplier_id
        self.manager = manager
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        # 1. التاريخ
        self.date_edit = QDateEdit(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        
        # 2. المبلغ
        self.amount_spin = QDoubleSpinBox()
        self.amount_spin.setRange(0, 1000000000)
        self.amount_spin.setDecimals(2)
        self.amount_spin.setSuffix(" DA")
        
        # 3. طريقة الدفع
        self.method_combo = QComboBox()
        self.method_combo.addItems(["Espèce", "Chèque", "Virement", "Versement", "Autre"])
        
        # 4. المرجع
        self.ref_edit = QLineEdit()
        self.ref_edit.setPlaceholderText("Ex: Chèque N° 12345")
        
        # 5. ربط بفاتورة (ميزة جديدة)
        self.chk_link_br = QCheckBox("Lier à une Facture / BR spécifique")
        self.chk_link_br.toggled.connect(self.toggle_br_combo)
        
        self.combo_br = QComboBox()
        self.combo_br.setEnabled(False)
        self.load_receptions() # تحميل الفواتير
        
        # 6. ملاحظات
        self.note_edit = QLineEdit()

        # إضافة العناصر للنموذج
        form.addRow("Date:", self.date_edit)
        form.addRow("Montant:", self.amount_spin)
        form.addRow("Mode:", self.method_combo)
        form.addRow("Référence:", self.ref_edit)
        form.addRow("", self.chk_link_br)
        form.addRow("Facture Cible:", self.combo_br)
        form.addRow("Note:", self.note_edit)
        
        layout.addLayout(form)
        
        # الأزرار
        btn_layout = QHBoxLayout()
        btn_save = QPushButton("Enregistrer")
        btn_save.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; padding: 6px;")
        btn_save.clicked.connect(self.accept)
        
        btn_cancel = QPushButton("Annuler")
        btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_save)
        layout.addLayout(btn_layout)

    def load_receptions(self):
        """تحميل فواتير المورد المتاحة للربط"""
        try:
            if hasattr(self.manager.suppliers, 'get_supplier_receptions_for_linking'):
                receptions = self.manager.suppliers.get_supplier_receptions_for_linking(self.supplier_id)
                self.combo_br.clear()
                for r in receptions:
                    # تنسيق النص: Ref (Date) - Amount
                    ref = r.get('Supplier_Invoice_Ref') or f"BR #{r['BR_ID']}"
                    date_str = str(r['Reception_Date'])[:10]
                    amount = float(r['Invoice_Total_TTC'] or 0)
                    
                    display_text = f"{ref} ({date_str}) - {amount:,.2f} DA"
                    self.combo_br.addItem(display_text, r['BR_ID'])
        except Exception as e:
            logging.error(f"Error loading BRs for linking: {e}")

    def toggle_br_combo(self, checked):
        self.combo_br.setEnabled(checked)

    def get_data(self):
        br_id = self.combo_br.currentData() if self.chk_link_br.isChecked() else None
        
        return {
            'Payment_Date': self.date_edit.date().toString("yyyy-MM-dd"),
            'Amount': self.amount_spin.value(),
            'Payment_Method': self.method_combo.currentText(),
            'Reference': self.ref_edit.text(),
            'Notes': self.note_edit.text(),
            'BR_ID': br_id
        }

# ==============================================================================
# التبويب الرئيسي لإحصائيات الموردين (États Fournisseurs)
# ==============================================================================
class SupplierStatsTab(QWidget):
    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # --- Top Filter Bar ---
        filter_frame = QFrame()
        filter_frame.setStyleSheet("background-color: #f8f9fa; border-radius: 5px; padding: 5px;")
        filter_layout = QHBoxLayout(filter_frame)

        self.combo_supplier = QComboBox()
        self.combo_supplier.setMinimumWidth(250)
        self.load_suppliers()

        self.date_from = QDateEdit(QDate.currentDate().addMonths(-3))
        self.date_from.setCalendarPopup(True)
        self.date_to = QDateEdit(QDate.currentDate())
        self.date_to.setCalendarPopup(True)

        btn_search = QPushButton("Rechercher")
        btn_search.setIcon(qta.icon("fa5s.search"))
        btn_search.clicked.connect(self.load_data)

        filter_layout.addWidget(QLabel("Fournisseur:"))
        filter_layout.addWidget(self.combo_supplier)
        filter_layout.addWidget(QLabel("Du:"))
        filter_layout.addWidget(self.date_from)
        filter_layout.addWidget(QLabel("Au:"))
        filter_layout.addWidget(self.date_to)
        filter_layout.addWidget(btn_search)
        filter_layout.addStretch()

        layout.addWidget(filter_frame)

        # --- Buttons Bar ---
        action_layout = QHBoxLayout()
        
        btn_pdf = QPushButton("📄 Exporter PDF")
        btn_pdf.setStyleSheet("background-color: #c0392b; color: white; font-weight: bold; padding: 6px;")
        btn_pdf.setIcon(qta.icon("fa5s.file-pdf", color="white"))
        btn_pdf.clicked.connect(self.export_pdf)

        action_layout.addStretch()
        action_layout.addWidget(btn_pdf)
        
        layout.addLayout(action_layout)

        # --- Table ---
        self.table = QTableWidget()
        cols = ["Date", "Observation (Ref / Type)", "Montant Achat (DA)", "Versement (DA)", "Solde (DA)"]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        
        layout.addWidget(self.table)
        
        # Summary Labels
        self.lbl_totals = QLabel("Total Achats: 0.00 DA | Total Versements: 0.00 DA | Reste à Payer: 0.00 DA")
        self.lbl_totals.setStyleSheet("font-weight: bold; font-size: 14px; color: #2c3e50; margin-top: 10px;")
        self.lbl_totals.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_totals)

    def load_suppliers(self):
        self.combo_supplier.clear()
        if hasattr(self.manager, 'suppliers'):
            suppliers = self.manager.suppliers.get_all_suppliers()
            for s in suppliers:
                self.combo_supplier.addItem(s['Supplier_Name'], s['Supplier_ID'])

    def get_current_user_id(self):
        user_id = active_user_id.get()
        if user_id:
            return user_id

        parent_widget = self.parent()
        while parent_widget:
            current_user = getattr(parent_widget, 'current_user', None)
            if isinstance(current_user, dict):
                return current_user.get('User_ID') or current_user.get('id')
            parent_widget = parent_widget.parent()
        return None

    def load_data(self):
        supplier_id = self.combo_supplier.currentData()
        if not supplier_id: return

        d_start = self.date_from.date().toString("yyyy-MM-dd")
        d_end = self.date_to.date().toString("yyyy-MM-dd")

        if hasattr(self.manager.suppliers, 'get_supplier_account_statement'):
            data = self.manager.suppliers.get_supplier_account_statement(supplier_id, d_start, d_end)
        else:
            data = []
            logging.warning("Function get_supplier_account_statement not found in manager.")
        
        self.table.setRowCount(0)
        balance = 0.0
        t_achat = 0.0
        t_vers = 0.0

        for row_idx, item in enumerate(data):
            self.table.insertRow(row_idx)
            
            # Date
            d = item.get('Date_Op')
            date_str = d.strftime("%Y-%m-%d") if d else ""
            self.table.setItem(row_idx, 0, QTableWidgetItem(date_str))
            
            # Observation
            obs = item.get('Observation', '')
            self.table.setItem(row_idx, 1, QTableWidgetItem(str(obs)))
            
            # Achat
            achat = float(item.get('Montant_Achat') or 0)
            t_achat += achat
            item_achat = QTableWidgetItem(f"{achat:,.2f}" if achat > 0 else "-")
            item_achat.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if achat > 0: item_achat.setForeground(QBrush(QColor("#c0392b"))) # Red
            self.table.setItem(row_idx, 2, item_achat)
            
            # Versement
            vers = float(item.get('Montant_Versement') or 0)
            t_vers += vers
            item_vers = QTableWidgetItem(f"{vers:,.2f}" if vers > 0 else "-")
            item_vers.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if vers > 0: item_vers.setForeground(QBrush(QColor("#27ae60"))) # Green
            self.table.setItem(row_idx, 3, item_vers)
            
            # Solde (Running Balance)
            balance += (achat - vers)
            item_bal = QTableWidgetItem(f"{balance:,.2f}")
            item_bal.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            item_bal.setFont(QFont("Arial", 9, QFont.Bold))
            self.table.setItem(row_idx, 4, item_bal)

        self.lbl_totals.setText(
            f"Total Achats: {t_achat:,.2f} DA  |  Total Versements: {t_vers:,.2f} DA  |  Solde Période: {balance:,.2f} DA"
        )

    def add_payment(self):
        supplier_id = self.combo_supplier.currentData()
        if not supplier_id:
            QMessageBox.warning(self, "Erreur", "Veuillez sélectionner un fournisseur.")
            return

        # نمرر supplier_id و manager للنافذة
        dlg = AddPaymentDialog(supplier_id, self.manager, self)
        
        if dlg.exec():
            data = dlg.get_data()
            data['Supplier_ID'] = supplier_id
            data['Created_By'] = self.get_current_user_id()
            
            if hasattr(self.manager.suppliers, 'add_payment'):
                success, msg = self.manager.suppliers.add_payment(data)
                if success:
                    QMessageBox.information(self, "Succès", msg)
                    self.load_data()
                else:
                    QMessageBox.critical(self, "Erreur", msg)
            else:
                QMessageBox.critical(self, "Erreur", "Fonction add_payment introuvable dans le Manager.")

    def export_pdf(self):
        if not HAS_REPORTLAB:
            QMessageBox.warning(self, "Erreur", "ReportLab n'est pas installé.")
            return

        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(self, "Enregistrer PDF", "Etat_Fournisseur.pdf", "PDF Files (*.pdf)")
        if not path: return

        try:
            doc = SimpleDocTemplate(path, pagesize=A4, rightMargin=20, leftMargin=20, topMargin=30, bottomMargin=30)
            elements = []
            styles = getSampleStyleSheet()

            # Title
            title = Paragraph(f"<b>ÉTAT FOURNISSEUR: {self.combo_supplier.currentText()}</b>", styles['Heading1'])
            elements.append(title)
            elements.append(Paragraph(f"Période: {self.date_from.text()} au {self.date_to.text()}", styles['Normal']))
            elements.append(Spacer(1, 0.5 * cm))

            # Table Data
            data = [["Date", "Observation", "Achat", "Versement", "Solde"]]
            
            # Fetch data from table widget
            for r in range(self.table.rowCount()):
                row_data = []
                for c in range(5):
                    item = self.table.item(r, c)
                    row_data.append(item.text() if item else "")
                data.append(row_data)
            
            # Totals Row
            # Parsing totals from label text (simple parsing)
            try:
                parts = self.lbl_totals.text().split('|')
                tot_achat = parts[0].split(':')[1].strip()
                tot_vers = parts[1].split(':')[1].strip()
                tot_reste = parts[2].split(':')[1].strip()
            except:
                tot_achat = "0.00 DA"
                tot_vers = "0.00 DA"
                tot_reste = "0.00 DA"

            data.append(["TOTAL", "", tot_achat, tot_vers, tot_reste])

            t = Table(data, colWidths=[2.5*cm, 8*cm, 2.5*cm, 2.5*cm, 3*cm])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('ALIGN', (2, 1), (-1, -1), 'RIGHT'), # Align numbers right
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'), # Totals row bold
            ]))
            
            elements.append(t)
            doc.build(elements)
            
            QMessageBox.information(self, "Succès", "PDF généré avec succès.")
            import os
            os.startfile(path)
            
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur PDF: {e}")
