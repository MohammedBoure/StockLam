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

  Future<Map<String, dynamic>> sendRemoteBarcode(String barcode) async {
    final response = await http
        .post(
          uri('/api/remote-scans'),
          headers: headers,
          body: jsonEncode({'barcode': barcode}),
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
  }) async {
    final response = await http
        .post(
          uri('/api/stock/transfer'),
          headers: headers,
          body: jsonEncode({
            'batch_id': batchId,
            'target_location_id': targetLocationId,
            'qty': qty,
          }),
        )
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
