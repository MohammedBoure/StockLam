# توثيق إضافة Inventaire

## الهدف

إضافة شاشة `Inventaire` داخل قسم المخزون تسمح بجرد المخزون الفعلي عن طريق قارئ كود بار، ثم عرض الفرق بين:

- الكمية الموجودة في البرنامج: `Inventory_Batches.Quantity_Current`
- الكمية الموجودة في الواقع بعد الجرد

بعد مراجعة الفروقات، يستطيع المستخدم تطبيق الجرد على المخزون في البرنامج. التطبيق لا يغيّر المخزون مباشرة أثناء المسح، بل يتم فقط بعد تأكيد نهائي حتى تبقى العملية قابلة للمراجعة.

## فهم قاعدة البيانات الحالية

المخزون الفعلي في النظام محفوظ على مستوى الدفعات في جدول `Inventory_Batches`.

أهم الأعمدة:

- `Batch_ID`: معرف الدفعة.
- `Internal_Barcode`: كود بار داخلي فريد للدفعة.
- `Product_ID`: المنتج.
- `Location_ID`: الموقع الحالي.
- `Lot_Number`: رقم اللوت.
- `Expiry_Date`: تاريخ انتهاء الصلاحية.
- `Quantity_Current`: الرصيد الحالي في البرنامج.
- `Quantity_Initial`: الكمية الأصلية عند الاستلام.
- `Status`: حالة الدفعة: `Available`, `Quarantined`, `Expired`, `Depleted`.

كل حركة تؤثر على المخزون يجب أن تسجل في `Stock_Movement_Log`.

أهم الأعمدة:

- `Product_ID`
- `Batch_ID`
- `Movement_Type`
- `Qty_Change`
- `Unit_Used`
- `User_ID`
- `Notes`
- `Stock_After`

لأن نوع الحركة `Adjustment` موجود بالفعل، سيتم استخدامه عند تطبيق فروقات الجرد.

## مكان الإضافة في الواجهة

الإضافة تكون داخل:

```text
Stock & Magasin
```

في الملف الحالي:

```text
ui/widgets/inventory/inventory_tabs.py
```

تقترح الإضافة تبويبًا ثالثًا:

```text
Inventaire
```

الصلاحيات المقترحة:

- `tab_inv_inventaire`: رؤية تبويب الجرد.
- `act_inventory_create`: إنشاء جلسة جرد.
- `act_inventory_scan`: إدخال/مسح كود بار.
- `act_inventory_apply`: تطبيق الفروقات على المخزون.
- `act_inventory_cancel`: إلغاء جلسة جرد.

يجب إضافة هذه الصلاحيات إلى `_ALL_PERMISSIONS` في:

```text
database/base/schema_initializer.py
```

## نموذج العمل

### 1. إنشاء جلسة جرد

المستخدم ينشئ جلسة جديدة ويختار نطاق الجرد:

- كل المخزون.
- موقع محدد `Location_ID`.
- عائلة منتجات `Family_ID`.
- منتج واحد.
- دفعات ذات رصيد موجب فقط.

عند إنشاء الجلسة، يتم أخذ Snapshot من المخزون الحالي داخل جدول تفاصيل الجرد. هذا مهم لأن المخزون قد يتغير بعد بدء الجرد.

### 2. نافذة قارئ كود بار

نافذة بسيطة وسريعة:

- حقل كود بار يأخذ التركيز دائمًا.
- قارئ كود بار يعمل مثل keyboard input وينهي الإدخال بـ Enter.
- عند قراءة `Internal_Barcode` موجود:
  - يتم جلب الدفعة.
  - يتم زيادة الكمية المعدودة للدفعة.
  - يمكن استعمال كمية افتراضية `1`.
  - يمكن تغيير الكمية يدويًا قبل/بعد المسح.
- عند قراءة كود غير معروف:
  - يسجل كسطر `Unknown`.
  - لا يطبق على المخزون.
  - يظهر للمستخدم للمراجعة.

### 3. عرض الفروقات

بعد أو أثناء الجرد، تعرض الشاشة جدولًا يحتوي:

- المنتج.
- الكود الداخلي.
- اللوت.
- تاريخ الانتهاء.
- الموقع.
- الكمية في البرنامج وقت إنشاء الجرد.
- الكمية المعدودة في الواقع.
- الفرق: `Counted_Qty - Program_Qty_Snapshot`.
- الحالة:
  - `OK`: لا يوجد فرق.
  - `SHORT`: نقص في الواقع.
  - `EXCESS`: زيادة في الواقع.
  - `NOT_COUNTED`: موجود في البرنامج ولم يتم جرده.
  - `UNKNOWN`: كود ممسوح غير موجود في البرنامج.

### 4. مراجعة الجرد

قبل التطبيق، يجب أن يرى المستخدم ملخصًا:

- عدد الدفعات المطابقة.
- عدد الدفعات التي بها نقص.
- عدد الدفعات التي بها زيادة.
- عدد الأكواد غير المعروفة.
- القيمة المالية التقديرية للفروقات، إن أمكن، باستخدام `Unit_Price_Received`.

لا يسمح بالتطبيق إذا كانت هناك أكواد `UNKNOWN` غير معالجة، إلا إذا اختار المستخدم تجاهلها صراحة.

### 5. تطبيق الجرد على المخزون

عند الضغط على `Appliquer l'inventaire`:

1. يبدأ Transaction.
2. يتم قفل كل دفعة مستهدفة بـ `SELECT ... FOR UPDATE`.
3. يعاد قراءة `Quantity_Current`.
4. إذا تغيرت الكمية الحالية منذ Snapshot، يتم إيقاف التطبيق لهذه الدفعة أو للجلسة كلها حسب السياسة المختارة.
5. يتم تحديث `Inventory_Batches.Quantity_Current` إلى الكمية المعدودة.
6. يتم تحديث `Status`:
   - إذا أصبحت الكمية `0`: `Depleted`.
   - إذا كانت أكبر من `0` وكانت الحالة `Depleted`: تعود إلى `Available`.
   - الحالات `Quarantined` و `Expired` لا تغير تلقائيًا إلا إذا قررنا ذلك لاحقًا.
7. يسجل سطر في `Stock_Movement_Log` لكل فرق غير صفري:
   - `Movement_Type = 'Adjustment'`
   - `Qty_Change = Counted_Qty - Current_Qty`
   - `Notes = 'Inventaire #<session_id>: <comment>'`
8. يتم تحديث حالة الجلسة إلى `Applied`.

## الجداول المقترحة

### Inventory_Count_Sessions

```sql
CREATE TABLE IF NOT EXISTS Inventory_Count_Sessions (
    Session_ID BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    Session_Name VARCHAR(150) NOT NULL,
    Scope_Type ENUM('ALL', 'LOCATION', 'FAMILY', 'PRODUCT') NOT NULL DEFAULT 'ALL',
    Scope_ID BIGINT UNSIGNED NULL,
    Status ENUM('Draft', 'Counting', 'Review', 'Applied', 'Cancelled') NOT NULL DEFAULT 'Draft',
    Started_At DATETIME DEFAULT CURRENT_TIMESTAMP,
    Completed_At DATETIME NULL,
    Applied_At DATETIME NULL,
    Created_By INT UNSIGNED NULL,
    Applied_By INT UNSIGNED NULL,
    Notes TEXT NULL,
    FOREIGN KEY (Created_By) REFERENCES Users(User_ID) ON DELETE SET NULL,
    FOREIGN KEY (Applied_By) REFERENCES Users(User_ID) ON DELETE SET NULL
);
```

### Inventory_Count_Lines

```sql
CREATE TABLE IF NOT EXISTS Inventory_Count_Lines (
    Line_ID BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    Session_ID BIGINT UNSIGNED NOT NULL,
    Batch_ID BIGINT UNSIGNED NULL,
    Product_ID INT UNSIGNED NULL,
    Internal_Barcode VARCHAR(50) NULL,
    Program_Qty_Snapshot DECIMAL(15, 2) NOT NULL DEFAULT 0,
    Counted_Qty DECIMAL(15, 2) NOT NULL DEFAULT 0,
    Difference_Qty DECIMAL(15, 2) GENERATED ALWAYS AS (Counted_Qty - Program_Qty_Snapshot) STORED,
    Line_Status ENUM('OK', 'SHORT', 'EXCESS', 'NOT_COUNTED', 'UNKNOWN') NOT NULL DEFAULT 'NOT_COUNTED',
    Last_Scanned_At DATETIME NULL,
    Comment TEXT NULL,
    FOREIGN KEY (Session_ID) REFERENCES Inventory_Count_Sessions(Session_ID) ON DELETE CASCADE,
    FOREIGN KEY (Batch_ID) REFERENCES Inventory_Batches(Batch_ID) ON DELETE SET NULL,
    FOREIGN KEY (Product_ID) REFERENCES Products_Master(Product_ID) ON DELETE SET NULL,
    UNIQUE KEY uq_inventory_count_line_batch (Session_ID, Batch_ID),
    INDEX idx_inventory_count_barcode (Internal_Barcode)
);
```

ملاحظة: إذا كانت نسخة MySQL أو MariaDB لا تدعم generated columns بالشكل المطلوب، يتم تخزين `Difference_Qty` كعمود عادي وتحديثه من الكود.

### Inventory_Count_Scans

```sql
CREATE TABLE IF NOT EXISTS Inventory_Count_Scans (
    Scan_ID BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    Session_ID BIGINT UNSIGNED NOT NULL,
    Line_ID BIGINT UNSIGNED NULL,
    Scanned_Barcode VARCHAR(100) NOT NULL,
    Qty DECIMAL(15, 2) NOT NULL DEFAULT 1,
    Scan_Status ENUM('MATCHED', 'UNKNOWN', 'IGNORED') NOT NULL DEFAULT 'MATCHED',
    Scanned_At DATETIME DEFAULT CURRENT_TIMESTAMP,
    Scanned_By INT UNSIGNED NULL,
    FOREIGN KEY (Session_ID) REFERENCES Inventory_Count_Sessions(Session_ID) ON DELETE CASCADE,
    FOREIGN KEY (Line_ID) REFERENCES Inventory_Count_Lines(Line_ID) ON DELETE SET NULL,
    FOREIGN KEY (Scanned_By) REFERENCES Users(User_ID) ON DELETE SET NULL,
    INDEX idx_inventory_scan_barcode (Scanned_Barcode)
);
```

## Manager المقترح

ملف جديد:

```text
database/inventory_count_manager.py
```

الكلاس:

```python
class InventoryCountManager:
    def create_session(...)
    def build_snapshot(session_id)
    def scan_barcode(session_id, barcode, qty, user_id)
    def update_counted_quantity(line_id, qty)
    def get_session_lines(session_id)
    def get_session_summary(session_id)
    def apply_session(session_id, user_id)
    def cancel_session(session_id, user_id)
```

ثم يضاف إلى `LabDataManager`:

```python
self.inventory_counts = InventoryCountManager(db_instance)
```

## شاشة الواجهة المقترحة

ملفات جديدة:

```text
ui/widgets/inventory/inventory_count_tab.py
ui/widgets/inventory/inventory_count_scan_dialog.py
```

الشاشة الرئيسية تعرض:

- قائمة جلسات الجرد.
- زر إنشاء جلسة.
- زر فتح نافذة المسح.
- جدول الفروقات.
- فلاتر: الموقع، المنتج، الحالة.
- أزرار: مراجعة، تطبيق، إلغاء، تصدير Excel.

نافذة المسح تعرض:

- حقل كود بار كبير.
- كمية المسح.
- آخر منتج تم التعرف عليه.
- صوت/لون نجاح أو خطأ.
- قائمة آخر الأكواد الممسوحة.

## قواعد مهمة عند التطبيق

- لا يتم حذف أي Batch بسبب الجرد.
- إذا الكمية الفعلية `0`، يتم فقط جعل `Quantity_Current = 0` و `Status = 'Depleted'`.
- لا يتم تعديل `Quantity_Initial`.
- لا يتم تعديل أسعار الدفعات.
- كل فرق يمر عبر `Stock_Movement_Log`.
- لا يسمح بتطبيق نفس الجلسة مرتين.
- لا يطبق الجرد على `Active_Containers` في المرحلة الأولى، لأن نظام الحاويات المفتوحة يستخدم وحدة استعمال مختلفة (`Usage_Unit`) عن رصيد الدفعات (`Stock_Unit`).

## سياسة التعارضات

لأن المخزون قد يتغير أثناء الجرد، يجب عند التطبيق مقارنة:

- `Program_Qty_Snapshot`
- `Inventory_Batches.Quantity_Current` الحالي

إذا اختلفا:

- الخيار المحافظ: إيقاف التطبيق وإظهار الدفعات المتغيرة.
- الخيار العملي لاحقًا: السماح بإعادة حساب الفرق على الكمية الحالية بعد تأكيد المستخدم.

الاقتراح الأول للمرحلة الأولى هو الخيار المحافظ.

## خطوات التنفيذ المقترحة

1. إضافة صلاحيات inventaire إلى schema.
2. إضافة جداول الجرد إلى `schema_initializer.py`.
3. إنشاء `InventoryCountManager`.
4. ربطه داخل `LabDataManager`.
5. إضافة تبويب `Inventaire` إلى `InventoryTab`.
6. بناء نافذة scanner.
7. بناء جدول الفروقات والملخص.
8. تنفيذ `apply_session` بـ transaction و `FOR UPDATE`.
9. إضافة export Excel.
10. اختبار السيناريوهات الأساسية:
    - جرد مطابق.
    - نقص.
    - زيادة.
    - كود غير معروف.
    - تطبيق جلسة مرة واحدة فقط.
    - تغير المخزون بعد snapshot وقبل التطبيق.

## قرار المرحلة الأولى

المرحلة الأولى يجب أن تكون على مستوى `Inventory_Batches.Internal_Barcode` فقط، لأنه أدق رابط بين قارئ الكود والمخزون الحالي.

استخدام `Products_Master.Barcode` يمكن إضافته لاحقًا كمسار مساعد، لكنه يحتاج قرارًا عند وجود أكثر من دفعة لنفس المنتج.
