// mobile_inventory_scanner/lib/views/physical_inventory_view.dart
// ignore_for_file: deprecated_member_use

import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../api_client.dart';
import '../models.dart';
import 'scanner_camera_widget.dart';

class PhysicalInventoryView extends StatefulWidget {
  const PhysicalInventoryView({
    super.key,
    required this.api,
    required this.connected,
    this.currentUser,
  });

  final ApiClient api;
  final bool connected;
  final AuthUser? currentUser;

  @override
  State<PhysicalInventoryView> createState() => _PhysicalInventoryViewState();
}

class _PhysicalInventoryViewState extends State<PhysicalInventoryView> {
  final TextEditingController _barcodeController = TextEditingController();
  final TextEditingController _searchController = TextEditingController();
  final FocusNode _barcodeFocus = FocusNode();

  List<InventorySessionItem> _sessions = [];
  InventorySessionItem? _selectedSession;
  InventorySummaryData? _summary;
  List<InventoryLineItem> _lines = [];

  bool _loading = false;
  bool _cameraOpen = false;
  bool _replaceMode = true; // true = Replace count, false = Accumulate (+1)
  String _activeFilter = 'ALL'; // ALL, SHORT, EXCESS, NOT_COUNTED, UNKNOWN, OK
  String? _errorMessage;
  String? _successMessage;

  InventoryScanResultData? _lastScanResult;

  @override
  void initState() {
    super.initState();
    if (widget.connected) {
      unawaited(_loadSessions());
    }
  }

  @override
  void didUpdateWidget(covariant PhysicalInventoryView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.connected && !oldWidget.connected) {
      unawaited(_loadSessions());
    }
  }

  @override
  void dispose() {
    _barcodeController.dispose();
    _searchController.dispose();
    _barcodeFocus.dispose();
    super.dispose();
  }

  Future<void> _loadSessions({int? autoSelectId}) async {
    if (!widget.connected) return;
    setState(() => _loading = true);
    try {
      final list = await widget.api.getInventorySessions(limit: 50);
      if (!mounted) return;
      setState(() {
        _sessions = list;
        if (autoSelectId != null) {
          _selectedSession = list.where((s) => s.sessionId == autoSelectId).firstOrNull ?? _selectedSession;
        } else if (_selectedSession != null) {
          _selectedSession = list.where((s) => s.sessionId == _selectedSession!.sessionId).firstOrNull;
        }
      });
      if (_selectedSession != null) {
        await _loadSessionDetails(_selectedSession!.sessionId);
      }
    } catch (e) {
      if (mounted) setState(() => _errorMessage = 'Erreur chargement sessions : $e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _loadSessionDetails(int sessionId) async {
    setState(() {
      _loading = true;
      _errorMessage = null;
    });
    try {
      final summaryFuture = widget.api.getInventorySessionSummary(sessionId);
      final linesFuture = widget.api.getInventorySessionLines(
        sessionId,
        status: _activeFilter == 'ALL' ? null : _activeFilter,
        search: _searchController.text.trim().isEmpty ? null : _searchController.text.trim(),
      );

      final results = await Future.wait([summaryFuture, linesFuture]);
      if (!mounted) return;

      setState(() {
        _summary = results[0] as InventorySummaryData;
        _lines = results[1] as List<InventoryLineItem>;
      });
    } catch (e) {
      if (mounted) setState(() => _errorMessage = 'Erreur détails session : $e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _performScan(String barcode, {double qty = 1.0}) async {
    final code = barcode.trim();
    if (code.isEmpty || _selectedSession == null) return;

    setState(() {
      _loading = true;
      _errorMessage = null;
      _successMessage = null;
    });

    try {
      final result = await widget.api.scanInventoryBarcode(
        _selectedSession!.sessionId,
        code,
        qty: qty,
        userId: widget.currentUser?.userId,
        replaceCounted: _replaceMode,
      );

      if (!mounted) return;

      setState(() {
        _lastScanResult = result;
        _barcodeController.clear();
      });

      HapticFeedback.lightImpact();

      // Refresh session summary & lines
      await _loadSessionDetails(_selectedSession!.sessionId);
    } catch (e) {
      if (mounted) setState(() => _errorMessage = 'Erreur lors du comptage : $e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _showNewSessionDialog() async {
    if (!widget.connected) return;
    InventoryScopeData? scopes;
    try {
      scopes = await widget.api.getInventoryScopes();
    } catch (_) {}

    if (!mounted) return;

    final nameController = TextEditingController(text: 'Inventaire ${DateTime.now().day}/${DateTime.now().month}/${DateTime.now().year}');
    final notesController = TextEditingController();
    String scopeType = 'ALL';
    int? scopeId;

    await showDialog<void>(
      context: context,
      builder: (ctx) {
        return StatefulBuilder(
          builder: (context, setDialogState) {
            return AlertDialog(
              title: const Row(
                children: [
                  Icon(Icons.add_circle, color: Color(0xFF007572)),
                  SizedBox(width: 8),
                  Text('Nouvelle Session', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
                ],
              ),
              content: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    TextField(
                      controller: nameController,
                      decoration: const InputDecoration(
                        labelText: 'Nom de la session *',
                        hintText: 'Ex: Inventaire Frigo A',
                      ),
                    ),
                    const SizedBox(height: 12),
                    DropdownButtonFormField<String>(
                      value: scopeType,
                      decoration: const InputDecoration(labelText: 'Périmètre (Scope)'),
                      items: const [
                        DropdownMenuItem(value: 'ALL', child: Text('🌍 Tout le stock')),
                        DropdownMenuItem(value: 'LOCATION', child: Text('📍 Par Emplacement')),
                        DropdownMenuItem(value: 'FAMILY', child: Text('🏷️ Par Famille de produit')),
                      ],
                      onChanged: (val) {
                        setDialogState(() {
                          scopeType = val ?? 'ALL';
                          scopeId = null;
                        });
                      },
                    ),
                    if (scopeType == 'LOCATION' && scopes != null) ...[
                      const SizedBox(height: 12),
                      DropdownButtonFormField<int>(
                        value: scopeId,
                        decoration: const InputDecoration(labelText: 'Choisir l\'emplacement'),
                        items: scopes.locations.map((loc) {
                          return DropdownMenuItem(
                            value: loc.locationId,
                            child: Text(loc.locationName, overflow: TextOverflow.ellipsis),
                          );
                        }).toList(),
                        onChanged: (val) => setDialogState(() => scopeId = val),
                      ),
                    ],
                    if (scopeType == 'FAMILY' && scopes != null) ...[
                      const SizedBox(height: 12),
                      DropdownButtonFormField<int>(
                        value: scopeId,
                        decoration: const InputDecoration(labelText: 'Choisir la famille'),
                        items: scopes.families.map((fam) {
                          return DropdownMenuItem(
                            value: fam['Family_ID'] as int,
                            child: Text(fam['Family_Name'] as String, overflow: TextOverflow.ellipsis),
                          );
                        }).toList(),
                        onChanged: (val) => setDialogState(() => scopeId = val),
                      ),
                    ],
                    const SizedBox(height: 12),
                    TextField(
                      controller: notesController,
                      decoration: const InputDecoration(
                        labelText: 'Remarques / Notes',
                        hintText: 'Optionnel...',
                      ),
                      maxLines: 2,
                    ),
                  ],
                ),
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(ctx),
                  child: const Text('Annuler'),
                ),
                FilledButton(
                  style: FilledButton.styleFrom(backgroundColor: const Color(0xFF007572)),
                  onPressed: () async {
                    final name = nameController.text.trim();
                    if (name.isEmpty) return;
                    Navigator.pop(ctx);
                    setState(() => _loading = true);
                    try {
                      final res = await widget.api.createInventorySession(
                        name: name,
                        scopeType: scopeType,
                        scopeId: scopeId,
                        userId: widget.currentUser?.userId,
                        notes: notesController.text.trim(),
                      );
                      if (res['success'] == true) {
                        final newId = res['session_id'] as int?;
                        await _loadSessions(autoSelectId: newId);
                        if (mounted) {
                          setState(() => _successMessage = 'Session #$newId créée avec succès.');
                        }
                      }
                    } catch (e) {
                      if (mounted) setState(() => _errorMessage = 'Erreur création : $e');
                    } finally {
                      if (mounted) setState(() => _loading = false);
                    }
                  },
                  child: const Text('Créer et Démarrer'),
                ),
              ],
            );
          },
        );
      },
    );
  }

  Future<void> _showEditLineDialog(InventoryLineItem line) async {
    final qtyController = TextEditingController(text: line.countedQty.toStringAsFixed(line.countedQty.truncateToDouble() == line.countedQty ? 0 : 2));
    await showDialog<void>(
      context: context,
      builder: (ctx) {
        return AlertDialog(
          title: Text(line.productName, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Lot: ${line.lotNumber} | Emplacement: ${line.locationName}'),
              const SizedBox(height: 4),
              Text(
                'Stock attendu (Snapshot) : ${line.programQtySnapshot} ${line.stockUnit}',
                style: const TextStyle(fontWeight: FontWeight.w600, color: Color(0xFF52616F)),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: qtyController,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                autofocus: true,
                decoration: const InputDecoration(
                  labelText: 'Nouvelle Quantité Comptée',
                  prefixIcon: Icon(Icons.edit),
                ),
              ),
              const SizedBox(height: 8),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                children: [
                  OutlinedButton(
                    onPressed: () => qtyController.text = '0',
                    child: const Text('0'),
                  ),
                  OutlinedButton(
                    onPressed: () => qtyController.text = line.programQtySnapshot.toString(),
                    child: const Text('Snapshot'),
                  ),
                  OutlinedButton(
                    onPressed: () {
                      final cur = double.tryParse(qtyController.text) ?? 0.0;
                      qtyController.text = (cur + 1).toString();
                    },
                    child: const Text('+1'),
                  ),
                ],
              ),
            ],
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Annuler')),
            FilledButton(
              style: FilledButton.styleFrom(backgroundColor: const Color(0xFF007572)),
              onPressed: () async {
                final newQty = double.tryParse(qtyController.text);
                if (newQty == null || _selectedSession == null) return;
                Navigator.pop(ctx);
                setState(() => _loading = true);
                try {
                  await widget.api.updateInventoryLineQuantity(
                    _selectedSession!.sessionId,
                    line.lineId,
                    newQty,
                  );
                  await _loadSessionDetails(_selectedSession!.sessionId);
                } catch (e) {
                  if (mounted) setState(() => _errorMessage = 'Erreur modification : $e');
                } finally {
                  if (mounted) setState(() => _loading = false);
                }
              },
              child: const Text('Enregistrer'),
            ),
          ],
        );
      },
    );
  }

  Future<void> _showSessionActionsDialog() async {
    if (_selectedSession == null) return;
    final s = _selectedSession!;
    final isCounting = s.status == 'Counting';
    final isReview = s.status == 'Review';

    await showModalBottomSheet<void>(
      context: context,
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(16))),
      builder: (ctx) {
        return SafeArea(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  'Actions Session #${s.sessionId}',
                  style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                ),
                Text('${s.sessionName} (${s.status})', style: const TextStyle(color: Colors.grey)),
                const Divider(),
                if (isCounting)
                  ListTile(
                    leading: const Icon(Icons.check_circle_outline, color: Colors.blue),
                    title: const Text('Terminer le comptage (Passer en revue)'),
                    subtitle: const Text('Bloque les nouveaux ajouts et prépare l\'application.'),
                    onTap: () async {
                      Navigator.pop(ctx);
                      setState(() => _loading = true);
                      try {
                        await widget.api.markInventoryReview(s.sessionId);
                        await _loadSessions(autoSelectId: s.sessionId);
                      } catch (e) {
                        if (mounted) setState(() => _errorMessage = '$e');
                      } finally {
                        if (mounted) setState(() => _loading = false);
                      }
                    },
                  ),
                if (isCounting || isReview)
                  ListTile(
                    leading: const Icon(Icons.inventory, color: Color(0xFF007572)),
                    title: const Text('Appliquer les écarts au stock réel'),
                    subtitle: const Text('Met à jour la base de données avec traçabilité complète.'),
                    onTap: () async {
                      Navigator.pop(ctx);
                      await _showApplyConfirmationDialog();
                    },
                  ),
                if (isCounting || isReview)
                  ListTile(
                    leading: const Icon(Icons.cancel_outlined, color: Colors.orange),
                    title: const Text('Annuler la session'),
                    subtitle: const Text('Ferme la session sans modifier le stock.'),
                    onTap: () async {
                      Navigator.pop(ctx);
                      final confirm = await showDialog<bool>(
                        context: context,
                        builder: (c) => AlertDialog(
                          title: const Text('Confirmer l\'annulation'),
                          content: const Text('Voulez-vous vraiment annuler cette session d\'inventaire ?'),
                          actions: [
                            TextButton(onPressed: () => Navigator.pop(c, false), child: const Text('Non')),
                            FilledButton(onPressed: () => Navigator.pop(c, true), child: const Text('Oui, Annuler')),
                          ],
                        ),
                      );
                      if (confirm == true) {
                        setState(() => _loading = true);
                        try {
                          await widget.api.cancelInventorySession(s.sessionId, userId: widget.currentUser?.userId);
                          await _loadSessions(autoSelectId: s.sessionId);
                        } catch (e) {
                          if (mounted) setState(() => _errorMessage = '$e');
                        } finally {
                          if (mounted) setState(() => _loading = false);
                        }
                      }
                    },
                  ),
                ListTile(
                  leading: const Icon(Icons.delete_outline, color: Colors.red),
                  title: const Text('Supprimer définitivement la session'),
                  onTap: () async {
                    Navigator.pop(ctx);
                    final confirm = await showDialog<bool>(
                      context: context,
                      builder: (c) => AlertDialog(
                        title: const Text('Supprimer la session'),
                        content: Text('Supprimer définitivement la session #${s.sessionId} et ses scans ?'),
                        actions: [
                          TextButton(onPressed: () => Navigator.pop(c, false), child: const Text('Annuler')),
                          FilledButton(
                            style: FilledButton.styleFrom(backgroundColor: Colors.red),
                            onPressed: () => Navigator.pop(c, true),
                            child: const Text('Supprimer'),
                          ),
                        ],
                      ),
                    );
                    if (confirm == true) {
                      setState(() => _loading = true);
                      try {
                        await widget.api.deleteInventorySession(s.sessionId);
                        _selectedSession = null;
                        await _loadSessions();
                      } catch (e) {
                        if (mounted) setState(() => _errorMessage = '$e');
                      } finally {
                        if (mounted) setState(() => _loading = false);
                      }
                    }
                  },
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  Future<void> _showApplyConfirmationDialog() async {
    if (_selectedSession == null) return;
    String uncountedAction = 'ignore';
    bool allowUnknown = true;

    await showDialog<void>(
      context: context,
      builder: (ctx) {
        return StatefulBuilder(
          builder: (context, setDialogState) {
            return AlertDialog(
              title: const Text('Appliquer l\'inventaire', style: TextStyle(fontWeight: FontWeight.bold)),
              content: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Cette action va modifier le stock réel en base selon les quantités comptées.'),
                  const SizedBox(height: 14),
                  const Text('Articles non comptés (NOT_COUNTED) :', style: TextStyle(fontWeight: FontWeight.bold)),
                  RadioListTile<String>(
                    title: const Text('Conserver le stock actuel (Ignorer)'),
                    value: 'ignore',
                    groupValue: uncountedAction,
                    contentPadding: EdgeInsets.zero,
                    onChanged: (val) => setDialogState(() => uncountedAction = val ?? 'ignore'),
                  ),
                  RadioListTile<String>(
                    title: const Text('Mettre la quantité à zéro'),
                    value: 'zero',
                    groupValue: uncountedAction,
                    contentPadding: EdgeInsets.zero,
                    onChanged: (val) => setDialogState(() => uncountedAction = val ?? 'zero'),
                  ),
                  const SizedBox(height: 8),
                  CheckboxListTile(
                    title: const Text('Ignorer les codes inconnus'),
                    value: allowUnknown,
                    contentPadding: EdgeInsets.zero,
                    onChanged: (val) => setDialogState(() => allowUnknown = val ?? false),
                  ),
                ],
              ),
              actions: [
                TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Annuler')),
                FilledButton(
                  style: FilledButton.styleFrom(backgroundColor: const Color(0xFF007572)),
                  onPressed: () async {
                    Navigator.pop(ctx);
                    setState(() => _loading = true);
                    try {
                      final res = await widget.api.applyInventorySession(
                        _selectedSession!.sessionId,
                        userId: widget.currentUser?.userId,
                        allowUnknown: allowUnknown,
                        uncountedAction: uncountedAction,
                      );
                      if (res['success'] == true) {
                        await _loadSessions(autoSelectId: _selectedSession!.sessionId);
                        if (mounted) {
                          setState(() => _successMessage = 'Inventaire appliqué avec succès !');
                        }
                      } else {
                        if (mounted) setState(() => _errorMessage = res['message'] ?? 'Échec application.');
                      }
                    } catch (e) {
                      if (mounted) setState(() => _errorMessage = 'Erreur : $e');
                    } finally {
                      if (mounted) setState(() => _loading = false);
                    }
                  },
                  child: const Text('Confirmer et Appliquer'),
                ),
              ],
            );
          },
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    return RefreshIndicator(
      onRefresh: () => _loadSessions(),
      child: SingleChildScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            if (_loading) ...[
              const LinearProgressIndicator(color: Color(0xFF007572)),
              const SizedBox(height: 8),
            ],
            _buildSessionHeader(),
            const SizedBox(height: 10),

            if (_errorMessage != null) ...[
              _buildMessageBox(_errorMessage!, isError: true),
              const SizedBox(height: 10),
            ],
            if (_successMessage != null) ...[
              _buildMessageBox(_successMessage!, isError: false),
              const SizedBox(height: 10),
            ],

            if (_selectedSession != null) ...[
              _buildSummarySection(),
              const SizedBox(height: 10),
              _buildScanSection(),
              const SizedBox(height: 10),
              if (_lastScanResult != null) ...[
                _buildLastScanFeedback(),
                const SizedBox(height: 10),
              ],
              _buildFilterAndSearchSection(),
              const SizedBox(height: 10),
              _buildLinesList(),
            ] else ...[
              const SizedBox(height: 40),
              Center(
                child: Column(
                  children: [
                    Icon(Icons.inventory_2_outlined, size: 64, color: Colors.grey.shade400),
                    const SizedBox(height: 12),
                    const Text(
                      'Sélectionnez ou créez une session d\'inventaire pour commencer.',
                      style: TextStyle(color: Colors.grey, fontSize: 14),
                      textAlign: TextAlign.center,
                    ),
                  ],
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildSessionHeader() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.assignment, color: Color(0xFF007572)),
                const SizedBox(width: 8),
                const Expanded(
                  child: Text(
                    'Sessions d\'inventaire',
                    style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                  ),
                ),
                IconButton.filledTonal(
                  tooltip: 'Nouvelle Session',
                  onPressed: widget.connected ? _showNewSessionDialog : null,
                  icon: const Icon(Icons.add),
                ),
              ],
            ),
            const SizedBox(height: 8),
            DropdownButtonFormField<int>(
              value: _selectedSession?.sessionId,
              decoration: const InputDecoration(
                contentPadding: EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                labelText: 'Session Active',
              ),
              items: _sessions.map((s) {
                return DropdownMenuItem(
                  value: s.sessionId,
                  child: Text(
                    '#${s.sessionId} - ${s.sessionName} (${s.status})',
                    overflow: TextOverflow.ellipsis,
                  ),
                );
              }).toList(),
              onChanged: (id) {
                if (id != null) {
                  final found = _sessions.where((s) => s.sessionId == id).firstOrNull;
                  setState(() => _selectedSession = found);
                  if (found != null) {
                    _loadSessionDetails(found.sessionId);
                  }
                }
              },
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSummarySection() {
    final sum = _summary ?? const InventorySummaryData();
    final s = _selectedSession!;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Expanded(
                  child: Text(
                    '${s.sessionName} (${s.status})',
                    style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15),
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                IconButton(
                  tooltip: 'Actions de la session',
                  onPressed: _showSessionActionsDialog,
                  icon: const Icon(Icons.more_vert),
                ),
              ],
            ),
            const SizedBox(height: 6),
            ClipRRect(
              borderRadius: BorderRadius.circular(4),
              child: LinearProgressIndicator(
                value: s.progressPercentage,
                minHeight: 8,
                backgroundColor: Colors.grey.shade200,
                color: const Color(0xFF007572),
              ),
            ),
            const SizedBox(height: 6),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text('Progression : ${(s.progressPercentage * 100).toStringAsFixed(1)}%'),
                Text('${s.countedLines} / ${s.totalLines} lignes'),
              ],
            ),
            const Divider(height: 16),
            SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(
                children: [
                  _kpiBadge('Total', sum.totalLines, Colors.blueGrey),
                  _kpiBadge('OK', sum.ok, Colors.green),
                  _kpiBadge('Manquants', sum.short, Colors.red),
                  _kpiBadge('Excédents', sum.excess, Colors.blue),
                  _kpiBadge('Non Comptés', sum.notCounted, Colors.grey),
                  if (sum.unknown > 0) _kpiBadge('Inconnus', sum.unknown, Colors.orange),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _kpiBadge(String label, int count, Color color) {
    return Container(
      margin: const EdgeInsets.only(right: 6),
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withOpacity(0.12),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: color.withOpacity(0.3)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text('$label : ', style: TextStyle(fontSize: 11, color: color, fontWeight: FontWeight.w600)),
          Text('$count', style: TextStyle(fontSize: 12, color: color, fontWeight: FontWeight.bold)),
        ],
      ),
    );
  }

  Widget _buildScanSection() {
    final isClosed = _selectedSession?.status == 'Applied' || _selectedSession?.status == 'Cancelled';

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          children: [
            if (_cameraOpen) ...[
              ScannerCameraWidget(
                onCodeDetected: (code) {
                  _performScan(code);
                },
                onClose: () => setState(() => _cameraOpen = false),
              ),
              const SizedBox(height: 10),
            ],
            Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _barcodeController,
                    focusNode: _barcodeFocus,
                    enabled: !isClosed,
                    decoration: InputDecoration(
                      hintText: isClosed ? 'Session fermée' : 'Code-barres / Lot...',
                      prefixIcon: const Icon(Icons.qr_code_scanner),
                      suffixIcon: IconButton(
                        icon: const Icon(Icons.clear),
                        onPressed: () => _barcodeController.clear(),
                      ),
                    ),
                    onSubmitted: (code) => _performScan(code),
                  ),
                ),
                const SizedBox(width: 8),
                IconButton.filled(
                  tooltip: _cameraOpen ? 'Fermer caméra' : 'Scanner caméra',
                  style: IconButton.styleFrom(backgroundColor: const Color(0xFF007572)),
                  onPressed: isClosed ? null : () => setState(() => _cameraOpen = !_cameraOpen),
                  icon: Icon(_cameraOpen ? Icons.videocam_off : Icons.camera_alt),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                const Text('Mode : ', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 12)),
                ChoiceChip(
                  label: const Text('Remplacer'),
                  selected: _replaceMode,
                  onSelected: (val) => setState(() => _replaceMode = true),
                ),
                const SizedBox(width: 6),
                ChoiceChip(
                  label: const Text('Incrémenter (+1)'),
                  selected: !_replaceMode,
                  onSelected: (val) => setState(() => _replaceMode = false),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildLastScanFeedback() {
    final res = _lastScanResult!;
    final line = res.line;
    final isMatched = res.status == 'MATCHED';
    final color = isMatched
        ? (line?.lineStatus == 'OK' ? Colors.green : (line?.lineStatus == 'SHORT' ? Colors.red : Colors.blue))
        : Colors.orange;

    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color.withOpacity(0.08),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withOpacity(0.3)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(isMatched ? Icons.check_circle : Icons.warning, color: color, size: 20),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  line?.productName ?? 'Code ${res.line?.internalBarcode}',
                  style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14, color: color),
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: color,
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Text(
                  line?.lineStatus ?? res.status,
                  style: const TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.bold),
                ),
              ),
            ],
          ),
          const SizedBox(height: 4),
          Text(
            'Attendu : ${line?.programQtySnapshot ?? 0} | Compté : ${line?.countedQty ?? 0} | Écart : ${line?.differenceQty ?? 0}',
            style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
          ),
        ],
      ),
    );
  }

  Widget _buildFilterAndSearchSection() {
    return Column(
      children: [
        TextField(
          controller: _searchController,
          decoration: InputDecoration(
            hintText: 'Rechercher produit, lot, code...',
            prefixIcon: const Icon(Icons.search),
            contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            suffixIcon: _searchController.text.isNotEmpty
                ? IconButton(
                    icon: const Icon(Icons.clear),
                    onPressed: () {
                      _searchController.clear();
                      if (_selectedSession != null) _loadSessionDetails(_selectedSession!.sessionId);
                    },
                  )
                : null,
          ),
          onChanged: (val) {
            if (_selectedSession != null) {
              _loadSessionDetails(_selectedSession!.sessionId);
            }
          },
        ),
        const SizedBox(height: 8),
        SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: Row(
            children: [
              _filterChip('Tous', 'ALL'),
              _filterChip('Écarts', 'SHORT'),
              _filterChip('Excédents', 'EXCESS'),
              _filterChip('Non Comptés', 'NOT_COUNTED'),
              _filterChip('Inconnus', 'UNKNOWN'),
              _filterChip('Conformes (OK)', 'OK'),
            ],
          ),
        ),
      ],
    );
  }

  Widget _filterChip(String label, String value) {
    final isSelected = _activeFilter == value;
    return Padding(
      padding: const EdgeInsets.only(right: 6),
      child: FilterChip(
        label: Text(label),
        selected: isSelected,
        selectedColor: const Color(0xFF007572).withOpacity(0.2),
        checkmarkColor: const Color(0xFF007572),
        onSelected: (selected) {
          setState(() => _activeFilter = selected ? value : 'ALL');
          if (_selectedSession != null) {
            _loadSessionDetails(_selectedSession!.sessionId);
          }
        },
      ),
    );
  }

  Widget _buildLinesList() {
    if (_lines.isEmpty) {
      return const Padding(
        padding: EdgeInsets.symmetric(vertical: 24),
        child: Center(
          child: Text('Aucune ligne correspondant aux critères.', style: TextStyle(color: Colors.grey)),
        ),
      );
    }

    return ListView.separated(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      itemCount: _lines.length,
      separatorBuilder: (_, __) => const SizedBox(height: 6),
      itemBuilder: (context, index) {
        final line = _lines[index];
        final statusColor = _statusColor(line.lineStatus);

        return Card(
          child: ListTile(
            contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
            title: Text(
              line.productName,
              style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
              overflow: TextOverflow.ellipsis,
            ),
            subtitle: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Lot: ${line.lotNumber} | Empl: ${line.locationName}',
                  style: const TextStyle(fontSize: 11, color: Color(0xFF607080)),
                ),
                Text(
                  'Attendu: ${line.programQtySnapshot} -> Compté: ${line.countedQty} (Écart: ${line.differenceQty})',
                  style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: statusColor),
                ),
              ],
            ),
            trailing: Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              decoration: BoxDecoration(
                color: statusColor.withOpacity(0.12),
                borderRadius: BorderRadius.circular(6),
                border: Border.all(color: statusColor.withOpacity(0.4)),
              ),
              child: Text(
                line.lineStatus,
                style: TextStyle(color: statusColor, fontSize: 11, fontWeight: FontWeight.bold),
              ),
            ),
            onTap: () => _showEditLineDialog(line),
          ),
        );
      },
    );
  }

  Color _statusColor(String status) {
    switch (status) {
      case 'OK':
        return Colors.green;
      case 'SHORT':
        return Colors.red;
      case 'EXCESS':
        return Colors.blue;
      case 'UNKNOWN':
        return Colors.orange;
      default:
        return Colors.grey;
    }
  }

  Widget _buildMessageBox(String message, {required bool isError}) {
    final color = isError ? Colors.red : Colors.green;
    return Container(
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: color.withOpacity(0.08),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withOpacity(0.3)),
      ),
      child: Row(
        children: [
          Icon(isError ? Icons.error_outline : Icons.check_circle_outline, color: color, size: 20),
          const SizedBox(width: 8),
          Expanded(
            child: Text(message, style: TextStyle(color: color, fontSize: 13, fontWeight: FontWeight.w600)),
          ),
        ],
      ),
    );
  }
}
