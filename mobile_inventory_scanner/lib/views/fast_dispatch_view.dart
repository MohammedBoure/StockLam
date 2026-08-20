// mobile_inventory_scanner/lib/views/fast_dispatch_view.dart

import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../api_client.dart';
import '../models.dart';
import 'scanner_camera_widget.dart';

class FastDispatchView extends StatefulWidget {
  const FastDispatchView({
    super.key,
    required this.api,
    required this.connected,
    this.currentUser,
  });

  final ApiClient api;
  final bool connected;
  final AuthUser? currentUser;

  @override
  State<FastDispatchView> createState() => _FastDispatchViewState();
}

class _FastDispatchViewState extends State<FastDispatchView> {
  final TextEditingController _barcodeController = TextEditingController();
  final FocusNode _barcodeFocus = FocusNode();

  String _mode = 'consume'; // 'consume' or 'transfer'
  bool _loading = false;
  bool _cameraOpen = false;
  String? _errorMessage;
  String? _successMessage;

  final List<BulkDispatchItem> _items = [];
  List<LocationItem> _locations = [];
  int? _commonTargetLocationId;

  @override
  void initState() {
    super.initState();
    if (widget.connected) {
      unawaited(_loadLocations());
    }
  }

  @override
  void didUpdateWidget(covariant FastDispatchView oldWidget) {
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
      if (mounted) {
        setState(() {
          _locations = locs;
          if (_locations.isNotEmpty && _commonTargetLocationId == null) {
            _commonTargetLocationId = _locations.first.locationId;
          }
        });
      }
    } catch (_) {}
  }

  Future<void> _processBarcodeScan([String? code]) async {
    final barcode = (code ?? _barcodeController.text).trim();
    if (barcode.isEmpty) return;

    if (!widget.connected) {
      setState(() => _errorMessage = 'Connectez d’abord un ordinateur ModernStock.');
      return;
    }

    setState(() {
      _loading = true;
      _errorMessage = null;
      _successMessage = null;
    });

    try {
      final result = await widget.api.lookupBarcode(barcode);
      if (!mounted) return;

      if (result['found'] == false) {
        setState(() {
          _errorMessage = result['message'] ?? 'Aucun produit ou lot trouvé pour "$barcode".';
        });
        HapticFeedback.vibrate();
        return;
      }

      final prodJson = result['product'] as Map<String, dynamic>?;
      final rawBatches = result['batches'] as List<dynamic>? ?? [];
      final prod = prodJson != null ? ProductDetails.fromJson(prodJson) : null;
      final batches = rawBatches
          .map((item) => BatchDetails.fromJson(item as Map<String, dynamic>))
          .where((b) => b.quantityCurrent > 0)
          .toList();

      if (batches.isEmpty) {
        setState(() {
          _errorMessage = 'Aucun lot en stock pour ${prod?.productName ?? barcode}.';
        });
        return;
      }

      // Sélection du lot:
      // Si un seul lot ou si le scan correspond exactement à un lot spécifique
      BatchDetails selectedBatch = batches.first;
      final matched = batches.where((b) => b.isScannedMatch).toList();
      if (matched.isNotEmpty) {
        selectedBatch = matched.first;
      } else {
        final recId = result['recommended_batch_id'] as int?;
        if (recId != null) {
          selectedBatch = batches.firstWhere((b) => b.batchId == recId, orElse: () => batches.first);
        }
      }

      // Si plusieurs lots et aucun scan précis, permettre le choix si nécessaire
      if (batches.length > 1 && matched.isEmpty) {
        final chosen = await _showBatchPickerDialog(prod?.productName ?? 'Produit', batches);
        if (chosen == null) return;
        selectedBatch = chosen;
      }

      _addItemToDispatch(prod, selectedBatch);
      _barcodeController.clear();
      _barcodeFocus.requestFocus();
      HapticFeedback.lightImpact();
    } catch (e) {
      if (mounted) setState(() => _errorMessage = 'Erreur lors du scan : $e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  void _addItemToDispatch(ProductDetails? prod, BatchDetails batch) {
    final existingIndex = _items.indexWhere((i) => i.batchId == batch.batchId);
    if (existingIndex >= 0) {
      final existing = _items[existingIndex];
      final maxQty = existing.currentQty.toInt();
      if (existing.qty < maxQty) {
        setState(() {
          existing.qty += 1;
          _successMessage = 'Quantité augmentée pour ${existing.productName} (Lot ${existing.lotNumber}) : ${existing.qty}';
        });
      } else {
        setState(() {
          _errorMessage = 'Quantité maximale disponible atteinte pour ce lot ($maxQty).';
        });
      }
      return;
    }

    int? initialTargetLocation;
    String? initialTargetName;
    if (_mode == 'transfer' && _locations.isNotEmpty) {
      final diffLoc = _locations.where((l) => l.locationId != batch.locationId).toList();
      if (diffLoc.isNotEmpty) {
        final matchedCommon = diffLoc.where((l) => l.locationId == _commonTargetLocationId).toList();
        final selected = matchedCommon.isNotEmpty ? matchedCommon.first : diffLoc.first;
        initialTargetLocation = selected.locationId;
        initialTargetName = selected.fullPath;
      }
    }

    final newItem = BulkDispatchItem(
      batchId: batch.batchId,
      productId: batch.productId,
      productName: prod?.productName ?? 'Produit #${batch.productId}',
      lotNumber: batch.lotNumber,
      expiryDate: batch.expiryDate,
      currentQty: batch.quantityCurrent,
      qty: 1,
      locationId: batch.locationId,
      locationName: batch.locationName,
      targetLocationId: initialTargetLocation,
      targetLocationName: initialTargetName,
      isRecommended: batch.isRecommended,
    );

    setState(() {
      _items.add(newItem);
      _successMessage = 'Ajouté : ${newItem.productName} (Lot ${newItem.lotNumber})';
    });
  }

  Future<BatchDetails?> _showBatchPickerDialog(String productName, List<BatchDetails> batches) async {
    return showDialog<BatchDetails>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text('Sélectionner un lot - $productName', style: const TextStyle(fontSize: 16)),
        content: SizedBox(
          width: double.maxFinite,
          child: ListView.separated(
            shrinkWrap: true,
            itemCount: batches.length,
            separatorBuilder: (_, __) => const Divider(height: 1),
            itemBuilder: (ctx, i) {
              final b = batches[i];
              return ListTile(
                dense: true,
                leading: Icon(
                  b.isRecommended ? Icons.star : Icons.inventory_2_outlined,
                  color: b.isRecommended ? const Color(0xFF27AE60) : Colors.grey,
                ),
                title: Text(
                  'Lot: ${b.lotNumber}  •  Qté: ${b.quantityCurrent.toInt()}',
                  style: TextStyle(fontWeight: b.isRecommended ? FontWeight.bold : FontWeight.normal),
                ),
                subtitle: Text('Exp: ${b.expiryDate}  |  📍 ${b.locationName}'),
                onTap: () => Navigator.pop(ctx, b),
              );
            },
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, null),
            child: const Text('Annuler'),
          ),
        ],
      ),
    );
  }

  void _applyCommonDestinationToAll() {
    if (_commonTargetLocationId == null || _locations.isEmpty) return;
    final locObj = _locations.firstWhere(
      (l) => l.locationId == _commonTargetLocationId,
      orElse: () => _locations.first,
    );

    int applied = 0;
    setState(() {
      for (final item in _items) {
        if (item.locationId != _commonTargetLocationId) {
          item.targetLocationId = _commonTargetLocationId;
          item.targetLocationName = locObj.fullPath;
          applied++;
        }
      }
      _successMessage = 'Emplacement "${locObj.locationName}" appliqué à $applied article(s).';
    });
  }

  Future<void> _executeBulkDispatch() async {
    if (_items.isEmpty) {
      setState(() => _errorMessage = 'La liste est vide. Scannez des articles à traiter.');
      return;
    }

    if (!widget.connected) {
      setState(() => _errorMessage = 'Connexion au serveur requise.');
      return;
    }

    // Validation mode transfert
    if (_mode == 'transfer') {
      for (int i = 0; i < _items.length; i++) {
        final item = _items[i];
        if (item.targetLocationId == null) {
          setState(() {
            _errorMessage = 'Veuillez choisir un emplacement de destination pour "${item.productName}".';
          });
          return;
        }
        if (item.targetLocationId == item.locationId) {
          setState(() {
            _errorMessage = 'L\'emplacement cible de "${item.productName}" doit différer de sa source.';
          });
          return;
        }
      }
    }

    final actionLabel = _mode == 'consume' ? 'Consommation' : 'Transfert';
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text('Confirmer la $actionLabel'),
        content: Text(
          'Voulez-vous exécuter la $actionLabel de ${_items.length} produit(s) (${_totalQuantity()} unités au total) ?'
          '\n\nUtilisateur : ${widget.currentUser?.fullName ?? widget.currentUser?.username ?? 'Opérateur standard'}',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Annuler'),
          ),
          FilledButton(
            style: FilledButton.styleFrom(
              backgroundColor: _mode == 'consume' ? const Color(0xFFC0392B) : const Color(0xFF2980B9),
            ),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Confirmer'),
          ),
        ],
      ),
    );

    if (confirmed != true) return;

    setState(() {
      _loading = true;
      _errorMessage = null;
      _successMessage = null;
    });

    try {
      final res = await widget.api.bulkDispatch(
        mode: _mode,
        items: _items,
        userId: widget.currentUser?.userId,
        allowFefoOverride: false,
      );

      if (!mounted) return;

      final successCount = res['success_count'] as int? ?? 0;
      final failedCount = res['failed_count'] as int? ?? 0;

      if (res['success'] == true || successCount > 0) {
        HapticFeedback.mediumImpact();
        await showDialog<void>(
          context: context,
          builder: (ctx) => AlertDialog(
            title: Row(
              children: [
                Icon(
                  failedCount == 0 ? Icons.check_circle : Icons.warning_amber_rounded,
                  color: failedCount == 0 ? const Color(0xFF27AE60) : Colors.orange,
                ),
                const SizedBox(width: 8),
                Text(failedCount == 0 ? 'Opération réussie' : 'Résultat partiel'),
              ],
            ),
            content: Text(
              '$successCount / ${_items.length} opération(s) enregistrée(s) avec succès.\n\n'
              'Traçabilité enregistrée pour : ${widget.currentUser?.fullName ?? 'Utilisateur'}.',
            ),
            actions: [
              FilledButton(
                onPressed: () => Navigator.pop(ctx),
                child: const Text('OK'),
              ),
            ],
          ),
        );

        setState(() {
          _items.clear();
          _successMessage = '✅ Opération groupée validée avec succès.';
        });
      } else {
        setState(() {
          _errorMessage = res['message'] ?? 'Échec du traitement de la liste.';
        });
      }
    } catch (e) {
      if (mounted) setState(() => _errorMessage = 'Erreur: $e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  int _totalQuantity() => _items.fold(0, (sum, item) => sum + item.qty);

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(12),
      children: [
        // 1. Sélecteur de Mode (Consommation vs Transfert)
        Card(
          child: Padding(
            padding: const EdgeInsets.all(8),
            child: Row(
              children: [
                Expanded(
                  child: ChoiceChip(
                    label: const Center(
                      child: Text('📉 CONSOMMATION', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
                    ),
                    selected: _mode == 'consume',
                    selectedColor: const Color(0xFFFDEEED),
                    labelStyle: TextStyle(
                      color: _mode == 'consume' ? const Color(0xFFC0392B) : Colors.black87,
                    ),
                    onSelected: (selected) {
                      if (selected) setState(() => _mode = 'consume');
                    },
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: ChoiceChip(
                    label: const Center(
                      child: Text('🚚 TRANSFERT', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
                    ),
                    selected: _mode == 'transfer',
                    selectedColor: const Color(0xFFEBF5FB),
                    labelStyle: TextStyle(
                      color: _mode == 'transfer' ? const Color(0xFF2980B9) : Colors.black87,
                    ),
                    onSelected: (selected) {
                      if (selected) setState(() => _mode = 'transfer');
                    },
                  ),
                ),
              ],
            ),
          ),
        ),

        const SizedBox(height: 10),

        // 2. Zone de Scan Rapide Multi-Produits
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
                        decoration: InputDecoration(
                          labelText: 'Scannez un code-barres à la suite',
                          hintText: 'Code-barres ou N° Lot...',
                          prefixIcon: const Icon(Icons.qr_code_scanner),
                          suffixIcon: _barcodeController.text.isNotEmpty
                              ? IconButton(
                                  icon: const Icon(Icons.clear),
                                  onPressed: () => setState(() => _barcodeController.clear()),
                                )
                              : null,
                        ),
                        textInputAction: TextInputAction.search,
                        onSubmitted: (val) => unawaited(_processBarcodeScan(val)),
                      ),
                    ),
                    const SizedBox(width: 8),
                    IconButton.filledTonal(
                      tooltip: _cameraOpen ? 'Fermer caméra' : 'Scanner caméra',
                      onPressed: () => setState(() => _cameraOpen = !_cameraOpen),
                      icon: Icon(_cameraOpen ? Icons.close : Icons.camera_alt),
                    ),
                    const SizedBox(width: 4),
                    FilledButton(
                      onPressed: _loading ? null : () => unawaited(_processBarcodeScan()),
                      child: const Icon(Icons.add),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),

        const SizedBox(height: 10),

        // 3. Caméra
        if (_cameraOpen) ...[
          ScannerCameraWidget(
            onCodeDetected: (code) {
              _barcodeController.text = code;
              unawaited(_processBarcodeScan(code));
            },
            onClose: () => setState(() => _cameraOpen = false),
          ),
          const SizedBox(height: 10),
        ],

        // 4. Messages d'état
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

        // 5. Emplacement commun pour le mode Transfert
        if (_mode == 'transfer' && _locations.isNotEmpty) ...[
          Card(
            color: const Color(0xFFF0F9FF),
            child: Padding(
              padding: const EdgeInsets.all(10),
              child: Row(
                children: [
                  const Icon(Icons.location_on, color: Color(0xFF2980B9)),
                  const SizedBox(width: 8),
                  Expanded(
                    child: DropdownButtonFormField<int>(
                      isExpanded: true,
                      initialValue: _commonTargetLocationId,
                      decoration: const InputDecoration(
                        labelText: 'Destination commune',
                        isDense: true,
                        filled: true,
                        fillColor: Colors.white,
                      ),
                      items: _locations.map((loc) {
                        return DropdownMenuItem<int>(
                          value: loc.locationId,
                          child: Text(loc.fullPath, overflow: TextOverflow.ellipsis),
                        );
                      }).toList(),
                      onChanged: (val) {
                        setState(() => _commonTargetLocationId = val);
                      },
                    ),
                  ),
                  const SizedBox(width: 8),
                  FilledButton.tonal(
                    onPressed: _items.isEmpty ? null : _applyCommonDestinationToAll,
                    child: const Text('Appliquer'),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 10),
        ],

        // 6. En-tête de la liste
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 4),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'Articles dans la liste (${_items.length})',
                style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
              ),
              if (_items.isNotEmpty)
                Text(
                  'Total : ${_totalQuantity()} unités',
                  style: const TextStyle(fontWeight: FontWeight.bold, color: Color(0xFF007572)),
                ),
            ],
          ),
        ),

        // 7. Liste des articles
        if (_items.isEmpty) ...[
          const Card(
            child: Padding(
              padding: EdgeInsets.all(32),
              child: Center(
                child: Column(
                  children: [
                    Icon(Icons.playlist_add, size: 48, color: Colors.black26),
                    SizedBox(height: 8),
                    Text(
                      'Aucun produit ajouté pour le moment.\nScannez des codes-barres pour remplir la liste rapide.',
                      textAlign: TextAlign.center,
                      style: TextStyle(color: Colors.black54),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ] else ...[
          ..._items.asMap().entries.map((entry) {
            final index = entry.key;
            final item = entry.value;
            return _buildDispatchItemCard(index, item);
          }),
          const SizedBox(height: 12),

          // 8. Boutons d'action globale
          Row(
            children: [
              OutlinedButton.icon(
                style: OutlinedButton.styleFrom(foregroundColor: Colors.red),
                onPressed: () => setState(() => _items.clear()),
                icon: const Icon(Icons.delete_sweep),
                label: const Text('Vider'),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: FilledButton.icon(
                  style: FilledButton.styleFrom(
                    backgroundColor: _mode == 'consume' ? const Color(0xFFC0392B) : const Color(0xFF2980B9),
                    padding: const EdgeInsets.symmetric(vertical: 14),
                  ),
                  onPressed: _loading ? null : _executeBulkDispatch,
                  icon: Icon(_mode == 'consume' ? Icons.trending_down : Icons.local_shipping),
                  label: Text(
                    _mode == 'consume'
                        ? 'Valider Consommation (${_items.length})'
                        : 'Valider Transfert (${_items.length})',
                    style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15),
                  ),
                ),
              ),
            ],
          ),
        ],
      ],
    );
  }

  Widget _buildDispatchItemCard(int index, BulkDispatchItem item) {
    final maxQty = item.currentQty.toInt();

    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    item.productName,
                    style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15),
                  ),
                ),
                IconButton(
                  visualDensity: VisualDensity.compact,
                  icon: const Icon(Icons.close, color: Colors.red, size: 20),
                  onPressed: () {
                    setState(() => _items.removeAt(index));
                  },
                ),
              ],
            ),
            const SizedBox(height: 4),
            Row(
              children: [
                Text('Lot : ${item.lotNumber}', style: const TextStyle(fontWeight: FontWeight.w600)),
                const SizedBox(width: 12),
                Text('Exp : ${item.expiryDate}', style: const TextStyle(color: Colors.black54)),
              ],
            ),
            const SizedBox(height: 4),
            Row(
              children: [
                const Icon(Icons.warehouse, size: 16, color: Colors.black54),
                const SizedBox(width: 4),
                Text('Source : ${item.locationName} (Dispo: $maxQty)', style: const TextStyle(fontSize: 12, color: Colors.black54)),
              ],
            ),
            const Divider(height: 16),
            Row(
              children: [
                const Text('Quantité :', style: TextStyle(fontWeight: FontWeight.bold)),
                const Spacer(),
                IconButton.filledTonal(
                  visualDensity: VisualDensity.compact,
                  onPressed: item.qty > 1
                      ? () => setState(() => item.qty--)
                      : null,
                  icon: const Icon(Icons.remove, size: 16),
                ),
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 14),
                  child: Text(
                    '${item.qty}',
                    style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                  ),
                ),
                IconButton.filledTonal(
                  visualDensity: VisualDensity.compact,
                  onPressed: item.qty < maxQty
                      ? () => setState(() => item.qty++)
                      : null,
                  icon: const Icon(Icons.add, size: 16),
                ),
              ],
            ),
            if (_mode == 'transfer') ...[
              const SizedBox(height: 10),
              DropdownButtonFormField<int>(
                isExpanded: true,
                initialValue: item.targetLocationId,
                decoration: const InputDecoration(
                  labelText: '📍 Destination pour cet article',
                  isDense: true,
                ),
                items: _locations
                    .where((loc) => loc.locationId != item.locationId)
                    .map((loc) => DropdownMenuItem<int>(
                          value: loc.locationId,
                          child: Text(loc.fullPath, overflow: TextOverflow.ellipsis),
                        ))
                    .toList(),
                onChanged: (val) {
                  setState(() {
                    item.targetLocationId = val;
                    if (val != null) {
                      final found = _locations.where((l) => l.locationId == val);
                      item.targetLocationName = found.isNotEmpty ? found.first.fullPath : null;
                    }
                  });
                },
              ),
            ],
          ],
        ),
      ),
    );
  }
}
