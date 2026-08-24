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
  final GlobalKey<ScannerCameraWidgetState> _scannerKey = GlobalKey<ScannerCameraWidgetState>();

  List<InventorySessionItem> _openSessions = [];
  InventorySessionItem? _selectedSession;
  List<InventoryLineItem> _countedLines = [];

  bool _loading = false;
  bool _cameraOpen = false;
  String? _statusMessage;
  bool _isSuccessMessage = true;

  @override
  void initState() {
    super.initState();
    if (widget.connected) {
      unawaited(_loadOpenSessions());
    }
  }

  @override
  void didUpdateWidget(covariant PhysicalInventoryView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.connected && !oldWidget.connected) {
      unawaited(_loadOpenSessions());
    }
  }

  @override
  void dispose() {
    _barcodeController.dispose();
    _searchController.dispose();
    _barcodeFocus.dispose();
    super.dispose();
  }

  Future<void> _loadOpenSessions({int? autoSelectId}) async {
    if (!widget.connected) return;
    setState(() => _loading = true);
    try {
      // Charger uniquement les sessions ouvertes / en cours (Counting) créées depuis le bureau
      final allSessions = await widget.api.getInventorySessions(limit: 30);
      if (!mounted) return;

      final openList = allSessions.where((s) => s.status == 'Counting' || s.status == 'Draft').toList();

      setState(() {
        _openSessions = openList;
        if (autoSelectId != null) {
          _selectedSession = openList.where((s) => s.sessionId == autoSelectId).firstOrNull ??
              (openList.isNotEmpty ? openList.first : null);
        } else if (_selectedSession != null) {
          _selectedSession = openList.where((s) => s.sessionId == _selectedSession!.sessionId).firstOrNull ??
              (openList.isNotEmpty ? openList.first : null);
        } else if (openList.isNotEmpty) {
          _selectedSession = openList.first;
        } else {
          _selectedSession = null;
        }
      });

      if (_selectedSession != null) {
        await _loadCountedLines(_selectedSession!.sessionId);
      }
    } catch (e) {
      if (mounted) _showMessage('Erreur chargement sessions : $e', isSuccess: false);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _loadCountedLines(int sessionId) async {
    try {
      final search = _searchController.text.trim();
      final lines = await widget.api.getInventorySessionLines(
        sessionId,
        search: search.isNotEmpty ? search : null,
      );
      if (!mounted) return;

      setState(() {
        _countedLines = lines;
      });
    } catch (_) {}
  }

  void _showMessage(String msg, {bool isSuccess = true}) {
    if (isSuccess) {
      unawaited(SystemSound.play(SystemSoundType.click));
    } else {
      unawaited(SystemSound.play(SystemSoundType.alert));
      HapticFeedback.vibrate();
    }
    setState(() {
      _statusMessage = msg;
      _isSuccessMessage = isSuccess;
    });
  }

  /// Traitement immédiat après scan ou saisie de code-barres
  Future<void> _handleBarcodeEntered(String rawBarcode) async {
    final barcode = rawBarcode.trim();
    if (barcode.isEmpty) return;

    if (_selectedSession == null) {
      _showMessage('Aucune session ouverte sélectionnée.', isSuccess: false);
      _barcodeController.clear();
      _scannerKey.currentState?.resume();
      return;
    }

    _barcodeController.clear();

    // Récupérer les infos existantes de la ligne dans la session
    InventoryLineItem? existingLine;
    try {
      existingLine = await widget.api.lookupInventoryLine(_selectedSession!.sessionId, barcode);
    } catch (_) {}

    if (!mounted) return;

    // Ouvrir directement la boîte de saisie de quantité entière (strict integer)
    await _promptQuantityForBarcode(barcode, existingLine);
  }

  /// Boîte de dialogue simple et rapide pour saisir la quantité existante (Entiers purs uniquement)
  Future<void> _promptQuantityForBarcode(String barcode, InventoryLineItem? existingLine) async {
    final qtyController = TextEditingController();
    final qtyFocusNode = FocusNode();

    // Suggestion : entier existant ou vide
    final initialInt = existingLine != null && existingLine.countedQty > 0
        ? existingLine.countedQty.toInt().toString()
        : '';
    qtyController.text = initialInt;

    final productName = existingLine?.productName ?? 'Code: $barcode';
    final lot = existingLine?.lotNumber;
    final lotInfo = (lot != null && lot.isNotEmpty && lot != '---') ? 'Lot: $lot' : '';
    final loc = existingLine?.locationName;
    final locInfo = (loc != null && loc.isNotEmpty && loc != '---') ? 'Empl: $loc' : '';
    final snapshotQty = (existingLine?.programQtySnapshot ?? 0.0).toInt();
    final unit = existingLine?.stockUnit ?? 'Unité';

    final confirmed = await showDialog<bool>(
      context: context,
      barrierDismissible: false, // Forcer l'utilisateur à valider ou annuler
      builder: (ctx) {
        return AlertDialog(
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          titlePadding: const EdgeInsets.fromLTRB(20, 20, 20, 10),
          contentPadding: const EdgeInsets.fromLTRB(20, 0, 20, 16),
          title: Row(
            children: [
              const Icon(Icons.qr_code_2, color: Color(0xFF007572), size: 28),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  productName,
                  style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ],
          ),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (lotInfo.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 4),
                    child: Text(
                      lotInfo,
                      style: const TextStyle(fontSize: 13, fontWeight: FontWeight.bold, color: Colors.black87),
                      softWrap: true,
                    ),
                  ),
                Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: Text(
                    '🏷️ Code : $barcode${locInfo.isNotEmpty ? " • $locInfo" : ""}',
                    style: const TextStyle(fontSize: 11, color: Color(0xFF556677), fontWeight: FontWeight.w500),
                    softWrap: true,
                  ),
                ),
                if (snapshotQty > 0)
                  Container(
                    margin: const EdgeInsets.only(bottom: 12),
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                    decoration: BoxDecoration(
                      color: const Color(0xFFE8F8F0),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        const Text('Stock attendu :', style: TextStyle(fontSize: 12, color: Color(0xFF007572))),
                        Text('$snapshotQty $unit', style: const TextStyle(fontSize: 13, fontWeight: FontWeight.bold, color: Color(0xFF007572))),
                      ],
                    ),
                  ),
                const Text(
                  'Quantité réelle comptée (Entier) *',
                  style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
                ),
                const SizedBox(height: 6),
                TextField(
                  controller: qtyController,
                  focusNode: qtyFocusNode,
                  keyboardType: TextInputType.number,
                  inputFormatters: [FilteringTextInputFormatter.digitsOnly], // STRICT INTEGER - AUCUNE VIRGULE
                  autofocus: true,
                  textAlign: TextAlign.center,
                  style: const TextStyle(fontSize: 28, fontWeight: FontWeight.bold, color: Color(0xFF007572)),
                  decoration: InputDecoration(
                    hintText: 'Ex: 12',
                    hintStyle: TextStyle(fontSize: 16, color: Colors.grey.shade400),
                    contentPadding: const EdgeInsets.symmetric(vertical: 12),
                    border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                  ),
                  onSubmitted: (_) => Navigator.pop(ctx, true),
                ),
                const SizedBox(height: 10),
                // Boutons d'aide rapide pour saisie directe en un clic
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    _quickQtyButton('1', () => qtyController.text = '1'),
                    _quickQtyButton('5', () => qtyController.text = '5'),
                    _quickQtyButton('10', () => qtyController.text = '10'),
                    if (snapshotQty > 0)
                      _quickQtyButton('$snapshotQty', () => qtyController.text = snapshotQty.toString()),
                    _quickQtyButton('+1', () {
                      final cur = int.tryParse(qtyController.text) ?? 0;
                      qtyController.text = (cur + 1).toString();
                    }),
                  ],
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx, false), // Annuler -> NE PAS INCLURE
              child: const Text('Annuler (Ne pas inclure)', style: TextStyle(color: Colors.red)),
            ),
            FilledButton.icon(
              style: FilledButton.styleFrom(backgroundColor: const Color(0xFF007572)),
              onPressed: () => Navigator.pop(ctx, true),
              icon: const Icon(Icons.check, size: 18),
              label: const Text('Valider'),
            ),
          ],
        );
      },
    );

    // Si l'utilisateur a annulé ou fermé -> Ne rien faire, ne pas inclure
    if (confirmed != true) {
      _showMessage('Scan ignoré (quantité non saisie).', isSuccess: false);
      _rearmScanner();
      return;
    }

    final rawText = qtyController.text.trim();
    if (rawText.isEmpty) {
      _showMessage('Aucune quantité saisie. Article non inclus.', isSuccess: false);
      _rearmScanner();
      return;
    }

    final enteredQty = int.tryParse(rawText);
    if (enteredQty == null) {
      _showMessage('Nombre invalide. Article non inclus.', isSuccess: false);
      _rearmScanner();
      return;
    }

    // Enregistrer la quantité entière comptée dans la session
    setState(() => _loading = true);
    try {
      final res = await widget.api.scanInventoryBarcode(
        _selectedSession!.sessionId,
        barcode,
        qty: enteredQty.toDouble(),
        userId: widget.currentUser?.userId,
        replaceCounted: true,
      );

      HapticFeedback.mediumImpact();
      final lineName = res.line?.productName ?? barcode;
      _showMessage('✓ $lineName : $enteredQty $unit enregistré(s)', isSuccess: true);

      // Recharger la liste
      await _loadCountedLines(_selectedSession!.sessionId);
    } catch (e) {
      _showMessage('Erreur enregistrement : $e', isSuccess: false);
    } finally {
      if (mounted) setState(() => _loading = false);
      _rearmScanner();
    }
  }

  Widget _quickQtyButton(String label, VoidCallback onTap) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(6),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        decoration: BoxDecoration(
          color: Colors.grey.shade200,
          borderRadius: BorderRadius.circular(6),
        ),
        child: Text(label, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
      ),
    );
  }

  void _rearmScanner() {
    _barcodeController.clear();
    _scannerKey.currentState?.resume();
    _barcodeFocus.requestFocus();
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        if (_loading) const LinearProgressIndicator(color: Color(0xFF007572)),

        // 1. En-tête compact de sélection de session ouverte
        _buildSessionSelectorBar(),

        // 2. Zone de message / feedback
        if (_statusMessage != null) _buildFeedbackBanner(),

        // 3. Zone principale de scan code-barres
        _buildScanInputCard(),

        // 4. Liste simple des articles de la session
        Expanded(child: _buildCountedList()),
      ],
    );
  }

  Widget _buildSessionSelectorBar() {
    return Container(
      color: Colors.white,
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      child: Row(
        children: [
          const Icon(Icons.assignment_turned_in, color: Color(0xFF007572), size: 22),
          const SizedBox(width: 8),
          Expanded(
            child: _openSessions.isEmpty
                ? const Text(
                    'Aucune session ouverte sur le bureau',
                    style: TextStyle(color: Colors.redAccent, fontSize: 12, fontWeight: FontWeight.bold),
                  )
                : DropdownButtonHideUnderline(
                    child: DropdownButton<int>(
                      isExpanded: true,
                      value: _selectedSession?.sessionId,
                      hint: const Text('Choisir une session ouverte...'),
                      items: _openSessions.map((s) {
                        return DropdownMenuItem<int>(
                          value: s.sessionId,
                          child: Text(
                            '#${s.sessionId} - ${s.sessionName}',
                            style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
                            overflow: TextOverflow.ellipsis,
                          ),
                        );
                      }).toList(),
                      onChanged: (id) {
                        if (id != null) {
                          final found = _openSessions.where((s) => s.sessionId == id).firstOrNull;
                          setState(() => _selectedSession = found);
                          if (found != null) {
                            _loadCountedLines(found.sessionId);
                          }
                        }
                      },
                    ),
                  ),
          ),
          IconButton(
            tooltip: 'Actualiser sessions',
            icon: const Icon(Icons.refresh, size: 20),
            onPressed: () => _loadOpenSessions(),
          ),
        ],
      ),
    );
  }

  Widget _buildFeedbackBanner() {
    final color = _isSuccessMessage ? Colors.green : Colors.red;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      color: color.withOpacity(0.1),
      child: Row(
        children: [
          Icon(_isSuccessMessage ? Icons.check_circle : Icons.info, color: color, size: 16),
          const SizedBox(width: 6),
          Expanded(
            child: Text(
              _statusMessage!,
              style: TextStyle(color: color, fontWeight: FontWeight.w600, fontSize: 12),
              overflow: TextOverflow.ellipsis,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildScanInputCard() {
    return Card(
      margin: const EdgeInsets.fromLTRB(10, 8, 10, 4),
      elevation: 2,
      child: Padding(
        padding: const EdgeInsets.all(10),
        child: Column(
          children: [
            if (_cameraOpen) ...[
              ScannerCameraWidget(
                key: _scannerKey,
                onCodeDetected: (code) => _handleBarcodeEntered(code),
                onClose: () => setState(() => _cameraOpen = false),
              ),
              const SizedBox(height: 8),
            ],
            Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _barcodeController,
                    focusNode: _barcodeFocus,
                    autofocus: true,
                    style: const TextStyle(fontSize: 15, fontWeight: FontWeight.bold),
                    decoration: InputDecoration(
                      hintText: 'Scanner ou saisir code-barres...',
                      prefixIcon: const Icon(Icons.barcode_reader, color: Color(0xFF007572)),
                      contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                      border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
                      suffixIcon: _barcodeController.text.isNotEmpty
                          ? IconButton(
                              icon: const Icon(Icons.clear),
                              onPressed: () => _barcodeController.clear(),
                            )
                          : null,
                    ),
                    onSubmitted: (code) => _handleBarcodeEntered(code),
                  ),
                ),
                const SizedBox(width: 8),
                IconButton.filled(
                  tooltip: _cameraOpen ? 'Fermer Caméra' : 'Ouvrir Caméra',
                  style: IconButton.styleFrom(backgroundColor: const Color(0xFF007572)),
                  onPressed: () {
                    setState(() => _cameraOpen = !_cameraOpen);
                    if (_cameraOpen) {
                      _scannerKey.currentState?.resume();
                    }
                  },
                  icon: Icon(_cameraOpen ? Icons.videocam_off : Icons.camera_alt),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildCountedList() {
    // Filtrer par recherche
    final search = _searchController.text.trim().toLowerCase();
    final displayed = _countedLines.where((l) {
      if (search.isEmpty) return true;
      return l.productName.toLowerCase().contains(search) ||
          l.internalBarcode.toLowerCase().contains(search) ||
          (l.lotNumber != null && l.lotNumber!.toLowerCase().contains(search));
    }).toList();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(12, 6, 12, 4),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'Articles (${displayed.length})',
                style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13, color: Color(0xFF556677)),
              ),
              SizedBox(
                width: 150,
                height: 32,
                child: TextField(
                  controller: _searchController,
                  style: const TextStyle(fontSize: 12),
                  decoration: InputDecoration(
                    hintText: 'Filtrer...',
                    prefixIcon: const Icon(Icons.search, size: 16),
                    contentPadding: EdgeInsets.zero,
                    border: OutlineInputBorder(borderRadius: BorderRadius.circular(20)),
                  ),
                  onChanged: (_) => setState(() {}),
                ),
              ),
            ],
          ),
        ),
        Expanded(
          child: displayed.isEmpty
              ? Center(
                  child: Text(
                    _selectedSession == null
                        ? 'Sélectionnez une session ouverte pour commencer le comptage.'
                        : 'Aucun article. Scannez un code-barres pour enregistrer la quantité.',
                    style: const TextStyle(color: Colors.grey, fontSize: 13),
                    textAlign: TextAlign.center,
                  ),
                )
              : ListView.separated(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  itemCount: displayed.length,
                  separatorBuilder: (_, __) => const SizedBox(height: 4),
                  itemBuilder: (context, index) {
                    final line = displayed[index];
                    final isCounted = line.countedQty > 0 || line.lineStatus != 'NOT_COUNTED';
                    final color = line.lineStatus == 'OK'
                        ? Colors.green
                        : (line.lineStatus == 'SHORT'
                            ? Colors.red
                            : (line.lineStatus == 'EXCESS' ? Colors.blue : Colors.grey));

                    final countedInt = line.countedQty.toInt();
                    final snapshotInt = line.programQtySnapshot.toInt();

                    return Card(
                      margin: EdgeInsets.zero,
                      elevation: 0.5,
                      child: ListTile(
                        dense: true,
                        contentPadding: const EdgeInsets.symmetric(horizontal: 10, vertical: 0),
                        title: Text(
                          line.productName,
                          style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
                          overflow: TextOverflow.ellipsis,
                        ),
                        subtitle: Text(
                          'Lot: ${line.lotNumber} | Code: ${line.internalBarcode}',
                          style: const TextStyle(fontSize: 11, color: Colors.grey),
                        ),
                        trailing: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Column(
                              mainAxisAlignment: MainAxisAlignment.center,
                              crossAxisAlignment: CrossAxisAlignment.end,
                              children: [
                                Text(
                                  isCounted ? 'Compté: $countedInt' : 'Non compté',
                                  style: TextStyle(
                                    fontWeight: FontWeight.bold,
                                    fontSize: 12,
                                    color: isCounted ? color : Colors.grey,
                                  ),
                                ),
                                Text(
                                  'Attendu: $snapshotInt',
                                  style: const TextStyle(fontSize: 10, color: Colors.grey),
                                ),
                              ],
                            ),
                            const SizedBox(width: 6),
                            IconButton(
                              icon: const Icon(Icons.edit, size: 18, color: Color(0xFF007572)),
                              onPressed: () => _promptQuantityForBarcode(line.internalBarcode, line),
                            ),
                          ],
                        ),
                      ),
                    );
                  },
                ),
        ),
      ],
    );
  }
}
