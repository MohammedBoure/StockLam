// mobile_inventory_scanner/lib/models.dart

class DesktopDevice {
  const DesktopDevice({
    required this.name,
    required this.id,
    required this.baseUrl,
  });

  final String name;
  final String id;
  final String baseUrl;
}

class ScanEntry {
  const ScanEntry({
    required this.barcode,
    required this.message,
    required this.time,
  });

  final String barcode;
  final String message;
  final DateTime time;
}

class AuthUser {
  const AuthUser({
    required this.userId,
    required this.username,
    required this.fullName,
    required this.role,
  });

  factory AuthUser.fromJson(Map<String, dynamic> json) {
    return AuthUser(
      userId: (json['user_id'] as num?)?.toInt() ?? 0,
      username: json['username'] as String? ?? '',
      fullName: json['full_name'] as String? ?? json['username'] as String? ?? 'Utilisateur',
      role: json['role'] as String? ?? 'Technician',
    );
  }

  Map<String, dynamic> toJson() => {
        'user_id': userId,
        'username': username,
        'full_name': fullName,
        'role': role,
      };

  final int userId;
  final String username;
  final String fullName;
  final String role;
}

class SavedAccount {
  const SavedAccount({
    required this.id,
    required this.serverUrl,
    required this.serverName,
    required this.username,
    required this.password,
    required this.userId,
    required this.fullName,
    required this.role,
    required this.savedAt,
  });

  factory SavedAccount.fromJson(Map<String, dynamic> json) {
    return SavedAccount(
      id: json['id'] as String? ?? '',
      serverUrl: json['server_url'] as String? ?? '',
      serverName: json['server_name'] as String? ?? 'StockLam PC',
      username: json['username'] as String? ?? '',
      password: json['password'] as String? ?? '',
      userId: (json['user_id'] as num?)?.toInt() ?? 0,
      fullName: json['full_name'] as String? ?? '',
      role: json['role'] as String? ?? 'Technician',
      savedAt: DateTime.tryParse(json['saved_at'] as String? ?? '') ?? DateTime.now(),
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'server_url': serverUrl,
        'server_name': serverName,
        'username': username,
        'password': password,
        'user_id': userId,
        'full_name': fullName,
        'role': role,
        'saved_at': savedAt.toIso8601String(),
      };

  final String id;
  final String serverUrl;
  final String serverName;
  final String username;
  final String password;
  final int userId;
  final String fullName;
  final String role;
  final DateTime savedAt;
}

class ProductDetails {
  const ProductDetails({
    required this.productId,
    required this.productName,
    required this.barcode,
    required this.familyName,
    required this.manufName,
    required this.stockUnit,
    required this.minStockLevel,
  });

  factory ProductDetails.fromJson(Map<String, dynamic> json) {
    return ProductDetails(
      productId: (json['Product_ID'] as num?)?.toInt() ?? 0,
      productName: json['Product_Name'] as String? ?? 'Produit sans nom',
      barcode: json['Barcode'] as String? ?? '',
      familyName: json['Family_Name'] as String? ?? 'Général',
      manufName: json['Manuf_Name'] as String? ?? 'Fabricant inconnu',
      stockUnit: json['Stock_Unit'] as String? ?? 'Unité',
      minStockLevel: (json['Minimum_Stock_Level'] as num?)?.toDouble() ?? 5.0,
    );
  }

  final int productId;
  final String productName;
  final String barcode;
  final String familyName;
  final String manufName;
  final String stockUnit;
  final double minStockLevel;
}

class BatchDetails {
  const BatchDetails({
    required this.batchId,
    required this.productId,
    required this.internalBarcode,
    required this.lotNumber,
    required this.expiryDate,
    required this.quantityCurrent,
    required this.locationId,
    required this.locationName,
    required this.dateReceived,
    required this.isRecommended,
    required this.isScannedMatch,
  });

  factory BatchDetails.fromJson(Map<String, dynamic> json) {
    return BatchDetails(
      batchId: (json['Batch_ID'] as num?)?.toInt() ?? 0,
      productId: (json['Product_ID'] as num?)?.toInt() ?? 0,
      internalBarcode: json['Internal_Barcode'] as String? ?? '',
      lotNumber: json['Lot_Number'] as String? ?? '---',
      expiryDate: json['Expiry_Date'] as String? ?? '',
      quantityCurrent: (json['Quantity_Current'] as num?)?.toDouble() ?? 0.0,
      locationId: (json['Location_ID'] as num?)?.toInt(),
      locationName: json['Location_Name'] as String? ?? 'Emplacement non défini',
      dateReceived: json['Date_Received'] as String? ?? '',
      isRecommended: json['is_recommended'] as bool? ?? false,
      isScannedMatch: json['is_scanned_match'] as bool? ?? false,
    );
  }

  final int batchId;
  final int productId;
  final String internalBarcode;
  final String lotNumber;
  final String expiryDate;
  final double quantityCurrent;
  final int? locationId;
  final String locationName;
  final String dateReceived;
  final bool isRecommended;
  final bool isScannedMatch;
}

class LocationItem {
  const LocationItem({
    required this.locationId,
    required this.locationName,
    required this.parentId,
    required this.typeName,
    required this.fullPath,
  });

  factory LocationItem.fromJson(Map<String, dynamic> json) {
    return LocationItem(
      locationId: (json['Location_ID'] as num?)?.toInt() ?? 0,
      locationName: json['Location_Name'] as String? ?? 'Emplacement',
      parentId: (json['Parent_ID'] as num?)?.toInt(),
      typeName: json['Type_Name'] as String? ?? '',
      fullPath: json['Full_Path'] as String? ?? json['Location_Name'] as String? ?? '',
    );
  }

  final int locationId;
  final String locationName;
  final int? parentId;
  final String typeName;
  final String fullPath;
}

class FefoViolationData {
  const FefoViolationData({
    required this.message,
    required this.scannedBatch,
    required this.recommendedBatch,
    required this.availableBatches,
  });

  factory FefoViolationData.fromJson(Map<String, dynamic> json) {
    final rawAvailable = json['available_batches'] as List<dynamic>? ?? [];
    return FefoViolationData(
      message: json['message'] as String? ?? 'Violation des règles FEFO détectée.',
      scannedBatch: json['scanned_batch'] as Map<String, dynamic>? ?? {},
      recommendedBatch: json['recommended_batch'] as Map<String, dynamic>? ?? {},
      availableBatches: rawAvailable.map((item) => item as Map<String, dynamic>).toList(),
    );
  }

  final String message;
  final Map<String, dynamic> scannedBatch;
  final Map<String, dynamic> recommendedBatch;
  final List<Map<String, dynamic>> availableBatches;
}

class BulkDispatchItem {
  BulkDispatchItem({
    String? lineId,
    required this.batchId,
    required this.productId,
    required this.productName,
    required this.lotNumber,
    required this.expiryDate,
    required this.currentQty,
    this.qty = 1,
    this.locationId,
    required this.locationName,
    this.targetLocationId,
    this.targetLocationName,
    this.notes,
    this.isRecommended = false,
    this.allowFefoOverride = false,
    this.availableBatches = const [],
  }) : lineId = lineId ?? DateTime.now().microsecondsSinceEpoch.toString();

  final String lineId;
  int batchId;
  final int productId;
  final String productName;
  String lotNumber;
  String expiryDate;
  double currentQty;
  int qty;
  int? locationId;
  String locationName;
  int? targetLocationId;
  String? targetLocationName;
  String? notes;
  bool isRecommended;
  bool allowFefoOverride;
  List<BatchDetails> availableBatches;

  void updateBatch(BatchDetails newBatch, {bool allowOverride = false}) {
    batchId = newBatch.batchId;
    lotNumber = newBatch.lotNumber;
    expiryDate = newBatch.expiryDate;
    currentQty = newBatch.quantityCurrent;
    locationId = newBatch.locationId;
    locationName = newBatch.locationName;
    isRecommended = newBatch.isRecommended;
    allowFefoOverride = allowOverride;
    if (qty > currentQty.toInt()) {
      qty = currentQty.toInt().clamp(1, 9999);
    }
  }

  Map<String, dynamic> toJson() => {
        'batch_id': batchId,
        'product_id': productId,
        'qty': qty,
        if (targetLocationId != null) 'target_location_id': targetLocationId,
        if (notes != null && notes!.isNotEmpty) 'notes': notes,
        'allow_fefo_override': allowFefoOverride,
      };
}

class InventorySessionItem {
  const InventorySessionItem({
    required this.sessionId,
    required this.sessionName,
    required this.scopeType,
    this.scopeId,
    required this.status,
    this.createdBy,
    this.notes,
    this.startedAt,
    this.completedAt,
    this.appliedAt,
    this.totalLines = 0,
    this.okCount = 0,
    this.shortCount = 0,
    this.excessCount = 0,
    this.notCountedCount = 0,
    this.unknownCount = 0,
    this.locationName,
    this.familyName,
    this.productName,
    this.summary,
  });

  factory InventorySessionItem.fromJson(Map<String, dynamic> json) {
    final rawSummary = json['summary'] as Map<String, dynamic>?;
    return InventorySessionItem(
      sessionId: (json['Session_ID'] as num?)?.toInt() ?? 0,
      sessionName: json['Session_Name'] as String? ?? 'Session',
      scopeType: json['Scope_Type'] as String? ?? 'ALL',
      scopeId: (json['Scope_ID'] as num?)?.toInt(),
      status: json['Status'] as String? ?? 'Draft',
      createdBy: (json['Created_By'] as num?)?.toInt(),
      notes: json['Notes'] as String?,
      startedAt: json['Started_At'] as String?,
      completedAt: json['Completed_At'] as String?,
      appliedAt: json['Applied_At'] as String?,
      totalLines: (json['Total_Lines'] as num?)?.toInt() ?? 0,
      okCount: (json['OK_Count'] as num?)?.toInt() ?? 0,
      shortCount: (json['Short_Count'] as num?)?.toInt() ?? 0,
      excessCount: (json['Excess_Count'] as num?)?.toInt() ?? 0,
      notCountedCount: (json['Not_Counted_Count'] as num?)?.toInt() ?? 0,
      unknownCount: (json['Unknown_Count'] as num?)?.toInt() ?? 0,
      locationName: json['Location_Name'] as String?,
      familyName: json['Family_Name'] as String?,
      productName: json['Product_Name'] as String?,
      summary: rawSummary != null ? InventorySummaryData.fromJson(rawSummary) : null,
    );
  }

  final int sessionId;
  final String sessionName;
  final String scopeType;
  final int? scopeId;
  final String status;
  final int? createdBy;
  final String? notes;
  final String? startedAt;
  final String? completedAt;
  final String? appliedAt;
  final int totalLines;
  final int okCount;
  final int shortCount;
  final int excessCount;
  final int notCountedCount;
  final int unknownCount;
  final String? locationName;
  final String? familyName;
  final String? productName;
  final InventorySummaryData? summary;

  int get countedLines => okCount + shortCount + excessCount;
  double get progressPercentage =>
      totalLines > 0 ? (countedLines / totalLines).clamp(0.0, 1.0) : 0.0;
}

class InventorySummaryData {
  const InventorySummaryData({
    this.totalLines = 0,
    this.ok = 0,
    this.short = 0,
    this.excess = 0,
    this.notCounted = 0,
    this.unknown = 0,
    this.estimatedVarianceValue = 0.0,
  });

  factory InventorySummaryData.fromJson(Map<String, dynamic> json) {
    return InventorySummaryData(
      totalLines: (json['Total_Lines'] as num?)?.toInt() ?? 0,
      ok: (json['OK'] as num?)?.toInt() ?? 0,
      short: (json['SHORT'] as num?)?.toInt() ?? 0,
      excess: (json['EXCESS'] as num?)?.toInt() ?? 0,
      notCounted: (json['NOT_COUNTED'] as num?)?.toInt() ?? 0,
      unknown: (json['UNKNOWN'] as num?)?.toInt() ?? 0,
      estimatedVarianceValue:
          (json['Estimated_Variance_Value'] as num?)?.toDouble() ?? 0.0,
    );
  }

  final int totalLines;
  final int ok;
  final int short;
  final int excess;
  final int notCounted;
  final int unknown;
  final double estimatedVarianceValue;
}

class InventoryLineItem {
  const InventoryLineItem({
    required this.lineId,
    required this.sessionId,
    this.batchId,
    this.productId,
    required this.internalBarcode,
    this.productBarcode,
    required this.productName,
    this.manufCatNo,
    this.familyName,
    this.lotNumber,
    this.expiryDate,
    this.locationName,
    this.programQtySnapshot = 0.0,
    this.countedQty = 0.0,
    this.differenceQty = 0.0,
    required this.lineStatus,
    this.stockUnit = 'Unité',
    this.lastScannedAt,
  });

  factory InventoryLineItem.fromJson(Map<String, dynamic> json) {
    return InventoryLineItem(
      lineId: (json['Line_ID'] as num?)?.toInt() ?? 0,
      sessionId: (json['Session_ID'] as num?)?.toInt() ?? 0,
      batchId: (json['Batch_ID'] as num?)?.toInt(),
      productId: (json['Product_ID'] as num?)?.toInt(),
      internalBarcode: json['Internal_Barcode'] as String? ?? '',
      productBarcode: json['Product_Barcode'] as String?,
      productName: json['Product_Name'] as String? ??
          (json['Internal_Barcode'] != null
              ? 'Code ${json['Internal_Barcode']}'
              : 'Article Inconnu'),
      manufCatNo: json['Manuf_Cat_No'] as String?,
      familyName: json['Family_Name'] as String?,
      lotNumber: json['Lot_Number'] as String? ?? '---',
      expiryDate: json['Expiry_Date'] as String?,
      locationName: json['Location_Name'] as String? ?? '---',
      programQtySnapshot:
          (json['Program_Qty_Snapshot'] as num?)?.toDouble() ?? 0.0,
      countedQty: (json['Counted_Qty'] as num?)?.toDouble() ?? 0.0,
      differenceQty: (json['Difference_Qty'] as num?)?.toDouble() ?? 0.0,
      lineStatus: json['Line_Status'] as String? ?? 'NOT_COUNTED',
      stockUnit: json['Stock_Unit'] as String? ?? 'Unité',
      lastScannedAt: json['Last_Scanned_At'] as String?,
    );
  }

  final int lineId;
  final int sessionId;
  final int? batchId;
  final int? productId;
  final String internalBarcode;
  final String? productBarcode;
  final String productName;
  final String? manufCatNo;
  final String? familyName;
  final String? lotNumber;
  final String? expiryDate;
  final String? locationName;
  final double programQtySnapshot;
  final double countedQty;
  final double differenceQty;
  final String lineStatus;
  final String stockUnit;
  final String? lastScannedAt;
}

class InventoryScanResultData {
  const InventoryScanResultData({
    required this.success,
    required this.status,
    required this.message,
    this.line,
  });

  factory InventoryScanResultData.fromJson(Map<String, dynamic> json) {
    final rawLine = json['line'] as Map<String, dynamic>?;
    return InventoryScanResultData(
      success: json['success'] as bool? ?? false,
      status: json['status'] as String? ?? 'UNKNOWN',
      message: json['message'] as String? ?? '',
      line: rawLine != null ? InventoryLineItem.fromJson(rawLine) : null,
    );
  }

  final bool success;
  final String status;
  final String message;
  final InventoryLineItem? line;
}

class InventoryScopeData {
  const InventoryScopeData({
    required this.locations,
    required this.families,
  });

  factory InventoryScopeData.fromJson(Map<String, dynamic> json) {
    final scopes = json['scopes'] as Map<String, dynamic>? ?? {};
    final rawLocs = scopes['locations'] as List<dynamic>? ?? [];
    final rawFams = scopes['families'] as List<dynamic>? ?? [];

    return InventoryScopeData(
      locations: rawLocs
          .map((i) => LocationItem.fromJson(i as Map<String, dynamic>))
          .toList(),
      families: rawFams
          .map((i) => {
                'Family_ID': (i['Family_ID'] as num?)?.toInt() ?? 0,
                'Family_Name': i['Family_Name'] as String? ?? 'Famille',
              })
          .toList(),
    );
  }

  final List<LocationItem> locations;
  final List<Map<String, dynamic>> families;
}

