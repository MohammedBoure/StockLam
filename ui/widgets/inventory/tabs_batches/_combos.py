# ui/widgets/inventory/tabs_batches/_combos.py
"""
تعبئة القوائم المنسدلة: العائلات، الماركات، الأتمتة
"""


def _adjust_combo_view_width(combo):
    """توسيع قائمة العرض لتلائم أطول نص"""
    width = combo.width()
    fm    = combo.fontMetrics()
    for i in range(combo.count()):
        text_width = fm.horizontalAdvance(combo.itemText(i)) + 30
        if text_width > width:
            width = text_width
    combo.view().setMinimumWidth(width)


def populate_families(self):
    self.combo_family.clear()
    self.combo_family.addItem("📁 Familles", None)
    try:
        if hasattr(self.manager, 'families'):
            for f in self.manager.families.get_all_families():
                self.combo_family.addItem(f['Family_Name'], f['Family_ID'])
        _adjust_combo_view_width(self.combo_family)
    except Exception:
        pass


def populate_manufacturers(self):
    self.combo_manuf.clear()
    self.combo_manuf.addItem("🏭 Marques", None)
    try:
        if hasattr(self.manager, 'manufacturers'):
            for m in self.manager.manufacturers.get_all_manufacturers():
                self.combo_manuf.addItem(m['Manuf_Name'], m['Manuf_ID'])
        _adjust_combo_view_width(self.combo_manuf)
    except Exception:
        pass


def populate_automates(self):
    self.combo_automate.clear()
    self.combo_automate.addItem("⚙️ Automates", None)
    try:
        if hasattr(self.manager, 'automates'):
            for a in self.manager.automates.get_all_automates():
                self.combo_automate.addItem(a['Automate_Name'], a['Automate_ID'])
        _adjust_combo_view_width(self.combo_automate)
    except Exception:
        pass
