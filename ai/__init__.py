# ai/__init__.py
"""
StockLam / MODERNSTOCK AI & Machine Learning Module.
Includes Demand Forecasting, Expiry Risk Analysis, Anomaly Detection, and Predictive Insights.
"""

from .ai_service import AIService
from .forecasting.demand_forecaster import DemandForecaster
from .risk.expiry_risk_analyzer import ExpiryRiskAnalyzer
from .anomaly.waste_detector import WasteAnomalyDetector

__all__ = [
    'AIService',
    'DemandForecaster',
    'ExpiryRiskAnalyzer',
    'WasteAnomalyDetector'
]
