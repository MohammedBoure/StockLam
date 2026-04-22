"""
reception_dialog/__init__.py
-----------------------------
نقطة الدخول الوحيدة للحزمة.
الاستيراد الخارجي يكفي:

    from .reception_dialog import ReceptionDialog

أو باستخدام المسار الكامل:

    from ui.widgets.reception.reception_dialog import ReceptionDialog
"""

from .reception_dialog        import ReceptionDialog
from .auto_select_widgets     import AutoSelectSpinBox, AutoSelectLineEdit, AutoSelectDoubleSpinBox
from .reception_dialog_ui     import ReceptionDialogUIMixin
from .reception_dialog_logic  import ReceptionDialogLogicMixin

__all__ = [
    "ReceptionDialog",
    "AutoSelectSpinBox",
    "AutoSelectLineEdit",
    "AutoSelectDoubleSpinBox",
    "ReceptionDialogUIMixin",
    "ReceptionDialogLogicMixin",
]
