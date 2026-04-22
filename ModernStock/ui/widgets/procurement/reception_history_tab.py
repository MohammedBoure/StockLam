# ui/widgets/procurement/reception_history_tab.py

import os
import logging
import traceback
from datetime import datetime
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QFrame,QMenu,
                               QTableWidgetItem, QHeaderView, QPushButton, QLineEdit,QInputDialog,
                               QMessageBox, QDialog, QLabel, QFormLayout, QFileDialog,
                               QDateEdit, QComboBox)
from PySide6.QtGui import QColor, QFont,QAction
from PySide6.QtCore import Qt, QDate, Signal 

# --- ReportLab Imports for PDF ---
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors, utils
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
    from reportlab.lib.units import cm
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False

from .reception_dialog import ReceptionDialog

class ReceptionHistoryTab(QWidget):
    """
    تبويب يعرض سجل جميع عمليات الاستلام المكتملة.
    """
    request_create_avoir = Signal(dict)
    def __init__(self, manager):
        super().__init__()
        self.manager = manager
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # --- Toolbar ---
        toolbar = QHBoxLayout()
        
        self.lbl_date = QLabel("Date :")
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDisplayFormat("yyyy-MM-dd")
        current_date = QDate.currentDate()
        self.date_from.setDate(QDate(current_date.year(), current_date.month(), 1))
        self.date_from.dateChanged.connect(self.load_data)

        self.lbl_to = QLabel("à")
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDisplayFormat("yyyy-MM-dd")
        self.date_to.setDate(current_date)
        self.date_to.dateChanged.connect(self.load_data)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Rechercher...")
        self.search_input.textChanged.connect(self.load_data)
        
        # --- [جديد] فلتر الموردين ---
        self.supplier_filter = QComboBox()
        self.supplier_filter.setFixedWidth(200)
        self.supplier_filter.addItem("Tous les fournisseurs")
        self.load_suppliers() # تعبئة القائمة
        self.supplier_filter.currentTextChanged.connect(self.load_data)
        # -----------------------------

        self.status_filter = QComboBox()
        self.status_filter.addItems(["Tous", "Terminée", "Variance détectée", "Pending Audit", "Avec notes"])
        self.status_filter.currentTextChanged.connect(self.load_data)
        
        btn_refresh = QPushButton("🔄 Actualiser")
        btn_refresh.clicked.connect(self.load_data)
        
        btn_edit = QPushButton("✏️ Modifier")
        btn_edit.setStyleSheet("background-color: #f39c12; color: white; font-weight: bold;")
        btn_edit.clicked.connect(self.edit_reception)

        btn_pdf = QPushButton("📄 PDF")
        btn_pdf.setStyleSheet("background-color: #e74c3c; color: white; font-weight: bold;")
        btn_pdf.clicked.connect(self.export_reception_pdf)
        
        toolbar.addWidget(self.lbl_date)
        toolbar.addWidget(self.date_from)
        toolbar.addWidget(self.lbl_to)
        toolbar.addWidget(self.date_to)
        toolbar.addSpacing(10)
        toolbar.addWidget(self.search_input)
        toolbar.addWidget(self.supplier_filter) # إضافة الفلتر هنا
        toolbar.addWidget(self.status_filter)
        toolbar.addWidget(btn_refresh)
        toolbar.addWidget(btn_edit)
        toolbar.addWidget(btn_pdf)
        
        layout.addLayout(toolbar)

        # --- Table ---
        self.table = QTableWidget()
        columns = ["ID (BR)", "Réf. Facture", "Fournisseur", "Date", "Total HT", "Total TVA", "Remise", "Total TTC", "Origine (PO)"]    
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setSectionsClickable(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setColumnHidden(0, True)
        
        # 2. تفعيل القائمة المخصصة (Right Click)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        
        self.table.doubleClicked.connect(self.edit_reception)
        
        layout.addWidget(self.table)
        self.load_data()

    def load_suppliers(self):
        """[جديد] تحميل قائمة الموردين في الفلتر"""
        try:
            # نتأكد من وجود مدير الموردين
            if hasattr(self.manager, 'suppliers'):
                suppliers = self.manager.suppliers.get_all_suppliers()
                for s in suppliers:
                    self.supplier_filter.addItem(s['Supplier_Name'], s['Supplier_ID'])
        except Exception as e:
            logging.error(f"Erreur chargement fournisseurs history: {e}")

    def open_reclamation_dialog(self):
        """فتح نافذة صغيرة لإضافة ملاحظة عامة على الاستلام"""
        row = self.table.currentRow()
        if row < 0: return
        
        item = self.table.item(row, 0)
        if not item: return
        
        # استرجاع البيانات المخزنة (التي تحتوي الآن على Variance_Notes بفضل تعديل المدير)
        reception_data = item.data(Qt.UserRole)
        br_id = reception_data.get('BR_ID')
        current_note = reception_data.get('Variance_Notes', '')
        
        # فتح مربع حوار للنصوص المتعددة الأسطر
        text, ok = QInputDialog.getMultiLineText(
            self, 
            "Réclamation / Note Générale", 
            f"Saisir une note pour le Bon #{br_id} :", 
            current_note
        )
        
        if ok:
            # استدعاء دالة التحديث الموجودة بالفعل في المدير
            if hasattr(self.manager.reception, 'update_variance_note'):
                success = self.manager.reception.update_variance_note(br_id, text.strip())
                if success:
                    QMessageBox.information(self, "Succès", "Note enregistrée avec succès.")
                    self.load_data() # تحديث الجدول لإظهار التغييرات (الأيقونات أو الألوان)
                else:
                    QMessageBox.critical(self, "Erreur", "Échec de l'enregistrement.")
            else:
                QMessageBox.warning(self, "Erreur", "Fonction update_variance_note introuvable dans le Manager.")

    def show_context_menu(self, pos):
        index = self.table.indexAt(pos)
        if not index.isValid(): return

        menu = QMenu(self)
        
        # خيار التعديل
        action_edit = QAction("✏️ Modifier la réception", self)
        action_edit.triggered.connect(self.edit_reception)
        menu.addAction(action_edit)

        # [جديد] خيار إضافة/تعديل ملاحظة
        action_note = QAction("📝 Ajouter une Réclamation / Note", self)
        action_note.triggered.connect(self.open_reclamation_dialog)
        menu.addAction(action_note)

        menu.addSeparator()

        # خيار الـ PDF
        action_pdf = QAction("📄 Exporter PDF", self)
        action_pdf.triggered.connect(self.export_reception_pdf)
        menu.addAction(action_pdf)

        menu.addSeparator()

        # خيار الـ Avoir
        action_avoir = QAction("↩️ Créer un Avoir (Retour)", self)
        action_avoir.triggered.connect(self.trigger_create_avoir)
        menu.addAction(action_avoir)

        menu.exec(self.table.viewport().mapToGlobal(pos))

    def trigger_create_avoir(self):
        row = self.table.currentRow()
        if row < 0: return
        
        item = self.table.item(row, 0)
        if not item: return
        
        reception_basic = item.data(Qt.UserRole)
        br_id = reception_basic.get('BR_ID')

        full_data = self.manager.reception.get_reception_details(br_id)
        
        if full_data:
            self.request_create_avoir.emit(full_data)
        else:
            QMessageBox.warning(self, "Erreur", "Impossible de charger les détails.")

    def _create_centered_item(self, text, is_numeric=False):
        item = QTableWidgetItem()
        if is_numeric:
            try:
                val = float(str(text).replace(',', ''))
                item.setData(Qt.EditRole, val)
            except:
                item.setText(str(text))
        else:
            item.setText(str(text))
        
        item.setTextAlignment(Qt.AlignCenter)
        return item

    def _has_variance_notes(self, po_id: int) -> bool:
        try:
            with self.manager.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = "SELECT COUNT(*) FROM Inventory_Batches b JOIN Reception_Log rl ON b.BR_ID = rl.BR_ID WHERE rl.PO_ID = %s AND b.Reception_Note IS NOT NULL AND b.Reception_Note != ''"
                cursor.execute(query, (po_id,))
                count = cursor.fetchone()[0]
                return count > 0
        except Exception as e:
            logging.error(f"Error checking variance notes: {e}")
            return False
        
    def _has_po_notes(self, po_id: int) -> bool:
        try:
            with self.manager.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = "SELECT COUNT(*) FROM PO_Details WHERE PO_ID = %s AND Item_Note IS NOT NULL AND Item_Note != ''"
                cursor.execute(query, (po_id,))
                count = cursor.fetchone()[0]
                return count > 0
        except Exception as e:
            logging.error(f"Error checking PO notes: {e}")
            return False

    def load_data(self):
        """
        تحميل سجل الاستلام مع منع التكرار وفلترة البيانات.
        """
        try:
            logging.info("Actualisation de l'historique des réceptions...")
            self.table.setSortingEnabled(False)  # إيقاف الفرز مؤقتاً لتحسين الأداء
            
            # جلب البيانات الخام من المدير
            receptions = self.manager.reception.get_all_receptions()
            self.table.setRowCount(0)
            
            # 1. إعداد متغيرات الفلترة
            from_date = datetime.combine(self.date_from.date().toPyDate(), datetime.min.time())
            to_date = datetime.combine(self.date_to.date().toPyDate(), datetime.max.time())
            
            search_txt = self.search_input.text().lower().strip()
            filter_status = self.status_filter.currentText()
            
            # [جديد] الحصول على المورد المختار
            supplier_sel = self.supplier_filter.currentText()

            # 2. مجموعة لتتبع المعرفات المضافة (منع التكرار)
            added_ids = set()

            for reception in receptions:
                br_id = reception.get('BR_ID')
                if not br_id or br_id in added_ids:
                    continue  

                # 3. التحقق من التاريخ
                r_date = reception.get('Reception_Date')
                try:
                    current_r_date = None
                    if isinstance(r_date, str):
                        current_r_date = datetime.strptime(r_date[:10], '%Y-%m-%d')
                    elif hasattr(r_date, 'year'): 
                        current_r_date = datetime(r_date.year, r_date.month, r_date.day)
                    
                    if current_r_date and not (from_date <= current_r_date <= to_date):
                        continue
                except Exception:
                    pass 

                # 4. فلترة المورد (جديد)
                if supplier_sel != "Tous les fournisseurs" and reception.get('Supplier_Name') != supplier_sel:
                    continue

                # 5. البحث النصي
                full_search_str = f"{br_id} {reception.get('Supplier_Name', '')} {reception.get('Supplier_Invoice_Ref', '')} {reception.get('Supplier_BL_Ref', '')} {reception.get('PO_ID', '')}".lower()
                if search_txt and search_txt not in full_search_str:
                    continue
                
                # 6. فلترة الحالة
                po_id = reception.get('PO_ID')
                has_notes = False
                if po_id:
                    has_notes = (self._has_variance_notes(po_id) or self._has_po_notes(po_id))
                
                status_match = True
                db_status = reception.get('Status', 'Completed')

                if filter_status == "Avec notes":
                    if not has_notes: status_match = False
                elif filter_status == "Variance détectée":
                    if not self._has_variance_notes(po_id): status_match = False
                elif filter_status != "Tous" and filter_status != db_status:
                    status_match = False
                
                if not status_match:
                    continue

                # 7. إضافة السطر للجدول
                row = self.table.rowCount()
                self.table.insertRow(row)
                
                # حساب القيم المالية
                total_ht = float(reception.get('Invoice_Total_HT') or 0)
                total_tva = float(reception.get('Invoice_Total_TVA') or 0)
                total_ttc = float(reception.get('Invoice_Total_TTC') or 0)
                
                remise = float(reception.get('Total_Discount') or 0)
                if remise == 0 and total_ttc > 0:
                    remise = max(0.0, (total_ht + total_tva) - total_ttc)

                display_date = current_r_date.strftime('%Y-%m-%d') if current_r_date else str(r_date)

                ref_invoice = reception.get('Supplier_Invoice_Ref')
                ref_bl = reception.get('Supplier_BL_Ref')
                
                ref_invoice = str(ref_invoice).strip() if ref_invoice else None
                ref_bl = str(ref_bl).strip() if ref_bl else None

                display_ref = ref_invoice if ref_invoice else (ref_bl if ref_bl else '---')

                self.table.setItem(row, 0, self._create_centered_item(br_id))
                self.table.setItem(row, 1, self._create_centered_item(display_ref)) 
                self.table.setItem(row, 2, self._create_centered_item(reception.get('Supplier_Name', 'N/A')))
                self.table.setItem(row, 3, self._create_centered_item(display_date))
                self.table.setItem(row, 4, self._create_centered_item(f"{total_ht:,.2f} DA", is_numeric=True))
                self.table.setItem(row, 5, self._create_centered_item(f"{total_tva:,.2f} DA", is_numeric=True))
                self.table.setItem(row, 6, self._create_centered_item(f"{remise:,.2f} DA", is_numeric=True))
                self.table.setItem(row, 7, self._create_centered_item(f"{total_ttc:,.2f} DA", is_numeric=True))
                self.table.setItem(row, 8, self._create_centered_item(po_id or '---'))
                
                self.table.item(row, 0).setData(Qt.UserRole, reception)
                
                # --- [تم إلغاء التنسيق الخاص بالملاحظات] ---
                # if has_notes:
                #    self._apply_row_style(row, "#e74c3c", "white")
                # ----------------------------------------

                added_ids.add(br_id)

            logging.info(f"Terminé : {self.table.rowCount()} réceptions affichées.")

        except Exception as e:
            logging.error(f"Error loading receptions: {e}\n{traceback.format_exc()}")
        
        finally:
            self.table.setSortingEnabled(True)

    def _apply_row_style(self, row, bg_color, fg_color):
        for col in range(self.table.columnCount()):
            item = self.table.item(row, col)
            if item:
                item.setBackground(QColor(bg_color))
                item.setForeground(QColor(fg_color))
                item.setFont(QFont("Arial", 9, QFont.Bold))

    def edit_reception(self):
        """
        فتح نافذة التعديل (يتم استدعاؤها عند الضغط المزدوج أو زر التعديل).
        """
        try:
            row = self.table.currentRow()
            if row < 0:
                QMessageBox.warning(self, "Attention", "Veuillez sélectionner une réception dans le tableau.")
                return
            
            item = self.table.item(row, 0)
            if not item: return

            reception = item.data(Qt.UserRole)
            if not reception:
                QMessageBox.critical(self, "Erreur", "Données de réception introuvables.")
                return

            br_id = reception.get('BR_ID')
            po_id = reception.get('PO_ID')

            if not br_id:
                QMessageBox.critical(self, "Erreur", "ID de réception (BR_ID) manquant.")
                return

            logging.info(f"Ouverture modification BR: {br_id}, PO: {po_id}")

            full_po_data = self.manager.po.get_full_order_details(po_id)
            if not full_po_data:
                # محاولة تحميل جزئي إذا لم نجد PO (لأنه قد يكون PO وهمي أو محذوف)
                # لكن الأفضل هنا افتراض وجود بيانات
                pass

            locations = self.manager.locations.get_all_locations_flat()
            reception_data = self.manager.reception.get_reception_summary(br_id)
            
            if not reception_data:
                raise ValueError(f"Impossible de charger le résumé de la réception #{br_id}")
            
            # إذا لم يوجد PO linked، نصنع واحداً وهمياً للعرض
            if not full_po_data:
                full_po_data = {
                    'PO_ID': po_id, 
                    'Supplier_Name': reception.get('Supplier_Name'), 
                    'Supplier_ID': reception.get('Supplier_ID')
                }

            dialog = ReceptionDialog(
                po_data=full_po_data,
                locations_list=locations,
                location_manager=self.manager.locations, 
                manager=self.manager.reception,
                printer_manager=self.manager.printer,
                parent=self,
                edit_mode=True,
                reception_data=reception_data
            )
            
            if dialog.exec():
                self.load_data()
                
        except Exception as e:
            logging.error(f"Error editing reception: {str(e)}")
            QMessageBox.critical(self, "Erreur", f"Impossible d'ouvrir la modification :\n{str(e)}")

    def export_reception_pdf(self):
        """
        تصدير ملف PDF مع التفاف النص وإظهار الباركود.
        """
        if not HAS_REPORTLAB:
            QMessageBox.warning(self, "Erreur", "La bibliothèque 'reportlab' n'est pas installée.")
            return

        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Attention", "Veuillez sélectionner une réception à exporter.")
            return

        item = self.table.item(row, 0)
        reception_data_basic = item.data(Qt.UserRole)
        br_id = reception_data_basic.get('BR_ID')

        try:
            # جلب البيانات التفصيلية
            full_data = self.manager.reception.get_reception_details(br_id)
            if not full_data:
                QMessageBox.warning(self, "Erreur", "Impossible de récupérer les détails.")
                return

            header = full_data['Header']
            batches = full_data['Batches']

            path, _ = QFileDialog.getSaveFileName(self, "Enregistrer PDF", f"Bon_Reception_BR_{br_id}.pdf", "Fichiers PDF (*.pdf)")
            if not path: return

            # إعداد الصفحة
            doc = SimpleDocTemplate(path, pagesize=A4, rightMargin=20, leftMargin=20, topMargin=30, bottomMargin=30)
            elements = []
            styles = getSampleStyleSheet()
            
            # نمط مخصص للنصوص داخل الجدول
            cell_style = ParagraphStyle(
                'CellStyle',
                parent=styles['Normal'],
                fontSize=9,
                leading=11,  # المسافة بين السطور
                alignment=1  # توسيط
            )
            
            # نمط مخصص لاسم المنتج (محاذاة لليسار)
            product_style = ParagraphStyle(
                'ProductStyle',
                parent=styles['Normal'],
                fontSize=9,
                leading=11,
                alignment=0  # محاذاة لليسار
            )

            # --- العنوان ---
            company_text = "<b><font color='#333333'>MODERN</font><font color='#16a085'>LAM</font></b>"
            elements.append(Paragraph(company_text, styles["Heading2"]))
            elements.append(Spacer(1, 0.5 * cm))
            
            title_st = styles["Heading1"]
            title_st.alignment = 1
            elements.append(Paragraph("<b>BON DE RÉCEPTION</b>", title_st))
            elements.append(Spacer(1, 1 * cm))

            # --- المعلومات ---
            info_data = [
                [f"N° Bon : #{br_id}", f"Date : {header.get('Reception_Date')}"],
                [f"Fournisseur : {header.get('Supplier_Name')}", f"Réf PO : #{header.get('PO_ID')}"],
                [f"Réf Facture : {header.get('Supplier_Invoice_Ref')}", ""]
            ]
            it = Table(info_data, colWidths=[9*cm, 9*cm])
            it.setStyle(TableStyle([
                ('FONTNAME', (0,0), (-1,-1), 'Helvetica-Bold'),
                ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                ('PADDING', (0,0), (-1,-1), 6)
            ]))
            elements.append(it)
            elements.append(Spacer(1, 1 * cm))

            # --- جدول المنتجات ---
            table_headers = ["Désignation / Code", "Lot", "Exp.", "Qté", "Prix U.", "Total TTC"]
            headers_formatted = [Paragraph(f"<b>{h}</b>", cell_style) for h in table_headers]
            table_data = [headers_formatted]
            
            for b in batches:
                product_name = b.get('Product_Name', 'N/A')
                barcode = b.get('Internal_Barcode') or b.get('Barcode') or '---'
                prod_cell_text = f"<b>{product_name}</b><br/><font color='grey' size='7'>Code: {barcode}</font>"
                prod_paragraph = Paragraph(prod_cell_text, product_style)

                try:
                    q = int(float(b.get('Quantity_Initial') or 0))
                except:
                    q = float(b.get('Quantity_Initial') or 0)

                p = float(b.get('Unit_Price_Received') or 0)
                discount = float(b.get('Discount_Percent', 0))
                tax = float(b.get('Tax_Rate_Percent', 0))
                line_ttc = q * p * (1 - discount/100) * (1 + tax/100)
                
                table_data.append([
                    prod_paragraph,                               
                    Paragraph(str(b.get('Lot_Number')), cell_style),
                    str(b.get('Expiry_Date')),
                    f"{q}",
                    f"{p:,.2f}",
                    f"{line_ttc:,.2f}"
                ])

            col_widths = [7.5*cm, 2.5*cm, 2.5*cm, 1.5*cm, 2.5*cm, 3*cm]

            main_t = Table(table_data, colWidths=col_widths)
            main_t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#2c3e50")), 
                ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),       
                ('ALIGN', (0,1), (0,-1), 'LEFT'),          
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),      
                ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                ('LEFTPADDING', (0,0), (-1,-1), 4),
                ('RIGHTPADDING', (0,0), (-1,-1), 4),
                ('TOPPADDING', (0,0), (-1,-1), 4),
                ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ]))
            elements.append(main_t)
            elements.append(Spacer(1, 1 * cm))

            # --- التذييل ---
            t_ttc = float(header.get('Invoice_Total_TTC') or 0)
            elements.append(Paragraph(f"<para align='right'><b>TOTAL TTC : {t_ttc:,.2f} DZD</b></para>", styles["Normal"]))
            elements.append(Spacer(1, 2 * cm))
            elements.append(Table([["Réceptionné par :", "Signature Autorisée :"]], colWidths=[9*cm, 9*cm]))

            doc.build(elements)
            os.startfile(path)

        except Exception as e:
            logging.error(f"PDF Error: {e}")
            QMessageBox.critical(self, "Erreur", f"Échec PDF : {e}")

    def show_history_for_po(self, po_id):
        """تصفية السجل لعرض استلامات طلب محدد فقط"""
        logging.info(f"Filtering history for PO #{po_id}")
        
        # 1. توسيع مجال البحث في التاريخ ليشمل كل الفترات
        # (نضع تاريخاً قديماً جداً وتاريخاً مستقبلياً لضمان عدم إخفاء أي سجل)
        self.date_from.setDate(QDate(2020, 1, 1))
        self.date_to.setDate(QDate.currentDate().addYears(1))
        
        # 2. تصفير فلاتر الحالة والموردين (لأننا نبحث عن طلب محدد بغض النظر عن حالته)
        self.status_filter.setCurrentIndex(0) # Tous
        if hasattr(self, 'supplier_filter'):
            self.supplier_filter.setCurrentIndex(0) # Tous
            
        # 3. وضع رقم الطلب في مربع البحث (هذا سيقوم بتفعيل الفلترة تلقائياً في load_data)
        self.search_input.setText(str(po_id))
        
        # 4. تنفيذ التحميل
        self.load_data()