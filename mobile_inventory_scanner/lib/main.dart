// mobile_inventory_scanner/lib/main.dart

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'api_client.dart';
import 'models.dart';
import 'views/direct_inventory_view.dart';
import 'views/remote_scanner_view.dart';

void main() {
  runApp(const ModernStockApp());
}

T? firstOrNull<T>(Iterable<T> values) {
  final iterator = values.iterator;
  return iterator.moveNext() ? iterator.current : null;
}

class ModernStockApp extends StatelessWidget {
  const ModernStockApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'MODERNSTOCK',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF007572),
          primary: const Color(0xFF007572),
        ),
        useMaterial3: true,
        inputDecorationTheme: const InputDecorationTheme(
          border: OutlineInputBorder(borderRadius: BorderRadius.all(Radius.circular(8))),
        ),
        cardTheme: const CardThemeData(
          elevation: 0,
          margin: EdgeInsets.zero,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.all(Radius.circular(10)),
            side: BorderSide(color: Color(0xFFE2E8F0)),
          ),
        ),
      ),
      home: const ScannerHomePage(),
    );
  }
}

class ScannerHomePage extends StatefulWidget {
  const ScannerHomePage({super.key});

  @override
  State<ScannerHomePage> createState() => _ScannerHomePageState();
}

class _ScannerHomePageState extends State<ScannerHomePage> {
  static const serverKey = 'modernstock_server_url';

  final TextEditingController serverController = TextEditingController();
  int _currentTabIndex = 0;

  List<DesktopDevice> discoveredDevices = const [];
  List<ScanEntry> recentScans = const [];
  DesktopDevice? selectedDevice;
  String status = 'Recherchez ou sélectionnez un ordinateur ModernStock.';
  bool loading = false;
  bool discovering = false;
  bool connected = false;
  bool settingsOpen = false;

  ApiClient get api => ApiClient(baseUrl: serverController.text);

  @override
  void initState() {
    super.initState();
    unawaited(_loadSettings());
  }

  @override
  void dispose() {
    serverController.dispose();
    super.dispose();
  }

  Future<void> _loadSettings() async {
    final preferences = await SharedPreferences.getInstance();
    final savedServer = preferences.getString(serverKey);
    if (!mounted || savedServer == null || savedServer.isEmpty) {
      setState(() => settingsOpen = true);
      return;
    }
    setState(() => serverController.text = savedServer);
    await checkServer();
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
      settingsOpen = true;
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
            final data = jsonDecode(utf8.decode(datagram!.data)) as Map<String, dynamic>;
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
          } catch (_) {}
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
      setState(() => status = 'Choisissez un ordinateur ou saisissez son adresse.');
      return;
    }
    await _saveSettings();
    setState(() {
      loading = true;
      status = 'Test de connexion à ModernStock...';
    });
    try {
      final health = await api.health();
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

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;

    return Scaffold(
      backgroundColor: const Color(0xFFF8FAFC),
      appBar: AppBar(
        title: const Text('MODERNSTOCK', style: TextStyle(fontWeight: FontWeight.bold)),
        backgroundColor: Colors.white,
        surfaceTintColor: Colors.transparent,
        elevation: 1,
        actions: [
          IconButton(
            tooltip: 'Connexion Serveur',
            onPressed: () => setState(() => settingsOpen = !settingsOpen),
            icon: Icon(settingsOpen ? Icons.expand_less : Icons.settings_ethernet),
          ),
          IconButton(
            tooltip: 'Rechercher sur le réseau',
            onPressed: loading || discovering ? null : discoverDevices,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: SafeArea(
        child: Stack(
          children: [
            Column(
              children: [
                if (settingsOpen) _serverCard(),
                _connectionBar(),
                Expanded(
                  child: IndexedStack(
                    index: _currentTabIndex,
                    children: [
                      DirectInventoryView(
                        api: api,
                        connected: connected,
                      ),
                      RemoteScannerView(
                        api: api,
                        connected: connected,
                        selectedDevice: selectedDevice,
                        recentScans: recentScans,
                        onScanSent: (entry) {
                          setState(() {
                            recentScans = [entry, ...recentScans].take(15).toList();
                          });
                        },
                      ),
                    ],
                  ),
                ),
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
      bottomNavigationBar: NavigationBar(
        selectedIndex: _currentTabIndex,
        onDestinationSelected: (index) => setState(() => _currentTabIndex = index),
        indicatorColor: const Color(0xFFE8F8F0),
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.inventory_2_outlined),
            selectedIcon: Icon(Icons.inventory_2, color: Color(0xFF007572)),
            label: 'Stock Direct',
          ),
          NavigationDestination(
            icon: Icon(Icons.phone_android_outlined),
            selectedIcon: Icon(Icons.phone_android, color: Color(0xFF007572)),
            label: 'Pont Bureau',
          ),
        ],
      ),
    );
  }

  Widget _connectionBar() {
    return Container(
      color: connected ? const Color(0xFFE8F8F0) : const Color(0xFFFFF3CD),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
      child: Row(
        children: [
          Icon(
            connected ? Icons.check_circle : Icons.link_off,
            color: connected ? const Color(0xFF27AE60) : const Color(0xFF856404),
            size: 18,
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              connected
                  ? 'Connecté à ${selectedDevice?.name ?? 'ModernStock'}'
                  : 'Non connecté ($status)',
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.bold,
                color: connected ? const Color(0xFF155724) : const Color(0xFF856404),
              ),
              overflow: TextOverflow.ellipsis,
            ),
          ),
          TextButton(
            onPressed: () => setState(() => settingsOpen = !settingsOpen),
            child: Text(
              settingsOpen ? 'Fermer' : 'Modifier',
              style: const TextStyle(fontSize: 12),
            ),
          ),
        ],
      ),
    );
  }

  Widget _serverCard() {
    return Container(
      color: Colors.white,
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
                    child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                  )
                : const Icon(Icons.radar),
            label: Text(discovering ? 'Recherche en cours...' : 'Rechercher les ordinateurs ModernStock'),
          ),
          if (discoveredDevices.isNotEmpty) ...[
            const SizedBox(height: 10),
            const Text('Ordinateurs détectés :', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
            const SizedBox(height: 4),
            ...discoveredDevices.map(
              (device) => ListTile(
                dense: true,
                contentPadding: EdgeInsets.zero,
                leading: const Icon(Icons.computer, color: Color(0xFF007572)),
                title: Text(device.name, style: const TextStyle(fontWeight: FontWeight.bold)),
                subtitle: Text(device.baseUrl),
                trailing: ElevatedButton(
                  onPressed: () => connectDevice(device),
                  child: const Text('Connecter'),
                ),
              ),
            ),
          ],
          const Divider(height: 20),
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: serverController,
                  decoration: const InputDecoration(
                    labelText: 'Adresse IP / URL',
                    hintText: 'http://192.168.1.50:8787',
                    isDense: true,
                  ),
                  keyboardType: TextInputType.url,
                  onSubmitted: (_) => checkServer(),
                ),
              ),
              const SizedBox(width: 8),
              FilledButton(
                onPressed: loading ? null : checkServer,
                child: const Text('OK'),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
