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
      userId: json['user_id'] as int? ?? 0,
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
      userId: json['user_id'] as int? ?? 0,
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
      productId: json['Product_ID'] as int? ?? 0,
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
      batchId: json['Batch_ID'] as int? ?? 0,
      productId: json['Product_ID'] as int? ?? 0,
      internalBarcode: json['Internal_Barcode'] as String? ?? '',
      lotNumber: json['Lot_Number'] as String? ?? '---',
      expiryDate: json['Expiry_Date'] as String? ?? '',
      quantityCurrent: (json['Quantity_Current'] as num?)?.toDouble() ?? 0.0,
      locationId: json['Location_ID'] as int?,
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
      locationId: json['Location_ID'] as int? ?? 0,
      locationName: json['Location_Name'] as String? ?? 'Emplacement',
      parentId: json['Parent_ID'] as int?,
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
  });

  final int batchId;
  final int productId;
  final String productName;
  final String lotNumber;
  final String expiryDate;
  final double currentQty;
  int qty;
  final int? locationId;
  final String locationName;
  int? targetLocationId;
  String? targetLocationName;
  String? notes;
  bool isRecommended;
  bool allowFefoOverride;

  Map<String, dynamic> toJson() => {
        'batch_id': batchId,
        'product_id': productId,
        'qty': qty,
        if (targetLocationId != null) 'target_location_id': targetLocationId,
        if (notes != null && notes!.isNotEmpty) 'notes': notes,
        'allow_fefo_override': allowFefoOverride,
      };
}
