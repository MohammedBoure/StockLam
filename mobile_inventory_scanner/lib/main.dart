// mobile_inventory_scanner/lib/main.dart

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'api_client.dart';
import 'models.dart';
import 'views/auth_dialog.dart';
import 'views/direct_inventory_view.dart';
import 'views/fast_dispatch_view.dart';
import 'views/physical_inventory_view.dart';
import 'views/remote_scanner_view.dart';

void main() {
  runApp(const ModernStockApp());
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
  AuthUser? currentUser;
  SavedAccount? activeSavedAccount;
  List<SavedAccount> savedAccounts = const [];

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
    savedAccounts = await AccountStorage.loadSavedAccounts();
    final activeId = await AccountStorage.getActiveAccountId();

    if (activeId != null && savedAccounts.isNotEmpty) {
      final found = savedAccounts.where((a) => a.id == activeId).toList();
      if (found.isNotEmpty) {
        activeSavedAccount = found.first;
      }
    }

    final savedServer = preferences.getString(serverKey);
    if (!mounted) return;

    if (savedServer == null || savedServer.isEmpty) {
      setState(() => settingsOpen = true);
      return;
    }

    setState(() => serverController.text = savedServer);
    await checkServer(autoAuth: true);
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
    await checkServer(autoAuth: true);
  }

  Future<void> checkServer({bool autoAuth = false}) async {
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

      // Tentative d'auto-authentification avec un compte déjà enregistré pour ce serveur
      if (autoAuth) {
        await _tryAutoAuth(baseUrl, device.name);
      }
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

  Future<void> _tryAutoAuth(String baseUrl, String serverName) async {
    final accounts = await AccountStorage.loadSavedAccounts();
    savedAccounts = accounts;

    final matchingAccounts = accounts.where((a) => cleanBaseUrl(a.serverUrl) == cleanBaseUrl(baseUrl)).toList();
    if (matchingAccounts.isNotEmpty) {
      final acc = matchingAccounts.first;
      try {
        final authUser = await api.login(username: acc.username, password: acc.password);
        if (mounted) {
          setState(() {
            currentUser = authUser;
            activeSavedAccount = acc;
          });
        }
        return;
      } catch (_) {
        // En cas d'échec du mot de passe sauvegardé, on demandera la connexion
      }
    }

    // Si aucun compte valide n'est connecté, proposer la connexion
    if (currentUser == null && mounted) {
      await _promptLoginDialog(serverName: serverName, serverUrl: baseUrl);
    }
  }

  Future<void> _promptLoginDialog({String? serverName, String? serverUrl}) async {
    final sName = serverName ?? selectedDevice?.name ?? 'StockLam PC';
    final sUrl = serverUrl ?? cleanBaseUrl(serverController.text);

    final savedAcc = await showDialog<SavedAccount?>(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => LoginDialog(
        api: api,
        serverName: sName,
        serverUrl: sUrl,
      ),
    );

    if (savedAcc != null && mounted) {
      setState(() {
        activeSavedAccount = savedAcc;
        currentUser = AuthUser(
          userId: savedAcc.userId,
          username: savedAcc.username,
          fullName: savedAcc.fullName,
          role: savedAcc.role,
        );
      });
      savedAccounts = await AccountStorage.loadSavedAccounts();
    }
  }

  void _showSavedAccountsSheet() {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (ctx) => SavedAccountsSheet(
        accounts: savedAccounts,
        activeAccountId: activeSavedAccount?.id,
        onSelectAccount: (acc) async {
          setState(() {
            serverController.text = acc.serverUrl;
          });
          await checkServer(autoAuth: false);
          try {
            final user = await api.login(username: acc.username, password: acc.password);
            await AccountStorage.setActiveAccountId(acc.id);
            if (mounted) {
              setState(() {
                currentUser = user;
                activeSavedAccount = acc;
              });
            }
          } catch (e) {
            if (mounted) {
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(content: Text('Échec de connexion : $e')),
              );
              await _promptLoginDialog(serverName: acc.serverName, serverUrl: acc.serverUrl);
            }
          }
        },
        onDeleteAccount: (id) async {
          await AccountStorage.removeAccount(id);
          final updated = await AccountStorage.loadSavedAccounts();
          if (mounted) {
            setState(() {
              savedAccounts = updated;
              if (activeSavedAccount?.id == id) {
                activeSavedAccount = null;
                currentUser = null;
              }
            });
          }
        },
        onAddNewLogin: () async {
          await _promptLoginDialog();
        },
        onLogout: () async {
          await AccountStorage.setActiveAccountId(null);
          if (mounted) {
            setState(() {
              activeSavedAccount = null;
              currentUser = null;
            });
            await _promptLoginDialog();
          }
        },
      ),
    );
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
            tooltip: 'Comptes & Sessions',
            onPressed: _showSavedAccountsSheet,
            icon: Icon(
              currentUser != null ? Icons.account_circle : Icons.no_accounts_outlined,
              color: currentUser != null ? const Color(0xFF007572) : Colors.black54,
            ),
          ),
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
                        currentUser: currentUser,
                      ),
                      FastDispatchView(
                        api: api,
                        connected: connected,
                        currentUser: currentUser,
                      ),
                      PhysicalInventoryView(
                        api: api,
                        connected: connected,
                        currentUser: currentUser,
                      ),
                      RemoteScannerView(
                        api: api,
                        connected: connected,
                        selectedDevice: selectedDevice,
                        currentUser: currentUser,
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
            icon: Icon(Icons.flash_on_outlined),
            selectedIcon: Icon(Icons.flash_on, color: Color(0xFF007572)),
            label: 'Saisie Rapide',
          ),
          NavigationDestination(
            icon: Icon(Icons.checklist_rtl_outlined),
            selectedIcon: Icon(Icons.checklist_rtl, color: Color(0xFF007572)),
            label: 'Inventaire',
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
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      child: Row(
        children: [
          Icon(
            connected ? Icons.check_circle : Icons.link_off,
            color: connected ? const Color(0xFF27AE60) : const Color(0xFF856404),
            size: 16,
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
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
                if (connected && currentUser != null)
                  Text(
                    '👤 ${currentUser!.fullName} (${currentUser!.role})',
                    style: const TextStyle(fontSize: 11, color: Color(0xFF007572), fontWeight: FontWeight.w600),
                    overflow: TextOverflow.ellipsis,
                  )
                else if (connected && currentUser == null)
                  const Text(
                    '⚠️ Non authentifié - Cliquez pour vous connecter',
                    style: TextStyle(fontSize: 11, color: Colors.orange, fontWeight: FontWeight.w600),
                  ),
              ],
            ),
          ),
          if (connected && currentUser == null)
            FilledButton.tonal(
              style: FilledButton.styleFrom(
                visualDensity: VisualDensity.compact,
                padding: const EdgeInsets.symmetric(horizontal: 10),
              ),
              onPressed: () => _promptLoginDialog(),
              child: const Text('Connexion', style: TextStyle(fontSize: 11)),
            )
          else if (connected && currentUser != null)
            TextButton(
              style: TextButton.styleFrom(
                visualDensity: VisualDensity.compact,
                padding: const EdgeInsets.symmetric(horizontal: 6),
              ),
              onPressed: _showSavedAccountsSheet,
              child: const Text('Changer', style: TextStyle(fontSize: 11)),
            )
          else
            TextButton(
              style: TextButton.styleFrom(
                visualDensity: VisualDensity.compact,
                padding: const EdgeInsets.symmetric(horizontal: 6),
              ),
              onPressed: () => setState(() => settingsOpen = !settingsOpen),
              child: Text(
                settingsOpen ? 'Fermer' : 'Modifier',
                style: const TextStyle(fontSize: 11),
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
                  onSubmitted: (_) => checkServer(autoAuth: true),
                ),
              ),
              const SizedBox(width: 8),
              FilledButton(
                onPressed: loading ? null : () => checkServer(autoAuth: true),
                child: const Text('OK'),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
