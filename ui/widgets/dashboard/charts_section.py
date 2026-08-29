# ui/widgets/dashboard/charts_section.py

import logging
from datetime import date, datetime, timedelta
from typing import List, Dict, Any, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel, 
    QPushButton, QComboBox, QDateEdit, QButtonGroup, 
    QSizePolicy, QGraphicsDropShadowEffect
)
from PySide6.QtCharts import (
    QChart, QChartView, QBarSeries, QStackedBarSeries, 
    QBarSet, QBarCategoryAxis, QValueAxis, QLegend, QCategoryAxis
)
from PySide6.QtCore import Qt, QDate, QMargins, Signal, QPoint, QRect, QEvent
from PySide6.QtGui import (
    QPainter, QColor, QFont, QCursor, QBrush, QPen
)

from ui.formatting import format_money, format_quantity


class ChartHoverCard(QFrame):
    """
    Carte flottante d'infobulle persistante et élégante :
    - Reste affichée sans jamais disparaître prématurément durant le survol d'une colonne.
    - Fond 100% blanc avec bordure subtile et ombre portée moderne.
    - Totalement indépendante des thèmes système ou du mode sombre OS.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        # Permet aux événements de souris de traverser la carte vers le graphique
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setObjectName("HoverDetailCard")
        self.setStyleSheet("""
            QFrame#HoverDetailCard {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 10px;
            }
        """)

        # Ombre portée douce
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(18)
        shadow.setColor(QColor(15, 23, 42, 45))
        shadow.setOffset(0, 5)
        self.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        # En-tête : Période
        self.lbl_period = QLabel("", self)
        self.lbl_period.setStyleSheet("""
            font-size: 12px;
            font-weight: 800;
            color: #0f172a;
            border-bottom: 1px solid #e2e8f0;
            padding-bottom: 4px;
            margin-bottom: 2px;
        """)
        layout.addWidget(self.lbl_period)

        # Ligne Entrées (Achats)
        self.row_in = QHBoxLayout()
        self.lbl_in_title = QLabel("📥 Entrées (Achats) :", self)
        self.lbl_in_title.setStyleSheet("font-size: 11px; font-weight: 600; color: #64748b;")
        self.lbl_in_val = QLabel("0,00 DA", self)
        self.lbl_in_val.setStyleSheet("font-size: 11px; font-weight: 800; color: #1e824c;")
        self.row_in.addWidget(self.lbl_in_title)
        self.row_in.addStretch()
        self.row_in.addWidget(self.lbl_in_val)
        layout.addLayout(self.row_in)

        # Ligne Sorties (Consommation)
        self.row_out = QHBoxLayout()
        self.lbl_out_title = QLabel("📤 Sorties (Consommation) :", self)
        self.lbl_out_title.setStyleSheet("font-size: 11px; font-weight: 600; color: #64748b;")
        self.lbl_out_val = QLabel("0,00 DA", self)
        self.lbl_out_val.setStyleSheet("font-size: 11px; font-weight: 800; color: #c0392b;")
        self.row_out.addWidget(self.lbl_out_title)
        self.row_out.addStretch()
        self.row_out.addWidget(self.lbl_out_val)
        layout.addLayout(self.row_out)

        # Ligne Solde Net
        self.row_net = QHBoxLayout()
        self.lbl_net_title = QLabel("⚖️ Solde Net (Flux) :", self)
        self.lbl_net_title.setStyleSheet("font-size: 11px; font-weight: 700; color: #334155;")
        self.lbl_net_val = QLabel("0,00 DA", self)
        self.lbl_net_val.setStyleSheet("font-size: 11px; font-weight: 800; color: #007572;")
        self.row_net.addWidget(self.lbl_net_title)
        self.row_net.addStretch()
        self.row_net.addWidget(self.lbl_net_val)
        layout.addLayout(self.row_net)

        # Ligne Transactions
        self.lbl_tx = QLabel("", self)
        self.lbl_tx.setStyleSheet("""
            font-size: 10px;
            font-weight: 500;
            color: #64748b;
            border-top: 1px dashed #e2e8f0;
            padding-top: 4px;
            margin-top: 2px;
        """)
        layout.addWidget(self.lbl_tx)

        self.hide()

    def update_and_show(self, data: Dict[str, Any], mouse_pos: QPoint, bounds: QRect):
        """Met à jour les informations et positionne la carte sans collision"""
        val_in = data.get('in', 0.0)
        val_out = data.get('out', 0.0)
        net_val = val_in - val_out
        cnt_in = data.get('count_in', 0)
        cnt_out = data.get('count_out', 0)

        # 1. Période
        self.lbl_period.setText(f"📅 {data.get('detail', '')}")

        # 2. Valeurs formatées
        self.lbl_in_val.setText(format_money(val_in, 'DA'))
        self.lbl_out_val.setText(format_money(val_out, 'DA'))

        net_prefix = "+" if net_val > 0 else ""
        self.lbl_net_val.setText(f"{net_prefix}{format_money(net_val, 'DA')}")
        if net_val > 0:
            self.lbl_net_val.setStyleSheet("font-size: 11px; font-weight: 800; color: #1e824c;")
        elif net_val < 0:
            self.lbl_net_val.setStyleSheet("font-size: 11px; font-weight: 800; color: #c0392b;")
        else:
            self.lbl_net_val.setStyleSheet("font-size: 11px; font-weight: 800; color: #334155;")

        # 3. Détail des transactions
        if cnt_in > 0 or cnt_out > 0:
            self.lbl_tx.setText(f"📋 {cnt_in} réception(s) / {cnt_out} sortie(s)")
            self.lbl_tx.setVisible(True)
        else:
            self.lbl_tx.setVisible(False)

        self.adjustSize()
        card_w = max(self.sizeHint().width(), 230)
        card_h = max(self.sizeHint().height(), 120)
        self.resize(card_w, card_h)

        # Positionnement intelligent par rapport au curseur
        offset_x = 18
        offset_y = 18

        target_x = mouse_pos.x() + offset_x
        target_y = mouse_pos.y() - card_h - 10

        # Éviter le débordement à droite
        if target_x + card_w > bounds.right() - 15:
            target_x = mouse_pos.x() - card_w - offset_x

        # Éviter le débordement en haut
        if target_y < bounds.top() + 10:
            target_y = mouse_pos.y() + offset_y

        # Éviter le débordement en bas
        if target_y + card_h > bounds.bottom() - 10:
            target_y = bounds.bottom() - card_h - 10

        self.move(max(10, target_x), max(10, target_y))
        self.show()
        self.raise_()


class ChartsSection(QWidget):
    """
    Section Graphique Dashboard Professionnelle :
    - Style Colonnes de Stock (Entrées en Vert 🟩, Sorties en Rouge 🟥).
    - Carte d'information flottante persistante qui reste visible tant que la souris est sur la colonne.
    - Affichage explicite du périmètre temporel / historique analysé.
    - Filtres historiques locaux dédiés au graphique (7j, 30j, 3m, 6m, 1an, Personnalisé).
    - Granularité temporelle paramétrable (Jour / Semaine / Mois).
    - Métriques KPI récapitulatives (Total Entrées, Total Sorties, Solde Net).
    - Modes d'affichage extensibles (Colonnes Groupées, Empilées, Solde Net).
    """

    filter_changed = Signal(dict)

    # --- Constantes de couleurs & style ---
    COLOR_IN = "#27ae60"         # Vert émeraude pour les Entrées / Achats
    COLOR_IN_BORDER = "#1e824c"
    COLOR_IN_LIGHT = "#e8f8f0"

    COLOR_OUT = "#e74c3c"        # Rouge pour les Sorties / Consommation
    COLOR_OUT_BORDER = "#c0392b"
    COLOR_OUT_LIGHT = "#fdeeed"

    COLOR_PRIMARY = "#007572"    # Couleur principale StockLam
    COLOR_PRIMARY_HOVER = "#005a58"
    COLOR_BG_CARD = "#ffffff"
    COLOR_BORDER = "#eef2f5"
    COLOR_TEXT_MUTED = "#7f8c8d"
    COLOR_TEXT_MAIN = "#2c3e50"

    # --- Options de granularité ---
    GRANULARITY_DAY = "DAY"
    GRANULARITY_WEEK = "WEEK"
    GRANULARITY_MONTH = "MONTH"

    # --- Options de vue ---
    VIEW_GROUPED = "GROUPED"
    VIEW_STACKED = "STACKED"
    VIEW_NET_FLOW = "NET_FLOW"

    def __init__(self, stats_manager=None, parent=None):
        super().__init__(parent)
        self.stats_manager = stats_manager

        # Données brutes en cache
        self._raw_consumption: List[Dict[str, Any]] = []
        self._raw_reception: List[Dict[str, Any]] = []
        self._aggregated_data: List[Dict[str, Any]] = []

        # Dates globales synchronisées
        self._global_start_date: date = date.today() - timedelta(days=365)
        self._global_end_date: date = date.today()

        # Paramètres d'affichage locaux (Par défaut : 12 Mois en mode Mensuel)
        self._granularity = self.GRANULARITY_MONTH
        self._view_mode = self.VIEW_GROUPED
        self._hovered_index: Optional[int] = None
        self._pinned_index: Optional[int] = None

        self._init_ui()

    def set_stats_manager(self, stats_manager):
        """Affecte le gestionnaire de statistiques pour les requêtes dynamiques"""
        self.stats_manager = stats_manager

    # =========================================================================
    # 1. INITIALISATION DE L'INTERFACE
    # =========================================================================
    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(8)

        # Conteneur principal sous forme de carte moderne
        self.card_frame = QFrame()
        self.card_frame.setStyleSheet(f"""
            QFrame#ChartCard {{
                background-color: {self.COLOR_BG_CARD};
                border-radius: 12px;
                border: 1px solid {self.COLOR_BORDER};
            }}
        """)
        self.card_frame.setObjectName("ChartCard")

        card_layout = QVBoxLayout(self.card_frame)
        card_layout.setContentsMargins(14, 10, 14, 8)
        card_layout.setSpacing(6)

        # 1.1 Barre d'outils supérieure (Filtres & Badges KPI combinés sur la même ligne)
        header_widget = self._create_header_toolbar()
        card_layout.addWidget(header_widget)

        # 1.2 Graphique QtCharts
        self.chart = QChart()
        self.chart.setTitle("")
        self.chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)
        self.chart.setBackgroundVisible(False)
        self.chart.setMargins(QMargins(6, 4, 6, 4))

        # Légende
        legend = self.chart.legend()
        legend.setVisible(True)
        legend.setAlignment(Qt.AlignmentFlag.AlignBottom)
        legend.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        legend.setMarkerShape(QLegend.MarkerShape.MarkerShapeRectangle)

        self.chart_view = QChartView(self.chart)
        self.chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.chart_view.setMouseTracking(True)
        self.chart_view.setStyleSheet("background: transparent; border: none;")
        self.chart_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # 1.5 Carte d'information flottante persistante (enfant direct de chart_view)
        self.hover_card = ChartHoverCard(parent=self.chart_view)

        # Message d'état vide
        self.empty_state_label = QLabel("📭 Aucune transaction enregistrée pour la période sélectionnée.")
        self.empty_state_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_state_label.setStyleSheet(f"""
            color: {self.COLOR_TEXT_MUTED};
            font-size: 13px;
            font-weight: 600;
            padding: 40px;
        """)
        self.empty_state_label.setVisible(False)

        card_layout.addWidget(self.chart_view, 1)
        card_layout.addWidget(self.empty_state_label)

        main_layout.addWidget(self.card_frame)

    # =========================================================================
    # 2. BARRE D'OUTILS ET CONTRÔLES LOCAUX
    # =========================================================================
    def _create_header_toolbar(self) -> QWidget:
        toolbar = QWidget()
        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # --- 1. Sélecteur de Granularité (Jour / Semaine / Mois) ---
        granularity_container = QFrame()
        granularity_container.setStyleSheet("""
            QFrame {
                background-color: #f1f5f9;
                border: 1px solid #e2e8f0;
                border-radius: 6px;
                padding: 1px;
            }
        """)
        g_layout = QHBoxLayout(granularity_container)
        g_layout.setContentsMargins(2, 2, 2, 2)
        g_layout.setSpacing(2)

        self.btn_group_granularity = QButtonGroup(self)
        self.btn_group_granularity.setExclusive(True)

        self.btn_day = self._create_toggle_btn("📅 Jour", self.GRANULARITY_DAY)
        self.btn_week = self._create_toggle_btn("📆 Semaine", self.GRANULARITY_WEEK)
        self.btn_month = self._create_toggle_btn("🗓️ Mois", self.GRANULARITY_MONTH, checked=True)

        for btn in [self.btn_day, self.btn_week, self.btn_month]:
            self.btn_group_granularity.addButton(btn)
            g_layout.addWidget(btn)

        self.btn_group_granularity.buttonClicked.connect(self._on_granularity_clicked)
        layout.addWidget(granularity_container)

        # --- 2. Sélecteur de Mode d'Affichage / Type de Graphique ---
        self.combo_view_mode = QComboBox()
        self.combo_view_mode.setFixedHeight(28)
        self.combo_view_mode.setStyleSheet(f"""
            QComboBox {{
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 2px 8px;
                font-size: 11px;
                font-weight: 600;
                color: {self.COLOR_TEXT_MAIN};
                min-width: 115px;
            }}
            QComboBox:hover {{ border-color: {self.COLOR_PRIMARY}; }}
            QComboBox::drop-down {{ border: none; width: 18px; }}
            QComboBox QAbstractItemView {{
                background-color: white;
                selection-background-color: #e2e8f0;
                selection-color: {self.COLOR_PRIMARY};
                border: 1px solid #cbd5e1;
                padding: 4px;
            }}
        """)
        self.combo_view_mode.addItem("📊 Groupées", self.VIEW_GROUPED)
        self.combo_view_mode.addItem("🥞 Empilées", self.VIEW_STACKED)
        self.combo_view_mode.addItem("⚖️ Solde Net", self.VIEW_NET_FLOW)
        self.combo_view_mode.currentIndexChanged.connect(self._on_view_mode_changed)
        layout.addWidget(self.combo_view_mode)

        # --- 3. Sélecteur de Période Historique Locale ---
        self.combo_preset = QComboBox()
        self.combo_preset.setFixedHeight(28)
        self.combo_preset.setStyleSheet(f"""
            QComboBox {{
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 2px 8px;
                font-size: 11px;
                font-weight: 600;
                color: {self.COLOR_TEXT_MAIN};
                min-width: 135px;
            }}
            QComboBox:hover {{ border-color: {self.COLOR_PRIMARY}; }}
            QComboBox::drop-down {{ border: none; width: 18px; }}
            QComboBox QAbstractItemView {{
                background-color: white;
                selection-background-color: #e2e8f0;
                selection-color: {self.COLOR_PRIMARY};
                border: 1px solid #cbd5e1;
                padding: 4px;
            }}
        """)
        self.combo_preset.addItem("🔗 Synchronisé", "SYNC")
        self.combo_preset.addItem("📅 7 Jours", "7D")
        self.combo_preset.addItem("📅 14 Jours", "14D")
        self.combo_preset.addItem("📅 30 Jours", "30D")
        self.combo_preset.addItem("📆 Ce Mois-ci", "THIS_MONTH")
        self.combo_preset.addItem("🗓️ 3 Mois", "3M")
        self.combo_preset.addItem("🗓️ 6 Mois", "6M")
        self.combo_preset.addItem("📈 Année (YTD)", "YTD")
        self.combo_preset.addItem("📊 12 Mois", "12M")
        self.combo_preset.addItem("⚙️ Personnalisé...", "CUSTOM")
        
        # Par défaut : 12 Mois (Dernière Année)
        idx_12m = self.combo_preset.findData("12M")
        if idx_12m != -1:
            self.combo_preset.setCurrentIndex(idx_12m)
            
        self.combo_preset.currentIndexChanged.connect(self._on_preset_changed)
        layout.addWidget(self.combo_preset)

        # --- 4. Sélecteurs de date personnalisée ---
        self.custom_dates_container = QWidget()
        custom_layout = QHBoxLayout(self.custom_dates_container)
        custom_layout.setContentsMargins(0, 0, 0, 0)
        custom_layout.setSpacing(3)

        lbl_from = QLabel("Du:")
        lbl_from.setStyleSheet("font-size: 10px; font-weight: 600; color: #64748b;")
        self.date_from = QDateEdit(QDate.currentDate().addDays(-30))
        self.date_from.setCalendarPopup(True)
        self.date_from.setFixedHeight(28)
        self.date_from.setFixedWidth(95)
        self.date_from.setStyleSheet(self._date_edit_style())

        lbl_to = QLabel("Au:")
        lbl_to.setStyleSheet("font-size: 10px; font-weight: 600; color: #64748b;")
        self.date_to = QDateEdit(QDate.currentDate())
        self.date_to.setCalendarPopup(True)
        self.date_to.setFixedHeight(28)
        self.date_to.setFixedWidth(95)
        self.date_to.setStyleSheet(self._date_edit_style())

        self.btn_apply_dates = QPushButton("OK")
        self.btn_apply_dates.setFixedHeight(28)
        self.btn_apply_dates.setFixedWidth(32)
        self.btn_apply_dates.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_apply_dates.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.COLOR_PRIMARY};
                color: white;
                font-weight: bold;
                border-radius: 4px;
                border: none;
            }}
            QPushButton:hover {{ background-color: {self.COLOR_PRIMARY_HOVER}; }}
        """)
        self.btn_apply_dates.clicked.connect(self._on_custom_dates_applied)

        custom_layout.addWidget(lbl_from)
        custom_layout.addWidget(self.date_from)
        custom_layout.addWidget(lbl_to)
        custom_layout.addWidget(self.date_to)
        custom_layout.addWidget(self.btn_apply_dates)
        
        self.custom_dates_container.setVisible(False)
        layout.addWidget(self.custom_dates_container)

        layout.addStretch()

        # --- 5. Badges KPI Compacts (sur la droite) ---
        self.badge_in = self._create_compact_metric_pill(
            title="Entrées :", 
            value="0,00 DA", 
            icon="📥", 
            bg_color=self.COLOR_IN_LIGHT, 
            text_color=self.COLOR_IN_BORDER,
            border_color="#a7f3d0"
        )
        self.badge_out = self._create_compact_metric_pill(
            title="Sorties :", 
            value="0,00 DA", 
            icon="📤", 
            bg_color=self.COLOR_OUT_LIGHT, 
            text_color=self.COLOR_OUT_BORDER,
            border_color="#fecaca"
        )
        self.badge_net = self._create_compact_metric_pill(
            title="Solde :", 
            value="0,00 DA", 
            icon="⚖️", 
            bg_color="#f8fafc", 
            text_color=self.COLOR_TEXT_MAIN,
            border_color="#e2e8f0"
        )

        layout.addWidget(self.badge_in)
        layout.addWidget(self.badge_out)
        layout.addWidget(self.badge_net)

        return toolbar

    def _create_toggle_btn(self, text: str, mode: str, checked: bool = False) -> QPushButton:
        btn = QPushButton(text)
        btn.setCheckable(True)
        btn.setChecked(checked)
        btn.setProperty("granularity_mode", mode)
        btn.setFixedHeight(28)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{
                border: none;
                border-radius: 5px;
                padding: 3px 10px;
                font-size: 11px;
                font-weight: 600;
                color: #475569;
                background-color: transparent;
            }}
            QPushButton:hover {{
                background-color: #e2e8f0;
                color: {self.COLOR_PRIMARY};
            }}
            QPushButton:checked {{
                background-color: #ffffff;
                color: {self.COLOR_PRIMARY};
                font-weight: 700;
                border: 1px solid #cbd5e1;
            }}
        """)
        return btn

    def _date_edit_style(self) -> str:
        return f"""
            QDateEdit {{
                background-color: white;
                border: 1px solid #cbd5e1;
                border-radius: 5px;
                padding: 3px 6px;
                font-size: 11px;
                color: {self.COLOR_TEXT_MAIN};
            }}
            QDateEdit:hover {{ border-color: {self.COLOR_PRIMARY}; }}
        """

    # =========================================================================
    # 3. BADGES DE MÉTRIQUES RÉSUMÉES (KPI MINI-BADGES COMPACTS)
    # =========================================================================
    def _create_compact_metric_pill(self, title: str, value: str, icon: str, 
                                    bg_color: str, text_color: str, border_color: str) -> QFrame:
        pill = QFrame()
        pill.setFixedHeight(28)
        pill.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 6px;
            }}
        """)
        p_layout = QHBoxLayout(pill)
        p_layout.setContentsMargins(8, 2, 8, 2)
        p_layout.setSpacing(5)

        lbl_icon = QLabel(icon)
        lbl_icon.setStyleSheet("font-size: 12px; border: none; background: transparent;")

        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("font-size: 10px; font-weight: 700; color: #64748b; border: none; background: transparent;")

        lbl_val = QLabel(value)
        lbl_val.setStyleSheet(f"font-size: 11px; font-weight: 800; color: {text_color}; border: none; background: transparent;")
        lbl_val.setObjectName("val_label")

        p_layout.addWidget(lbl_icon)
        p_layout.addWidget(lbl_title)
        p_layout.addWidget(lbl_val)

        return pill

    def _update_summary_metrics(self, total_in: float, total_out: float, period_count: int):
        """Met à jour les valeurs dans les badges du haut"""
        net_val = total_in - total_out

        lbl_in = self.badge_in.findChild(QLabel, "val_label")
        if lbl_in:
            lbl_in.setText(format_money(total_in, 'DA'))

        lbl_out = self.badge_out.findChild(QLabel, "val_label")
        if lbl_out:
            lbl_out.setText(format_money(total_out, 'DA'))

        lbl_net = self.badge_net.findChild(QLabel, "val_label")
        if lbl_net:
            prefix = "+" if net_val > 0 else ""
            lbl_net.setText(f"{prefix}{format_money(net_val, 'DA')}")
            if net_val > 0:
                lbl_net.setStyleSheet(f"font-size: 11px; font-weight: 800; color: {self.COLOR_IN_BORDER}; border: none; background: transparent;")
            elif net_val < 0:
                lbl_net.setStyleSheet(f"font-size: 11px; font-weight: 800; color: {self.COLOR_OUT_BORDER}; border: none; background: transparent;")
            else:
                lbl_net.setStyleSheet(f"font-size: 11px; font-weight: 800; color: {self.COLOR_TEXT_MAIN}; border: none; background: transparent;")

    # =========================================================================
    # 5. GESTION DES DATES ET AGRÉGATION TEMPORELLE
    # =========================================================================
    def _parse_date(self, date_val: Any) -> Optional[date]:
        """Conversion unifiée et robuste de formats de dates"""
        if isinstance(date_val, datetime):
            return date_val.date()
        if isinstance(date_val, date):
            return date_val
        if isinstance(date_val, str):
            try:
                date_clean = date_val.strip()
                if "T" in date_clean:
                    return datetime.fromisoformat(date_clean).date()
                if " " in date_clean:
                    return datetime.strptime(date_clean.split(" ")[0], "%Y-%m-%d").date()
                return datetime.strptime(date_clean, "%Y-%m-%d").date()
            except Exception:
                pass
        return None

    def _get_active_date_range(self) -> tuple[date, date]:
        """Retourne la plage de dates active selon le filtre sélectionné"""
        preset = self.combo_preset.currentData()
        today = date.today()

        if preset == "SYNC":
            return self._global_start_date, self._global_end_date
        elif preset == "7D":
            return today - timedelta(days=6), today
        elif preset == "14D":
            return today - timedelta(days=13), today
        elif preset == "30D":
            return today - timedelta(days=29), today
        elif preset == "THIS_MONTH":
            start_month = date(today.year, today.month, 1)
            return start_month, today
        elif preset == "3M":
            start_date = today - timedelta(days=90)
            return start_date, today
        elif preset == "6M":
            start_date = today - timedelta(days=180)
            return start_date, today
        elif preset == "YTD":
            start_year = date(today.year, 1, 1)
            return start_year, today
        elif preset == "12M":
            start_year = today - timedelta(days=365)
            return start_year, today
        elif preset == "CUSTOM":
            d_from = self.date_from.date().toPython()
            d_to = self.date_to.date().toPython()
            if d_from > d_to:
                d_from, d_to = d_to, d_from
            return d_from, d_to

        return self._global_start_date, self._global_end_date

    def _generate_period_buckets(self, start_date: date, end_date: date, granularity: str) -> List[Dict[str, Any]]:
        """Génère la liste ordonnée des périodes (Jours, Semaines, Mois)"""
        month_fr_short = ['', 'Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Juin', 'Juil', 'Août', 'Sep', 'Oct', 'Nov', 'Déc']
        month_fr_full = ['', 'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin', 'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']

        periods: List[Dict[str, Any]] = []

        if granularity == self.GRANULARITY_DAY:
            curr = start_date
            while curr <= end_date:
                key = curr.strftime("%Y-%m-%d")
                label = curr.strftime("%d/%m")
                detail = f"{curr.day:02d} {month_fr_full[curr.month]} {curr.year}"
                periods.append({
                    'key': key,
                    'label': label,
                    'detail': detail,
                    'start': curr,
                    'end': curr,
                    'in': 0.0,
                    'out': 0.0,
                    'count_in': 0,
                    'count_out': 0
                })
                curr += timedelta(days=1)

        elif granularity == self.GRANULARITY_WEEK:
            curr_monday = start_date - timedelta(days=start_date.weekday())
            end_sunday = end_date + timedelta(days=(6 - end_date.weekday()))
            seen_weeks = set()
            curr = curr_monday
            while curr <= end_sunday:
                iso_year, iso_week, _ = curr.isocalendar()
                week_key = f"{iso_year}-W{iso_week:02d}"
                if week_key not in seen_weeks:
                    seen_weeks.add(week_key)
                    w_start = curr
                    w_end = curr + timedelta(days=6)
                    s_str = w_start.strftime("%d/%m")
                    e_str = w_end.strftime("%d/%m/%Y")
                    label = f"S{iso_week:02d}"
                    detail = f"Semaine {iso_week} ({s_str} au {e_str})"
                    periods.append({
                        'key': week_key,
                        'label': label,
                        'detail': detail,
                        'start': w_start,
                        'end': w_end,
                        'in': 0.0,
                        'out': 0.0,
                        'count_in': 0,
                        'count_out': 0
                    })
                curr += timedelta(days=7)

        elif granularity == self.GRANULARITY_MONTH:
            y, m = start_date.year, start_date.month
            ey, em = end_date.year, end_date.month
            while (y < ey) or (y == ey and m <= em):
                month_key = f"{y}-{m:02d}"
                label = f"{month_fr_short[m]} {str(y)[2:]}"
                detail = f"{month_fr_full[m]} {y}"
                periods.append({
                    'key': month_key,
                    'label': label,
                    'detail': detail,
                    'year': y,
                    'month': m,
                    'in': 0.0,
                    'out': 0.0,
                    'count_in': 0,
                    'count_out': 0
                })
                m += 1
                if m > 12:
                    m = 1
                    y += 1

        return periods

    def _aggregate_data(self, consumption_data: List[Dict[str, Any]], 
                        reception_data: List[Dict[str, Any]], 
                        start_date: date, end_date: date, 
                        granularity: str) -> tuple[List[Dict[str, Any]], float, float, float]:
        """Agrège les transactions d'entrées et de sorties par période"""
        buckets = self._generate_period_buckets(start_date, end_date, granularity)
        lookup = {b['key']: b for b in buckets}

        # 1. Agrégation des Réceptions (Entrées / Achats)
        for item in reception_data:
            d = self._parse_date(item.get('date'))
            if not d or d < start_date or d > end_date:
                continue
            val = float(item.get('daily_value', 0) or item.get('daily_cost', 0) or item.get('Invoice_Total_TTC', 0) or 0.0)
            count = int(item.get('transaction_count', 1) or 1)

            if granularity == self.GRANULARITY_DAY:
                key = d.strftime("%Y-%m-%d")
            elif granularity == self.GRANULARITY_WEEK:
                iy, iw, _ = d.isocalendar()
                key = f"{iy}-W{iw:02d}"
            else:
                key = f"{d.year}-{d.month:02d}"

            if key in lookup:
                lookup[key]['in'] += val
                lookup[key]['count_in'] += count

        # 2. Agrégation des Consommations (Sorties / Consommation)
        for item in consumption_data:
            d = self._parse_date(item.get('date'))
            if not d or d < start_date or d > end_date:
                continue
            val = float(item.get('daily_value', 0) or item.get('daily_cost', 0) or 0.0)
            count = int(item.get('transaction_count', 1) or 1)

            if granularity == self.GRANULARITY_DAY:
                key = d.strftime("%Y-%m-%d")
            elif granularity == self.GRANULARITY_WEEK:
                iy, iw, _ = d.isocalendar()
                key = f"{iy}-W{iw:02d}"
            else:
                key = f"{d.year}-{d.month:02d}"

            if key in lookup:
                lookup[key]['out'] += val
                lookup[key]['count_out'] += count

        total_in = sum(b['in'] for b in buckets)
        total_out = sum(b['out'] for b in buckets)
        
        # Trouver la valeur maximale pour l'échelle de l'axe Y
        if self._view_mode == self.VIEW_STACKED:
            max_val = max([b['in'] + b['out'] for b in buckets] + [0.0])
        elif self._view_mode == self.VIEW_NET_FLOW:
            max_val = max([abs(b['in'] - b['out']) for b in buckets] + [0.0])
        else:
            max_val = max([max(b['in'], b['out']) for b in buckets] + [0.0])

        return buckets, total_in, total_out, max_val

    # =========================================================================
    # 6. DESSIN ET MISE À JOUR DU GRAPHIQUE (QTCHARTS)
    # =========================================================================
    def render_chart(self):
        """Reconstruit et dessine le graphique à barres selon les réglages actuels"""
        try:
            # 1. Cacher la carte flottante avant redessin
            self.hover_card.hide()
            self._hovered_index = None

            # 2. Nettoyage des anciennes séries et axes
            self.chart.removeAllSeries()
            for axis in self.chart.axes():
                self.chart.removeAxis(axis)

            start_date, end_date = self._get_active_date_range()
            buckets, total_in, total_out, max_val = self._aggregate_data(
                self._raw_consumption, self._raw_reception, 
                start_date, end_date, self._granularity
            )
            self._aggregated_data = buckets

            # 3. Mise à jour des badges résumés
            self._update_summary_metrics(total_in, total_out, len(buckets))

            # 4. Vérification de l'état vide
            has_data = any(b['in'] > 0 or b['out'] > 0 for b in buckets)
            if not buckets or not has_data:
                self.chart_view.setVisible(False)
                self.empty_state_label.setVisible(True)
                return

            self.chart_view.setVisible(True)
            self.empty_state_label.setVisible(False)

            # 5. Construction des séries de colonnes
            categories = [b['label'] for b in buckets]

            if self._view_mode == self.VIEW_NET_FLOW:
                self._render_net_flow_chart(buckets, categories, max_val)
            else:
                self._render_in_out_bars(buckets, categories, max_val)

        except Exception as e:
            logging.error(f"Erreur lors du rendu du graphique de stock: {e}", exc_info=True)

    def _render_in_out_bars(self, buckets: List[Dict[str, Any]], categories: List[str], max_val: float):
        """Construit les colonnes d'entrées (Vert) et sorties (Rouge) groupées ou empilées"""
        # Colonnes Entrées (Vert)
        set_in = QBarSet("📥 Entrées (Achats)")
        set_in.setColor(QColor(self.COLOR_IN))
        set_in.setBorderColor(QColor(self.COLOR_IN_BORDER))
        set_in.setBrush(QBrush(QColor(self.COLOR_IN)))

        # Colonnes Sorties (Rouge)
        set_out = QBarSet("📤 Sorties (Consommation)")
        set_out.setColor(QColor(self.COLOR_OUT))
        set_out.setBorderColor(QColor(self.COLOR_OUT_BORDER))
        set_out.setBrush(QBrush(QColor(self.COLOR_OUT)))

        for b in buckets:
            set_in.append(b['in'])
            set_out.append(b['out'])

        if self._view_mode == self.VIEW_STACKED:
            series = QStackedBarSeries()
        else:
            series = QBarSeries()

        series.append(set_in)
        series.append(set_out)
        series.setBarWidth(0.7 if self._view_mode == self.VIEW_STACKED else 0.75)

        # Connexion du signal Hover
        series.hovered.connect(self._on_bar_hovered)
        series.clicked.connect(self._on_bar_clicked)

        self.chart.addSeries(series)

        # --- Axe X (Catégories) ---
        axis_x = QBarCategoryAxis()
        axis_x.append(categories)
        axis_x.setLabelsFont(QFont("Segoe UI", 9))
        axis_x.setGridLineColor(QColor("#f1f5f9"))
        
        if len(categories) > 14 and self._granularity == self.GRANULARITY_DAY:
            axis_x.setLabelsAngle(-45)
        else:
            axis_x.setLabelsAngle(0)

        self.chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        series.attachAxis(axis_x)

        # --- Axe Y (Valeurs en DA) ---
        axis_y = QCategoryAxis()
        self._setup_y_axis(axis_y, max_val, "Montant (DA)")
        self.chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis_y)

    def _setup_y_axis(self, axis_y: QCategoryAxis, max_val: float, title: str = "Montant (DA)"):
        """Configure l'axe Y avec des intervalles clairs formatés en dinars (1 987 654,32 DA)"""
        axis_y.setLabelsFont(QFont("Segoe UI", 9))
        axis_y.setGridLineColor(QColor("#f1f5f9"))
        axis_y.setTitleText(title)
        axis_y.setTitleFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        axis_y.setLabelsPosition(QCategoryAxis.AxisLabelsPosition.AxisLabelsPositionOnValue)

        y_max = max(max_val * 1.15, 1000.0)
        raw_step = y_max / 5.0
        magnitude = 10 ** max(0, len(str(int(raw_step))) - 1)
        factor = raw_step / magnitude
        if factor < 1.5:
            step = 1 * magnitude
        elif factor < 3.5:
            step = 2 * magnitude
        elif factor < 7.5:
            step = 5 * magnitude
        else:
            step = 10 * magnitude

        actual_max = step * 5
        while actual_max < y_max:
            actual_max += step

        axis_y.setRange(0, actual_max)
        axis_y.append(format_money(0, "DA"), 0)
        curr = step
        while curr <= actual_max:
            axis_y.append(format_money(curr, "DA"), curr)
            curr += step

    def _render_net_flow_chart(self, buckets: List[Dict[str, Any]], categories: List[str], max_val: float):
        """Construit le graphique de solde net (Vert si positif, Rouge si négatif)"""
        set_pos = QBarSet("🟩 Solde Positif (Entrées > Sorties)")
        set_pos.setColor(QColor(self.COLOR_IN))
        set_pos.setBorderColor(QColor(self.COLOR_IN_BORDER))
        set_pos.setBrush(QBrush(QColor(self.COLOR_IN)))

        set_neg = QBarSet("🟥 Solde Négatif (Sorties > Entrées)")
        set_neg.setColor(QColor(self.COLOR_OUT))
        set_neg.setBorderColor(QColor(self.COLOR_OUT_BORDER))
        set_neg.setBrush(QBrush(QColor(self.COLOR_OUT)))

        for b in buckets:
            net = b['in'] - b['out']
            if net >= 0:
                set_pos.append(net)
                set_neg.append(0.0)
            else:
                set_pos.append(0.0)
                set_neg.append(abs(net))

        series = QBarSeries()
        series.append(set_pos)
        series.append(set_neg)
        series.hovered.connect(self._on_bar_hovered)
        series.clicked.connect(self._on_bar_clicked)

        self.chart.addSeries(series)

        axis_x = QBarCategoryAxis()
        axis_x.append(categories)
        axis_x.setLabelsFont(QFont("Segoe UI", 9))
        self.chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        series.attachAxis(axis_x)

        axis_y = QCategoryAxis()
        self._setup_y_axis(axis_y, max_val, "Solde Net (DA)")
        self.chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis_y)

    # =========================================================================
    # 7. GESTION DES INFOBULLES PERSISTANTES (CHARTHOVERCARD)
    # =========================================================================
    def _on_bar_hovered(self, status: bool, index: int, barset: QBarSet = None):
        """Affiche ou masque la carte d'information persistante sans timeout abrupt"""
        if status and 0 <= index < len(self._aggregated_data):
            self._hovered_index = index
            item = self._aggregated_data[index]
            
            # Positionner la carte par rapport aux coordonnées relatives de chart_view
            global_pos = QCursor.pos()
            local_pos = self.chart_view.mapFromGlobal(global_pos)
            self.hover_card.update_and_show(item, local_pos, self.chart_view.rect())
        else:
            self._hovered_index = None
            # Masquer seulement si aucune sélection n'est verrouillée
            if self._pinned_index is None:
                self.hover_card.hide()

    def _on_bar_clicked(self, index: int, barset: QBarSet = None):
        """Permet de verrouiller/déverrouiller l'affichage d'une colonne au clic"""
        if 0 <= index < len(self._aggregated_data):
            if self._pinned_index == index:
                self._pinned_index = None
                self.hover_card.hide()
            else:
                self._pinned_index = index
                item = self._aggregated_data[index]
                global_pos = QCursor.pos()
                local_pos = self.chart_view.mapFromGlobal(global_pos)
                self.hover_card.update_and_show(item, local_pos, self.chart_view.rect())

    # =========================================================================
    # 8. ÉVÉNEMENTS ET ACTIONS UTILISATEUR
    # =========================================================================
    def _on_granularity_clicked(self, button: QPushButton):
        """Changement de granularité (Jour / Semaine / Mois)"""
        mode = button.property("granularity_mode")
        if mode and mode != self._granularity:
            self._granularity = mode
            self.render_chart()

    def _on_preset_changed(self, index: int):
        """Changement du filtre de période prédéfini"""
        preset = self.combo_preset.currentData()
        self.custom_dates_container.setVisible(preset == "CUSTOM")

        # Ajustement intelligent de la granularité recommandée
        if preset in ["7D", "14D", "30D", "THIS_MONTH"]:
            self._set_granularity_silent(self.GRANULARITY_DAY)
        elif preset in ["3M", "6M"]:
            self._set_granularity_silent(self.GRANULARITY_WEEK)
        elif preset in ["YTD", "12M"]:
            self._set_granularity_silent(self.GRANULARITY_MONTH)

        self._fetch_and_render_data()

    def _set_granularity_silent(self, mode: str):
        self._granularity = mode
        if mode == self.GRANULARITY_DAY:
            self.btn_day.setChecked(True)
        elif mode == self.GRANULARITY_WEEK:
            self.btn_week.setChecked(True)
        elif mode == self.GRANULARITY_MONTH:
            self.btn_month.setChecked(True)

    def _on_custom_dates_applied(self):
        """Application de dates personnalisées"""
        self._fetch_and_render_data()

    def _on_view_mode_changed(self, index: int):
        """Changement de mode de visualisation (Groupé / Empilé / Solde Net)"""
        mode = self.combo_view_mode.currentData()
        if mode and mode != self._view_mode:
            self._view_mode = mode
            self.render_chart()

    def _fetch_and_render_data(self):
        """Charge les données requises depuis stats_manager ou réagrège les données locales"""
        start_d, end_d = self._get_active_date_range()
        s_str = start_d.strftime("%Y-%m-%d")
        e_str = end_d.strftime("%Y-%m-%d")

        preset = self.combo_preset.currentData()
        if self.stats_manager and preset != "SYNC":
            try:
                cons_data = self.stats_manager.get_consumption_trend(s_str, e_str)
                rec_data = self.stats_manager.get_reception_trend(s_str, e_str)
                self._raw_consumption = cons_data or []
                self._raw_reception = rec_data or []
            except Exception as e:
                logging.error(f"Erreur chargement données historiques du graphique: {e}")

        self.render_chart()

    # =========================================================================
    # 9. API PUBLIQUE POUR LE DASHBOARD PARENT
    # =========================================================================
    def update_charts(self, consumption_data: List[Dict[str, Any]], 
                      reception_data: List[Dict[str, Any]], 
                      stats_manager=None,
                      global_start_date=None, 
                      global_end_date=None):
        """
        Point d'entrée principal appelé par OverviewTab / DashboardTab.
        Maintient une compatibilité 100% avec les appels existants.
        """
        if stats_manager:
            self.stats_manager = stats_manager

        if global_start_date:
            parsed_start = self._parse_date(global_start_date)
            if parsed_start: self._global_start_date = parsed_start

        if global_end_date:
            parsed_end = self._parse_date(global_end_date)
            if parsed_end: self._global_end_date = parsed_end

        preset = self.combo_preset.currentData()
        if preset == "SYNC" or not self.stats_manager:
            self._raw_consumption = consumption_data or []
            self._raw_reception = reception_data or []
            self.render_chart()
        else:
            self._fetch_and_render_data()