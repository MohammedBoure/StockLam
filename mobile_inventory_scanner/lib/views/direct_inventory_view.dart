// mobile_inventory_scanner/lib/views/direct_inventory_view.dart

import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../api_client.dart';
import '../models.dart';
import 'scanner_camera_widget.dart';

class DirectInventoryView extends StatefulWidget {
  const DirectInventoryView({
    super.key,
    required this.api,
    required this.connected,
    this.currentUser,
  });

  final ApiClient api;
  final bool connected;
  final AuthUser? currentUser;

  @override
  State<DirectInventoryView> createState() => _DirectInventoryViewState();
}

class _DirectInventoryViewState extends State<DirectInventoryView> {
  final TextEditingController _barcodeController = TextEditingController();
  final FocusNode _barcodeFocus = FocusNode();

  bool _loading = false;
  bool _cameraOpen = false;
  String? _errorMessage;
  String? _successMessage;

  ProductDetails? _product;
  List<BatchDetails> _batches = [];
  int? _recommendedBatchId;
  String? _lastSearchedBarcode;

  List<LocationItem> _locations = [];

  @override
  void initState() {
    super.initState();
    if (widget.connected) {
      unawaited(_loadLocations());
    }
  }

  @override
  void didUpdateWidget(covariant DirectInventoryView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.connected && !oldWidget.connected) {
      unawaited(_loadLocations());
    }
  }

  @override
  void dispose() {
    _barcodeController.dispose();
    _barcodeFocus.dispose();
    super.dispose();
  }

  Future<void> _loadLocations() async {
    try {
      final locs = await widget.api.getLocations();
      if (mounted) setState(() => _locations = locs);
    } catch (_) {}
  }

  Future<void> _performLookup([String? code]) async {
    final barcode = (code ?? _barcodeController.text).trim();
    if (barcode.isEmpty) return;

    if (!widget.connected) {
      setState(() => _errorMessage = 'Connectez d’abord un serveur StockLam.');
      return;
    }

    setState(() {
      _loading = true;
      _errorMessage = null;
      _successMessage = null;
      _cameraOpen = false;
      _lastSearchedBarcode = barcode;
    });

    try {
      final result = await widget.api.lookupBarcode(barcode);
      if (!mounted) return;

      if (result['found'] == false) {
        setState(() {
          _product = null;
          _batches = [];
          _recommendedBatchId = null;
          _errorMessage = result['message'] ?? 'Aucun produit ou lot trouvé pour ce code.';
        });
        return;
      }

      final prodJson = result['product'] as Map<String, dynamic>?;
      final rawBatches = result['batches'] as List<dynamic>? ?? [];

      setState(() {
        _product = prodJson != null ? ProductDetails.fromJson(prodJson) : null;
        _batches = rawBatches.map((item) => BatchDetails.fromJson(item as Map<String, dynamic>)).toList();
        _recommendedBatchId = result['recommended_batch_id'] as int?;
        _barcodeController.text = barcode;
      });
      HapticFeedback.lightImpact();
    } catch (e) {
      if (mounted) {
        setState(() {
          _errorMessage = 'Erreur lors de la recherche : $e';
        });
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  void _onCameraDetected(String code) {
    _barcodeController.text = code;
    setState(() => _cameraOpen = false);
    unawaited(_performLookup(code));
  }

  Future<void> _showConsumeDialog(BatchDetails batch) async {
    int qty = 1;
    final maxQty = batch.quantityCurrent.toInt();
    final notesController = TextEditingController();

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDialogState) => AlertDialog(
          title: Row(
            children: [
              const Icon(Icons.trending_down, color: Colors.red),
              const SizedBox(width: 8),
              const Text('Consommation Directe'),
            ],
          ),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  _product?.productName ?? 'Produit',
                  style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15),
                ),
                const SizedBox(height: 4),
                Text('Lot : ${batch.lotNumber}  |  Exp : ${batch.expiryDate}'),
                Text('Emplacement : ${batch.locationName}'),
                Text('Stock disponible : $maxQty ${_product?.stockUnit ?? 'Unités'}'),
                const Divider(height: 24),
                const Text('Quantité à consommer :', style: TextStyle(fontWeight: FontWeight.bold)),
                const SizedBox(height: 8),
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    IconButton.filledTonal(
                      onPressed: qty > 1 ? () => setDialogState(() => qty--) : null,
                      icon: const Icon(Icons.remove),
                    ),
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 20),
                      child: Text(
                        '$qty',
                        style: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
                      ),
                    ),
                    IconButton.filledTonal(
                      onPressed: qty < maxQty ? () => setDialogState(() => qty++) : null,
                      icon: const Icon(Icons.add),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: notesController,
                  decoration: const InputDecoration(
                    labelText: 'Remarque / Patient (Optionnel)',
                    isDense: true,
                  ),
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Annuler'),
            ),
            FilledButton(
              style: FilledButton.styleFrom(backgroundColor: const Color(0xFFC0392B)),
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('Valider la sortie'),
            ),
          ],
        ),
      ),
    );

    if (confirmed != true) return;

    await _executeConsume(
      batch: batch,
      qty: qty,
      allowFefoOverride: false,
      notes: notesController.text.trim(),
    );
  }

  Future<void> _executeConsume({
    required BatchDetails batch,
    required int qty,
    required bool allowFefoOverride,
    String? notes,
  }) async {
    setState(() => _loading = true);
    try {
      final res = await widget.api.consumeStock(
        batchId: batch.batchId,
        qty: qty,
        userId: widget.currentUser?.userId,
        allowFefoOverride: allowFefoOverride,
        notes: notes,
      );

      if (!mounted) return;

      // Si violation FEFO
      if (res['fefo_violation'] == true) {
        final violation = FefoViolationData.fromJson(res);
        final action = await _showFefoWarningDialog(violation, batch, qty);
        if (action == 'recommended') {
          final recId = violation.recommendedBatch['Batch_ID'] as int?;
          final recBatch = _batches.firstWhere((b) => b.batchId == recId, orElse: () => batch);
          await _executeConsume(
            batch: recBatch,
            qty: qty,
            allowFefoOverride: false,
            notes: notes,
          );
        } else if (action == 'override') {
          await _executeConsume(
            batch: batch,
            qty: qty,
            allowFefoOverride: true,
            notes: notes,
          );
        }
        return;
      }

      if (res['success'] == true) {
        HapticFeedback.mediumImpact();
        setState(() {
          _successMessage = '✅ Consommation de $qty unité(s) validée avec succès.';
        });
        if (_lastSearchedBarcode != null) {
          unawaited(_performLookup(_lastSearchedBarcode));
        }
      } else {
        setState(() => _errorMessage = res['message'] ?? 'Échec de la consommation.');
      }
    } catch (e) {
      if (mounted) setState(() => _errorMessage = 'Erreur: $e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<String?> _showFefoWarningDialog(
    FefoViolationData violation,
    BatchDetails currentBatch,
    int qty,
  ) async {
    final recLot = violation.recommendedBatch['Lot_Number'] ?? '---';
    final recExp = violation.recommendedBatch['Expiry_Date'] ?? '---';
    final recBarcode = violation.recommendedBatch['Internal_Barcode'] ?? '';
    final recLoc = violation.recommendedBatch['Location_Name'] ?? 'Emplacement';

    return showDialog<String>(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFFFFFDF5),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: const Row(
          children: [
            Icon(Icons.warning_amber_rounded, color: Colors.orange, size: 28),
            SizedBox(width: 8),
            Expanded(
              child: Text(
                'Respect du FEFO',
                style: TextStyle(fontWeight: FontWeight.bold, color: Color(0xFF856404), fontSize: 16),
              ),
            ),
          ],
        ),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Text(
                '⚠️ Vous tentez de consommer un lot plus récent alors qu’un lot plus ancien est disponible :',
                style: TextStyle(color: Color(0xFF856404), fontSize: 13, fontWeight: FontWeight.w500),
              ),
              const SizedBox(height: 12),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: const Color(0xFFD4EDDA),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: const Color(0xFFC3E6CB), width: 1.5),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('⭐ Lot Recommandé (Plus ancien) :', style: TextStyle(fontWeight: FontWeight.bold, color: Color(0xFF155724), fontSize: 13)),
                    const SizedBox(height: 4),
                    Text('Lot : $recLot', style: const TextStyle(fontWeight: FontWeight.bold, color: Color(0xFF155724), fontSize: 14), softWrap: true),
                    if (recBarcode.toString().isNotEmpty)
                      Padding(
                        padding: const EdgeInsets.symmetric(vertical: 2),
                        child: Text('🏷️ Code-barres : $recBarcode', style: const TextStyle(fontFamily: 'monospace', fontSize: 11, fontWeight: FontWeight.w600, color: Color(0xFF155724)), softWrap: true),
                      ),
                    Text('Exp : $recExp  |  📍 $recLoc', style: const TextStyle(color: Color(0xFF155724), fontSize: 12)),
                  ],
                ),
              ),
              const SizedBox(height: 8),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: const Color(0xFFFFF0ED),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: const Color(0xFFF5C6CB), width: 1.5),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('✋ Lot Sélectionné (Scanné) :', style: TextStyle(fontWeight: FontWeight.bold, color: Color(0xFF721C24), fontSize: 13)),
                    const SizedBox(height: 4),
                    Text('Lot : ${currentBatch.lotNumber}', style: const TextStyle(fontWeight: FontWeight.bold, color: Color(0xFF721C24), fontSize: 14), softWrap: true),
                    if (currentBatch.internalBarcode.isNotEmpty)
                      Padding(
                        padding: const EdgeInsets.symmetric(vertical: 2),
                        child: Text('🏷️ Code-barres : ${currentBatch.internalBarcode}', style: const TextStyle(fontFamily: 'monospace', fontSize: 11, fontWeight: FontWeight.w600, color: Color(0xFF721C24)), softWrap: true),
                      ),
                    Text('Exp : ${currentBatch.expiryDate}  |  📍 ${currentBatch.locationName}', style: const TextStyle(color: Color(0xFF721C24), fontSize: 12)),
                  ],
                ),
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, null),
            child: const Text('Annuler'),
          ),
          OutlinedButton(
            onPressed: () => Navigator.pop(ctx, 'override'),
            child: const Text('Forcer ce lot'),
          ),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: const Color(0xFF27AE60)),
            onPressed: () => Navigator.pop(ctx, 'recommended'),
            child: const Text('Prendre le lot recommandé'),
          ),
        ],
      ),
    );
  }

  Future<void> _showTransferDialog(BatchDetails batch) async {
    if (_locations.isEmpty) {
      await _loadLocations();
      if (!mounted) return;
    }

    int qty = 1;
    final maxQty = batch.quantityCurrent.toInt();
    int? selectedLocId = _locations.isNotEmpty
        ? (_locations.firstWhere((l) => l.locationId != batch.locationId, orElse: () => _locations.first).locationId)
        : null;

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDialogState) => AlertDialog(
          title: Row(
            children: [
              const Icon(Icons.local_shipping, color: Color(0xFF2980B9)),
              const SizedBox(width: 8),
              const Text('Transfert d’Emplacement'),
            ],
          ),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  _product?.productName ?? 'Produit',
                  style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15),
                ),
                const SizedBox(height: 4),
                Text('Lot : ${batch.lotNumber}  |  Stock actuel : $maxQty'),
                Text('Source : 📍 ${batch.locationName}', style: const TextStyle(color: Colors.black54)),
                const Divider(height: 24),
                const Text('Quantité à transférer :', style: TextStyle(fontWeight: FontWeight.bold)),
                const SizedBox(height: 8),
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    IconButton.filledTonal(
                      onPressed: qty > 1 ? () => setDialogState(() => qty--) : null,
                      icon: const Icon(Icons.remove),
                    ),
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 20),
                      child: Text(
                        '$qty',
                        style: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
                      ),
                    ),
                    IconButton.filledTonal(
                      onPressed: qty < maxQty ? () => setDialogState(() => qty++) : null,
                      icon: const Icon(Icons.add),
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                const Text('Nouvel emplacement (Destination) :', style: TextStyle(fontWeight: FontWeight.bold)),
                const SizedBox(height: 6),
                DropdownButtonFormField<int>(
                  isExpanded: true,
                  initialValue: selectedLocId,
                  decoration: const InputDecoration(
                    isDense: true,
                    prefixIcon: Icon(Icons.location_on),
                  ),
                  items: _locations
                      .where((loc) => loc.locationId != batch.locationId)
                      .map((loc) => DropdownMenuItem<int>(
                            value: loc.locationId,
                            child: Text(loc.fullPath, overflow: TextOverflow.ellipsis),
                          ))
                      .toList(),
                  onChanged: (val) => setDialogState(() => selectedLocId = val),
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Annuler'),
            ),
            FilledButton(
              style: FilledButton.styleFrom(backgroundColor: const Color(0xFF2980B9)),
              onPressed: selectedLocId != null ? () => Navigator.pop(ctx, true) : null,
              child: const Text('Valider le transfert'),
            ),
          ],
        ),
      ),
    );

    if (confirmed != true || selectedLocId == null) return;

    setState(() => _loading = true);
    try {
      final res = await widget.api.transferStock(
        batchId: batch.batchId,
        targetLocationId: selectedLocId!,
        qty: qty,
        userId: widget.currentUser?.userId,
      );

      if (!mounted) return;

      if (res['success'] == true) {
        HapticFeedback.mediumImpact();
        setState(() {
          _successMessage = '✅ Transfert de $qty unité(s) vers ${res['target_location_name']} effectué.';
        });
        if (_lastSearchedBarcode != null) {
          unawaited(_performLookup(_lastSearchedBarcode));
        }
      } else {
        setState(() => _errorMessage = res['message'] ?? 'Échec du transfert.');
      }
    } catch (e) {
      if (mounted) setState(() => _errorMessage = 'Erreur lors du transfert : $e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(12),
      children: [
        // 1. Barre de Recherche et Scan
        Card(
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: TextField(
                        controller: _barcodeController,
                        focusNode: _barcodeFocus,
                        decoration: const InputDecoration(
                          labelText: 'Code-barres ou N° Lot',
                          hintText: 'Ex: 613000101 ou scannez...',
                          prefixIcon: Icon(Icons.qr_code_scanner),
                        ),
                        textInputAction: TextInputAction.search,
                        onSubmitted: (val) => unawaited(_performLookup(val)),
                      ),
                    ),
                    const SizedBox(width: 8),
                    IconButton.filledTonal(
                      tooltip: _cameraOpen ? 'Fermer caméra' : 'Scanner avec la caméra',
                      onPressed: () => setState(() => _cameraOpen = !_cameraOpen),
                      icon: Icon(_cameraOpen ? Icons.close : Icons.camera_alt),
                    ),
                    const SizedBox(width: 4),
                    FilledButton(
                      onPressed: _loading ? null : () => unawaited(_performLookup()),
                      child: const Icon(Icons.search),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),

        const SizedBox(height: 10),

        // 2. Caméra intégrée
        if (_cameraOpen) ...[
          ScannerCameraWidget(
            onCodeDetected: _onCameraDetected,
            onClose: () => setState(() => _cameraOpen = false),
          ),
          const SizedBox(height: 10),
        ],

        // 3. Messages de statut
        if (_errorMessage != null) ...[
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: const Color(0xFFFDEEED),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: const Color(0xFFF5C6CB)),
            ),
            child: Row(
              children: [
                const Icon(Icons.error_outline, color: Colors.red),
                const SizedBox(width: 8),
                Expanded(child: Text(_errorMessage!, style: const TextStyle(color: Colors.red))),
              ],
            ),
          ),
          const SizedBox(height: 10),
        ],

        if (_successMessage != null) ...[
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: const Color(0xFFE8F8F0),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: const Color(0xFFC3E6CB)),
            ),
            child: Row(
              children: [
                const Icon(Icons.check_circle_outline, color: Color(0xFF27AE60)),
                const SizedBox(width: 8),
                Expanded(child: Text(_successMessage!, style: const TextStyle(color: Color(0xFF155724)))),
              ],
            ),
          ),
          const SizedBox(height: 10),
        ],

        // 4. Fiche Produit
        if (_product != null) ...[
          _buildProductCard(),
          const SizedBox(height: 12),
        ],

        // 5. Liste des Lots
        if (_batches.isNotEmpty) ...[
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 4),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  'Lots disponibles (${_batches.length})',
                  style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                ),
                const Text('Priorité FEFO', style: TextStyle(color: Color(0xFF007572), fontWeight: FontWeight.w600, fontSize: 12)),
              ],
            ),
          ),
          ..._batches.map(_buildBatchCard),
        ] else if (_product != null && !_loading) ...[
          const Card(
            child: Padding(
              padding: EdgeInsets.all(24),
              child: Center(
                child: Text('Aucun lot actif disponible en stock pour ce produit.', style: TextStyle(color: Colors.black54)),
              ),
            ),
          ),
        ],
      ],
    );
  }

  Widget _buildProductCard() {
    final prod = _product!;
    final totalStock = _batches.fold<double>(0, (sum, b) => sum + b.quantityCurrent);

    return Card(
      elevation: 1,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(10),
        side: const BorderSide(color: Color(0xFF007572), width: 1.5),
      ),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const CircleAvatar(
                  backgroundColor: Color(0xFFE8F8F0),
                  child: Icon(Icons.inventory_2, color: Color(0xFF007572)),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        prod.productName,
                        style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                      ),
                      Text(
                        '${prod.familyName}  •  ${prod.manufName}',
                        style: const TextStyle(color: Colors.black54, fontSize: 12),
                      ),
                    ],
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                  decoration: BoxDecoration(
                    color: totalStock > 0 ? const Color(0xFFE8F8F0) : const Color(0xFFFDEEED),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Text(
                    '${totalStock.toInt()} ${prod.stockUnit}',
                    style: TextStyle(
                      fontWeight: FontWeight.bold,
                      color: totalStock > 0 ? const Color(0xFF27AE60) : Colors.red,
                    ),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildBatchCard(BatchDetails batch) {
    final isRec = (batch.batchId == _recommendedBatchId);

    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(10),
        side: BorderSide(
          color: isRec ? const Color(0xFF27AE60) : const Color(0xFFE2E8F0),
          width: isRec ? 2.0 : 1.0,
        ),
      ),
      color: isRec ? const Color(0xFFF4FBF7) : Colors.white,
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                if (isRec) ...[
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                    decoration: BoxDecoration(
                      color: const Color(0xFF27AE60),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: const Text(
                      '⭐ RECOMMANDÉ (FEFO)',
                      style: TextStyle(color: Colors.white, fontSize: 11, fontWeight: FontWeight.bold),
                    ),
                  ),
                  const Spacer(),
                ] else ...[
                  const Spacer(),
                ],
                Text(
                  'Qté : ${batch.quantityCurrent.toInt()}',
                  style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15),
                ),
              ],
            ),
            const SizedBox(height: 6),
            Wrap(
              spacing: 8,
              runSpacing: 4,
              children: [
                Text(
                  'Lot : ${batch.lotNumber}',
                  style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
                  softWrap: true,
                ),
                Text(
                  'Exp : ${batch.expiryDate}',
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    color: isRec ? const Color(0xFFC0392B) : Colors.black87,
                  ),
                ),
              ],
            ),
            if (batch.internalBarcode.isNotEmpty)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 2),
                child: Text(
                  '🏷️ Code-barres : ${batch.internalBarcode}',
                  style: const TextStyle(fontFamily: 'monospace', fontSize: 11, color: Colors.black87),
                  softWrap: true,
                ),
              ),
            const SizedBox(height: 2),
            Row(
              children: [
                const Icon(Icons.location_on, size: 16, color: Colors.black54),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    batch.locationName,
                    style: const TextStyle(color: Colors.black54, fontSize: 12),
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ],
            ),
            const Divider(height: 16),
            Row(
              children: [
                Expanded(
                  child: FilledButton.tonalIcon(
                    style: FilledButton.styleFrom(
                      backgroundColor: const Color(0xFFFDEEED),
                      foregroundColor: const Color(0xFFC0392B),
                    ),
                    onPressed: _loading ? null : () => _showConsumeDialog(batch),
                    icon: const Icon(Icons.trending_down, size: 18),
                    label: const Text('Consommer'),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: FilledButton.tonalIcon(
                    style: FilledButton.styleFrom(
                      backgroundColor: const Color(0xFFEBF5FB),
                      foregroundColor: const Color(0xFF2980B9),
                    ),
                    onPressed: _loading ? null : () => _showTransferDialog(batch),
                    icon: const Icon(Icons.local_shipping, size: 18),
                    label: const Text('Transférer'),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
