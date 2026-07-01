import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:mobile_scanner/mobile_scanner.dart';
import 'package:http/http.dart' as http;

void main() {
  runApp(const StockLamInventoryScannerApp());
}

T? firstOrNull<T>(Iterable<T> values) {
  final iterator = values.iterator;
  return iterator.moveNext() ? iterator.current : null;
}

class StockLamInventoryScannerApp extends StatelessWidget {
  const StockLamInventoryScannerApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'StockLam Inventaire',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF007572)),
        useMaterial3: true,
        scaffoldBackgroundColor: const Color(0xFFF5F7F8),
      ),
      home: const ScannerHomePage(),
    );
  }
}

class InventorySession {
  const InventorySession({
    required this.id,
    required this.name,
    required this.status,
    required this.totalLines,
    required this.notCounted,
    required this.unknown,
  });

  final int id;
  final String name;
  final String status;
  final int totalLines;
  final int notCounted;
  final int unknown;

  factory InventorySession.fromJson(Map<String, dynamic> json) {
    int asInt(dynamic value) => int.tryParse('${value ?? 0}') ?? 0;
    return InventorySession(
      id: asInt(json['Session_ID']),
      name: '${json['Session_Name'] ?? 'Session'}',
      status: '${json['Status'] ?? '-'}',
      totalLines: asInt(json['Total_Lines']),
      notCounted: asInt(json['Not_Counted_Count']),
      unknown: asInt(json['Unknown_Count']),
    );
  }
}

class ApiClient {
  ApiClient({required this.baseUrl, this.token = ''});

  final String baseUrl;
  final String token;

  Map<String, String> get headers => {
        'Content-Type': 'application/json',
        if (token.trim().isNotEmpty) 'X-API-Key': token.trim(),
      };

  Uri uri(String path, [Map<String, String>? query]) {
    final root = baseUrl.trim().replaceAll(RegExp(r'/+$'), '');
    return Uri.parse('$root$path').replace(queryParameters: query);
  }

  Future<List<InventorySession>> sessions() async {
    final res = await http
        .get(
          uri('/api/inventory-sessions', {'status': 'Counting'}),
          headers: headers,
        )
        .timeout(const Duration(seconds: 8));
    final body = _decode(res);
    final items = (body['sessions'] as List? ?? const []);
    return items
        .map(
          (item) =>
              InventorySession.fromJson(Map<String, dynamic>.from(item as Map)),
        )
        .toList();
  }

  Future<Map<String, dynamic>?> lookup(int sessionId, String barcode) async {
    final res = await http
        .get(
          uri('/api/inventory-sessions/$sessionId/lookup', {
            'barcode': barcode,
          }),
          headers: headers,
        )
        .timeout(const Duration(seconds: 8));
    final body = _decode(res);
    return body['line'] == null
        ? null
        : Map<String, dynamic>.from(body['line'] as Map);
  }

  Future<Map<String, dynamic>> scan(
    int sessionId,
    String barcode,
    num qty,
  ) async {
    final res = await http
        .post(
          uri('/api/inventory-sessions/$sessionId/scan'),
          headers: headers,
          body: jsonEncode({
            'barcode': barcode,
            'qty': qty,
            'replace_counted': true,
          }),
        )
        .timeout(const Duration(seconds: 8));
    return _decode(res);
  }

  Map<String, dynamic> _decode(http.Response res) {
    final decoded =
        jsonDecode(utf8.decode(res.bodyBytes)) as Map<String, dynamic>;
    if (res.statusCode >= 400) {
      throw Exception(decoded['message'] ?? 'Erreur ${res.statusCode}');
    }
    return decoded;
  }
}

class ScannerHomePage extends StatefulWidget {
  const ScannerHomePage({super.key});

  @override
  State<ScannerHomePage> createState() => _ScannerHomePageState();
}

class _ScannerHomePageState extends State<ScannerHomePage> {
  final serverController = TextEditingController(
    text: 'http://192.168.1.10:8787',
  );
  final tokenController = TextEditingController();
  final barcodeController = TextEditingController();
  final qtyController = TextEditingController(text: '1');

  List<InventorySession> sessions = const [];
  InventorySession? selectedSession;
  Map<String, dynamic>? currentLine;
  String status = 'Configurez le serveur puis chargez les sessions.';
  bool loading = false;
  bool cameraOpen = false;
  bool scanBusy = false;

  ApiClient get api =>
      ApiClient(baseUrl: serverController.text, token: tokenController.text);

  @override
  void dispose() {
    serverController.dispose();
    tokenController.dispose();
    barcodeController.dispose();
    qtyController.dispose();
    super.dispose();
  }

  Future<void> loadSessions() async {
    setState(() {
      loading = true;
      status = 'Chargement des sessions...';
    });
    try {
      final data = await api.sessions();
      setState(() {
        sessions = data;
        selectedSession = data.isEmpty
            ? null
            : (selectedSession == null
                ? data.first
                : data.firstWhere(
                    (s) => s.id == selectedSession!.id,
                    orElse: () => data.first,
                  ));
        status = data.isEmpty
            ? 'Aucune session Counting ouverte.'
            : '${data.length} session(s) disponible(s).';
      });
    } catch (e) {
      setState(() => status = 'Erreur connexion: $e');
    } finally {
      setState(() => loading = false);
    }
  }

  Future<void> lookupBarcode([String? value]) async {
    final session = selectedSession;
    final barcode = (value ?? barcodeController.text).trim();
    if (session == null || barcode.isEmpty) return;
    setState(() {
      loading = true;
      status = 'Recherche du code...';
    });
    try {
      final line = await api.lookup(session.id, barcode);
      setState(() {
        currentLine = line;
        if (line == null) {
          status =
              'Code inconnu. Vous pouvez entrer une quantite pour le signaler.';
          qtyController.text = '1';
        } else {
          status = '${line['Product_Name'] ?? barcode} trouve.';
          final lineStatus = '${line['Line_Status'] ?? ''}';
          qtyController.text = lineStatus == 'NOT_COUNTED'
              ? '${line['Program_Qty_Snapshot'] ?? 1}'
              : '${line['Counted_Qty'] ?? 1}';
        }
      });
    } catch (e) {
      setState(() => status = 'Erreur recherche: $e');
    } finally {
      setState(() => loading = false);
    }
  }

  Future<void> saveScan() async {
    final session = selectedSession;
    final barcode = barcodeController.text.trim();
    final qty = num.tryParse(qtyController.text.replaceAll(',', '.'));
    if (session == null || barcode.isEmpty || qty == null || qty < 0) {
      setState(
        () => status =
            'Session, code-barres et quantite valide sont obligatoires.',
      );
      return;
    }
    setState(() {
      loading = true;
      status = 'Enregistrement...';
    });
    try {
      final result = await api.scan(session.id, barcode, qty);
      setState(() {
        currentLine = result['line'] == null
            ? null
            : Map<String, dynamic>.from(result['line'] as Map);
        status = '${result['status'] ?? 'OK'} - ${result['message'] ?? ''}';
        barcodeController.clear();
        qtyController.text = '1';
      });
      await loadSessions();
    } catch (e) {
      setState(() => status = 'Erreur scan: $e');
    } finally {
      setState(() => loading = false);
    }
  }

  void onCameraCode(String code) {
    if (scanBusy || code.trim().isEmpty) return;
    scanBusy = true;
    setState(() {
      cameraOpen = false;
      barcodeController.text = code.trim();
    });
    lookupBarcode(code.trim()).whenComplete(() {
      Timer(const Duration(milliseconds: 700), () => scanBusy = false);
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Inventaire mobile')),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            _serverCard(),
            const SizedBox(height: 12),
            _sessionCard(),
            const SizedBox(height: 12),
            if (cameraOpen) _cameraCard(),
            if (cameraOpen) const SizedBox(height: 12),
            _scanCard(),
            const SizedBox(height: 12),
            _detailsCard(),
          ],
        ),
      ),
    );
  }

  Widget _serverCard() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          children: [
            TextField(
              controller: serverController,
              decoration: const InputDecoration(
                labelText: 'Serveur API',
                prefixIcon: Icon(Icons.lan),
              ),
            ),
            TextField(
              controller: tokenController,
              decoration: const InputDecoration(
                labelText: 'Token optionnel',
                prefixIcon: Icon(Icons.key),
              ),
              obscureText: true,
            ),
            const SizedBox(height: 10),
            FilledButton.icon(
              onPressed: loading ? null : loadSessions,
              icon: const Icon(Icons.refresh),
              label: const Text('Charger sessions'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _sessionCard() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            DropdownButtonFormField<int>(
              initialValue: selectedSession?.id,
              decoration: const InputDecoration(
                labelText: 'Session Inventaire',
              ),
              items: sessions
                  .map(
                    (s) => DropdownMenuItem(
                      value: s.id,
                      child: Text('#${s.id} ${s.name}'),
                    ),
                  )
                  .toList(),
              onChanged: (id) => setState(
                () => selectedSession = firstOrNull(
                  sessions.where((s) => s.id == id),
                ),
              ),
            ),
            const SizedBox(height: 8),
            if (selectedSession != null)
              Text(
                'Statut: ${selectedSession!.status} | Lignes: ${selectedSession!.totalLines} | Non comptes: ${selectedSession!.notCounted} | Inconnus: ${selectedSession!.unknown}',
              ),
            const SizedBox(height: 8),
            Text(
              status,
              style: TextStyle(
                color: status.startsWith('Erreur')
                    ? Colors.red
                    : const Color(0xFF23423F),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _cameraCard() {
    return SizedBox(
      height: 280,
      child: ClipRRect(
        borderRadius: BorderRadius.circular(8),
        child: MobileScanner(
          onDetect: (capture) {
            final code = firstOrNull(capture.barcodes)?.rawValue;
            if (code != null) onCameraCode(code);
          },
        ),
      ),
    );
  }

  Widget _scanCard() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          children: [
            Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: barcodeController,
                    decoration: const InputDecoration(
                      labelText: 'Code-barres',
                      prefixIcon: Icon(Icons.qr_code_2),
                    ),
                    textInputAction: TextInputAction.search,
                    onSubmitted: (_) => lookupBarcode(),
                  ),
                ),
                IconButton.filledTonal(
                  onPressed: () => setState(() => cameraOpen = !cameraOpen),
                  icon: Icon(cameraOpen ? Icons.close : Icons.camera_alt),
                ),
              ],
            ),
            const SizedBox(height: 10),
            TextField(
              controller: qtyController,
              keyboardType: const TextInputType.numberWithOptions(
                decimal: true,
              ),
              decoration: const InputDecoration(
                labelText: 'Quantite physique',
                prefixIcon: Icon(Icons.numbers),
              ),
              onSubmitted: (_) => saveScan(),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: loading ? null : () => lookupBarcode(),
                    icon: const Icon(Icons.search),
                    label: const Text('Verifier'),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: FilledButton.icon(
                    onPressed: loading ? null : saveScan,
                    icon: const Icon(Icons.save),
                    label: const Text('Enregistrer'),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _detailsCard() {
    final line = currentLine;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text(
              'Produit scanne',
              style: TextStyle(fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            if (line == null)
              const Text('Aucun produit charge.')
            else ...[
              Text(
                '${line['Product_Name'] ?? line['Internal_Barcode'] ?? '-'}',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              Text('Barcode: ${line['Internal_Barcode'] ?? '-'}'),
              Text(
                'Lot: ${line['Lot_Number'] ?? '-'} | Exp: ${line['Expiry_Date'] ?? '-'}',
              ),
              Text('Emplacement: ${line['Location_Name'] ?? '-'}'),
              Text(
                'Programme: ${line['Program_Qty_Snapshot'] ?? 0} | Compte: ${line['Counted_Qty'] ?? 0} | Ecart: ${line['Difference_Qty'] ?? 0}',
              ),
              Text('Statut: ${line['Line_Status'] ?? '-'}'),
            ],
          ],
        ),
      ),
    );
  }
}
