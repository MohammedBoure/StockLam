# database/statistics_manager.py

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from .system_logger import log_methods 

@log_methods()
class StatisticsManager:
    """
    Gestionnaire avancé des statistiques et du tableau de bord.
    Fournit des données financières précises (Coût Réel TTC avec Remise), des alertes intelligentes,
    et une conversion précise des unités de stock vers les unités d'usage.
    """
    def __init__(self, db_instance):
        self.db = db_instance

    def get_kpi_summary(self):
        """
        واجهة القياس الرئيسية (Dashboard).
        تم التعديل: حساب الاستهلاك والحذف يعرض الآن (وحدات الاستخدام - Tests/Units) 
        بدلاً من (وحدات المخزون - Boxes) لإزالة الفواصل العشرية غير المرغوبة في العدد.
        """
        stats = {
            'total_products': 0,
            'total_stock_value': Decimal('0.00'),
            'total_consumed_units': 0,        # تم تغيير النوع إلى int ليكون رقم صحيح
            'total_consumed_value': Decimal('0.00'), 
            'total_waste_units': 0,           # تم تغيير النوع إلى int ليكون رقم صحيح
            'total_waste_value': Decimal('0.00'),
            'critical_alerts': 0
        }
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                
                # 1. عدد المنتجات النشطة حالياً
                cursor.execute("SELECT COUNT(*) FROM Products_Master WHERE Deleted_At IS NULL")
                stats['total_products'] = cursor.fetchone()[0]

                # 2. قيمة المخزون الحالي (المتوفر فقط)
                query_stock_val = """
                    SELECT SUM(
                        ib.Quantity_Current * 
                        COALESCE(ib.Unit_Price_Received, 0) * 
                        (1 - COALESCE(ib.Discount_Percent, 0) / 100.0) * 
                        (1 + COALESCE(ib.Tax_Rate_Percent, 0) / 100.0)
                    ) 
                    FROM Inventory_Batches ib
                    JOIN Products_Master pm ON ib.Product_ID = pm.Product_ID
                    WHERE ib.Quantity_Current > 0 
                    AND ib.Status = 'Available'
                    AND pm.Deleted_At IS NULL
                """
                cursor.execute(query_stock_val)
                val = cursor.fetchone()[0]
                stats['total_stock_value'] = Decimal(str(val)) if val else Decimal('0.00')

                # 3. حساب الاستهلاك (Consumption) - وحدة الاستخدام (Tests)
                # التعديل: تم إزالة القسمة في العمود الأول لعرض عدد الاختبارات الفعلي
                query_consumption = """
                    SELECT 
                        -- العمود 1: الكمية (عدد الاختبارات/الوحدات المفتوحة)
                        SUM(ABS(sml.Qty_Change)),
                        
                        -- العمود 2: القيمة المالية (تبقى معادلة القسمة هنا ضرورية لحساب التكلفة الجزئية من العلبة)
                        SUM(
                            (ABS(sml.Qty_Change) / COALESCE(NULLIF(pm.Usage_Qty_Per_Stock_Unit, 0), 1)) * 
                            COALESCE(ib.Unit_Price_Received, 0) * 
                            (1 - COALESCE(ib.Discount_Percent, 0) / 100.0) * 
                            (1 + COALESCE(ib.Tax_Rate_Percent, 0) / 100.0)
                        )
                    FROM Stock_Movement_Log sml
                    LEFT JOIN Products_Master pm ON sml.Product_ID = pm.Product_ID
                    LEFT JOIN Inventory_Batches ib ON sml.Batch_ID = ib.Batch_ID
                    WHERE sml.Movement_Type IN ('Patient_Test', 'QC_Run')
                """
                cursor.execute(query_consumption)
                row_cons = cursor.fetchone()
                if row_cons:
                    # تحويل الكمية إلى int لإزالة الفواصل
                    stats['total_consumed_units'] = int(row_cons[0]) if row_cons[0] is not None else 0
                    stats['total_consumed_value'] = Decimal(str(row_cons[1])) if row_cons[1] is not None else Decimal('0.00')

                # 4. حساب الحذف/التلف (Waste) - وحدة الاستخدام
                # التعديل: نفس التعديل السابق، عرض عدد الوحدات التالفة مباشرة
                query_waste = """
                    SELECT 
                        -- العمود 1: الكمية (عدد الوحدات التالفة)
                        SUM(ABS(sml.Qty_Change)),
                        
                        -- العمود 2: القيمة المالية
                        SUM(
                            (ABS(sml.Qty_Change) / COALESCE(NULLIF(pm.Usage_Qty_Per_Stock_Unit, 0), 1)) * 
                            COALESCE(ib.Unit_Price_Received, 0) * 
                            (1 - COALESCE(ib.Discount_Percent, 0) / 100.0) * 
                            (1 + COALESCE(ib.Tax_Rate_Percent, 0) / 100.0)
                        )
                    FROM Stock_Movement_Log sml
                    LEFT JOIN Products_Master pm ON sml.Product_ID = pm.Product_ID
                    LEFT JOIN Inventory_Batches ib ON sml.Batch_ID = ib.Batch_ID
                    WHERE sml.Movement_Type = 'Waste'
                """
                cursor.execute(query_waste)
                row_waste = cursor.fetchone()
                if row_waste:
                    # تحويل الكمية إلى int لإزالة الفواصل
                    stats['total_waste_units'] = int(row_waste[0]) if row_waste[0] is not None else 0
                    stats['total_waste_value'] = Decimal(str(row_waste[1])) if row_waste[1] is not None else Decimal('0.00')

                # 5. التنبيهات (Alerts)
                alerts = self.get_active_alerts()
                stats['critical_alerts'] = len(alerts)

                return stats
        except Exception as e:
            logging.error(f"Erreur KPIs: {e}")
            return stats

        
    def get_active_alerts(self):
        """
        جلب التنبيهات مع:
        1. الفلترة (العائلة والماركة).
        2. المنطق الديناميكي: (الكمية × أيام الإنذار).
        """
        alerts = []
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                today = datetime.now().date()
                
                # 1. تنبيهات انتهاء الصلاحية (Péremption)
                query_expiry = """
                    SELECT 
                        p.Product_Name, 
                        b.Lot_Number, 
                        b.Expiry_Date, 
                        b.Quantity_Current, 
                        p.Alert_Before_Expiry_Days,
                        COALESCE(pf.Family_Name, 'Autre') as Family_Name, -- جلب العائلة
                        COALESCE(m.Manuf_Name, 'Autre') as Manuf_Name     -- جلب الماركة
                    FROM Inventory_Batches b
                    JOIN Products_Master p ON b.Product_ID = p.Product_ID
                    LEFT JOIN Product_Families pf ON p.Family_ID = pf.Family_ID
                    LEFT JOIN Manufacturers m ON p.Manuf_ID = m.Manuf_ID
                    WHERE b.Quantity_Current > 0 AND b.Expiry_Date IS NOT NULL AND p.Deleted_At IS NULL
                    -- المعادلة الديناميكية: الأيام المتبقية <= (الكمية * أيام الإنذار)
                    AND DATEDIFF(b.Expiry_Date, CURDATE()) <= (b.Quantity_Current * COALESCE(p.Alert_Before_Expiry_Days, 2))
                """
                cursor.execute(query_expiry)
                for item in cursor.fetchall():
                    days_diff = (item['Expiry_Date'] - today).days
                    fixed_threshold = item['Alert_Before_Expiry_Days'] or 2
                    
                    # تصنيف نوع الخطر
                    if days_diff <= fixed_threshold:
                        alert_type = "Péremption Urgente"
                        crit = "High"
                    else:
                        alert_type = "Péremption Anticipée"
                        crit = "Medium"
                    
                    dynamic_threshold = item['Quantity_Current'] * fixed_threshold
                    
                    alerts.append({
                        "Product": item['Product_Name'],
                        "Type": alert_type,
                        "RawValue": days_diff,
                        "Details": f"Lot: {item['Lot_Number']} | Seuil: {dynamic_threshold}j (Stock: {item['Quantity_Current']})",
                        "Family": item['Family_Name'],
                        "Brand": item['Manuf_Name'],
                        "Criticality": crit
                    })

                # 2. تنبيهات نفاد المخزون (Rupture)
                query_stock = """
                    SELECT 
                        p.Product_Name, 
                        p.Minimum_Stock_Level, 
                        SUM(b.Quantity_Current) as Total,
                        COALESCE(pf.Family_Name, 'Autre') as Family_Name,
                        COALESCE(m.Manuf_Name, 'Autre') as Manuf_Name
                    FROM Products_Master p
                    LEFT JOIN Inventory_Batches b ON p.Product_ID = b.Product_ID AND b.Status='Available'
                    LEFT JOIN Product_Families pf ON p.Family_ID = pf.Family_ID
                    LEFT JOIN Manufacturers m ON p.Manuf_ID = m.Manuf_ID
                    WHERE p.Deleted_At IS NULL
                    GROUP BY p.Product_ID, p.Product_Name, p.Minimum_Stock_Level, pf.Family_Name, m.Manuf_Name
                    HAVING Total <= p.Minimum_Stock_Level
                """
                cursor.execute(query_stock)
                for item in cursor.fetchall():
                    curr = float(item['Total'] or 0)
                    alerts.append({
                        "Product": item['Product_Name'],
                        "Type": "Rupture de Stock",
                        "RawValue": curr,
                        "Details": f"Stock actuel: {curr} (Min: {item['Minimum_Stock_Level']})",
                        "Family": item['Family_Name'],
                        "Brand": item['Manuf_Name'],
                        "Criticality": "High" if curr == 0 else "Medium"
                    })
            
            return alerts
        except Exception as e:
            logging.error(f"Alerts Error: {e}")
            return []
        
    def get_detailed_consumption_report(self, start_date, end_date, report_type='consumed'):
        """
        تقرير التفاصيل.
        [تصحيح جذري]: 
        بما أن قاعدة البيانات تخزن الكميات بوحدة التخزين (Stock Unit)،
        يجب ضرب الكمية في معامل التحويل لعرض وحدة الاستخدام (Usage Unit).
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                
                if report_type == 'consumed':
                    mvt_types = "('Patient_Test', 'QC_Run')"
                else:
                    mvt_types = "('Waste')"

                query = f"""
                    SELECT 
                        pm.Product_ID, 
                        pm.Product_Name, 
                        
                        -- وحدات القياس
                        pm.Stock_Unit as Stock_Unit,
                        COALESCE(pm.Usage_Unit, 'Unité') as Usage_Unit,
                        
                        -- 1. الكمية بوحدة الاستخدام (Tests)
                        -- المعادلة: الكمية المخزنة (علب) * معامل التحويل = عدد الفحوصات
                        COALESCE(
                            SUM(ABS(sml.Qty_Change) * COALESCE(NULLIF(pm.Usage_Qty_Per_Stock_Unit, 0), 1)), 
                            0
                        ) as total_qty_usage,

                        -- 2. الكمية بوحدة التخزين (Boîtes) - هي نفسها المخزنة
                        COALESCE(SUM(ABS(sml.Qty_Change)), 0) as total_qty_stock,
                        
                        -- 3. التكلفة الإجمالية
                        -- المعادلة: الكمية المخزنة (علب) * سعر العلبة
                        COALESCE(
                            SUM(
                                ABS(sml.Qty_Change) *
                                COALESCE(ib.Unit_Price_Received, 0) *
                                (1 - COALESCE(ib.Discount_Percent, 0) / 100.0) *
                                (1 + COALESCE(ib.Tax_Rate_Percent, 0) / 100.0)
                            ),
                        0) as total_cost_ttc
                        
                    FROM Stock_Movement_Log sml
                    LEFT JOIN Products_Master pm ON sml.Product_ID = pm.Product_ID
                    LEFT JOIN Inventory_Batches ib ON sml.Batch_ID = ib.Batch_ID
                    
                    WHERE sml.Movement_Type IN {mvt_types}
                      AND DATE(sml.Transaction_Date) BETWEEN %s AND %s
                      
                    GROUP BY pm.Product_ID, pm.Product_Name, pm.Stock_Unit, pm.Usage_Unit, pm.Usage_Qty_Per_Stock_Unit
                    ORDER BY total_cost_ttc DESC
                """
                cursor.execute(query, (start_date, end_date))
                return cursor.fetchall()
        except Exception as e:
            logging.error(f"Erreur Consumption Report: {e}")
            return []

    def get_waste_analysis(self, start_date, end_date):
        """
        Analyse des déchets par raison (Valeur TTC avec Remise).
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT 
                        wr.Reason_Name,
                        COUNT(*) as frequency,
                        -- Calcul perte TTC
                        SUM(ABS(sml.Qty_Change) * 
                            ib.Unit_Price_Received * 
                            (1 - COALESCE(ib.Discount_Percent, 0) / 100.0) * 
                            (1 + COALESCE(ib.Tax_Rate_Percent, 0) / 100.0)
                        ) as estimated_loss
                    FROM Stock_Movement_Log sml
                    LEFT JOIN Waste_Reasons wr ON sml.Reason_ID = wr.Reason_ID
                    JOIN Inventory_Batches ib ON sml.Batch_ID = ib.Batch_ID
                    WHERE sml.Movement_Type = 'Waste'
                      AND DATE(sml.Transaction_Date) BETWEEN %s AND %s
                    GROUP BY wr.Reason_Name
                    ORDER BY estimated_loss DESC
                """
                cursor.execute(query, (start_date, end_date))
                return cursor.fetchall()
        except Exception as e:
            logging.error(f"Erreur Waste Analysis: {e}")
            return []

    def get_stock_valuation_detailed(self):
        """
        Rapport de la valeur du stock actuel (TTC avec Remise).
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT 
                        p.Product_Name,
                        SUM(b.Quantity_Current) as total_boxes,
                        p.Stock_Unit,
                        SUM(b.Quantity_Current * p.Usage_Qty_Per_Stock_Unit) as total_tests,
                        p.Usage_Unit,
                        
                        -- Valeur TTC Réelle (avec Remise)
                        SUM(b.Quantity_Current * 
                            b.Unit_Price_Received * 
                            (1 - COALESCE(b.Discount_Percent, 0) / 100.0) * 
                            (1 + COALESCE(b.Tax_Rate_Percent, 0) / 100.0)
                        ) as total_value_ht
                        
                    FROM Inventory_Batches b
                    JOIN Products_Master p ON b.Product_ID = p.Product_ID
                    WHERE b.Quantity_Current > 0 
                      AND b.Status = 'Available'
                      AND p.Deleted_At IS NULL
                    GROUP BY p.Product_ID, p.Product_Name, p.Stock_Unit, p.Usage_Unit, p.Usage_Qty_Per_Stock_Unit
                    ORDER BY total_value_ht DESC
                """
                cursor.execute(query)
                return cursor.fetchall()
        except Exception as e:
            logging.error(f"Erreur Stock Valuation: {e}")
            return []

    def get_consumption_trend(self, start_date, end_date):
        """
        بيانات الاستهلاك (Sorties/Consommation).
        نحسب تكلفة المواد التي خرجت فعلياً (Tests, QC, Waste).
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT 
                        DATE(sml.Transaction_Date) as date,
                        COUNT(sml.Movement_ID) as transaction_count,
                        
                        -- حساب التكلفة: الكمية المستهلكة * سعر الشراء الصافي (بعد الخصم والضريبة)
                        SUM(ABS(sml.Qty_Change) * ib.Unit_Price_Received * (1 - COALESCE(ib.Discount_Percent, 0) / 100.0) * (1 + COALESCE(ib.Tax_Rate_Percent, 0) / 100.0)
                        ) as daily_value
                        
                    FROM Stock_Movement_Log sml
                    JOIN Inventory_Batches ib ON sml.Batch_ID = ib.Batch_ID
                    
                    -- تحديد أنواع الحركات التي تعتبر "خروج أموال/استهلاك"
                    WHERE sml.Movement_Type IN ('Patient_Test', 'QC_Run', 'Waste', 'Open_Pack')
                      AND DATE(sml.Transaction_Date) BETWEEN %s AND %s
                      
                    GROUP BY DATE(sml.Transaction_Date)
                    ORDER BY date ASC
                """
                cursor.execute(query, (start_date, end_date))
                return cursor.fetchall()
        except Exception as e:
            logging.error(f"Erreur Consumption Trend: {e}")
            return []
    
    def get_deleted_products_consumption(self, start_date, end_date):
        """
        Statistiques pour les produits supprimés (Valeur TTC).
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT 
                        p.Product_Name, 
                        p.Deleted_At,
                        SUM(ABS(sml.Qty_Change)) as qty_consumed,
                        -- Valeur consommée TTC
                        SUM(ABS(sml.Qty_Change) * 
                            ib.Unit_Price_Received * 
                            (1 - COALESCE(ib.Discount_Percent, 0) / 100.0) * 
                            (1 + COALESCE(ib.Tax_Rate_Percent, 0) / 100.0)
                        ) as value_consumed
                    FROM Stock_Movement_Log sml
                    JOIN Products_Master p ON sml.Product_ID = p.Product_ID
                    JOIN Inventory_Batches ib ON sml.Batch_ID = ib.Batch_ID
                    WHERE p.Deleted_At IS NOT NULL
                      AND sml.Movement_Type IN ('Patient_Test', 'QC_Run', 'Waste')
                      AND DATE(sml.Transaction_Date) BETWEEN %s AND %s
                    GROUP BY p.Product_ID, p.Product_Name, p.Deleted_At
                """
                cursor.execute(query, (start_date, end_date))
                return cursor.fetchall()
        except Exception as e:
            logging.error(f"Error fetching deleted products stats: {e}")
            return []

    def get_zombie_stock(self):
        """
        Vérifie s'il existe du stock pour des produits supprimés.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT 
                        p.Product_Name, 
                        b.Batch_ID, 
                        b.Lot_Number, 
                        b.Quantity_Current,
                        l.Location_Name
                    FROM Inventory_Batches b
                    JOIN Products_Master p ON b.Product_ID = p.Product_ID
                    LEFT JOIN Locations l ON b.Location_ID = l.Location_ID
                    WHERE p.Deleted_At IS NOT NULL 
                      AND b.Quantity_Current > 0
                """
                cursor.execute(query)
                return cursor.fetchall()
        except Exception as e:
            logging.error(f"Error checking zombie stock: {e}")
            return []

    # -------------------------------------------------------------------------
    # NEW FUNCTION: Reception by Family & Date
    # -------------------------------------------------------------------------
    def get_reception_by_family_timeline(self, start_date, end_date):
        """
        Retourne la quantité totale reçue (Quantity_Initial) groupée par
        famille de produit et par date de réception.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT
                        COALESCE(pf.Family_Name, 'Autres') as Family_Name,
                        rl.Reception_Date,
                        SUM(ib.Quantity_Initial) as Total_Qty_Received
                    FROM Inventory_Batches ib
                    JOIN Reception_Log rl ON ib.BR_ID = rl.BR_ID
                    JOIN Products_Master pm ON ib.Product_ID = pm.Product_ID
                    LEFT JOIN Product_Families pf ON pm.Family_ID = pf.Family_ID
                    WHERE rl.Reception_Date BETWEEN %s AND %s
                    GROUP BY pf.Family_Name, rl.Reception_Date
                    ORDER BY rl.Reception_Date ASC, pf.Family_Name ASC
                """
                cursor.execute(query, (start_date, end_date))
                return cursor.fetchall()
        except Exception as e:
            logging.error(f"Error fetching reception by family timeline: {e}")
            return []

    def get_reception_matrix_data(self, family_id, start_date, end_date):
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                family_condition = "AND pm.Family_ID = %s" if family_id else ""
                
                query = f"""
                    SELECT 
                        pm.Product_ID, 
                        TRIM(pm.Product_Name) as Product_Name,
                        pf.Family_Name,
                        LEFT(rl.Reception_Date, 7) as Month_Year,
                        SUM(ib.Quantity_Initial) as Total_Stock_Qty,
                        -- تنظيف الوحدات من أي مسافات خفية
                        COALESCE(NULLIF(TRIM(pm.Stock_Unit), ''), 'N/A') as Stock_Unit,
                        COALESCE(NULLIF(TRIM(pm.Ordering_Unit), ''), 'N/A') as Ordering_Unit,
                        COALESCE(NULLIF(TRIM(pm.Usage_Unit), ''), 'N/A') as Usage_Unit,
                        COALESCE(pm.Stock_Qty_Per_Order_Unit, 1) as Stock_Qty_Per_Order_Unit,
                        COALESCE(pm.Usage_Qty_Per_Stock_Unit, 1) as Usage_Qty_Per_Stock_Unit
                    FROM Inventory_Batches ib
                    JOIN Reception_Log rl ON ib.BR_ID = rl.BR_ID
                    JOIN Products_Master pm ON ib.Product_ID = pm.Product_ID
                    LEFT JOIN Product_Families pf ON pm.Family_ID = pf.Family_ID
                    WHERE rl.Reception_Date BETWEEN %s AND %s {family_condition}
                    GROUP BY 
                        pm.Product_ID, Month_Year -- التجميع حسب المعرف لضمان الدقة
                    ORDER BY pm.Product_Name ASC, Month_Year ASC
                """
                params = [start_date, end_date]
                if family_id: params.append(family_id)
                cursor.execute(query, tuple(params))
                return cursor.fetchall()
        except Exception as e:
            logging.error(f"Error fetching reception matrix: {e}")
            return []
        
    def get_reception_trend(self, start_date, end_date):
        """
        بيانات المشتريات (Entrées/Achats).
        التصحيح: الاعتماد على إجمالي الفاتورة من جدول Reception_Log مباشرة.
        هذا يمنع تضخيم الأرقام الناتج عن أخطاء تحويل الوحدات في الباتشات.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT 
                        DATE(Reception_Date) as date,
                        COUNT(BR_ID) as transaction_count,
                        -- نجمع إجمالي الفواتير مباشرة (أدق مالياً)
                        SUM(Invoice_Total_TTC) as daily_value
                    FROM Reception_Log
                    WHERE DATE(Reception_Date) BETWEEN %s AND %s
                      AND Status != 'Pending Audit' -- استثناء الفواتير غير المكتملة
                    GROUP BY DATE(Reception_Date)
                    ORDER BY date ASC
                """
                cursor.execute(query, (start_date, end_date))
                return cursor.fetchall()
        except Exception as e:
            logging.error(f"Erreur Reception Trend: {e}")
            return []