# ai/forecasting/demand_forecaster.py

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import math

class DemandForecaster:
    """
    محرك التنبؤ بالطلب للذكاء الاصطناعي (Demand Forecasting Engine).
    يحلل السلاسل الزمنية لاستهلاك المواد والكواشف في المختبر لتحديد:
    - معدل الاستهلاك اليومي المتوقع (Forecasted Daily Demand)
    - عدد الأيام المتبقية قبل نفاد المخزون (Days to Stockout)
    - النقطة المثالية لإعادة الطلب تلقائياً (Reorder Level & Quantity)
    """

    def __init__(self, db_instance):
        self.db = db_instance

    def get_historical_consumption(self, product_id: int, days_back: int = 90) -> List[Dict[str, Any]]:
        """
        جلب بيانات الاستهلاك اليومية لمنتج معين خلال الأيام السابقة.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT 
                        DATE(sml.Transaction_Date) AS movement_date,
                        SUM(ABS(sml.Qty_Change)) AS daily_qty
                    FROM Stock_Movement_Log sml
                    WHERE sml.Product_ID = %s
                      AND sml.Movement_Type IN ('Patient_Test', 'QC_Run', 'Open_Pack', 'Waste', 'Sale')
                      AND sml.Transaction_Date >= CURDATE() - INTERVAL %s DAY
                    GROUP BY DATE(sml.Transaction_Date)
                    ORDER BY movement_date ASC
                """
                cursor.execute(query, (product_id, days_back))
                return cursor.fetchall()
        except Exception as e:
            logging.error(f"Error fetching historical consumption for product {product_id}: {e}")
            return []

    def forecast_product_demand(
        self, 
        product_id: int, 
        current_stock_boxes: float, 
        usage_qty_per_unit: float = 1.0,
        lead_time_days: int = 7
    ) -> Dict[str, Any]:
        """
        حساب التنبؤ بالطلب والتحليل الذكي لمنتج محدد.
        """
        history = self.get_historical_consumption(product_id, days_back=90)
        
        if not history:
            # افتراض عدم وجود سجل استهلاك كافٍ
            return {
                "product_id": product_id,
                "has_enough_data": False,
                "daily_demand_avg": 0.0,
                "forecast_method": "Insufficient Data",
                "days_until_depletion": float('inf'),
                "recommended_reorder_qty": 0,
                "reorder_point": 0.0,
                "safety_stock": 0.0,
                "confidence_score": 0.0
            }

        daily_quantities = [row['daily_qty'] for row in history]

        # 1. حساب المتوسط الموزون أسيّاً (Exponential Moving Average / Weighted Trend)
        alpha = 0.3  # وزن البيانات الأحدث
        ema = daily_quantities[0]
        for qty in daily_quantities[1:]:
            ema = alpha * qty + (1 - alpha) * ema

        # حساب الانحراف المعياري لتقدير مخزون الأمان (Safety Stock)
        avg = sum(daily_quantities) / len(daily_quantities)
        variance = sum((x - avg) ** 2 for x in daily_quantities) / max(len(daily_quantities), 1)
        std_dev = math.sqrt(variance)

        # مخزون الأمان (Safety Stock) بمستوى ثقة 95% (Z = 1.65)
        safety_stock = 1.65 * std_dev * math.sqrt(lead_time_days)

        # نقطة إعادة الطلب (Reorder Point in Usage Units)
        reorder_point_units = (ema * lead_time_days) + safety_stock

        # تحويل الوحدات إلى علب (Boxes)
        usage_per_unit = max(usage_qty_per_unit, 1.0)
        current_stock_units = current_stock_boxes * usage_per_unit

        days_until_depletion = (
            current_stock_units / ema if ema > 0 else float('inf')
        )

        reorder_qty_boxes = math.ceil(
            (reorder_point_units + (ema * 14)) / usage_per_unit
        ) if current_stock_units <= reorder_point_units else 0

        # درجة الثقة في التنبؤ بناءً على عدد أيام البيانات والتغير
        confidence = min(100.0, max(20.0, (len(daily_quantities) / 90.0) * 100.0 - (std_dev / (avg + 1e-5)) * 10.0))

        return {
            "product_id": product_id,
            "has_enough_data": True,
            "daily_demand_avg": round(float(ema), 2),
            "forecast_method": "Exponential Smoothing (EMA) + Trend",
            "days_until_depletion": round(float(days_until_depletion), 1) if days_until_depletion != float('inf') else 999,
            "current_stock_units": round(float(current_stock_units), 2),
            "reorder_point_units": round(float(reorder_point_units), 2),
            "safety_stock": round(float(safety_stock), 2),
            "recommended_reorder_qty_boxes": reorder_qty_boxes,
            "needs_reorder": current_stock_units <= reorder_point_units,
            "confidence_score": round(confidence, 1)
        }

    def forecast_all_products(self) -> List[Dict[str, Any]]:
        """
        تشغيل التنبؤ لجميع المنتجات النشطة في النظام.
        """
        results = []
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT 
                        pm.Product_ID,
                        pm.Product_Name,
                        pm.Usage_Qty_Per_Stock_Unit,
                        COALESCE(SUM(ib.Quantity_Current), 0) AS Current_Stock_Boxes
                    FROM Products_Master pm
                    LEFT JOIN Inventory_Batches ib ON pm.Product_ID = ib.Product_ID AND ib.Status = 'Available'
                    WHERE pm.Deleted_At IS NULL
                    GROUP BY pm.Product_ID, pm.Product_Name, pm.Usage_Qty_Per_Stock_Unit
                """
                cursor.execute(query)
                products = cursor.fetchall()

                for p in products:
                    fc = self.forecast_product_demand(
                        product_id=p['Product_ID'],
                        current_stock_boxes=float(p['Current_Stock_Boxes']),
                        usage_qty_per_unit=float(p['Usage_Qty_Per_Stock_Unit'] or 1.0)
                    )
                    fc['product_name'] = p['Product_Name']
                    fc['current_stock_boxes'] = float(p['Current_Stock_Boxes'])
                    results.append(fc)

        except Exception as e:
            logging.error(f"Error in forecast_all_products: {e}")

        return results
