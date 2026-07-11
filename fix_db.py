import json
from database import DatabaseManager

updates = {
    'dest_label_bl': 'Correspondant:',
    'dest_label_rt': 'Correspondant:',
    'footer_left_bl': 'Responsable Stock',
    'footer_left_rt': 'Responsable Stock',
    'footer_right_bl': 'Accusé de réception',
    'footer_right_rt': 'Accusé de réception',
    'footer_left_label': 'Responsable Stock',
    'footer_right_label': 'Accusé de réception'
}

db = DatabaseManager()
conn = db.get_db_connection()
c = conn.cursor()
c.execute("SELECT Setting_Value FROM Settings WHERE Setting_Key = 'pdf_settings'")
row = c.fetchone()
if row and row[0]:
    db_data = json.loads(row[0])
    db_data.update(updates)
    c.execute("UPDATE Settings SET Setting_Value = %s WHERE Setting_Key = 'pdf_settings'", (json.dumps(db_data, ensure_ascii=False),))
    conn.commit()
    print('DB updated successfully')
else:
    print('No pdf_settings found in DB')
