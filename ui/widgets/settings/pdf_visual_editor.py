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
        
        # Static table visualization (Mock)
        self.table_mock = QGraphicsRectItem(1.0 * CM_TO_PX, 9.5 * CM_TO_PX, 19.0 * CM_TO_PX, 5.0 * CM_TO_PX)
        self.table_mock.setBrush(QBrush(QColor("#f1c40f").lighter(150)))
        self.table_mock.setPen(QPen(Qt.NoPen))
        self.scene.addItem(self.table_mock)
        txt = QGraphicsTextItem("Zone du Tableau", self.table_mock)
        txt.setPos(1.0 * CM_TO_PX + 5, 9.5 * CM_TO_PX + 5)
        
        # --- Create Draggable Elements ---
        
        # Destinataire Box (Can move X and Y)
        self.el_dest = DraggableElement(
            'dest_box_x_cm', 'dest_box_y_cm', 
            width_cm=self.settings.get('dest_box_w_cm', 8.0), height_cm=2.5, 
            label="Boîte Destinataire", color="#9b59b6"
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
        
        self.lbl_dest_x = QLabel("0.0 cm")
        self.lbl_dest_y = QLabel("0.0 cm")
        self.lbl_sig_l_x = QLabel("0.0 cm")
        self.lbl_sig_r_x = QLabel("0.0 cm")
        
        form.addRow(QLabel("<b>Boîte Destinataire</b>"))
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
        
        # Destinataire
        dx = float(s.get('dest_box_x_cm', 11.5))
        dy = float(s.get('dest_box_y_cm', 6.0))
        self.el_dest.setPos(dx * CM_TO_PX, dy * CM_TO_PX)
        self.lbl_dest_x.setText(f"{dx:.2f} cm")
        self.lbl_dest_y.setText(f"{dy:.2f} cm")
        
        # Table Y (Mock)
        table_y = float(s.get('table_start_y_cm', 9.5))
        self.table_mock.setRect(1.0 * CM_TO_PX, table_y * CM_TO_PX, 19.0 * CM_TO_PX, 5.0 * CM_TO_PX)
        
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
            if key_x == 'dest_box_x_cm': self.lbl_dest_x.setText(f"{val_x:.2f} cm")
            if key_x == 'footer_left_x_cm': self.lbl_sig_l_x.setText(f"{val_x:.2f} cm")
            if key_x == 'footer_right_x_cm': self.lbl_sig_r_x.setText(f"{val_x:.2f} cm")
            
        if key_y:
            self.settings[key_y] = round(val_y, 2)
            if key_y == 'dest_box_y_cm': self.lbl_dest_y.setText(f"{val_y:.2f} cm")
            
        self.settings_changed.emit(self.settings)

    def update_settings_from_external(self, new_settings):
        # Called when spinboxes change
        self.settings.update(new_settings)
        
        # Update width of elements dynamically
        self.el_dest.setRect(0, 0, float(self.settings.get('dest_box_w_cm', 8.0)) * CM_TO_PX, 2.5 * CM_TO_PX)
        fh = float(self.settings.get('footer_height_cm', 2.5)) * CM_TO_PX
        self.el_sig_l.setRect(0, 0, 4.0 * CM_TO_PX, fh)
        self.el_sig_r.setRect(0, 0, 4.0 * CM_TO_PX, fh)
        
        self.load_from_settings()
