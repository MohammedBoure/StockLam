import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:http/http.dart' as http;
import 'package:mobile_scanner/mobile_scanner.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  runApp(const ModernStockApp());
}

T? firstOrNull<T>(Iterable<T> values) {
  final iterator = values.iterator;
  return iterator.moveNext() ? iterator.current : null;
}

const stockLamMobileApiKey = 'StockLam-Inventaire-Mobile-2026';

String cleanBaseUrl(String value) =>
    value.trim().replaceAll(RegExp(r'/+$'), '');

class ModernStockApp extends StatelessWidget {
  const ModernStockApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'ModernStock',
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
            borderRadius: BorderRadius.all(Radius.circular(8)),
          ),
        ),
      ),
      home: const ScannerHomePage(),
    );
  }
}

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

  Map<String, dynamic> _decode(http.Response response) {
    final decoded =
        jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
    if (response.statusCode >= 400) {
      throw Exception(decoded['message'] ?? 'Erreur ${response.statusCode}');
    }
    return decoded;
  }
}

class ScannerHomePage extends StatefulWidget {
  const ScannerHomePage({super.key});

  @override
  State<ScannerHomePage> createState() => _ScannerHomePageState();
}

class _ScannerHomePageState extends State<ScannerHomePage>
    with WidgetsBindingObserver {
  static const serverKey = 'modernstock_server_url';

  final serverController = TextEditingController();
  final barcodeController = TextEditingController();
  final barcodeFocus = FocusNode();
  final cameraController = MobileScannerController(
    autoStart: false,
    facing: CameraFacing.back,
    detectionSpeed: DetectionSpeed.normal,
    detectionTimeoutMs: 400,
  );

  List<DesktopDevice> discoveredDevices = const [];
  List<ScanEntry> recentScans = const [];
  DesktopDevice? selectedDevice;
  CameraFacing cameraFacing = CameraFacing.back;
  String status = 'Recherchez puis choisissez un ordinateur ModernStock.';
  bool loading = false;
  bool discovering = false;
  bool connected = false;
  bool settingsOpen = true;
  bool cameraOpen = false;
  bool scanBusy = false;
  bool cameraStarting = false;

  ApiClient get api => ApiClient(baseUrl: serverController.text);

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    unawaited(_loadSettings());
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    unawaited(cameraController.dispose());
    serverController.dispose();
    barcodeController.dispose();
    barcodeFocus.dispose();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (!cameraOpen || !cameraController.value.isInitialized) return;

    switch (state) {
      case AppLifecycleState.detached:
      case AppLifecycleState.hidden:
      case AppLifecycleState.paused:
      case AppLifecycleState.inactive:
        unawaited(cameraController.stop());
      case AppLifecycleState.resumed:
        unawaited(_startCamera());
    }
  }

  Future<void> _loadSettings() async {
    final preferences = await SharedPreferences.getInstance();
    final savedServer = preferences.getString(serverKey);
    if (!mounted || savedServer == null || savedServer.isEmpty) return;
    setState(() => serverController.text = savedServer);
  }

  Future<void> _saveSettings() async {
    final preferences = await SharedPreferences.getInstance();
    await preferences.setString(
      serverKey,
      cleanBaseUrl(serverController.text),
    );
  }

  Future<void> discoverDevices() async {
    if (discovering) return;
    setState(() {
      discovering = true;
      status = 'Recherche des ordinateurs ModernStock sur le réseau...';
    });

    RawDatagramSocket? socket;
    StreamSubscription<RawSocketEvent>? subscription;
    final found = <String, DesktopDevice>{};
    try {
      socket = await RawDatagramSocket.bind(InternetAddress.anyIPv4, 0);
      socket.broadcastEnabled = true;
      subscription = socket.listen((event) {
        if (event != RawSocketEvent.read) return;
        Datagram? datagram;
        while ((datagram = socket?.receive()) != null) {
          try {
            final data =
                jsonDecode(utf8.decode(datagram!.data)) as Map<String, dynamic>;
            if (data['app'] != 'StockLam') continue;
            final address = datagram.address.address;
            final port = int.tryParse('${data['api_port'] ?? 8787}') ?? 8787;
            final id = '${data['device_id'] ?? '$address:$port'}';
            found[id] = DesktopDevice(
              name: '${data['device_name'] ?? address}',
              id: id,
              baseUrl: 'http://$address:$port',
            );
            if (mounted) {
              setState(() {
                discoveredDevices = _sortedDevices(found.values);
              });
            }
          } catch (_) {
            // Ignore packets that are not ModernStock discovery replies.
          }
        }
      });

      final destinations = <String>{'255.255.255.255'};
      final interfaces = await NetworkInterface.list(
        type: InternetAddressType.IPv4,
        includeLoopback: false,
      );
      for (final networkInterface in interfaces) {
        for (final address in networkInterface.addresses) {
          final parts = address.address.split('.');
          if (parts.length == 4) {
            destinations.add('${parts[0]}.${parts[1]}.${parts[2]}.255');
          }
        }
      }

      final request = utf8.encode('STOCKLAM_DISCOVER_V1');
      for (final destination in destinations) {
        socket.send(request, InternetAddress(destination), 8788);
      }
      await Future<void>.delayed(const Duration(milliseconds: 2200));

      if (!mounted) return;
      setState(() {
        discoveredDevices = _sortedDevices(found.values);
        status = found.isEmpty
            ? 'Aucun ordinateur trouvé. Vérifiez le Wi-Fi et le pare-feu Windows.'
            : '${found.length} ordinateur(s) ModernStock trouvé(s).';
      });
    } catch (error) {
      if (mounted) setState(() => status = 'Erreur de découverte : $error');
    } finally {
      await subscription?.cancel();
      socket?.close();
      if (mounted) setState(() => discovering = false);
    }
  }

  List<DesktopDevice> _sortedDevices(Iterable<DesktopDevice> devices) {
    final result = devices.toList();
    result.sort((a, b) => a.name.compareTo(b.name));
    return result;
  }

  Future<void> connectDevice(DesktopDevice device) async {
    setState(() {
      selectedDevice = device;
      serverController.text = device.baseUrl;
      connected = false;
    });
    await checkServer();
  }

  Future<void> checkServer() async {
    final baseUrl = cleanBaseUrl(serverController.text);
    if (baseUrl.isEmpty) {
      setState(
          () => status = 'Choisissez un ordinateur ou saisissez son adresse.');
      return;
    }
    await _saveSettings();
    setState(() {
      loading = true;
      status = 'Test de connexion à ModernStock...';
    });
    try {
      final health = await api.health();
      if (health['remote_input'] != true) {
        throw Exception(
            'Ce serveur n’est pas une instance ModernStock active.');
      }
      final device = DesktopDevice(
        name: '${health['device_name'] ?? Uri.parse(baseUrl).host}',
        id: '${health['device_id'] ?? baseUrl}',
        baseUrl: baseUrl,
      );
      if (!mounted) return;
      setState(() {
        connected = true;
        selectedDevice = device;
        settingsOpen = false;
        status = 'Connecté à ${device.name}.';
      });
    } catch (error) {
      if (mounted) {
        setState(() {
          connected = false;
          status = 'Connexion impossible : $error';
        });
      }
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  Future<void> sendRemoteBarcode([String? value]) async {
    final barcode = (value ?? barcodeController.text).trim();
    if (!connected) {
      setState(() => status = 'Connectez d’abord un ordinateur ModernStock.');
      return;
    }
    if (barcode.isEmpty) {
      barcodeFocus.requestFocus();
      return;
    }
    setState(() {
      loading = true;
      status = 'Envoi du code vers ${selectedDevice?.name ?? 'ordinateur'}...';
    });
    try {
      await api.sendRemoteBarcode(barcode);
      if (!mounted) return;
      HapticFeedback.mediumImpact();
      setState(() {
        status = 'Code $barcode envoyé à ModernStock.';
        recentScans = [
          ScanEntry(
            barcode: barcode,
            message: 'Envoyé à ${selectedDevice?.name ?? 'ModernStock'}',
            time: DateTime.now(),
          ),
          ...recentScans,
        ].take(12).toList();
        barcodeController.clear();
      });
      barcodeFocus.requestFocus();
    } catch (error) {
      if (mounted) setState(() => status = 'Erreur d’envoi : $error');
    } finally {
      if (mounted) setState(() => loading = false);
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
    unawaited(_completeCameraScan(clean));
  }

  Future<void> _completeCameraScan(String barcode) async {
    try {
      await cameraController.stop();
      await sendRemoteBarcode(barcode);
    } finally {
      Timer(const Duration(milliseconds: 700), () => scanBusy = false);
    }
  }

  String _cameraErrorMessage(MobileScannerException error) {
    final details = error.errorDetails;
    final technicalDetails = [details?.message, details?.code]
        .whereType<String>()
        .where((value) => value.trim().isNotEmpty)
        .join(' - ');
    final reason =
        technicalDetails.isEmpty ? error.errorCode.name : technicalDetails;
    return 'Impossible d\'ouvrir cette caméra.\n$reason\n\n'
        'Autorisez l\'accès à la caméra et fermez les autres applications qui '
        'l\'utilisent.';
  }

  Future<void> _startCamera() async {
    if (!mounted || !cameraOpen || cameraStarting) return;
    cameraStarting = true;
    try {
      await cameraController.start(cameraDirection: cameraFacing);
      if (!mounted) return;
      if (!cameraOpen) {
        await cameraController.stop();
        return;
      }
      final error = cameraController.value.error;
      setState(() {
        status = error == null
            ? cameraFacing == CameraFacing.back
                ? 'Caméra arrière active.'
                : 'Caméra avant active.'
            : _cameraErrorMessage(error);
      });
    } catch (error) {
      if (mounted) {
        setState(() => status = 'Erreur de caméra : $error');
      }
    } finally {
      cameraStarting = false;
      if (mounted) setState(() {});
    }
  }

  Future<void> _retryCamera() async {
    if (!cameraOpen || cameraStarting) return;
    await cameraController.stop();
    await _startCamera();
  }

  Future<void> toggleCamera() async {
    if (!cameraOpen || cameraStarting) return;
    try {
      await cameraController.switchCamera();
      if (!mounted) return;
      final actualFacing = cameraController.value.cameraDirection;
      final error = cameraController.value.error;
      setState(() {
        cameraFacing = actualFacing;
        status = error == null
            ? actualFacing == CameraFacing.back
                ? 'Caméra arrière active.'
                : 'Caméra avant active.'
            : _cameraErrorMessage(error);
      });
    } catch (error) {
      if (mounted) {
        setState(() => status = 'Impossible de changer de caméra : $error');
      }
    }
  }

  Future<void> toggleCameraPanel() async {
    if (cameraOpen) {
      setState(() => cameraOpen = false);
      await cameraController.stop();
      return;
    }

    setState(() {
      cameraOpen = true;
      status = 'Ouverture de la caméra...';
    });
    await WidgetsBinding.instance.endOfFrame;
    if (mounted && cameraOpen) await _startCamera();
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Scaffold(
      backgroundColor: const Color(0xFFF5F7F8),
      appBar: AppBar(
        title: const Text('ModernStock'),
        actions: [
          IconButton(
            tooltip: 'Ordinateurs ModernStock',
            onPressed: () => setState(() => settingsOpen = !settingsOpen),
            icon: Icon(settingsOpen ? Icons.expand_less : Icons.settings),
          ),
          IconButton(
            tooltip: 'Rechercher les ordinateurs',
            onPressed: loading || discovering ? null : discoverDevices,
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
                _connectionCard(),
                const SizedBox(height: 10),
                if (cameraOpen) _cameraCard(),
                if (cameraOpen) const SizedBox(height: 10),
                _scanCard(),
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
            FilledButton.icon(
              onPressed: discovering ? null : discoverDevices,
              icon: discovering
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.radar),
              label: Text(discovering
                  ? 'Recherche en cours...'
                  : 'Rechercher les ordinateurs ModernStock'),
            ),
            if (discoveredDevices.isNotEmpty) ...[
              const SizedBox(height: 10),
              const Text(
                'Ordinateurs disponibles',
                style: TextStyle(fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 4),
              RadioGroup<String>(
                groupValue: selectedDevice?.id,
                onChanged: (id) {
                  if (loading) return;
                  final device = firstOrNull(
                      discoveredDevices.where((item) => item.id == id));
                  if (device != null) connectDevice(device);
                },
                child: Column(
                  children: discoveredDevices
                      .map(
                        (device) => RadioListTile<String>(
                          value: device.id,
                          title: Text(device.name),
                          subtitle: Text(device.baseUrl),
                          secondary: const Icon(Icons.computer),
                        ),
                      )
                      .toList(),
                ),
              ),
            ],
            const Divider(height: 24),
            TextField(
              controller: serverController,
              decoration: const InputDecoration(
                labelText: 'Adresse manuelle',
                prefixIcon: Icon(Icons.lan),
              ),
              keyboardType: TextInputType.url,
              textInputAction: TextInputAction.done,
              onSubmitted: (_) => checkServer(),
            ),
            const SizedBox(height: 10),
            OutlinedButton.icon(
              onPressed: loading ? null : checkServer,
              icon: const Icon(Icons.link),
              label: const Text('Se connecter à cette adresse'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _connectionCard() {
    final error = status.startsWith('Erreur') ||
        status.startsWith('Connexion impossible') ||
        status.startsWith('Aucun ordinateur');
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                Icon(
                  connected ? Icons.check_circle : Icons.link_off,
                  color: connected ? Colors.green : Colors.orange,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    connected
                        ? 'Connecté à ${selectedDevice?.name ?? 'ModernStock'}'
                        : 'Aucun ordinateur connecté',
                    style: const TextStyle(fontWeight: FontWeight.bold),
                  ),
                ),
                TextButton(
                  onPressed: () => setState(() => settingsOpen = true),
                  child: const Text('Changer'),
                ),
              ],
            ),
            const SizedBox(height: 6),
            Text(
              status,
              style: TextStyle(
                color: error ? Colors.red : const Color(0xFF23423F),
              ),
            ),
            const SizedBox(height: 6),
            const Text(
              'Ouvrez un champ code-barres dans ModernStock, puis utilisez la caméra du téléphone.',
              style: TextStyle(color: Colors.black54),
            ),
          ],
        ),
      ),
    );
  }

  Widget _cameraCard() {
    final backCamera = cameraFacing == CameraFacing.back;
    return SizedBox(
      height: 360,
      child: ClipRRect(
        borderRadius: BorderRadius.circular(8),
        child: Stack(
          children: [
            MobileScanner(
              controller: cameraController,
              onDetect: (capture) {
                final code = firstOrNull(capture.barcodes)?.rawValue;
                if (code != null) onCameraCode(code);
              },
              errorBuilder: (context, error) => ColoredBox(
                color: Colors.black,
                child: Center(
                  child: Padding(
                    padding: const EdgeInsets.all(20),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(
                          _cameraErrorMessage(error),
                          textAlign: TextAlign.center,
                          style: const TextStyle(color: Colors.white),
                        ),
                        const SizedBox(height: 16),
                        FilledButton.icon(
                          onPressed: cameraStarting
                              ? null
                              : () => unawaited(_retryCamera()),
                          icon: const Icon(Icons.refresh),
                          label: const Text('Réessayer'),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
            Positioned(
              top: 8,
              left: 8,
              child: IconButton.filled(
                tooltip: 'Fermer la caméra',
                onPressed: () => unawaited(toggleCameraPanel()),
                icon: const Icon(Icons.close),
              ),
            ),
            Positioned(
              top: 8,
              right: 8,
              child: IconButton.filled(
                tooltip: backCamera
                    ? 'Passer à la caméra avant'
                    : 'Revenir à la caméra arrière',
                onPressed: () => unawaited(toggleCamera()),
                icon: const Icon(Icons.cameraswitch),
              ),
            ),
            Positioned(
              bottom: 12,
              left: 12,
              right: 12,
              child: Center(
                child: DecoratedBox(
                  decoration: BoxDecoration(
                    color: Colors.black54,
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Padding(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 14,
                      vertical: 8,
                    ),
                    child: Text(
                      backCamera ? 'Caméra arrière' : 'Caméra avant',
                      style: const TextStyle(color: Colors.white),
                    ),
                  ),
                ),
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
                      prefixIcon: Icon(Icons.qr_code_2),
                    ),
                    textInputAction: TextInputAction.send,
                    onSubmitted: (_) => sendRemoteBarcode(),
                  ),
                ),
                const SizedBox(width: 8),
                SizedBox(
                  height: 56,
                  width: 56,
                  child: IconButton.filledTonal(
                    onPressed:
                        connected ? () => unawaited(toggleCameraPanel()) : null,
                    tooltip: 'Ouvrir la caméra arrière',
                    icon: Icon(cameraOpen ? Icons.close : Icons.camera_alt),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                onPressed: loading || !connected ? null : sendRemoteBarcode,
                icon: const Icon(Icons.send),
                label:
                    Text('Envoyer à ${selectedDevice?.name ?? 'ModernStock'}'),
              ),
            ),
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
            const Text(
              'Derniers envois',
              style: TextStyle(fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            if (recentScans.isEmpty)
              const Text('Aucun code envoyé à ModernStock.')
            else
              ...recentScans.map(
                (scan) => ListTile(
                  dense: true,
                  contentPadding: EdgeInsets.zero,
                  title: Text(scan.barcode),
                  subtitle: Text(
                      '${scan.time.hour.toString().padLeft(2, '0')}:${scan.time.minute.toString().padLeft(2, '0')} | ${scan.message}'),
                  trailing: const Icon(Icons.check_circle, color: Colors.green),
                ),
              ),
          ],
        ),
      ),
    );
  }
}
