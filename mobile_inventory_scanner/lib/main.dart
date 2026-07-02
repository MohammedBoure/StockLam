import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:http/http.dart' as http;
import 'package:mobile_scanner/mobile_scanner.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  runApp(const StockLamInventoryScannerApp());
}

T? firstOrNull<T>(Iterable<T> values) {
  final iterator = values.iterator;
  return iterator.moveNext() ? iterator.current : null;
}

const stockLamMobileApiKey = 'StockLam-Inventaire-Mobile-2026';

String cleanBaseUrl(String value) =>
    value.trim().replaceAll(RegExp(r'/+$'), '');

int asInt(dynamic value) => int.tryParse('${value ?? 0}') ?? 0;

num asNumber(dynamic value) {
  if (value is num) {
    return value;
  }
  return num.tryParse('${value ?? 0}'.replaceAll(',', '.')) ?? 0;
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
        inputDecorationTheme:
            const InputDecorationTheme(border: OutlineInputBorder()),
        cardTheme: const CardThemeData(
          elevation: 0,
          margin: EdgeInsets.zero,
          shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.all(Radius.circular(8))),
        ),
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
    required this.ok,
    required this.short,
    required this.excess,
    required this.notCounted,
    required this.unknown,
  });

  final int id;
  final String name;
  final String status;
  final int totalLines;
  final int ok;
  final int short;
  final int excess;
  final int notCounted;
  final int unknown;

  int get counted => ok + short + excess + unknown;
  double get progress => totalLines <= 0 ? 0 : counted / totalLines;

  factory InventorySession.fromJson(Map<String, dynamic> json) {
    return InventorySession(
      id: asInt(json['Session_ID']),
      name: '${json['Session_Name'] ?? 'Session'}',
      status: '${json['Status'] ?? '-'}',
      totalLines: asInt(json['Total_Lines']),
      ok: asInt(json['OK_Count']),
      short: asInt(json['Short_Count']),
      excess: asInt(json['Excess_Count']),
      notCounted: asInt(json['Not_Counted_Count']),
      unknown: asInt(json['Unknown_Count']),
    );
  }
}

class ScanEntry {
  const ScanEntry({
    required this.barcode,
    required this.qty,
    required this.status,
    required this.message,
    required this.time,
  });

  final String barcode;
  final num qty;
  final String status;
  final String message;
  final DateTime time;
}

class ApiClient {
  ApiClient({required this.baseUrl});

  final String baseUrl;

  Map<String, String> get headers => {
        'Content-Type': 'application/json',
        'X-API-Key': stockLamMobileApiKey,
      };

  Uri uri(String path, [Map<String, String>? query]) {
    return Uri.parse('${cleanBaseUrl(baseUrl)}$path')
        .replace(queryParameters: query);
  }

  Future<Map<String, dynamic>> health() async {
    final res = await http
        .get(uri('/api/health'), headers: headers)
        .timeout(const Duration(seconds: 8));
    return _decode(res);
  }

  Future<List<InventorySession>> sessions() async {
    final res = await http
        .get(uri('/api/inventory-sessions', {'status': 'Counting'}),
            headers: headers)
        .timeout(const Duration(seconds: 10));
    final body = _decode(res);
    final items = body['sessions'] as List? ?? const [];
    return items
        .map((item) =>
            InventorySession.fromJson(Map<String, dynamic>.from(item as Map)))
        .toList();
  }

  Future<Map<String, dynamic>?> lookup(int sessionId, String barcode) async {
    final res = await http
        .get(
            uri('/api/inventory-sessions/$sessionId/lookup',
                {'barcode': barcode}),
            headers: headers)
        .timeout(const Duration(seconds: 8));
    final body = _decode(res);
    return body['line'] == null
        ? null
        : Map<String, dynamic>.from(body['line'] as Map);
  }

  Future<Map<String, dynamic>> scan(
      int sessionId, String barcode, num qty) async {
    final res = await http
        .post(
          uri('/api/inventory-sessions/$sessionId/scan'),
          headers: headers,
          body: jsonEncode(
              {'barcode': barcode, 'qty': qty, 'replace_counted': true}),
        )
        .timeout(const Duration(seconds: 10));
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
  static const serverKey = 'stocklam_server_url';
  final serverController =
      TextEditingController(text: 'http://192.168.1.10:8787');
  final barcodeController = TextEditingController();
  final qtyController = TextEditingController(text: '1');
  final barcodeFocus = FocusNode();
  final qtyFocus = FocusNode();

  List<InventorySession> sessions = const [];
  List<ScanEntry> recentScans = const [];
  InventorySession? selectedSession;
  Map<String, dynamic>? currentLine;
  String status = 'Configurez le serveur puis chargez les sessions.';
  bool loading = false;
  bool settingsOpen = true;
  bool cameraOpen = false;
  bool scanBusy = false;

  ApiClient get api => ApiClient(baseUrl: serverController.text);

  @override
  void initState() {
    super.initState();
    unawaited(_loadSettings());
  }

  @override
  void dispose() {
    serverController.dispose();
    barcodeController.dispose();
    qtyController.dispose();
    barcodeFocus.dispose();
    qtyFocus.dispose();
    super.dispose();
  }

  Future<void> _loadSettings() async {
    final prefs = await SharedPreferences.getInstance();
    final savedServer = prefs.getString(serverKey);
    if (!mounted) {
      return;
    }
    setState(() {
      if (savedServer != null && savedServer.isNotEmpty) {
        serverController.text = savedServer;
      }
    });
  }

  Future<void> _saveSettings() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(serverKey, cleanBaseUrl(serverController.text));
  }

  Future<void> checkServer() async {
    await _saveSettings();
    setState(() {
      loading = true;
      status = 'Test de connexion...';
    });
    try {
      await api.health();
      setState(() => status = 'Serveur connecte.');
      await loadSessions();
    } catch (e) {
      setState(() => status = 'Connexion impossible: $e');
    } finally {
      if (mounted) {
        setState(() => loading = false);
      }
    }
  }

  Future<void> loadSessions() async {
    await _saveSettings();
    setState(() {
      loading = true;
      status = 'Chargement des sessions ouvertes...';
    });
    try {
      final data = await api.sessions();
      final selected = selectedSession == null
          ? null
          : firstOrNull(data.where((s) => s.id == selectedSession!.id));
      setState(() {
        sessions = data;
        selectedSession = selected ?? (data.isEmpty ? null : data.first);
        settingsOpen = data.isEmpty;
        status = data.isEmpty
            ? 'Aucune session Counting ouverte dans StockLam.'
            : '${data.length} session(s) ouverte(s).';
      });
    } catch (e) {
      setState(() => status = 'Erreur sessions: $e');
    } finally {
      if (mounted) {
        setState(() => loading = false);
      }
    }
  }

  Future<void> lookupBarcode([String? value]) async {
    final session = selectedSession;
    final barcode = (value ?? barcodeController.text).trim();
    if (session == null) {
      setState(() => status = 'Selectionnez une session Inventaire ouverte.');
      return;
    }
    if (barcode.isEmpty) {
      barcodeFocus.requestFocus();
      return;
    }
    setState(() {
      loading = true;
      status = 'Recherche du code...';
    });
    try {
      final line = await api.lookup(session.id, barcode);
      if (!mounted) {
        return;
      }
      setState(() {
        currentLine = line;
        if (line == null) {
          status = 'Code inconnu. Enregistrer le comptera comme UNKNOWN.';
          qtyController.text = '1';
        } else {
          status =
              '${line['Product_Name'] ?? barcode} trouve. Entrez la quantite physique.';
          final lineStatus = '${line['Line_Status'] ?? ''}';
          final defaultQty = lineStatus == 'NOT_COUNTED'
              ? line['Program_Qty_Snapshot']
              : line['Counted_Qty'];
          qtyController.text = '${defaultQty ?? 1}';
        }
      });
      qtyFocus.requestFocus();
      qtyController.selection =
          TextSelection(baseOffset: 0, extentOffset: qtyController.text.length);
    } catch (e) {
      setState(() => status = 'Erreur recherche: $e');
    } finally {
      if (mounted) {
        setState(() => loading = false);
      }
    }
  }

  Future<void> saveScan() async {
    final session = selectedSession;
    final barcode = barcodeController.text.trim();
    final qty = num.tryParse(qtyController.text.replaceAll(',', '.'));
    if (session == null) {
      setState(() => status = 'Selectionnez une session Inventaire ouverte.');
      return;
    }
    if (barcode.isEmpty || qty == null || qty < 0) {
      setState(() => status = 'Code-barres et quantite valide obligatoires.');
      return;
    }
    setState(() {
      loading = true;
      status = 'Enregistrement du comptage...';
    });
    try {
      final result = await api.scan(session.id, barcode, qty);
      final entry = ScanEntry(
        barcode: barcode,
        qty: qty,
        status: '${result['status'] ?? 'OK'}',
        message: '${result['message'] ?? ''}',
        time: DateTime.now(),
      );
      if (!mounted) {
        return;
      }
      HapticFeedback.mediumImpact();
      setState(() {
        currentLine = result['line'] == null
            ? null
            : Map<String, dynamic>.from(result['line'] as Map);
        status = '${entry.status} - ${entry.message}';
        recentScans = [entry, ...recentScans].take(12).toList();
        barcodeController.clear();
        qtyController.text = '1';
      });
      await loadSessions();
      barcodeFocus.requestFocus();
    } catch (e) {
      setState(() => status = 'Erreur enregistrement: $e');
    } finally {
      if (mounted) {
        setState(() => loading = false);
      }
    }
  }

  void onCameraCode(String code) {
    if (scanBusy || code.trim().isEmpty) return;
    scanBusy = true;
    final clean = code.trim();
    setState(() {
      cameraOpen = false;
      barcodeController.text = clean;
    });
    lookupBarcode(clean).whenComplete(() {
      Timer(const Duration(milliseconds: 700), () => scanBusy = false);
    });
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Scaffold(
      backgroundColor: const Color(0xFFF5F7F8),
      appBar: AppBar(
        title: const Text('StockLam Inventaire'),
        actions: [
          IconButton(
            tooltip: 'Parametres serveur',
            onPressed: () => setState(() => settingsOpen = !settingsOpen),
            icon: Icon(settingsOpen ? Icons.expand_less : Icons.settings),
          ),
          IconButton(
            tooltip: 'Actualiser sessions',
            onPressed: loading ? null : loadSessions,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: SafeArea(
        child: Stack(
          children: [
            ListView(
              padding: const EdgeInsets.all(12),
              children: [
                if (settingsOpen) _serverCard(),
                if (settingsOpen) const SizedBox(height: 10),
                _sessionCard(),
                const SizedBox(height: 10),
                if (cameraOpen) _cameraCard(),
                if (cameraOpen) const SizedBox(height: 10),
                _scanCard(),
                const SizedBox(height: 10),
                _detailsCard(),
                const SizedBox(height: 10),
                _recentCard(),
                const SizedBox(height: 28),
              ],
            ),
            if (loading)
              Positioned(
                left: 0,
                right: 0,
                top: 0,
                child: LinearProgressIndicator(color: scheme.primary),
              ),
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
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            TextField(
              controller: serverController,
              decoration: const InputDecoration(
                  labelText: 'Serveur API', prefixIcon: Icon(Icons.lan)),
              keyboardType: TextInputType.url,
              textInputAction: TextInputAction.next,
            ),
            const SizedBox(height: 10),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: loading ? null : checkServer,
                    icon: const Icon(Icons.wifi_tethering),
                    label: const Text('Tester'),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: FilledButton.icon(
                    onPressed: loading ? null : loadSessions,
                    icon: const Icon(Icons.inventory_2),
                    label: const Text('Sessions'),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _sessionCard() {
    final session = selectedSession;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            InputDecorator(
              decoration:
                  const InputDecoration(labelText: 'Session Inventaire'),
              child: DropdownButtonHideUnderline(
                child: DropdownButton<int>(
                  value: session?.id,
                  isExpanded: true,
                  hint: const Text('Aucune session ouverte'),
                  items: sessions
                      .map((s) => DropdownMenuItem(
                          value: s.id, child: Text('#${s.id} ${s.name}')))
                      .toList(),
                  onChanged: (id) => setState(() => selectedSession =
                      firstOrNull(sessions.where((s) => s.id == id))),
                ),
              ),
            ),
            const SizedBox(height: 10),
            if (session != null) ...[
              Row(
                children: [
                  Expanded(child: Text('Statut: ${session.status}')),
                  Text('${session.counted}/${session.totalLines}'),
                ],
              ),
              const SizedBox(height: 6),
              LinearProgressIndicator(
                  value: session.progress.clamp(0, 1), minHeight: 8),
              const SizedBox(height: 6),
              Text(
                  'OK ${session.ok} | Short ${session.short} | Excess ${session.excess} | Non comptes ${session.notCounted} | Inconnus ${session.unknown}'),
            ],
            const SizedBox(height: 8),
            Text(status,
                style: TextStyle(
                    color: status.startsWith('Erreur') ||
                            status.startsWith('Connexion impossible')
                        ? Colors.red
                        : const Color(0xFF23423F))),
          ],
        ),
      ),
    );
  }

  Widget _cameraCard() {
    return SizedBox(
      height: 300,
      child: ClipRRect(
        borderRadius: BorderRadius.circular(8),
        child: Stack(
          children: [
            MobileScanner(
              onDetect: (capture) {
                final code = firstOrNull(capture.barcodes)?.rawValue;
                if (code != null) {
                  onCameraCode(code);
                }
              },
            ),
            Positioned(
              top: 8,
              right: 8,
              child: IconButton.filled(
                onPressed: () => setState(() => cameraOpen = false),
                icon: const Icon(Icons.close),
              ),
            ),
          ],
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
                    focusNode: barcodeFocus,
                    decoration: const InputDecoration(
                        labelText: 'Code-barres',
                        prefixIcon: Icon(Icons.qr_code_2)),
                    textInputAction: TextInputAction.search,
                    onSubmitted: (_) => lookupBarcode(),
                  ),
                ),
                const SizedBox(width: 8),
                SizedBox(
                  height: 56,
                  width: 56,
                  child: IconButton.filledTonal(
                    onPressed: () => setState(() => cameraOpen = !cameraOpen),
                    icon: Icon(cameraOpen ? Icons.close : Icons.camera_alt),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            TextField(
              controller: qtyController,
              focusNode: qtyFocus,
              keyboardType:
                  const TextInputType.numberWithOptions(decimal: true),
              decoration: const InputDecoration(
                  labelText: 'Quantite physique',
                  prefixIcon: Icon(Icons.numbers)),
              textInputAction: TextInputAction.done,
              onSubmitted: (_) => saveScan(),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                    child: OutlinedButton.icon(
                        onPressed: loading ? null : () => lookupBarcode(),
                        icon: const Icon(Icons.search),
                        label: const Text('Verifier'))),
                const SizedBox(width: 10),
                Expanded(
                    child: FilledButton.icon(
                        onPressed: loading ? null : saveScan,
                        icon: const Icon(Icons.save),
                        label: const Text('Enregistrer'))),
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
            Row(
              children: [
                const Expanded(
                    child: Text('Produit scanne',
                        style: TextStyle(fontWeight: FontWeight.bold))),
                if (line != null) _statusChip('${line['Line_Status'] ?? '-'}'),
              ],
            ),
            const SizedBox(height: 8),
            if (line == null)
              const Text('Aucun produit charge.')
            else ...[
              Text('${line['Product_Name'] ?? line['Internal_Barcode'] ?? '-'}',
                  style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 4),
              Text('Barcode: ${line['Internal_Barcode'] ?? '-'}'),
              Text(
                  'Lot: ${line['Lot_Number'] ?? '-'} | Exp: ${line['Expiry_Date'] ?? '-'}'),
              Text('Emplacement: ${line['Location_Name'] ?? '-'}'),
              Text(
                  'Programme: ${line['Program_Qty_Snapshot'] ?? 0} | Compte: ${line['Counted_Qty'] ?? 0} | Ecart: ${line['Difference_Qty'] ?? 0}'),
            ],
          ],
        ),
      ),
    );
  }

  Widget _recentCard() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text('Derniers scans',
                style: TextStyle(fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            if (recentScans.isEmpty)
              const Text('Aucun scan enregistre dans cette session mobile.')
            else
              ...recentScans.map(
                (scan) => ListTile(
                  dense: true,
                  contentPadding: EdgeInsets.zero,
                  title: Text(scan.barcode),
                  subtitle: Text(
                      '${scan.time.hour.toString().padLeft(2, '0')}:${scan.time.minute.toString().padLeft(2, '0')} | Qty ${scan.qty} | ${scan.message}'),
                  trailing: _statusChip(scan.status),
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _statusChip(String status) {
    final normalized = status.toUpperCase();
    final color = switch (normalized) {
      'MATCHED' || 'OK' => Colors.green,
      'UNKNOWN' => Colors.orange,
      'SHORT' => Colors.redAccent,
      'EXCESS' => Colors.blue,
      _ => Colors.blueGrey,
    };
    return Chip(
      label: Text(status,
          style: const TextStyle(color: Colors.white, fontSize: 12)),
      backgroundColor: color,
      visualDensity: VisualDensity.compact,
      padding: EdgeInsets.zero,
    );
  }
}
