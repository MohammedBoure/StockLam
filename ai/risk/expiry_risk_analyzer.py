# ai/risk/expiry_risk_analyzer.py

import logging
from datetime import datetime, date
from typing import List, Dict, Any

class ExpiryRiskAnalyzer:
    """
    محلل مخاطر انتهاء الصلاحية للدفعة (Expiry Risk Predictive Model).
    يقارن بين العمر المتبقي للدفعة ومعدل الاستهلاك المتوقع لمنع التلف.
    """

    def __init__(self, db_instance, demand_forecaster):
        self.db = db_instance
        self.forecaster = demand_forecaster

    def analyze_batch_risks(self) -> List[Dict[str, Any]]:
        """
        تحليل جميع الدفعات المتوفرة في المخزون وحساب نسبة خطر التلف قبل الانتهاء.
        """
        risks = []
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT 
                        ib.Batch_ID,
                        ib.Batch_Number,
                        ib.Product_ID,
                        pm.Product_Name,
                        pm.Usage_Qty_Per_Stock_Unit,
                        ib.Quantity_Current,
                        ib.Expiry_Date,
                        ib.Location_ID
                    FROM Inventory_Batches ib
                    JOIN Products_Master pm ON ib.Product_ID = pm.Product_ID
                    WHERE ib.Status = 'Available'
                      AND ib.Quantity_Current > 0
                      AND pm.Deleted_At IS NULL
                    ORDER BY ib.Expiry_Date ASC
                """
                cursor.execute(query)
                batches = cursor.fetchall()

                today = date.today()

                for b in batches:
                    expiry = b['Expiry_Date']
                    if not expiry:
                        continue

                    if isinstance(expiry, datetime):
                        expiry = expiry.date()

                    days_left = (expiry - today).days

                    # جلب التنبؤ بالطلب اليومي
                    fc = self.forecaster.forecast_product_demand(
                        product_id=b['Product_ID'],
                        current_stock_boxes=float(b['Quantity_Current']),
                        usage_qty_per_unit=float(b['Usage_Qty_Per_Stock_Unit'] or 1.0)
                    )

                    daily_demand_units = fc.get('daily_demand_avg', 0.0)
                    usage_per_unit = float(b['Usage_Qty_Per_Stock_Unit'] or 1.0)
                    current_batch_units = float(b['Quantity_Current']) * usage_per_unit

                    # كمية الاستهلاك المتوقعة خلال الأيام المتبقية لصلاحية هذه الدفعة
                    if days_left > 0:
                        expected_consumption_units = daily_demand_units * days_left
                    else:
                        expected_consumption_units = 0

                    # حساب نسبة الخطر (Risk Percentage)
                    if days_left <= 0:
                        risk_score = 100.0  # منتهية الصلاحية بالفعل
                        risk_level = "CRITICAL_EXPIRED"
                        recommendation = "حذف الدفعة وتسجيل تلف (Waste Log)"
                    elif expected_consumption_units < current_batch_units:
                        # الاستهلاك المتوقع أقل من كمية الدفعة -> خطر تلف جزئي أو كلي
                        unconsumed_units = current_batch_units - expected_consumption_units
                        unconsumed_boxes = round(unconsumed_units / usage_per_unit, 2)
                        
                        risk_score = min(99.0, max(40.0, (1 - (expected_consumption_units / current_batch_units)) * 100.0))
                        
                        if risk_score > 70:
                            risk_level = "HIGH_EXPIRY_RISK"
                            recommendation = f"اقتراح نقل {unconsumed_boxes} علبة لمختبر آخر (External Transfer) فوراً"
                        else:
                            risk_level = "MEDIUM_EXPIRY_RISK"
                            recommendation = "إعطاء أولوية صرف قصوى لهذه الدفعة (Priority FEFO)"
                    else:
                        risk_score = max(0.0, 100.0 - (days_left * 2.0))
                        risk_level = "LOW_RISK"
                        recommendation = "المخزون سينفد قبل تاريخ الصلاحية بشكل طبيعي"

                    risks.append({
                        "batch_id": b['Batch_ID'],
                        "batch_number": b['Batch_Number'],
                        "product_id": b['Product_ID'],
                        "product_name": b['Product_Name'],
                        "quantity_boxes": float(b['Quantity_Current']),
                        "expiry_date": str(expiry),
                        "days_left": days_left,
                        "daily_demand_units": daily_demand_units,
                        "risk_score": round(risk_score, 1),
                        "risk_level": risk_level,
                        "recommendation": recommendation
                    })

        except Exception as e:
            logging.error(f"Error analyzing batch expiry risks: {e}")

        # ترتيب النتائج حسب الأكثر خطورة
        risks.sort(key=lambda x: x['risk_score'], reverse=True)
        return risks
