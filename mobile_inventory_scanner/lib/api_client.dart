// mobile_inventory_scanner/lib/api_client.dart

import 'dart:convert';
import 'package:http/http.dart' as http;
import 'models.dart';

const stockLamMobileApiKey = 'StockLam-Inventaire-Mobile-2026';

String cleanBaseUrl(String value) =>
    value.trim().replaceAll(RegExp(r'/+$'), '');

class ApiClient {
  ApiClient({required this.baseUrl});

  final String baseUrl;

  Map<String, String> get headers => {
        'Content-Type': 'application/json',
        'X-API-Key': stockLamMobileApiKey,
      };

  Uri uri(String path) => Uri.parse('${cleanBaseUrl(baseUrl)}$path');

  Future<Map<String, dynamic>> health() async {
    final response = await http
        .get(uri('/api/health'), headers: headers)
        .timeout(const Duration(seconds: 8));
    return _decode(response);
  }

  Future<AuthUser> login({
    required String username,
    required String password,
  }) async {
    final response = await http
        .post(
          uri('/api/auth/login'),
          headers: headers,
          body: jsonEncode({
            'username': username,
            'password': password,
          }),
        )
        .timeout(const Duration(seconds: 8));
    final data = _decode(response);
    if (data['success'] == true && data['user'] != null) {
      return AuthUser.fromJson(data['user'] as Map<String, dynamic>);
    }
    throw Exception(data['message'] ?? 'Échec de l\'authentification');
  }

  Future<List<Map<String, dynamic>>> getUsersList() async {
    final response = await http
        .get(uri('/api/users/list'), headers: headers)
        .timeout(const Duration(seconds: 8));
    final data = _decode(response);
    final list = data['users'] as List<dynamic>? ?? [];
    return list.cast<Map<String, dynamic>>();
  }

  Future<Map<String, dynamic>> sendRemoteBarcode(
    String barcode, {
    int? userId,
    String? userName,
  }) async {
    final response = await http
        .post(
          uri('/api/remote-scans'),
          headers: headers,
          body: jsonEncode({
            'barcode': barcode,
            if (userId != null) 'user_id': userId,
            if (userName != null) 'user_name': userName,
          }),
        )
        .timeout(const Duration(seconds: 8));
    return _decode(response);
  }

  Future<Map<String, dynamic>> lookupBarcode(String barcode) async {
    final encoded = Uri.encodeQueryComponent(barcode.trim());
    final response = await http
        .get(
          uri('/api/barcode/lookup?barcode=$encoded'),
          headers: headers,
        )
        .timeout(const Duration(seconds: 8));
    return _decode(response);
  }

  Future<List<LocationItem>> getLocations() async {
    final response = await http
        .get(uri('/api/locations'), headers: headers)
        .timeout(const Duration(seconds: 8));
    final data = _decode(response);
    final list = data['locations'] as List<dynamic>? ?? [];
    return list.map((item) => LocationItem.fromJson(item as Map<String, dynamic>)).toList();
  }

  Future<Map<String, dynamic>> consumeStock({
    required int batchId,
    required int qty,
    int? userId,
    bool allowFefoOverride = false,
    String? notes,
  }) async {
    final response = await http
        .post(
          uri('/api/stock/consume'),
          headers: headers,
          body: jsonEncode({
            'batch_id': batchId,
            'qty': qty,
            if (userId != null) 'user_id': userId,
            'allow_fefo_override': allowFefoOverride,
            if (notes != null && notes.isNotEmpty) 'notes': notes,
          }),
        )
        .timeout(const Duration(seconds: 8));
    return _decode(response);
  }

  Future<Map<String, dynamic>> transferStock({
    required int batchId,
    required int targetLocationId,
    required int qty,
    int? userId,
  }) async {
    final response = await http
        .post(
          uri('/api/stock/transfer'),
          headers: headers,
          body: jsonEncode({
            'batch_id': batchId,
            'target_location_id': targetLocationId,
            'qty': qty,
            if (userId != null) 'user_id': userId,
          }),
        )
        .timeout(const Duration(seconds: 8));
    return _decode(response);
  }

  Future<Map<String, dynamic>> bulkDispatch({
    required String mode,
    required List<BulkDispatchItem> items,
    int? userId,
    bool allowFefoOverride = false,
  }) async {
    final response = await http
        .post(
          uri('/api/stock/bulk-dispatch'),
          headers: headers,
          body: jsonEncode({
            'mode': mode,
            'items': items.map((i) => i.toJson()).toList(),
            if (userId != null) 'user_id': userId,
            'allow_fefo_override': allowFefoOverride,
          }),
        )
        .timeout(const Duration(seconds: 15));
    return _decode(response);
  }

  // =========================================================================
  // Inventaire Physique (Physical Inventory Count Sessions)
  // =========================================================================

  Future<List<InventorySessionItem>> getInventorySessions({
    String? status,
    int limit = 50,
    String? year,
  }) async {
    final queryParams = <String, String>{
      'limit': limit.toString(),
      if (status != null && status.isNotEmpty) 'status': status,
      if (year != null && year.isNotEmpty) 'year': year,
    };
    final queryString = Uri(queryParameters: queryParams).query;
    final path = '/api/inventory-sessions${queryString.isNotEmpty ? '?$queryString' : ''}';
    final response = await http.get(uri(path), headers: headers).timeout(const Duration(seconds: 10));
    final data = _decode(response);
    final list = data['sessions'] as List<dynamic>? ?? [];
    return list.map((item) => InventorySessionItem.fromJson(item as Map<String, dynamic>)).toList();
  }

  Future<InventorySessionItem> getInventorySession(int sessionId) async {
    final response =
        await http.get(uri('/api/inventory-sessions/$sessionId'), headers: headers).timeout(const Duration(seconds: 8));
    final data = _decode(response);
    final sessionMap = data['session'] as Map<String, dynamic>? ?? {};
    return InventorySessionItem.fromJson(sessionMap);
  }

  Future<Map<String, dynamic>> createInventorySession({
    required String name,
    String scopeType = 'ALL',
    int? scopeId,
    int? userId,
    String? notes,
  }) async {
    final response = await http
        .post(
          uri('/api/inventory-sessions'),
          headers: headers,
          body: jsonEncode({
            'name': name,
            'scope_type': scopeType,
            if (scopeId != null) 'scope_id': scopeId,
            if (userId != null) 'user_id': userId,
            if (notes != null && notes.isNotEmpty) 'notes': notes,
          }),
        )
        .timeout(const Duration(seconds: 10));
    return _decode(response);
  }

  Future<InventoryScopeData> getInventoryScopes() async {
    final response =
        await http.get(uri('/api/inventory-scopes'), headers: headers).timeout(const Duration(seconds: 8));
    final data = _decode(response);
    return InventoryScopeData.fromJson(data);
  }

  Future<List<InventoryLineItem>> getInventorySessionLines(
    int sessionId, {
    String? status,
    String? search,
  }) async {
    final queryParams = <String, String>{
      if (status != null && status.isNotEmpty) 'status': status,
      if (search != null && search.isNotEmpty) 'search': search,
    };
    final queryString = Uri(queryParameters: queryParams).query;
    final path =
        '/api/inventory-sessions/$sessionId/lines${queryString.isNotEmpty ? '?$queryString' : ''}';
    final response = await http.get(uri(path), headers: headers).timeout(const Duration(seconds: 12));
    final data = _decode(response);
    final list = data['lines'] as List<dynamic>? ?? [];
    return list.map((item) => InventoryLineItem.fromJson(item as Map<String, dynamic>)).toList();
  }

  Future<InventorySummaryData> getInventorySessionSummary(int sessionId) async {
    final response = await http
        .get(uri('/api/inventory-sessions/$sessionId/summary'), headers: headers)
        .timeout(const Duration(seconds: 8));
    final data = _decode(response);
    final summaryMap = data['summary'] as Map<String, dynamic>? ?? {};
    return InventorySummaryData.fromJson(summaryMap);
  }

  Future<InventoryLineItem?> lookupInventoryLine(int sessionId, String barcode) async {
    final encoded = Uri.encodeQueryComponent(barcode.trim());
    final response = await http
        .get(uri('/api/inventory-sessions/$sessionId/lookup?barcode=$encoded'), headers: headers)
        .timeout(const Duration(seconds: 8));
    final data = _decode(response);
    final lineMap = data['line'] as Map<String, dynamic>?;
    return lineMap != null ? InventoryLineItem.fromJson(lineMap) : null;
  }

  Future<InventoryScanResultData> scanInventoryBarcode(
    int sessionId,
    String barcode, {
    double qty = 1.0,
    int? userId,
    bool replaceCounted = true,
  }) async {
    final response = await http
        .post(
          uri('/api/inventory-sessions/$sessionId/scan'),
          headers: headers,
          body: jsonEncode({
            'barcode': barcode.trim(),
            'qty': qty,
            if (userId != null) 'user_id': userId,
            'replace_counted': replaceCounted,
          }),
        )
        .timeout(const Duration(seconds: 10));
    final data = _decode(response);
    return InventoryScanResultData.fromJson(data);
  }

  Future<Map<String, dynamic>> bulkScanInventory(
    int sessionId,
    List<Map<String, dynamic>> scans, {
    int? userId,
    bool replaceCounted = false,
  }) async {
    final response = await http
        .post(
          uri('/api/inventory-sessions/$sessionId/bulk-scan'),
          headers: headers,
          body: jsonEncode({
            'scans': scans,
            if (userId != null) 'user_id': userId,
            'replace_counted': replaceCounted,
          }),
        )
        .timeout(const Duration(seconds: 20));
    return _decode(response);
  }

  Future<Map<String, dynamic>> updateInventoryLineQuantity(
    int sessionId,
    int lineId,
    double countedQty,
  ) async {
    final response = await http
        .put(
          uri('/api/inventory-sessions/$sessionId/lines/$lineId'),
          headers: headers,
          body: jsonEncode({
            'counted_qty': countedQty,
          }),
        )
        .timeout(const Duration(seconds: 8));
    return _decode(response);
  }

  Future<Map<String, dynamic>> markInventoryReview(int sessionId) async {
    final response = await http
        .post(uri('/api/inventory-sessions/$sessionId/review'), headers: headers)
        .timeout(const Duration(seconds: 8));
    return _decode(response);
  }

  Future<Map<String, dynamic>> applyInventorySession(
    int sessionId, {
    int? userId,
    bool allowUnknown = false,
    String uncountedAction = 'ignore',
  }) async {
    final response = await http
        .post(
          uri('/api/inventory-sessions/$sessionId/apply'),
          headers: headers,
          body: jsonEncode({
            if (userId != null) 'user_id': userId,
            'allow_unknown': allowUnknown,
            'uncounted_action': uncountedAction,
          }),
        )
        .timeout(const Duration(seconds: 15));
    return _decode(response);
  }

  Future<Map<String, dynamic>> cancelInventorySession(
    int sessionId, {
    int? userId,
  }) async {
    final response = await http
        .post(
          uri('/api/inventory-sessions/$sessionId/cancel'),
          headers: headers,
          body: jsonEncode({
            if (userId != null) 'user_id': userId,
          }),
        )
        .timeout(const Duration(seconds: 8));
    return _decode(response);
  }

  Future<Map<String, dynamic>> deleteInventorySession(int sessionId) async {
    final response = await http
        .delete(uri('/api/inventory-sessions/$sessionId'), headers: headers)
        .timeout(const Duration(seconds: 8));
    return _decode(response);
  }

  Map<String, dynamic> _decode(http.Response response) {
    final decoded =
        jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
    if (response.statusCode == 409) {
      // 409 Conflict represents a FEFO rule violation warning with full payload
      return decoded;
    }
    if (response.statusCode >= 400) {
      throw Exception(decoded['message'] ?? 'Erreur ${response.statusCode}');
    }
    return decoded;
  }
}
