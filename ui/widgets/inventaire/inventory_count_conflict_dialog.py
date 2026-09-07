from decimal import Decimal
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ui.formatting import format_quantity


CONFLICT_STYLE = """
QDialog#inventoryConflictDialog {
    background: #f8fafc;
    color: #1e293b;
}
QFrame#conflictHeaderCard {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 12px 16px;
}
QFrame#instructionsCard {
    background: #fffbeb;
    border: 1px solid #fef3c7;
    border-radius: 6px;
    padding: 10px 14px;
}
QTableWidget {
    background: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    gridline-color: #f1f5f9;
}
QTableWidget::item {
    padding: 4px 6px;
}
QTableWidget::item:selected {
    background-color: #e2e8f0;
    color: #0f172a;
}
QHeaderView::section {
    background-color: #f1f5f9;
    color: #334155;
    font-size: 11px;
    font-weight: 700;
    padding: 6px 4px;
    border: 1px solid #e2e8f0;
}
QComboBox {
    background: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 4px;
    padding: 3px 6px;
    font-size: 12px;
    min-height: 26px;
}
QPushButton#applyResolutionsBtn {
    background: #007572;
    border: 1px solid #005f5d;
    border-radius: 6px;
    color: #ffffff;
    font-size: 13px;
    font-weight: 700;
    padding: 8px 18px;
    min-height: 36px;
}
QPushButton#applyResolutionsBtn:hover {
    background: #005f5d;
}
QPushButton#cancelResolutionsBtn {
    background: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    color: #475569;
    font-size: 13px;
    font-weight: 600;
    padding: 8px 16px;
    min-height: 36px;
}
QPushButton#cancelResolutionsBtn:hover {
    background: #f1f5f9;
}
QPushButton.bulkBtn {
    background: #f1f5f9;
    border: 1px solid #cbd5e1;
    border-radius: 4px;
    color: #334155;
    font-size: 11px;
    font-weight: 600;
    padding: 4px 10px;
    min-height: 26px;
}
QPushButton.bulkBtn:hover {
    background: #e2e8f0;
}
"""


class InventoryConflictDialog(QDialog):
    """Interactive conflict resolution dialog when batches changed after snapshot."""

    ACTION_FORCE = "force_counted"
    ACTION_DELTA = "apply_delta"
    ACTION_SKIP = "skip"

    def __init__(self, conflicts: List[Dict[str, Any]], parent: Optional[QDialog] = None):
        super().__init__(parent)
        self.setObjectName("inventoryConflictDialog")
        self.setStyleSheet(CONFLICT_STYLE)
        self.setWindowTitle("Inventaire - Conflits de stock détectés")
        self.resize(1080, 580)
        self.setMinimumSize(900, 480)

        self.conflicts = list(conflicts or [])
        self.combos: List[QComboBox] = []

        self._build_ui()
        self._populate_conflicts()

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(12)

        # Header card
        header_card = QFrame()
        header_card.setObjectName("conflictHeaderCard")
        header_layout = QVBoxLayout(header_card)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(4)

        title_label = QLabel(f"⚠️ {len(self.conflicts)} conflit(s) détecté(s) lors de l'application")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(12)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #b45309;")

        desc_label = QLabel(
            "Le stock de ces produits a été modifié dans le système après la création de la session d'inventaire "
            "(ex: consommation, sortie, réception ou ajustement en cours). "
            "Veuillez choisir la règle d'ajustement à appliquer pour chaque lot :"
        )
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #475569; font-size: 12px;")

        header_layout.addWidget(title_label)
        header_layout.addWidget(desc_label)
        root_layout.addWidget(header_card)

        # Instructions / Explanations card
        instr_card = QFrame()
        instr_card.setObjectName("instructionsCard")
        instr_layout = QVBoxLayout(instr_card)
        instr_layout.setContentsMargins(0, 0, 0, 0)
        instr_layout.setSpacing(4)

        help_text = QLabel(
            "• <b>Écraser (stock = compté)</b> : La quantité comptée physiquement est la vérité absolue. Le stock final sera égal au comptage.<br>"
            "• <b>Écart relatif (stock = actuel + écart)</b> : Applique la variation comptée sur le stock actuel (préserve une consommation légitime intervenue entre-temps).<br>"
            "• <b>Ignorer le lot</b> : Aucune modification ne sera appliquée à ce lot (son stock actuel reste intact)."
        )
        help_text.setWordWrap(True)
        help_text.setStyleSheet("color: #92400e; font-size: 11px;")
        instr_layout.addWidget(help_text)
        root_layout.addWidget(instr_card)

        # Bulk actions bar
        bulk_bar = QHBoxLayout()
        bulk_bar.setSpacing(8)

        bulk_label = QLabel("Appliquer à tous les lots :")
        bulk_label.setStyleSheet("font-weight: 700; font-size: 11px; color: #475569;")
        bulk_bar.addWidget(bulk_label)

        btn_all_force = QPushButton("Tout écraser (Comptage physique)")
        btn_all_force.setProperty("class", "bulkBtn")
        btn_all_force.clicked.connect(lambda: self._set_all_action(self.ACTION_FORCE))
        bulk_bar.addWidget(btn_all_force)

        btn_all_delta = QPushButton("Tout en écart relatif (+/-)")
        btn_all_delta.setProperty("class", "bulkBtn")
        btn_all_delta.clicked.connect(lambda: self._set_all_action(self.ACTION_DELTA))
        bulk_bar.addWidget(btn_all_delta)

        btn_all_skip = QPushButton("Tout ignorer (Garder actuel)")
        btn_all_skip.setProperty("class", "bulkBtn")
        btn_all_skip.clicked.connect(lambda: self._set_all_action(self.ACTION_SKIP))
        bulk_bar.addWidget(btn_all_skip)

        bulk_bar.addStretch()
        root_layout.addLayout(bulk_bar)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "Réf. Produit",
            "Désignation",
            "Lot / Code-barres",
            "Stock Initial\n(Snapshot)",
            "Stock Actuel\n(Système)",
            "Mouvement\nIntermédiaire",
            "Stock Compté\n(Physique)",
            "Règle de résolution",
            "Stock Final\nRésultant",
        ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(8, QHeaderView.ResizeToContents)
        root_layout.addWidget(self.table, 1)

        # Footer buttons
        footer_layout = QHBoxLayout()
        footer_layout.setSpacing(10)

        self.summary_footer_label = QLabel(f"{len(self.conflicts)} lot(s) en attente de décision.")
        self.summary_footer_label.setStyleSheet("color: #64748b; font-size: 12px; font-weight: 600;")
        footer_layout.addWidget(self.summary_footer_label)
        footer_layout.addStretch()

        btn_cancel = QPushButton("Annuler l'application")
        btn_cancel.setObjectName("cancelResolutionsBtn")
        btn_cancel.clicked.connect(self.reject)
        footer_layout.addWidget(btn_cancel)

        btn_apply = QPushButton("Valider et Appliquer l'inventaire")
        btn_apply.setObjectName("applyResolutionsBtn")
        btn_apply.clicked.connect(self.accept)
        footer_layout.addWidget(btn_apply)

        root_layout.addLayout(footer_layout)

    def _to_decimal(self, value) -> Decimal:
        if value is None:
            return Decimal("0")
        try:
            return Decimal(str(value))
        except Exception:
            return Decimal("0")

    def _populate_conflicts(self):
        self.table.setRowCount(len(self.conflicts))
        self.combos = []

        for row, conflict in enumerate(self.conflicts):
            code = conflict.get("Product_Code") or ""
            name = conflict.get("Product_Name") or conflict.get("barcode") or f"Lot #{conflict.get('Batch_ID')}"
            lot = conflict.get("Lot_Number") or conflict.get("barcode") or "-"
            
            snapshot_qty = self._to_decimal(conflict.get("snapshot_qty"))
            current_qty = self._to_decimal(conflict.get("current_qty"))
            counted_qty = self._to_decimal(conflict.get("counted_qty"))
            mvt_inter = current_qty - snapshot_qty

            # Col 0: Product Code
            it_code = QTableWidgetItem(code)
            it_code.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 0, it_code)

            # Col 1: Product Name
            it_name = QTableWidgetItem(name)
            it_name.setToolTip(name)
            self.table.setItem(row, 1, it_name)

            # Col 2: Lot / Barcode
            it_lot = QTableWidgetItem(lot)
            it_lot.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 2, it_lot)

            # Col 3: Snapshot Qty
            it_snap = QTableWidgetItem(format_quantity(snapshot_qty))
            it_snap.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(row, 3, it_snap)

            # Col 4: Current Qty
            it_curr = QTableWidgetItem(format_quantity(current_qty))
            it_curr.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            it_curr.setFont(self._bold_font())
            self.table.setItem(row, 4, it_curr)

            # Col 5: Intermediate movement
            mvt_sign = "+" if mvt_inter > 0 else ""
            it_mvt = QTableWidgetItem(f"{mvt_sign}{format_quantity(mvt_inter)}")
            it_mvt.setTextAlignment(Qt.AlignCenter)
            if mvt_inter < 0:
                it_mvt.setForeground(QColor("#dc2626"))  # Red
                it_mvt.setToolTip("Le stock a diminué (consommation ou sortie) depuis le snapshot.")
            elif mvt_inter > 0:
                it_mvt.setForeground(QColor("#16a34a"))  # Green
                it_mvt.setToolTip("Le stock a augmenté (réception ou ajout) depuis le snapshot.")
            else:
                it_mvt.setForeground(QColor("#64748b"))
            self.table.setItem(row, 5, it_mvt)

            # Col 6: Counted Qty
            it_counted = QTableWidgetItem(format_quantity(counted_qty))
            it_counted.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            it_counted.setFont(self._bold_font())
            it_counted.setForeground(QColor("#007572"))
            self.table.setItem(row, 6, it_counted)

            # Col 7: Combo Resolution
            combo = QComboBox()
            combo.addItem("Écraser (stock = compté)", self.ACTION_FORCE)
            combo.addItem("Écart relatif (+/-)", self.ACTION_DELTA)
            combo.addItem("Ignorer le lot", self.ACTION_SKIP)
            combo.setCurrentIndex(0)
            combo.currentIndexChanged.connect(lambda _idx, r=row: self._update_row_preview(r))
            self.combos.append(combo)
            self.table.setCellWidget(row, 7, combo)

            # Col 8: Resulting Stock Preview
            it_res = QTableWidgetItem()
            it_res.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            it_res.setFont(self._bold_font())
            self.table.setItem(row, 8, it_res)

            self._update_row_preview(row)

    def _bold_font(self) -> QFont:
        font = QFont()
        font.setBold(True)
        return font

    def _update_row_preview(self, row: int):
        if row < 0 or row >= len(self.conflicts) or row >= len(self.combos):
            return

        conflict = self.conflicts[row]
        combo = self.combos[row]
        action = combo.currentData()

        snapshot_qty = self._to_decimal(conflict.get("snapshot_qty"))
        current_qty = self._to_decimal(conflict.get("current_qty"))
        counted_qty = self._to_decimal(conflict.get("counted_qty"))

        if action == self.ACTION_FORCE:
            resulting = counted_qty
            color = "#007572"
            tooltip = "Le stock actuel sera ajusté pour correspondre exactement au comptage physique."
        elif action == self.ACTION_DELTA:
            delta = counted_qty - snapshot_qty
            resulting = max(Decimal("0"), current_qty + delta)
            color = "#2563eb"
            tooltip = f"L'écart compté initial ({delta:+}) est reporté sur le stock actuel ({current_qty})."
        else:  # skip
            resulting = current_qty
            color = "#64748b"
            tooltip = "Ce lot ne sera pas modifié. Le stock reste à sa valeur actuelle."

        item = self.table.item(row, 8)
        if item:
            item.setText(format_quantity(resulting))
            item.setForeground(QColor(color))
            item.setToolTip(tooltip)

    def _set_all_action(self, action: str):
        for row, combo in enumerate(self.combos):
            idx = combo.findData(action)
            if idx >= 0:
                combo.setCurrentIndex(idx)
                self._update_row_preview(row)

    def get_resolutions(self) -> Dict[int, str]:
        """Returns a mapping of batch_id -> resolution action."""
        resolutions = {}
        for row, conflict in enumerate(self.conflicts):
            batch_id = conflict.get("Batch_ID")
            if batch_id is None:
                continue
            action = self.combos[row].currentData() if row < len(self.combos) else self.ACTION_FORCE
            resolutions[int(batch_id)] = action
        return resolutions
