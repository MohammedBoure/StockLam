# ai/ai_service.py

import logging
from typing import List, Dict, Any, Optional
from .forecasting.demand_forecaster import DemandForecaster
from .risk.expiry_risk_analyzer import ExpiryRiskAnalyzer
from .anomaly.waste_detector import WasteAnomalyDetector

class AIService:
    """
    الخدمة المركزية للذكاء الاصطناعي وتعلم الآلة في StockLam / MODERNSTOCK.
    توفر واجهة بسيطة وموحدة لكافة الميزات التنبؤية واكتشاف الشذوذ.
    """

    def __init__(self, db_instance):
        self.db = db_instance
        self.forecaster = DemandForecaster(db_instance)
        self.risk_analyzer = ExpiryRiskAnalyzer(db_instance, self.forecaster)
        self.anomaly_detector = WasteAnomalyDetector(db_instance)

    def get_smart_reorder_recommendations(self) -> List[Dict[str, Any]]:
        """
        جلب توصيات إعادة الطلب الذاتي للمنتجات التي تحتاج لشراء قريباً بناءً على الذكاء الاصطناعي.
        """
        forecasts = self.forecaster.forecast_all_products()
        reorder_list = [f for f in forecasts if f.get('needs_reorder', False)]
        reorder_list.sort(key=lambda x: x['days_until_depletion'])
        return reorder_list

    def get_expiry_risk_report(self) -> List[Dict[str, Any]]:
        """
        جلب تقرير مخاطر الصلاحية والدفعات المعرضة للتلف.
        """
        return self.risk_analyzer.analyze_batch_risks()

    def get_consumption_anomalies(self) -> List[Dict[str, Any]]:
        """
        جلب العمليات التي تم اكتشاف شذوذ أو قيَم متطرفة بها في الهدر.
        """
        return self.anomaly_detector.detect_waste_anomalies()

    def get_ai_kpi_summary(self) -> Dict[str, Any]:
        """
        ملخص تنفيذي لسير عمل الذكاء الاصطناعي (أرقام سريعة للداشبورد).
        """
        try:
            reorder_recs = self.get_smart_reorder_recommendations()
            expiry_risks = self.get_expiry_risk_report()
            high_risks = [r for r in expiry_risks if r['risk_score'] >= 70.0]
            anomalies = self.get_consumption_anomalies()

            return {
                "products_needing_reorder": len(reorder_recs),
                "batches_high_expiry_risk": len(high_risks),
                "detected_waste_anomalies": len(anomalies),
                "total_batches_analyzed": len(expiry_risks)
            }
        except Exception as e:
            logging.error(f"Error compiling AI KPI summary: {e}")
            return {
                "products_needing_reorder": 0,
                "batches_high_expiry_risk": 0,
                "detected_waste_anomalies": 0,
                "total_batches_analyzed": 0
            }
