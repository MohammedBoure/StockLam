# test/test_ai_forecasting.py

import unittest
from unittest.mock import MagicMock
from datetime import date, datetime, timedelta

from ai.forecasting.demand_forecaster import DemandForecaster
from ai.risk.expiry_risk_analyzer import ExpiryRiskAnalyzer
from ai.anomaly.waste_detector import WasteAnomalyDetector
from ai.ai_service import AIService

class TestAIFeatures(unittest.TestCase):

    def setUp(self):
        self.mock_db = MagicMock()
        self.mock_conn = MagicMock()
        self.mock_cursor = MagicMock()

        self.mock_db.get_db_connection.return_value.__enter__.return_value = self.mock_conn
        self.mock_conn.cursor.return_value = self.mock_cursor

    def test_demand_forecaster(self):
        # محاكاة سجل استهلاك لـ 10 أيام
        self.mock_cursor.fetchall.return_value = [
            {'movement_date': date.today() - timedelta(days=i), 'daily_qty': 10.0}
            for i in range(10)
        ]

        forecaster = DemandForecaster(self.mock_db)
        result = forecaster.forecast_product_demand(
            product_id=1,
            current_stock_boxes=5.0,
            usage_qty_per_unit=100.0,
            lead_time_days=7
        )

        self.assertTrue(result['has_enough_data'])
        self.assertGreater(result['daily_demand_avg'], 0)
        self.assertIn('days_until_depletion', result)
        self.assertIn('confidence_score', result)

    def test_expiry_risk_analyzer(self):
        forecaster = DemandForecaster(self.mock_db)
        forecaster.forecast_product_demand = MagicMock(return_value={
            'daily_demand_avg': 5.0,
            'days_until_depletion': 10
        })

        # محاكاة دفعات في المخزون
        self.mock_cursor.fetchall.return_value = [
            {
                'Batch_ID': 101,
                'Batch_Number': 'LOT-2026-001',
                'Product_ID': 1,
                'Product_Name': 'Reagent A',
                'Usage_Qty_Per_Stock_Unit': 100.0,
                'Quantity_Current': 10.0,
                'Expiry_Date': date.today() + timedelta(days=5),
                'Location_ID': 1
            }
        ]

        analyzer = ExpiryRiskAnalyzer(self.mock_db, forecaster)
        risks = analyzer.analyze_batch_risks()

        self.assertEqual(len(risks), 1)
        self.assertEqual(risks[0]['batch_number'], 'LOT-2026-001')
        self.assertGreaterEqual(risks[0]['risk_score'], 40.0)

    def test_waste_anomaly_detector(self):
        # محاكاة سجلات هدر منتج بمعامل شذوذ
        self.mock_cursor.fetchall.return_value = [
            {
                'Movement_ID': 1, 'Transaction_Date': datetime.now(), 'Product_ID': 1,
                'Product_Name': 'Reagent B', 'Movement_Type': 'Waste', 'qty_wasted': 2.0,
                'Unit_Used': 'Tests', 'Notes': '', 'Reason_Name': 'Expired', 'Operator_Name': 'User'
            },
            {
                'Movement_ID': 2, 'Transaction_Date': datetime.now(), 'Product_ID': 1,
                'Product_Name': 'Reagent B', 'Movement_Type': 'Waste', 'qty_wasted': 2.0,
                'Unit_Used': 'Tests', 'Notes': '', 'Reason_Name': 'Expired', 'Operator_Name': 'User'
            },
            {
                'Movement_ID': 3, 'Transaction_Date': datetime.now(), 'Product_ID': 1,
                'Product_Name': 'Reagent B', 'Movement_Type': 'Waste', 'qty_wasted': 50.0,  # Outlier
                'Unit_Used': 'Tests', 'Notes': 'Spill', 'Reason_Name': 'Accident', 'Operator_Name': 'User'
            }
        ]

        detector = WasteAnomalyDetector(self.mock_db)
        anomalies = detector.detect_waste_anomalies()

        self.assertTrue(len(anomalies) >= 1)
        self.assertEqual(anomalies[0]['movement_id'], 3)
        self.assertGreater(anomalies[0]['z_score'], 1.2)


    def test_ai_service_facade(self):
        service = AIService(self.mock_db)
        service.forecaster.forecast_all_products = MagicMock(return_value=[])
        service.risk_analyzer.analyze_batch_risks = MagicMock(return_value=[])
        service.anomaly_detector.detect_waste_anomalies = MagicMock(return_value=[])

        kpis = service.get_ai_kpi_summary()
        self.assertIn('products_needing_reorder', kpis)
        self.assertIn('batches_high_expiry_risk', kpis)

if __name__ == '__main__':
    unittest.main()
