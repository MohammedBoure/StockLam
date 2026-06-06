# Prompts مؤقتة لتنفيذ إضافة Inventaire

هذه الوثيقة تحتوي prompts جاهزة لتنفيذ إضافة `Inventaire` على مراحل. كل prompt يعتمد على التوثيق الأساسي:

```text
docs/inventaire-feature-design.md
```

الفكرة العامة: إضافة زر جديد في الـ nav bar باسم `Inventaire`، يفتح شاشة جرد مستقلة تسمح بإنشاء جلسات جرد، المسح بقارئ كود بار، مقارنة مخزون البرنامج مع الواقع، ثم تطبيق الفروقات على قاعدة البيانات بطريقة آمنة.

## قواعد عامة لكل prompts

استخدم هذه القواعد في كل مرحلة تنفيذ:

- اقرأ أولًا `docs/inventaire-feature-design.md`.
- لا تغيّر منطق المخزون الحالي إلا من خلال نقاط ربط واضحة.
- لا تعدّل `Quantity_Initial` عند تطبيق الجرد.
- كل فرق مطبق على المخزون يجب أن يسجل في `Stock_Movement_Log` كـ `Adjustment`.
- لا تطبق الجرد أثناء المسح. المسح يسجل فقط داخل جداول الجرد.
- التطبيق النهائي يجب أن يتم داخل transaction مع `SELECT ... FOR UPDATE`.
- لا تسمح بتطبيق نفس جلسة الجرد مرتين.
- إذا كان هناك `UNKNOWN` codes، لا تطبق الجلسة إلا إذا تم تجاهلها أو حلها صراحة.
- حافظ على نمط المشروع الحالي: managers في `database/`، وتجميعها في `LabDataManager`، والواجهات في `ui/widgets/`.
- لا تلمس تغييرات غير مرتبطة بالمهمة.

---

## Prompt 01 - إضافة جداول Inventaire والصلاحيات إلى قاعدة البيانات

```text
أنت تعمل داخل مشروع StockLam. اقرأ:
- docs/inventaire-feature-design.md
- database/base/schema_initializer.py
- database/base/config.py
- database/__init__.py

المطلوب:
نفذ الجزء الخاص بقاعدة البيانات لإضافة Inventaire.

أضف الصلاحيات التالية إلى `_ALL_PERMISSIONS` في `database/base/schema_initializer.py`:
- nav_inventaire
- tab_inv_inventaire
- act_inventory_create
- act_inventory_scan
- act_inventory_apply
- act_inventory_cancel
- act_inventory_export

أضف الجداول التالية إلى `SCHEMA_QUERIES`:

1. `Inventory_Count_Sessions`
   - `Session_ID BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY`
   - `Session_Name VARCHAR(150) NOT NULL`
   - `Scope_Type ENUM('ALL', 'LOCATION', 'FAMILY', 'PRODUCT') NOT NULL DEFAULT 'ALL'`
   - `Scope_ID BIGINT UNSIGNED NULL`
   - `Status ENUM('Draft', 'Counting', 'Review', 'Applied', 'Cancelled') NOT NULL DEFAULT 'Draft'`
   - `Started_At DATETIME DEFAULT CURRENT_TIMESTAMP`
   - `Completed_At DATETIME NULL`
   - `Applied_At DATETIME NULL`
   - `Created_By INT UNSIGNED NULL`
   - `Applied_By INT UNSIGNED NULL`
   - `Notes TEXT NULL`
   - foreign keys إلى `Users(User_ID)` مع `ON DELETE SET NULL`

2. `Inventory_Count_Lines`
   - `Line_ID BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY`
   - `Session_ID BIGINT UNSIGNED NOT NULL`
   - `Batch_ID BIGINT UNSIGNED NULL`
   - `Product_ID INT UNSIGNED NULL`
   - `Internal_Barcode VARCHAR(50) NULL`
   - `Program_Qty_Snapshot DECIMAL(15, 2) NOT NULL DEFAULT 0`
   - `Counted_Qty DECIMAL(15, 2) NOT NULL DEFAULT 0`
   - `Difference_Qty DECIMAL(15, 2) NOT NULL DEFAULT 0`
   - `Line_Status ENUM('OK', 'SHORT', 'EXCESS', 'NOT_COUNTED', 'UNKNOWN') NOT NULL DEFAULT 'NOT_COUNTED'`
   - `Last_Scanned_At DATETIME NULL`
   - `Comment TEXT NULL`
   - foreign keys إلى `Inventory_Count_Sessions`, `Inventory_Batches`, `Products_Master`
   - unique key على `(Session_ID, Batch_ID)`

3. `Inventory_Count_Scans`
   - `Scan_ID BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY`
   - `Session_ID BIGINT UNSIGNED NOT NULL`
   - `Line_ID BIGINT UNSIGNED NULL`
   - `Scanned_Barcode VARCHAR(100) NOT NULL`
   - `Qty DECIMAL(15, 2) NOT NULL DEFAULT 1`
   - `Scan_Status ENUM('MATCHED', 'UNKNOWN', 'IGNORED') NOT NULL DEFAULT 'MATCHED'`
   - `Scanned_At DATETIME DEFAULT CURRENT_TIMESTAMP`
   - `Scanned_By INT UNSIGNED NULL`
   - foreign keys إلى جلسة الجرد، سطر الجرد، والمستخدم

أضف indexes مناسبة إلى `INDEX_QUERIES`:
- index على `Inventory_Count_Sessions(Status)`
- index على `Inventory_Count_Lines(Session_ID, Line_Status)`
- index على `Inventory_Count_Lines(Internal_Barcode)`
- index على `Inventory_Count_Scans(Session_ID, Scanned_Barcode)`

حدّث `TABLE_IMPORT_ORDER` في `database/base/config.py` بإضافة الجداول الثلاثة بعد `Stock_Movement_Log` أو قبل `SystemLogs`.

مهم:
- لا تستخدم generated columns لـ `Difference_Qty` في المرحلة الأولى، حتى يبقى التنفيذ متوافقًا مع MySQL/MariaDB.
- تعامل مع duplicate column/key errors بنفس نمط الملف الحالي.
- لا تغيّر الجداول الحالية إلا بإضافة الصلاحيات والجداول الجديدة.

معايير القبول:
- `python -m compileall database` ينجح.
- عند تشغيل schema initializer مع `DB_SCHEMA_CHECK_ON_STARTUP=true` تنشأ الجداول بدون كسر الجداول الحالية.
- حساب admin الافتراضي يحصل على الصلاحيات الجديدة لأن `_create_default_admin` يبني permissions من `_ALL_PERMISSIONS`.
```

---

## Prompt 02 - إنشاء InventoryCountManager ودوال التعامل مع الجداول

```text
أنت تعمل داخل مشروع StockLam. اقرأ:
- docs/inventaire-feature-design.md
- database/inventory_batch_manager.py
- database/stock_movement_log_manager.py
- database/base/connection.py
- database/__init__.py

المطلوب:
أنشئ manager جديد للتعامل مع جداول الجرد:

ملف جديد:
database/inventory_count_manager.py

الكلاس:
InventoryCountManager

اربطه بـ `@log_methods()` مثل managers الأخرى إذا كان مناسبًا.

أضف الدوال التالية:

1. `create_session(session_name, scope_type='ALL', scope_id=None, created_by=None, notes=None)`
   - ينشئ session في `Inventory_Count_Sessions`.
   - يستدعي `build_snapshot(session_id)`.
   - يغير الحالة إلى `Counting`.
   - يرجع `session_id` أو `None`.

2. `build_snapshot(session_id)`
   - يقرأ scope من الجلسة.
   - ينسخ الدفعات الحالية ذات `Quantity_Current > 0`.
   - يعتمد على `Inventory_Batches` مع joins اختيارية إلى `Products_Master`.
   - يملأ `Inventory_Count_Lines`:
     - `Batch_ID`
     - `Product_ID`
     - `Internal_Barcode`
     - `Program_Qty_Snapshot = Quantity_Current`
     - `Counted_Qty = 0`
     - `Difference_Qty = 0 - Quantity_Current`
     - `Line_Status = 'NOT_COUNTED'`

3. `scan_barcode(session_id, barcode, qty=1, user_id=None)`
   - ينظف barcode من الفراغات.
   - يرفض الجلسات غير `Counting` أو `Review`.
   - يبحث في `Inventory_Count_Lines` داخل نفس الجلسة عن `Internal_Barcode`.
   - إذا وجد السطر:
     - يزيد `Counted_Qty` بمقدار `qty`.
     - يعيد حساب `Difference_Qty`.
     - يحدث `Line_Status`:
       - `OK` إذا الفرق صفر.
       - `SHORT` إذا الفرق سالب.
       - `EXCESS` إذا الفرق موجب.
     - يحدث `Last_Scanned_At`.
     - يسجل scan في `Inventory_Count_Scans` بحالة `MATCHED`.
   - إذا لم يجد:
     - يسجل scan بحالة `UNKNOWN`.
     - ينشئ line بحالة `UNKNOWN` إذا أردت عرضها في جدول الفروقات، مع `Batch_ID = NULL` و `Program_Qty_Snapshot = 0`.
   - يرجع dict واضح يحتوي:
     - `success`
     - `status`
     - `message`
     - `line`

4. `set_counted_quantity(line_id, counted_qty)`
   - يسمح بالتعديل اليدوي للكمية المعدودة.
   - يعيد حساب الفرق والحالة.

5. `get_sessions(status=None, limit=100)`
   - يرجع جلسات الجرد مع ملخص مختصر إن أمكن.

6. `get_session_lines(session_id, status=None, search=None)`
   - يرجع خطوط الجرد مع joins إلى:
     - `Products_Master`
     - `Inventory_Batches`
     - `Locations`
   - يعرض المنتج، اللوت، الموقع، الكود، كمية البرنامج، الكمية المعدودة، الفرق، الحالة.

7. `get_session_summary(session_id)`
   - يرجع counts للحالات:
     - OK
     - SHORT
     - EXCESS
     - NOT_COUNTED
     - UNKNOWN
   - يرجع مجموع القيمة التقديرية للفروقات باستخدام `Inventory_Batches.Unit_Price_Received`.

8. `mark_review(session_id)`
   - يغير الحالة إلى `Review`.

9. `cancel_session(session_id, user_id=None)`
   - يرفض الإلغاء إذا كانت `Applied`.
   - يغير الحالة إلى `Cancelled`.

10. `apply_session(session_id, user_id=None, allow_unknown=False)`
   - أهم دالة.
   - يجب أن تعمل داخل transaction.
   - ترفض إذا الجلسة ليست `Counting` أو `Review`.
   - ترفض إذا هناك `UNKNOWN` ولم يكن `allow_unknown=True`.
   - تجلب lines التي لها `Batch_ID IS NOT NULL` وفرقها غير صفر.
   - لكل line:
     - تقفل batch بـ `SELECT ... FOR UPDATE`.
     - تقارن `Inventory_Batches.Quantity_Current` مع `Program_Qty_Snapshot`.
     - إذا اختلفت، توقف العملية كلها وترجع conflict list بدون أي تعديل.
     - تحدث `Quantity_Current` إلى `Counted_Qty`.
     - تحدث `Status`:
       - `Depleted` إذا `Counted_Qty == 0`.
       - `Available` إذا `Counted_Qty > 0` والحالة الحالية `Depleted`.
       - لا تغيّر `Quarantined` أو `Expired`.
     - تسجل `Stock_Movement_Log` عبر `StockMovementLogManager.create_movement_log` مع:
       - `Movement_Type='Adjustment'`
       - `Qty_Change = Counted_Qty - current_qty`
       - `Unit_Used = Products_Master.Stock_Unit`
       - `Notes = 'Inventaire #<session_id>'`
       - `external_cursor=cursor`
   - بعد نجاح كل الخطوط:
     - `Status='Applied'`
     - `Applied_At=NOW()`
     - `Applied_By=user_id`
   - يرجع dict:
     - `success`
     - `applied_count`
     - `conflicts`
     - `message`

11. `export_session_to_excel(session_id, output_path)`
   - يستخدم pandas أو xlsxwriter حسب نمط المشروع.
   - يصدر lines والsummary.

اربط manager داخل `database/__init__.py`:
- import `InventoryCountManager`
- داخل `LabDataManager.__init__`: `self.inventory_counts = InventoryCountManager(db_instance)`

مهم:
- لا تستخدم string formatting لإدخال SQL parameters.
- استخدم `%s` و params.
- لا تعمل commit جزئي يترك import مكسور.
- حافظ على `Decimal` في الحسابات.

معايير القبول:
- `python -m compileall database` ينجح.
- يمكن إنشاء جلسة، بناء snapshot، scan barcode معروف، scan barcode غير معروف.
- `apply_session` لا يطبق عند وجود conflict.
- كل adjustment يظهر في `Stock_Movement_Log`.
```

---

## Prompt 03 - إضافة زر Inventaire مستقل في nav bar

```text
أنت تعمل داخل مشروع StockLam. اقرأ:
- docs/inventaire-feature-design.md
- ui/main_window.py
- ui/widgets/inventory/inventory_tabs.py
- database/base/schema_initializer.py

المطلوب:
أضف زر navigation جديد مستقل باسم `Inventaire` في sidebar الرئيسي، وليس فقط تبويب داخل Stock & Magasin.

الهدف:
من القائمة الجانبية يظهر زر جديد:
Inventaire

عند الضغط عليه يفتح صفحة جرد مستقلة في `content_area`.

تعديلات `ui/main_window.py`:

1. أضف import للشاشة الجديدة:
   `from .widgets.inventory.inventory_count_tab import InventoryCountTab`

2. زِد عدد placeholders في `_init_placeholders` من `range(9)` إلى `range(10)` أو استخدم رقمًا واضحًا.

3. أضف زرًا جديدًا في `buttons_info`:
   - id جديد: `9`
   - text: `Inventaire`
   - icon: استخدم `fa5s.clipboard-list` أو أي icon متوفر من qtawesome

4. حدّث mapping الخاص بالصلاحيات في:
   - اختيار أول صفحة مسموحة
   - `apply_permissions`
   - `switch_page`

   أضف:
   `9: "nav_inventaire"`

5. في `_load_page`:
   إذا `page_id == 9`:
   - أنشئ `InventoryCountTab(self.data_manager, self.current_user)`
   - خزنه في `loaded_pages`

6. تأكد أن الصفحة لا تفتح إذا المستخدم لا يملك `nav_inventaire`.

7. إذا لم يوجد اتصال قاعدة بيانات (`connection_error`) لا تسمح بفتح Inventaire، وابق على نفس منطق Settings الحالي.

مهم:
- لا تكسر IDs الحالية للصفحات.
- لا تغيّر ترتيب الصفحات الحالية إلا بإضافة الزر الجديد في مكان منطقي بعد `Stock & Magasin`.
- لا تجعل Inventaire داخل `InventoryTab` في هذه المرحلة إذا كان المطلوب زر nav مستقل.

معايير القبول:
- التطبيق يفتح بدون import errors.
- زر Inventaire يظهر فقط لمن يملك `nav_inventaire`.
- الضغط على الزر يفتح شاشة الجرد.
- الصفحات الحالية Dashboard/Data/Procurement/Inventory/Finance/Services/History/Users/Settings تبقى تعمل بنفس IDs.
```

---

## Prompt 04 - بناء شاشة Inventaire الرئيسية

```text
أنت تعمل داخل مشروع StockLam. اقرأ:
- docs/inventaire-feature-design.md
- docs/inventaire-implementation-prompts.md
- ui/main_window.py
- ui/widgets/inventory/tabs_batches/__init__.py
- ui/widgets/inventory/tabs_dispatch.py
- database/inventory_count_manager.py

المطلوب:
أنشئ الشاشة الرئيسية للـ Inventaire.

ملف جديد:
ui/widgets/inventory/inventory_count_tab.py

الكلاس:
InventoryCountTab(QWidget)

constructor:
`def __init__(self, data_manager, current_user=None):`

العناصر المطلوبة:

1. شريط أعلى يحتوي:
   - عنوان `Inventaire`
   - زر `Nouvelle session`
   - زر `Scanner`
   - زر `Revue`
   - زر `Appliquer`
   - زر `Annuler`
   - زر `Exporter`

2. لوحة ملخص صغيرة:
   - OK
   - Manquant
   - Excédent
   - Non compté
   - Inconnu
   - Valeur écart

3. جدول الجلسات أو combo لاختيار الجلسة الحالية:
   - Session_ID
   - Session_Name
   - Status
   - Started_At
   - Created_By

4. جدول الفروقات:
   - Produit
   - Code-barres
   - Lot
   - Expiration
   - Emplacement
   - Stock programme
   - Stock compté
   - Écart
   - Statut
   - Commentaire

5. فلاتر:
   - search text
   - status combo

الدوال المطلوبة داخل الشاشة:

- `load_sessions()`
- `load_current_session()`
- `load_lines()`
- `refresh_summary()`
- `create_session()`
- `open_scan_dialog()`
- `mark_review()`
- `apply_session()`
- `cancel_session()`
- `export_session()`
- `has_action(permission_key)`

ربط الصلاحيات:

- زر إنشاء جلسة يحتاج `act_inventory_create`.
- زر scanner يحتاج `act_inventory_scan`.
- زر تطبيق يحتاج `act_inventory_apply`.
- زر إلغاء يحتاج `act_inventory_cancel`.
- زر تصدير يحتاج `act_inventory_export`.

نافذة إنشاء session:
- استخدم QDialog بسيط أو QInputDialog.
- الحقول:
  - name
  - scope type: ALL, LOCATION, FAMILY, PRODUCT
  - scope id اختياري
  - notes

مهم:
- لا تطبق المخزون من الشاشة مباشرة بدون استخدام manager.
- كل العمليات تمر عبر `self.data_manager.inventory_counts`.
- بعد كل عملية، اعمل refresh للجدول والsummary.
- استخدم رسائل QMessageBox واضحة عند النجاح أو الفشل.

معايير القبول:
- الصفحة تفتح حتى لو لا توجد جلسات.
- يمكن إنشاء جلسة فتظهر في القائمة.
- يمكن عرض خطوط snapshot.
- الأزرار غير المسموحة تختفي أو تتعطل حسب permissions.
```

---

## Prompt 05 - بناء نافذة قارئ كود بار للجرد

```text
أنت تعمل داخل مشروع StockLam. اقرأ:
- docs/inventaire-feature-design.md
- database/inventory_count_manager.py
- ui/widgets/inventory/inventory_count_tab.py
- ui/login_dialog.py لتفهم نمط QDialog البسيط

المطلوب:
أنشئ نافذة scanner لجلسة Inventaire.

ملف جديد:
ui/widgets/inventory/inventory_count_scan_dialog.py

الكلاس:
InventoryCountScanDialog(QDialog)

constructor:
`def __init__(self, data_manager, session_id, current_user=None, parent=None):`

العناصر:

- input كبير للباركود `QLineEdit`
- input للكمية `QDoubleSpinBox` أو `QSpinBox`
- label كبير لنتيجة آخر scan
- جدول آخر 20 scan:
  - barcode
  - qty
  - status
  - time
  - message
- زر close

السلوك:

- barcode input يأخذ focus عند فتح النافذة.
- عند الضغط Enter:
  - يقرأ barcode.
  - يقرأ qty.
  - يستدعي:
    `self.data_manager.inventory_counts.scan_barcode(session_id, barcode, qty, user_id)`
  - يعرض النتيجة فورًا.
  - إذا MATCHED: لون أخضر.
  - إذا UNKNOWN: لون أحمر أو تحذيري.
  - يفرغ input ويعيد focus.
  - يطلق signal مثل `scan_recorded = Signal()` حتى تحدث الشاشة الرئيسية نفسها.

مهم:
- قارئ كود بار عادة يعمل كkeyboard، لذلك لا تضف logic معقد يعتمد على hardware.
- لا تمنع إدخال كميات يدوية أكبر من 1.
- لا تطبق المخزون هنا.
- لا تغلق النافذة بعد كل scan.

معايير القبول:
- scan barcode معروف يزيد counted qty.
- scan barcode غير معروف يسجل UNKNOWN.
- الشاشة الرئيسية تحدث summary والlines بعد scan.
```

---

## Prompt 06 - تطبيق الجرد بأمان وربطه مع Stock_Movement_Log

```text
أنت تعمل داخل مشروع StockLam. اقرأ:
- database/inventory_count_manager.py
- database/inventory_batch_manager.py
- database/stock_movement_log_manager.py
- database/base/connection.py

المطلوب:
راجع ونفذ/أكمل دالة `apply_session` بأمان كامل.

الشروط:

1. لا تطبق session إذا:
   - Status = Applied
   - Status = Cancelled
   - لا توجد lines
   - توجد UNKNOWN lines أو UNKNOWN scans ولم يتم تمرير `allow_unknown=True`

2. استخدم raw connection:
   - `conn = self.db.get_raw_connection()`
   - `conn.start_transaction()`
   - cursor dictionary إن احتجت

3. قبل التطبيق:
   - اجلب كل lines ذات `Batch_ID IS NOT NULL`
   - تجاهل lines التي الفرق فيها صفر

4. لكل line:
   - `SELECT ... FROM Inventory_Batches JOIN Products_Master ... WHERE Batch_ID=%s FOR UPDATE`
   - تحقق أن `Quantity_Current == Program_Qty_Snapshot`
   - إذا يوجد اختلاف:
     - rollback
     - أرجع `success=False`
     - أرجع قائمة conflicts تحتوي Batch_ID, barcode, snapshot_qty, current_qty, counted_qty

5. إذا لا توجد conflicts:
   - `adjustment = Counted_Qty - Quantity_Current`
   - حدث `Quantity_Current`
   - حدث status:
     - counted 0 => Depleted
     - counted > 0 والحالة Depleted => Available
     - غير ذلك اترك status كما هو
   - سجل movement:
     - استخدم `StockMovementLogManager.create_movement_log`
     - مرر `external_cursor=cursor`
     - `movement_type='Adjustment'`
     - `qty_change=adjustment`
     - `unit_used=Stock_Unit`
     - `batch_id=Batch_ID`
     - `user_id=user_id`
     - `notes='Inventaire #<session_id> - ajustement apres comptage'`

6. بعد كل التعديلات:
   - حدث session إلى Applied.
   - ضع Applied_At و Applied_By.
   - commit.

7. عند أي exception:
   - rollback.
   - أرجع dict واضح بدل crash إذا أمكن.

مهم:
- لا تستخدم `InventoryBatchManager.adjust_batch_quantity` هنا إذا كانت لا تتحقق من snapshot conflict. نحتاج تطبيقًا خاصًا بالجلسة.
- لا تسجل movement إذا adjustment = 0.
- لا تغير `Quantity_Initial`.

معايير القبول:
- نقص 3 وحدات يسجل `Qty_Change = -3`.
- زيادة 2 تسجل `Qty_Change = 2`.
- إذا تغير المخزون بين snapshot والتطبيق، لا يتم تعديل أي batch.
- session applied لا يمكن تطبيقها مرة ثانية.
```

---

## Prompt 07 - إضافة تصدير Excel وفلترة عملية

```text
أنت تعمل داخل مشروع StockLam. اقرأ:
- database/inventory_count_manager.py
- ui/widgets/inventory/inventory_count_tab.py
- requirements.txt

المطلوب:
أضف تصدير Excel لجلسة Inventaire.

في manager:
نفذ أو أكمل:
`export_session_to_excel(session_id, output_path)`

المحتوى:
- sheet `Résumé`
  - Session_ID
  - Session_Name
  - Status
  - Started_At
  - Applied_At
  - OK count
  - SHORT count
  - EXCESS count
  - NOT_COUNTED count
  - UNKNOWN count
  - estimated variance value

- sheet `Lignes`
  - Product_Name
  - Internal_Barcode
  - Lot_Number
  - Expiry_Date
  - Location_Name
  - Program_Qty_Snapshot
  - Counted_Qty
  - Difference_Qty
  - Line_Status
  - Comment

- sheet `Scans`
  - Scanned_Barcode
  - Qty
  - Scan_Status
  - Scanned_At
  - Scanned_By

في UI:
- زر `Exporter`.
- QFileDialog لاختيار مسار الحفظ.
- رسالة نجاح أو فشل.

مهم:
- استخدم `xlsxwriter` أو pandas حسب الأسهل والمتوفر في requirements.
- لا تكتب الملف في مسار ثابت.
- تعامل مع session غير موجودة برسالة واضحة.

معايير القبول:
- ينتج ملف xlsx صالح.
- يمكن فتحه في Excel.
- لا يفشل إذا لا توجد scans.
```

---

## Prompt 08 - اختبارات وحدوية/تكاملية دون قاعدة MySQL حقيقية

```text
أنت تعمل داخل مشروع StockLam. اقرأ:
- database/inventory_count_manager.py
- database/inventory_batch_manager.py
- database/stock_movement_log_manager.py

المطلوب:
أضف اختبارات مركزة للمنطق الجديد قدر الإمكان بدون الحاجة إلى MySQL حقيقية.

إذا لا يوجد test framework حالي، استخدم unittest.

أنشئ:
test/test_inventory_count_manager.py

اختبر الدوال pure/helper إن وجدت:
- حساب Line_Status حسب snapshot/count.
- تنظيف barcode.
- رفض qty <= 0.
- منع تطبيق session Applied.

إذا كان manager مكتوبًا بطريقة تعتمد على db مباشرة، أضف helper methods صغيرة قابلة للاختبار:
- `_line_status(snapshot_qty, counted_qty)`
- `_difference(snapshot_qty, counted_qty)`
- `_normalize_barcode(value)`
- `_can_apply_status(status)`

اختبر:
- snapshot=10 counted=10 => OK diff 0
- snapshot=10 counted=7 => SHORT diff -3
- snapshot=10 counted=12 => EXCESS diff 2
- status Applied => لا يمكن التطبيق
- barcode with spaces => trimmed

مهم:
- لا تحاول تشغيل MySQL في الاختبارات.
- لا تكسر imports.

معايير القبول:
- `venv\Scripts\python.exe -m unittest discover` ينجح.
```

---

## Prompt 09 - مراجعة نهائية بعد التنفيذ

```text
أنت تعمل داخل مشروع StockLam بعد تنفيذ إضافة Inventaire.

راجع كل الملفات التالية:
- database/base/schema_initializer.py
- database/base/config.py
- database/__init__.py
- database/inventory_count_manager.py
- ui/main_window.py
- ui/widgets/inventory/inventory_count_tab.py
- ui/widgets/inventory/inventory_count_scan_dialog.py

المطلوب:
قم بمراجعة تقنية نهائية واصلح المشاكل التي تجدها.

تحقق من:

1. قاعدة البيانات:
   - الجداول موجودة في schema.
   - indexes موجودة.
   - TABLE_IMPORT_ORDER محدث.
   - الصلاحيات مضافة.

2. manager:
   - كل SQL parameterized.
   - كل transaction فيها rollback عند الفشل.
   - apply_session لا تطبق مرتين.
   - conflict detection يعمل.
   - Stock_Movement_Log يسجل فقط الفروقات غير الصفرية.

3. UI:
   - زر Inventaire يظهر في nav bar.
   - الصلاحيات تتحكم في الزر.
   - scanner يبقي focus على barcode input.
   - الأزرار تتعطل حسب حالة session.
   - الرسائل واضحة.

4. تشغيل:
   - `python -m compileall database ui`
   - `venv\Scripts\python.exe -m unittest discover` إذا وجدت اختبارات.

مهم:
- لا تعمل refactor واسع خارج Inventaire.
- لا تغير أسماء الجداول بعد اعتمادها.
- لا تعدل بيانات production.

في النهاية اعرض ملخصًا قصيرًا:
- الملفات التي تغيرت.
- الاختبارات التي شغلتها.
- أي مخاطر متبقية.
```

---

## ترتيب التنفيذ المقترح

1. Prompt 01: schema والصلاحيات.
2. Prompt 02: manager والدوال.
3. Prompt 06: تطبيق الجرد بأمان، لأنه أهم جزء.
4. Prompt 03: زر nav bar.
5. Prompt 04: شاشة Inventaire.
6. Prompt 05: نافذة scanner.
7. Prompt 07: export Excel.
8. Prompt 08: الاختبارات.
9. Prompt 09: المراجعة النهائية.

هذا الترتيب يقلل المخاطر: نثبت قاعدة البيانات والمنطق أولًا، ثم نبني الواجهة فوقها.
