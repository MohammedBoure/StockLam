from PySide6.QtGui import QPixmap, QPainter, QColor, QFont, QIcon
from PySide6.QtCore import Qt

_reclamation_icon_cache = None

def get_reclamation_icon() -> QIcon:
    global _reclamation_icon_cache
    if _reclamation_icon_cache is not None:
        return _reclamation_icon_cache
        
    pixmap = QPixmap(24, 24)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    
    # دائرة حمراء
    painter.setBrush(QColor("#e74c3c"))
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(2, 2, 20, 20)
    
    # علامة تعجب بيضاء
    painter.setPen(QColor("white"))
    font = QFont("Arial", 12, QFont.Bold)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignCenter, "!")
    
    painter.end()
    _reclamation_icon_cache = QIcon(pixmap)
    return _reclamation_icon_cache
