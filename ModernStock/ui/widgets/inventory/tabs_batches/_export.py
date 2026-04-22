# ui/widgets/inventory/tabs_batches/_export.py
"""
تصدير البيانات: طباعة الملصقات، Excel، PDF
"""

import logging
import csv
from datetime import date

from PySide6.QtWidgets import QMessageBox, QInputDialog, QFileDialog
from PySide6.QtCore import Qt

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

def get_table_data(self):
    """إرجاع (columns, rows) مع استبعاد الأعمدة المالية للتقني"""
    try:
        role = self.window().current_user.get('Role', 'Technician')
    except Exception:
        role = 'Technician'

    is_tech = (role == 'Technician')

    columns = []
    for c in range(self.table.columnCount()):
        if is_tech and c in [11, 12]:
            continue
        item = self.table.horizontalHeaderItem(c)
        columns.append(item.text() if item else f"Col {c}")

    rows = []
    for r in range(self.table.rowCount()):
        if self.table.isRowHidden(r):
            continue
        row_data = []
        for c in range(self.table.columnCount()):
            if is_tech and c in [11, 12]:
                continue
            item = self.table.item(r, c)
            row_data.append(item.text() if item else "")
        rows.append(row_data)

    return columns, rows


# ---------------------------------------------------------------------------
# طباعة الملصقات
# ---------------------------------------------------------------------------

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
        current_qty   = float(data.get('Quantity_Current', 0))
        default_copies = max(1, int(current_qty))

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
    """تصدير PDF بتخطيط أفقي مع التفاف النصوص الطويلة"""
    if self.table.rowCount() == 0:
        QMessageBox.warning(self, "Attention", "Aucune donnée à exporter.")
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
        style_left   = ParagraphStyle(
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
                f"État du Stock par Lot - {date.today().strftime('%d/%m/%Y')}",
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

        # بناء رأس الجدول
        headers = [
            self.table.horizontalHeaderItem(i).text()
            for i in range(self.table.columnCount())
        ]
        header_row = [Paragraph(f"<b>{h}</b>", style_center) for h in headers]
        data = [header_row]

        # الصفوف
        TEXT_COLS = {0, 1, 2, 3, 4, 10, 13, 14}
        for r in range(self.table.rowCount()):
            if self.table.isRowHidden(r):
                continue
            row_data = []
            for c in range(self.table.columnCount()):
                item = self.table.item(r, c)
                text = item.text() if item else ""
                style = style_left if c in TEXT_COLS else style_center
                row_data.append(Paragraph(text, style))
            data.append(row_data)

        # صف المجموع
        data.append(
            [Paragraph("<b>TOTAL</b>", style_left)] + [""] * 14
        )

        col_widths = [
            140, 45, 45, 40, 45, 35, 45, 40,
            45,  32, 50, 35, 45, 35, 45
        ]

        pdf_table = Table(data, colWidths=col_widths, repeatRows=1)
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
            ('SPAN',         (0, -1), (4, -1)),
        ])

        # تلوين متعاقب للصفوف (Zebra)
        for i in range(1, len(data) - 1):
            if i % 2 == 0:
                style.add('BACKGROUND', (0, i), (-1, i), colors.whitesmoke)

        pdf_table.setStyle(style)
        elements.append(pdf_table)
        doc.build(elements)

    except Exception as e:
        logging.error(f"PDF Export Error: {e}", exc_info=True)
        QMessageBox.critical(self, "Erreur", f"Erreur export PDF: {str(e)}")
