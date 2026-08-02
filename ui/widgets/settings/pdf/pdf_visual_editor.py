from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QGraphicsView, QGraphicsScene, 
    QGraphicsRectItem, QGraphicsTextItem, QGraphicsItem, QLabel, QPushButton,
    QScrollArea, QFormLayout, QDoubleSpinBox, QGroupBox, QSplitter
)
from PySide6.QtCore import Qt, Signal, QRectF
from PySide6.QtGui import QColor, QPen, QBrush, QFont, QPainter

# 1 CM = 30 Pixels for our canvas rendering
CM_TO_PX = 30.0

class DraggableElement(QGraphicsRectItem):
    def __init__(self, key_x, key_y, width_cm, height_cm, label, color="#3498db", allow_y=True, allow_x=True):
        super().__init__(0, 0, width_cm * CM_TO_PX, height_cm * CM_TO_PX)
        
        self.key_x = key_x
        self.key_y = key_y
        self.allow_y = allow_y
        self.allow_x = allow_x
        
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        
        self.setBrush(QBrush(QColor(color).lighter(150)))
        self.setPen(QPen(QColor(color), 2))
        
        # Add label text
        self.text_item = QGraphicsTextItem(label, self)
        self.text_item.setFont(QFont("Arial", 9, QFont.Bold))
        self.text_item.setDefaultTextColor(QColor(color).darker(150))
        
        # Center the text
        txt_rect = self.text_item.boundingRect()
        self.text_item.setPos((self.rect().width() - txt_rect.width()) / 2, 
                              (self.rect().height() - txt_rect.height()) / 2)
        self.setCursor(Qt.OpenHandCursor)

    def mousePressEvent(self, event):
        self.setCursor(Qt.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self.setCursor(Qt.OpenHandCursor)
        super().mouseReleaseEvent(event)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange:
            new_pos = value
            # Restrict movement bounds (A4 = 21x29.7)
            x = new_pos.x()
            y = new_pos.y()
            
            if not self.allow_x:
                x = self.pos().x()
            if not self.allow_y:
                y = self.pos().y()
                
            x = max(0, min(x, 21.0 * CM_TO_PX - self.rect().width()))
            y = max(0, min(y, 29.7 * CM_TO_PX - self.rect().height()))
            
            if self.scene():
                self.scene().element_moved.emit(self.key_x, self.key_y, x / CM_TO_PX, y / CM_TO_PX)
                
            return super().itemChange(change, new_pos)
        return super().itemChange(change, value)


class A4Scene(QGraphicsScene):
    element_moved = Signal(str, str, float, float)
    
    def __init__(self):
        super().__init__()
        self.setSceneRect(0, 0, 21.0 * CM_TO_PX, 29.7 * CM_TO_PX)
        
    def drawBackground(self, painter, rect):
        painter.fillRect(self.sceneRect(), Qt.white)
        # Draw some subtle grid lines every CM
        pen = QPen(QColor(240, 240, 240))
        painter.setPen(pen)
        
        # Vertical lines
        for i in range(1, 21):
            painter.drawLine(int(i * CM_TO_PX), 0, int(i * CM_TO_PX), int(29.7 * CM_TO_PX))
        # Horizontal lines
        for i in range(1, 30):
            painter.drawLine(0, int(i * CM_TO_PX), int(21.0 * CM_TO_PX), int(i * CM_TO_PX))
            
        # Draw border
        painter.setPen(QPen(Qt.black, 1))
        painter.drawRect(self.sceneRect())


class VisualPdfEditorDialog(QDialog):
    settings_changed = Signal(dict)
    
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Éditeur Visuel PDF (WYSIWYG)")
        self.resize(1000, 800) # Big window
        self.settings = settings.copy()
        self.elements = {}
        self.init_ui()
        self.load_from_settings()
        
    def init_ui(self):
        main_layout = QVBoxLayout(self)
        layout = QHBoxLayout()
        
        # --- LEFT: Visual Canvas ---
        self.scene = A4Scene()
        self.scene.element_moved.connect(self.on_element_moved)
        
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.Antialiasing)
        self.view.setDragMode(QGraphicsView.RubberBandDrag)
        
        # --- Create Draggable Elements ---
        self.el_header = DraggableElement(
            'header_info_x_cm', 'header_info_y_cm',
            width_cm=self.settings.get('header_info_w_cm', 9.5), height_cm=2.8,
            label="Informations / Adresse", color="#16a085"
        )
        self.scene.addItem(self.el_header)

        self.el_date = DraggableElement(
            'creation_date_x_cm', 'creation_date_y_cm',
            width_cm=9.5, height_cm=0.8,
            label="Date de création", color="#34495e"
        )
        self.scene.addItem(self.el_date)

        self.el_table = DraggableElement(
            'table_start_x_cm', 'table_start_y_cm',
            width_cm=19.0, height_cm=5.0,
            label="Zone du Tableau", color="#f1c40f"
        )
        self.scene.addItem(self.el_table)

        # Correspondant box (Can move X and Y)
        self.el_dest = DraggableElement(
            'dest_box_x_cm', 'dest_box_y_cm',
            width_cm=self.settings.get('dest_box_w_cm', 8.0), height_cm=4.5,
            label="Boîte Correspondant", color="#9b59b6"
        )
        self.scene.addItem(self.el_dest)
        
        # Signature Gauche (X only, Y depends on table + offset)
        self.el_sig_l = DraggableElement(
            'footer_left_x_cm', None, 
            width_cm=4.0, height_cm=self.settings.get('footer_height_cm', 2.5), 
            label="Sig. Gauche", color="#e74c3c", allow_y=False
        )
        self.scene.addItem(self.el_sig_l)
        
        # Signature Droite (X only)
        self.el_sig_r = DraggableElement(
            'footer_right_x_cm', None, 
            width_cm=4.0, height_cm=self.settings.get('footer_height_cm', 2.5), 
            label="Sig. Droite", color="#2ecc71", allow_y=False
        )
        self.scene.addItem(self.el_sig_r)

        # --- RIGHT: Live Property Panel ---
        self.panel = QWidget()
        self.panel.setMaximumWidth(300)
        form = QFormLayout(self.panel)
        
        self.lbl_header_x = QLabel("0.0 cm")
        self.lbl_header_y = QLabel("0.0 cm")
        self.lbl_date_x = QLabel("0.0 cm")
        self.lbl_date_y = QLabel("0.0 cm")
        self.lbl_table_x = QLabel("0.0 cm")
        self.lbl_table_y = QLabel("0.0 cm")
        self.lbl_dest_x = QLabel("0.0 cm")
        self.lbl_dest_y = QLabel("0.0 cm")
        self.lbl_sig_l_x = QLabel("0.0 cm")
        self.lbl_sig_r_x = QLabel("0.0 cm")

        form.addRow(QLabel("<b>Informations / Adresse</b>"))
        form.addRow("Position X:", self.lbl_header_x)
        form.addRow("Position Y (depuis le haut):", self.lbl_header_y)
        form.addRow(QLabel("<hr>"))
        form.addRow(QLabel("<b>Date de création</b>"))
        form.addRow("Position X:", self.lbl_date_x)
        form.addRow("Position Y (depuis le haut):", self.lbl_date_y)
        form.addRow(QLabel("<hr>"))
        form.addRow(QLabel("<b>Tableau</b>"))
        form.addRow("Position X:", self.lbl_table_x)
        form.addRow("Position Y (depuis le haut):", self.lbl_table_y)
        form.addRow(QLabel("<hr>"))
        form.addRow(QLabel("<b>Boîte Correspondant</b>"))
        form.addRow("Position X:", self.lbl_dest_x)
        form.addRow("Position Y (depuis le haut):", self.lbl_dest_y)
        form.addRow(QLabel("<hr>"))
        form.addRow(QLabel("<b>Signatures (X uniquement)</b>"))
        form.addRow("Sig. Gauche X:", self.lbl_sig_l_x)
        form.addRow("Sig. Droite X:", self.lbl_sig_r_x)
        form.addRow(QLabel("<br><i>Note : La position Y des signatures dépend de la taille du tableau (dynamique).</i>"))
        
        btn_close = QPushButton("Valider et Fermer")
        btn_close.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; padding: 10px; font-size: 14px;")
        btn_close.clicked.connect(self.accept)
        form.addRow(QLabel("<br>"))
        form.addRow(btn_close)
        
        layout.addWidget(self.view, stretch=1)
        layout.addWidget(self.panel)
        main_layout.addLayout(layout)
        
    def load_from_settings(self):
        s = self.settings
        
        # Header information
        header_x = float(s.get('header_info_x_cm', 1.0))
        header_y = float(s.get('header_info_y_cm', 5.4))
        self.el_header.setPos(header_x * CM_TO_PX, header_y * CM_TO_PX)
        self.lbl_header_x.setText(f"{header_x:.2f} cm")
        self.lbl_header_y.setText(f"{header_y:.2f} cm")

        # Creation date
        date_x = float(s.get('creation_date_x_cm', 1.0))
        date_y = float(s.get('creation_date_y_cm', 9.3))
        self.el_date.setPos(date_x * CM_TO_PX, date_y * CM_TO_PX)
        self.lbl_date_x.setText(f"{date_x:.2f} cm")
        self.lbl_date_y.setText(f"{date_y:.2f} cm")

        # Table
        table_x = float(s.get('table_start_x_cm', 1.0))
        table_y = float(s.get('table_start_y_cm', 10.5))
        self.el_table.setPos(table_x * CM_TO_PX, table_y * CM_TO_PX)
        self.lbl_table_x.setText(f"{table_x:.2f} cm")
        self.lbl_table_y.setText(f"{table_y:.2f} cm")

        # Correspondant
        dx = float(s.get('dest_box_x_cm', 11.5))
        dy = float(s.get('dest_box_y_cm', 5.4))
        self.el_dest.setPos(dx * CM_TO_PX, dy * CM_TO_PX)
        self.lbl_dest_x.setText(f"{dx:.2f} cm")
        self.lbl_dest_y.setText(f"{dy:.2f} cm")

        # Footer Y base (Table Y + Table Height + offset)
        base_y = table_y + 5.0 + float(s.get('footer_y_offset_cm', 1.5))
        
        # Sig Left
        sl_x = float(s.get('footer_left_x_cm', 1.0))
        self.el_sig_l.setPos(sl_x * CM_TO_PX, base_y * CM_TO_PX)
        self.lbl_sig_l_x.setText(f"{sl_x:.2f} cm")
        
        # Sig Right
        sr_x = float(s.get('footer_right_x_cm', 12.0))
        self.el_sig_r.setPos(sr_x * CM_TO_PX, base_y * CM_TO_PX)
        self.lbl_sig_r_x.setText(f"{sr_x:.2f} cm")

    def on_element_moved(self, key_x, key_y, val_x, val_y):
        if key_x:
            self.settings[key_x] = round(val_x, 2)
            if key_x == 'header_info_x_cm': self.lbl_header_x.setText(f"{val_x:.2f} cm")
            if key_x == 'creation_date_x_cm': self.lbl_date_x.setText(f"{val_x:.2f} cm")
            if key_x == 'table_start_x_cm': self.lbl_table_x.setText(f"{val_x:.2f} cm")
            if key_x == 'dest_box_x_cm': self.lbl_dest_x.setText(f"{val_x:.2f} cm")
            if key_x == 'footer_left_x_cm': self.lbl_sig_l_x.setText(f"{val_x:.2f} cm")
            if key_x == 'footer_right_x_cm': self.lbl_sig_r_x.setText(f"{val_x:.2f} cm")

        if key_y:
            self.settings[key_y] = round(val_y, 2)
            if key_y == 'header_info_y_cm': self.lbl_header_y.setText(f"{val_y:.2f} cm")
            if key_y == 'creation_date_y_cm': self.lbl_date_y.setText(f"{val_y:.2f} cm")
            if key_y == 'table_start_y_cm': self.lbl_table_y.setText(f"{val_y:.2f} cm")
            if key_y == 'dest_box_y_cm': self.lbl_dest_y.setText(f"{val_y:.2f} cm")
            
        self.settings_changed.emit(self.settings)

    def update_settings_from_external(self, new_settings):
        # Called when spinboxes change
        self.settings.update(new_settings)
        
        # Update element dimensions dynamically
        self.el_header.setRect(0, 0, float(self.settings.get('header_info_w_cm', 9.5)) * CM_TO_PX, 2.8 * CM_TO_PX)
        self.el_date.setRect(0, 0, 9.5 * CM_TO_PX, 0.8 * CM_TO_PX)
        self.el_table.setRect(0, 0, 19.0 * CM_TO_PX, 5.0 * CM_TO_PX)
        self.el_dest.setRect(0, 0, float(self.settings.get('dest_box_w_cm', 8.0)) * CM_TO_PX, 4.5 * CM_TO_PX)
        fh = float(self.settings.get('footer_height_cm', 2.5)) * CM_TO_PX
        self.el_sig_l.setRect(0, 0, 4.0 * CM_TO_PX, fh)
        self.el_sig_r.setRect(0, 0, 4.0 * CM_TO_PX, fh)
        
        self.load_from_settings()
