# ui/widgets/inventory/tabs_batches/_export.py
"""
تصدير البيانات: طباعة الملصقات، Excel، PDF
"""

import logging
import csv
from datetime import date

from PySide6.QtWidgets import QMessageBox, QInputDialog, QFileDialog
from PySide6.QtCore import Qt
from ui.formatting import format_money, format_quantity, quantity_to_int

try:
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT, TA_CENTER
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False


# ---------------------------------------------------------------------------
# استخراج بيانات الجدول (مشترك بين Excel و PDF)
# ---------------------------------------------------------------------------

EXPORT_COLUMN_KEYS = {
    0: 'Product_Name',
    1: 'Quantity_Current',
    2: 'Lot_Number',
    3: 'Expiry_Date',
    4: 'Quantity_Initial',
    5: 'Internal_Barcode',
    6: 'Unit_Price_Received',
    7: 'Unit_Price_Received_TTC',
    8: 'Total_Value',
    9: 'Location_Name',
    10: 'Family_Name',
    11: 'Manuf_Name',
    12: 'Automate_Name',
    13: 'Supplier_Name',
    14: 'PO_ID',
    15: 'Date_Received',
}


def _is_technician(self):
    try:
        role = self.window().current_user.get('Role', 'Technician')
    except Exception:
        role = 'Technician'
    return role == 'Technician'


def _export_column_indices(self):
    is_tech = _is_technician(self)
    return [
        c for c in range(self.table.columnCount())
        if not (is_tech and c in [6, 7, 8])
    ]


def _header_text(self, column_index):
    item = self.table.horizontalHeaderItem(column_index)
    return item.text() if item else f"Col {column_index}"


def _format_export_cell(row, column_index):
    if column_index == 1:
        return format_quantity(row.get('Quantity_Current', 0))
    if column_index == 2:
        return row.get('Lot_Number', '') or ''
    if column_index == 3:
        return str(row.get('Expiry_Date', ''))[:10]
    if column_index == 4:
        return format_quantity(row.get('Quantity_Initial', 0))
    if column_index == 5:
        return row.get('Internal_Barcode') or row.get('Barcode') or ''
    if column_index == 6:
        return format_money(float(row.get('Unit_Price_Received', 0) or 0))
    if column_index == 7:
        price = float(row.get('Unit_Price_Received', 0) or 0)
        discount = float(row.get('Discount_Percent', 0) or 0) / 100.0
        tax = float(row.get('Tax_Rate_Percent', 0) or 0) / 100.0
        return format_money(price * (1 - discount) * (1 + tax))
    if column_index == 8:
        qty = float(row.get('Quantity_Current', 0) or 0)
        price = float(row.get('Unit_Price_Received', 0) or 0)
        discount = float(row.get('Discount_Percent', 0) or 0) / 100.0
        tax = float(row.get('Tax_Rate_Percent', 0) or 0) / 100.0
        return format_money(qty * price * (1 - discount) * (1 + tax))
    if column_index == 15:
        return str(row.get('Date_Received') or row.get('Created_At', ''))[:10]

    key = EXPORT_COLUMN_KEYS.get(column_index)
    return row.get(key, '') if key else ''


def get_table_data(self):
    """Return all rows matching the current filters, not only lazy-loaded table rows."""
    column_indices = _export_column_indices(self)
    columns = [_header_text(self, c) for c in column_indices]

    rows = []
    for row in getattr(self, 'filtered_data', []) or []:
        rows.append([
            str(_format_export_cell(row, c) or '')
            for c in column_indices
        ])

    return columns, rows


def print_batch_label(self):
    """طباعة ملصق لكل صف محدد"""
    selected_rows = self.table.selectionModel().selectedRows()

    if not selected_rows:
        current_idx = self.table.currentIndex()
        if current_idx.isValid():
            selected_rows = [current_idx]
        else:
            QMessageBox.warning(self, "Attention", "Veuillez sélectionner au moins un lot.")
            return

    for index in selected_rows:
        row  = index.row()
        item = self.table.item(row, 0)
        if not item:
            continue
        data = item.data(Qt.UserRole)
        if not data:
            continue

        product_name  = data.get('Product_Name', 'Produit')
        lot_number    = data.get('Lot_Number', '')
        current_qty   = quantity_to_int(data.get('Quantity_Current', 0))
        default_copies = max(1, current_qty)

        qty, ok = QInputDialog.getInt(
            self,
            f"Étiquette : {product_name}",
            f"Nombre de copies pour le lot {lot_number}:",
            default_copies, 1, 9999
        )
        if ok:
            self.manager.printer.print_label(
                product_name,
                data.get('Internal_Barcode'),
                lot_number,
                data.get('Expiry_Date'),
                qty
            )
        else:
            break  # إيقاف الحلقة إذا ألغى المستخدم


# ---------------------------------------------------------------------------
# تصدير Excel / CSV
# ---------------------------------------------------------------------------

def export_to_excel(self):
    """تصدير بيانات الجدول إلى Excel أو CSV"""
    cols, rows = get_table_data(self)
    if not rows:
        QMessageBox.warning(self, "Export", "Aucune donnée à exporter.")
        return

    filename, _ = QFileDialog.getSaveFileName(
        self, "Exporter Excel",
        f"Stock_Lots_{date.today()}.xlsx",
        "Fichiers Excel (*.xlsx);;Fichiers CSV (*.csv)"
    )
    if not filename:
        return

    try:
        if filename.endswith('.xlsx') and HAS_PANDAS:
            df = pd.DataFrame(rows, columns=cols)
            for col_name in ['Stock (Actuel)', 'Qté Init.', 'Prix U.', 'Valeur (DA)']:
                if col_name in df.columns:
                    df[col_name] = (
                        df[col_name]
                        .astype(str)
                        .str.replace(r'[^\d\.\-]', '', regex=True)
                    )
                    df[col_name] = pd.to_numeric(df[col_name], errors='coerce').fillna(0)

            with pd.ExcelWriter(filename, engine='xlsxwriter') as writer:
                df.to_excel(writer, sheet_name='Stock', index=False)
                ws = writer.sheets['Stock']
                for idx, col in enumerate(df.columns):
                    max_len = max(df[col].astype(str).map(len).max(), len(col)) + 2
                    ws.set_column(idx, idx, max_len)
        else:
            if not filename.endswith('.csv'):
                filename += ".csv"
            with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f, delimiter=';')
                writer.writerow(cols)
                writer.writerows(rows)

    except Exception as e:
        logging.error(f"Erreur Export Excel: {e}")
        QMessageBox.critical(self, "Erreur", f"Échec: {str(e)}")


# ---------------------------------------------------------------------------
# تصدير PDF (A4 Landscape)
# ---------------------------------------------------------------------------

def export_to_pdf(self):
    """Export the full currently filtered batch list to PDF."""
    cols, rows = get_table_data(self)
    if not rows:
        QMessageBox.warning(self, "Attention", "Aucune donnÃ©e Ã  exporter.")
        return

    filename, _ = QFileDialog.getSaveFileName(
        self, "Exporter PDF",
        f"Etat_Stock_{date.today().strftime('%Y-%m-%d')}.pdf",
        "PDF Files (*.pdf)"
    )
    if not filename:
        return

    try:
        doc = SimpleDocTemplate(
            filename,
            pagesize=landscape(A4),
            rightMargin=10, leftMargin=10,
            topMargin=10,  bottomMargin=10
        )

        styles = getSampleStyleSheet()
        style_left = ParagraphStyle(
            'CellText', parent=styles['Normal'],
            fontName='Helvetica', fontSize=6, leading=7,
            alignment=TA_LEFT, splitLongWords=1, wordWrap='CJK'
        )
        style_center = ParagraphStyle(
            'CellCenter', parent=styles['Normal'],
            fontName='Helvetica', fontSize=6, leading=7,
            alignment=TA_CENTER
        )

        elements = []
        elements.append(
            Paragraph(
                f"Etat du Stock par Lot - {date.today().strftime('%d/%m/%Y')}",
                styles['Title']
            )
        )
        elements.append(
            Paragraph(
                f"<b>{self.lbl_total_value.text()}</b> | Famille: "
                f"{self.combo_family.currentText()}",
                styles['Normal']
            )
        )
        elements.append(Spacer(1, 10))

        header_row = [Paragraph(f"<b>{h}</b>", style_center) for h in cols]
        data = [header_row]

        text_headers = {
            'Produit', 'Famille', 'Fabricant', 'Automate', 'Fournisseur',
            'Lot', 'Code-Barres', 'PO', 'Emplacement'
        }
        for row in rows:
            row_data = []
            for header, value in zip(cols, row):
                style = style_left if header in text_headers else style_center
                row_data.append(Paragraph(str(value), style))
            data.append(row_data)

        data.append([Paragraph("<b>TOTAL</b>", style_left)] + [""] * (len(cols) - 1))

        base_widths = {
            'Produit': 140,
            'Famille': 45,
            'Fabricant': 45,
            'Automate': 40,
            'Fournisseur': 45,
            'Stock (Actuel)': 35,
            'Date EntrÃ©e': 45,
            'Lot': 40,
            'Expiration': 45,
            'QtÃ© Init.': 32,
            'Code-Barres': 50,
            'Prix U.': 35,
            'Valeur (DA)': 45,
            'PO': 35,
            'Emplacement': 45,
        }
        col_widths = [base_widths.get(col, 45) for col in cols]

        pdf_table = Table(data, colWidths=col_widths, repeatRows=1)
        span_end = min(4, len(cols) - 1)
        style = TableStyle([
            ('BACKGROUND',   (0, 0),  (-1, 0),  colors.grey),
            ('VALIGN',       (0, 0),  (-1, -1), 'TOP'),
            ('GRID',         (0, 0),  (-1, -1), 0.25, colors.black),
            ('BOX',          (0, 0),  (-1, -1), 0.5,  colors.black),
            ('LEFTPADDING',  (0, 0),  (-1, -1), 2),
            ('RIGHTPADDING', (0, 0),  (-1, -1), 2),
            ('TOPPADDING',   (0, 0),  (-1, -1), 2),
            ('BOTTOMPADDING',(0, 0),  (-1, -1), 2),
            ('BACKGROUND',   (0, -1), (-1, -1), colors.beige),
            ('SPAN',         (0, -1), (span_end, -1)),
        ])

        for i in range(1, len(data) - 1):
            if i % 2 == 0:
                style.add('BACKGROUND', (0, i), (-1, i), colors.whitesmoke)

        pdf_table.setStyle(style)
        elements.append(pdf_table)
        doc.build(elements)

    except Exception as e:
        logging.error(f"PDF Export Error: {e}", exc_info=True)
        QMessageBox.critical(self, "Erreur", f"Erreur export PDF: {str(e)}")
