# ai/anomaly/waste_detector.py

import logging
from datetime import datetime, date
from typing import List, Dict, Any
import math

class WasteAnomalyDetector:
    """
    محرك كشف الشذوذ (Anomaly Detection Engine) للذكاء الاصطناعي.
    يكتشف الأنماط الحركية غير العادية في الهدر أو تعديلات المخزون عبر التحليل الإحصائي (Z-Score / Modified IQR).
    """

    def __init__(self, db_instance):
        self.db = db_instance

    def detect_waste_anomalies(self, days_back: int = 90) -> List[Dict[str, Any]]:
        """
        تحليل حركات الهدر والتعديل واكتشاف العمليات التي تتجاوز حد الانحراف الإحصائي (Outliers).
        """
        anomalies = []
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                
                # 1. جلب حركات التلف وتعديل المخزون
                query = """
                    SELECT 
                        sml.Movement_ID,
                        sml.Transaction_Date,
                        sml.Product_ID,
                        pm.Product_Name,
                        sml.Movement_Type,
                        ABS(sml.Qty_Change) AS qty_wasted,
                        sml.Unit_Used,
                        sml.Notes,
                        r.Reason_Name,
                        u.Full_Name AS Operator_Name
                    FROM Stock_Movement_Log sml
                    JOIN Products_Master pm ON sml.Product_ID = pm.Product_ID
                    LEFT JOIN Waste_Reasons r ON sml.Reason_ID = r.Reason_ID
                    LEFT JOIN Users u ON sml.User_ID = u.User_ID
                    WHERE sml.Movement_Type IN ('Waste', 'Adjustment')
                      AND sml.Transaction_Date >= CURDATE() - INTERVAL %s DAY
                    ORDER BY sml.Product_ID, sml.Transaction_Date ASC
                """
                cursor.execute(query, (days_back,))
                records = cursor.fetchall()

                if not records:
                    return []

                # تجميع البيانات حسب المنتج لحساب المتوسط والانحراف المعياري لجميع العمليات
                prod_data = {}
                for r in records:
                    pid = r['Product_ID']
                    if pid not in prod_data:
                        prod_data[pid] = []
                    prod_data[pid].append(r)

                for pid, items in prod_data.items():
                    if len(items) < 3:
                        # لا توجد عينات كافية لحساب الشذوذ بدقة
                        continue

                    values = [float(x['qty_wasted']) for x in items]
                    mean = sum(values) / len(values)
                    variance = sum((x - mean) ** 2 for x in values) / len(values)
                    std_dev = math.sqrt(variance)

                    if std_dev == 0:
                        continue

                    for item in items:
                        val = float(item['qty_wasted'])
                        z_score = (val - mean) / std_dev

                        # Z-Score >= 1.25 (أو أعلى من 1.25 انحراف إيجابي عن المتوسط)
                        if z_score >= 1.25 and val > 1.0:
                            anomalies.append({
                                "movement_id": item['Movement_ID'],
                                "transaction_date": str(item['Transaction_Date']),
                                "product_id": item['Product_ID'],
                                "product_name": item['Product_Name'],
                                "movement_type": item['Movement_Type'],
                                "qty_wasted": val,
                                "unit": item['Unit_Used'],
                                "mean_product_waste": round(mean, 2),
                                "z_score": round(z_score, 2),
                                "operator_name": item['Operator_Name'] or "System",
                                "reason": item['Reason_Name'] or "غير محدد",
                                "notes": item['Notes'] or "",
                                "anomaly_severity": "HIGH" if z_score > 2.0 else "MEDIUM"
                            })


        except Exception as e:
            logging.error(f"Error in detect_waste_anomalies: {e}")

        anomalies.sort(key=lambda x: x['z_score'], reverse=True)
        return anomalies
