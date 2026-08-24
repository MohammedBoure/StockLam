// mobile_inventory_scanner/lib/views/fast_dispatch_view.dart
// ignore_for_file: deprecated_member_use

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
  final GlobalKey<ScannerCameraWidgetState> _scannerKey = GlobalKey<ScannerCameraWidgetState>();

  String _mode = 'consume'; // 'consume' or 'transfer'
  bool _loading = false;
  bool _cameraOpen = false;
  String? _errorMessage;
  String? _successMessage;

  // Suivi de l'état du panier et des retours sonores/visuels
  String? _highlightedLineId;
  String? _lastAction; // 'new', 'duplicate', 'max_reached', 'error'
  Timer? _highlightTimer;

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
    _highlightTimer?.cancel();
    _barcodeController.dispose();
    _barcodeFocus.dispose();
    super.dispose();
  }

  // --- Gestion du retour sonore (SystemSound) & haptique ---
  void _playPositiveSound() {
    unawaited(SystemSound.play(SystemSoundType.click));
  }

  void _playDuplicateSound() {
    // Double impulsion sonore distincte pour signaler l'ajout
    unawaited(SystemSound.play(SystemSoundType.click));
    Future.delayed(const Duration(milliseconds: 110), () {
      unawaited(SystemSound.play(SystemSoundType.click));
    });
  }

  void _playAlertSound() {
    unawaited(SystemSound.play(SystemSoundType.alert));
  }

  void _setHighlight(String lineId, String action) {
    _highlightTimer?.cancel();
    setState(() {
      _highlightedLineId = lineId;
      _lastAction = action;
    });
    _highlightTimer = Timer(const Duration(seconds: 4), () {
      if (mounted) {
        setState(() {
          if (_highlightedLineId == lineId) {
            _highlightedLineId = null;
          }
        });
      }
    });
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
      _playAlertSound();
      HapticFeedback.vibrate();
      setState(() {
        _errorMessage = 'Connectez d’abord un ordinateur ModernStock.';
        _successMessage = null;
        _lastAction = 'error';
      });
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
        _playAlertSound();
        HapticFeedback.vibrate();
        setState(() {
          _errorMessage = result['message'] ?? 'Aucun produit ou lot trouvé pour "$barcode".';
          _successMessage = null;
          _lastAction = 'error';
        });
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
        _playAlertSound();
        HapticFeedback.vibrate();
        setState(() {
          _errorMessage = 'Aucun lot en stock pour ${prod?.productName ?? barcode}.';
          _successMessage = null;
          _lastAction = 'error';
        });
        return;
      }

      final productName = prod?.productName ?? 'Produit #${batches.first.productId}';
      final recommendedBatch = batches.firstWhere((b) => b.isRecommended, orElse: () => batches.first);
      final matchedBatches = batches.where((b) => b.isScannedMatch).toList();

      final selectedBatch = matchedBatches.isNotEmpty ? matchedBatches.first : recommendedBatch;
      final allowOverride = (selectedBatch.batchId != recommendedBatch.batchId);

      _addItemToDispatch(prod, selectedBatch, batches, productName: productName, allowOverride: allowOverride);
      _barcodeController.clear();
      _barcodeFocus.requestFocus();
    } catch (e) {
      _playAlertSound();
      HapticFeedback.vibrate();
      if (mounted) {
        setState(() {
          _errorMessage = 'Erreur lors du scan : $e';
          _successMessage = null;
          _lastAction = 'error';
        });
      }
    } finally {
      if (mounted) setState(() => _loading = false);
      // Réarmement automatique de la caméra pour scan en continu
      Future.delayed(const Duration(milliseconds: 700), () {
        if (mounted && _cameraOpen) {
          _scannerKey.currentState?.resume();
        }
      });
    }
  }

  void _addItemToDispatch(
    ProductDetails? prod,
    BatchDetails batch,
    List<BatchDetails> allBatches, {
    String? productName,
    bool allowOverride = false,
  }) {
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

    final resolvedName = productName ?? prod?.productName ?? 'Produit #${batch.productId}';
    final newItem = BulkDispatchItem(
      batchId: batch.batchId,
      productId: batch.productId,
      productName: resolvedName,
      lotNumber: batch.lotNumber,
      expiryDate: batch.expiryDate,
      currentQty: batch.quantityCurrent,
      qty: 1,
      locationId: batch.locationId,
      locationName: batch.locationName,
      targetLocationId: initialTargetLocation,
      targetLocationName: initialTargetName,
      isRecommended: batch.isRecommended,
      allowFefoOverride: allowOverride,
      availableBatches: allBatches,
    );

    final isDuplicate = _items.any((i) => i.productId == batch.productId);
    if (isDuplicate) {
      _playDuplicateSound();
      HapticFeedback.mediumImpact();
    } else {
      _playPositiveSound();
      HapticFeedback.lightImpact();
    }

    setState(() {
      _items.add(newItem);
      _successMessage = isDuplicate
          ? '🔄 Nouvelle ligne ajoutée pour $resolvedName (Total : ${_items.where((i) => i.productId == batch.productId).length} lignes)'
          : '✅ Article #${_items.length} ajouté : $resolvedName (📍 ${newItem.locationName})';
      _errorMessage = null;
      _lastAction = isDuplicate ? 'duplicate' : 'new';
    });
    _setHighlight(newItem.lineId, isDuplicate ? 'duplicate' : 'new');
  }

  /// Boîte de dialogue FEFO conforme à celle du logiciel bureau (FEFOSelectionDialog)
  /// Affiche le Numéro de Lot COMPLET et le Code-barres associé
  Future<BatchDetails?> _showFefoSelectionDialog({
    required String productName,
    required List<BatchDetails> allBatches,
    required BatchDetails recommendedBatch,
    required BatchDetails scannedBatch,
  }) async {
    return showDialog<BatchDetails>(
      context: context,
      barrierDismissible: false,
      builder: (ctx) {
        BatchDetails currentlySelected = recommendedBatch;

        return StatefulBuilder(
          builder: (context, setDialogState) {
            final isRecSelected = currentlySelected.batchId == recommendedBatch.batchId;

            return AlertDialog(
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
              titlePadding: const EdgeInsets.fromLTRB(20, 16, 20, 8),
              contentPadding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
              title: Row(
                children: [
                  const Icon(Icons.warning_amber_rounded, color: Colors.orange, size: 28),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Respect du FEFO',
                          style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16, color: Color(0xFF856404)),
                        ),
                        Text(
                          productName,
                          style: const TextStyle(fontSize: 13, color: Colors.black87),
                          overflow: TextOverflow.ellipsis,
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              content: SizedBox(
                width: double.maxFinite,
                child: SingleChildScrollView(
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Container(
                        padding: const EdgeInsets.all(10),
                        decoration: BoxDecoration(
                          color: const Color(0xFFFFF3CD),
                          borderRadius: BorderRadius.circular(8),
                          border: Border.all(color: const Color(0xFFFFEEBA)),
                        ),
                        child: const Text(
                          '⚠️ Alerte FEFO : Vous avez sélectionné un lot récent alors que des lots plus anciens sont disponibles.\nVeuillez choisir ci-dessous le lot à consommer (Le lot recommandé est surligné en vert).',
                          style: TextStyle(fontSize: 12, color: Color(0xFF856404), fontWeight: FontWeight.w500),
                        ),
                      ),
                      const SizedBox(height: 12),
                      const Text(
                        'Lots disponibles :',
                        style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
                      ),
                      const SizedBox(height: 6),
                      ...allBatches.map((b) {
                        final isRec = b.batchId == recommendedBatch.batchId;
                        final isScanned = b.batchId == scannedBatch.batchId;
                        final isChosen = b.batchId == currentlySelected.batchId;

                        Color cardBg = Colors.white;
                        Color borderCol = Colors.grey.shade300;
                        if (isChosen) {
                          cardBg = isRec ? const Color(0xFFD4EDDA) : const Color(0xFFFFF0ED);
                          borderCol = isRec ? const Color(0xFF27AE60) : const Color(0xFFE74C3C);
                        } else if (isRec) {
                          cardBg = const Color(0xFFF4FAF6);
                          borderCol = const Color(0xFFC3E6CB);
                        }

                        return InkWell(
                          onTap: () {
                            setDialogState(() {
                              currentlySelected = b;
                            });
                          },
                          child: Container(
                            margin: const EdgeInsets.only(bottom: 8),
                            padding: const EdgeInsets.all(10),
                            decoration: BoxDecoration(
                              color: cardBg,
                              borderRadius: BorderRadius.circular(8),
                              border: Border.all(color: borderCol, width: isChosen ? 2 : 1),
                            ),
                            child: Row(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Padding(
                                  padding: const EdgeInsets.only(top: 2),
                                  child: Radio<int>(
                                    value: b.batchId,
                                    groupValue: currentlySelected.batchId,
                                    activeColor: isRec ? const Color(0xFF27AE60) : const Color(0xFFE74C3C),
                                    onChanged: (val) {
                                      setDialogState(() {
                                        currentlySelected = b;
                                      });
                                    },
                                  ),
                                ),
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      // 1. Numéro de lot complet & Badge
                                      Wrap(
                                        spacing: 6,
                                        runSpacing: 4,
                                        crossAxisAlignment: WrapCrossAlignment.center,
                                        children: [
                                          Text(
                                            'Lot : ${b.lotNumber}',
                                            style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14, color: Colors.black87),
                                            softWrap: true,
                                          ),
                                          if (isRec)
                                            Container(
                                              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                              decoration: BoxDecoration(
                                                color: const Color(0xFF27AE60),
                                                borderRadius: BorderRadius.circular(4),
                                              ),
                                              child: const Text(
                                                '⭐ RECOMMANDÉ',
                                                style: TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.bold),
                                              ),
                                            )
                                          else if (isScanned)
                                            Container(
                                              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                              decoration: BoxDecoration(
                                                color: const Color(0xFFE74C3C),
                                                borderRadius: BorderRadius.circular(4),
                                              ),
                                              child: const Text(
                                                '✋ SCANNÉ',
                                                style: TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.bold),
                                              ),
                                            ),
                                        ],
                                      ),
                                      const SizedBox(height: 4),

                                      // 2. Code-barres complet et visible
                                      if (b.internalBarcode.isNotEmpty)
                                        Container(
                                          margin: const EdgeInsets.only(bottom: 4),
                                          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                          decoration: BoxDecoration(
                                            color: Colors.black.withOpacity(0.06),
                                            borderRadius: BorderRadius.circular(4),
                                          ),
                                          child: Text(
                                            '🏷️ Code-barres : ${b.internalBarcode}',
                                            style: const TextStyle(
                                              fontSize: 12,
                                              fontFamily: 'monospace',
                                              fontWeight: FontWeight.w600,
                                              color: Colors.black87,
                                            ),
                                            softWrap: true,
                                          ),
                                        ),

                                      // 3. Date Exp, Qté, Emplacement
                                      Text(
                                        'Date Exp : ${b.expiryDate}  •  Stock dispo : ${b.quantityCurrent.toInt()}',
                                        style: TextStyle(
                                          fontSize: 12,
                                          fontWeight: isRec ? FontWeight.bold : FontWeight.normal,
                                          color: isRec ? const Color(0xFF155724) : Colors.black87,
                                        ),
                                      ),
                                      Text(
                                        '📍 Empl : ${b.locationName}${b.dateReceived.isNotEmpty ? " • Reçu le : ${b.dateReceived}" : ""}',
                                        style: const TextStyle(fontSize: 11, color: Colors.black54),
                                      ),
                                    ],
                                  ),
                                ),
                              ],
                            ),
                          ),
                        );
                      }),
                    ],
                  ),
                ),
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(ctx, null),
                  child: const Text('Annuler l\'opération'),
                ),
                FilledButton(
                  style: FilledButton.styleFrom(
                    backgroundColor: isRecSelected ? const Color(0xFF27AE60) : const Color(0xFFE74C3C),
                  ),
                  onPressed: () => Navigator.pop(ctx, currentlySelected),
                  child: Text(
                    isRecSelected ? '✅ Utiliser le lot recommandé' : '✋ Confirmer le lot sélectionné (Outrepasser)',
                  ),
                ),
              ],
            );
          },
        );
      },
    );
  }

  /// Permet à l'utilisateur de remplacer ou changer le lot d'un article déjà dans la liste
  Future<void> _changeItemBatch(BulkDispatchItem item) async {
    List<BatchDetails> available = item.availableBatches;

    if (available.isEmpty) {
      // Re-requêter le produit si les lots ne sont pas en cache
      setState(() => _loading = true);
      try {
        final res = await widget.api.lookupBarcode(item.lotNumber);
        final rawBatches = res['batches'] as List<dynamic>? ?? [];
        available = rawBatches
            .map((b) => BatchDetails.fromJson(b as Map<String, dynamic>))
            .where((b) => b.quantityCurrent > 0)
            .toList();
      } catch (_) {}
      if (mounted) setState(() => _loading = false);
    }

    if (available.isEmpty) {
      setState(() => _errorMessage = 'Aucun autre lot disponible pour ce produit.');
      return;
    }

    final recommended = available.firstWhere((b) => b.isRecommended, orElse: () => available.first);
    final currentBatch = available.firstWhere((b) => b.batchId == item.batchId, orElse: () => available.first);

    final selected = await _showFefoSelectionDialog(
      productName: item.productName,
      allBatches: available,
      recommendedBatch: recommended,
      scannedBatch: currentBatch,
    );

    if (selected != null && mounted) {
      setState(() {
        item.updateBatch(selected, allowOverride: selected.batchId != recommended.batchId);
        _successMessage = 'Lot mis à jour : ${item.productName} -> Lot: ${item.lotNumber} (Exp: ${item.expiryDate})';
      });
    }
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

      // Si le serveur signale une violation FEFO non autorisée
      if (res['fefo_violation'] == true) {
        final violation = FefoViolationData.fromJson(res);
        final failedBatchId = (violation.scannedBatch['Batch_ID'] as num?)?.toInt();
        final matchingItem = _items.where((i) => i.batchId == failedBatchId).firstOrNull;

        if (matchingItem != null) {
          await _changeItemBatch(matchingItem);
          return;
        }
      }

      final successCount = (res['success_count'] as num?)?.toInt() ?? 0;
      final failedCount = (res['failed_count'] as num?)?.toInt() ?? 0;

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
            key: _scannerKey,
            onCodeDetected: (code) {
              _barcodeController.text = code;
              unawaited(_processBarcodeScan(code));
            },
            onClose: () => setState(() => _cameraOpen = false),
          ),
          const SizedBox(height: 10),
        ],

        // 4. Messages d'état & de retour interactif
        if (_errorMessage != null) ...[
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: _lastAction == 'max_reached' ? const Color(0xFFFFF3CD) : const Color(0xFFFDEEED),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(
                color: _lastAction == 'max_reached' ? const Color(0xFFFFEEBA) : const Color(0xFFF5C6CB),
                width: 1.5,
              ),
            ),
            child: Row(
              children: [
                Icon(
                  _lastAction == 'max_reached' ? Icons.warning_amber_rounded : Icons.error_outline,
                  color: _lastAction == 'max_reached' ? const Color(0xFFD35400) : Colors.red,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    _errorMessage!,
                    style: TextStyle(
                      color: _lastAction == 'max_reached' ? const Color(0xFF856404) : Colors.red,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 10),
        ],

        if (_successMessage != null) ...[
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: _lastAction == 'duplicate' ? const Color(0xFFEBF5FB) : const Color(0xFFE8F8F0),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(
                color: _lastAction == 'duplicate' ? const Color(0xFFAED6F1) : const Color(0xFFC3E6CB),
                width: 1.5,
              ),
            ),
            child: Row(
              children: [
                Icon(
                  _lastAction == 'duplicate' ? Icons.sync : Icons.check_circle_outline,
                  color: _lastAction == 'duplicate' ? const Color(0xFF2980B9) : const Color(0xFF27AE60),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    _successMessage!,
                    style: TextStyle(
                      color: _lastAction == 'duplicate' ? const Color(0xFF1B4F72) : const Color(0xFF155724),
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
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
    final isConsumeMode = _mode == 'consume';
    final hasFefoWarning = isConsumeMode && !item.isRecommended;
    final isHighlighted = item.lineId == _highlightedLineId;

    Color borderColor = hasFefoWarning ? Colors.orange.shade300 : Colors.grey.shade300;
    double borderWidth = hasFefoWarning ? 1.5 : 1.0;

    if (isHighlighted) {
      borderColor = const Color(0xFF27AE60);
      borderWidth = 2.0;
    }

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      elevation: 2,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(
          color: borderColor,
          width: borderWidth,
        ),
      ),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // 1. En-tête : Numéro de ligne (#) + Nom du produit + Bouton Supprimer
            Row(
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
                  decoration: BoxDecoration(
                    color: const Color(0xFFE8F8F0),
                    borderRadius: BorderRadius.circular(6),
                    border: Border.all(color: const Color(0xFFC3E6CB)),
                  ),
                  child: Text(
                    '#${index + 1}',
                    style: const TextStyle(
                      fontWeight: FontWeight.bold,
                      fontSize: 12,
                      color: Color(0xFF007572),
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    item.productName,
                    style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                IconButton(
                  visualDensity: VisualDensity.compact,
                  tooltip: 'Retirer cet article du panier',
                  icon: const Icon(Icons.delete_outline, color: Colors.red, size: 22),
                  onPressed: () {
                    HapticFeedback.lightImpact();
                    setState(() {
                      _items.removeAt(index);
                    });
                  },
                ),
              ],
            ),
            const SizedBox(height: 8),

            // 2. Sélecteur Source (Emplacement & Lot) - Identique au QComboBox de tabs_dispatch.py
            DropdownButtonFormField<int>(
              isExpanded: true,
              value: item.availableBatches.any((b) => b.batchId == item.batchId) ? item.batchId : null,
              decoration: InputDecoration(
                labelText: '📍 Source (Emplacement & Lot)',
                labelStyle: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13, color: Color(0xFF2C3E50)),
                isDense: true,
                contentPadding: const EdgeInsets.symmetric(horizontal: 10, vertical: 10),
                filled: true,
                fillColor: const Color(0xFFF8F9FA),
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: const BorderSide(color: Color(0xFFBDC3C7))),
              ),
              items: item.availableBatches.map((b) {
                final qty = b.quantityCurrent.toInt();
                final fefoTag = b.isRecommended ? ' ⭐ [FEFO]' : '';
                return DropdownMenuItem<int>(
                  value: b.batchId,
                  child: Text(
                    '📍 ${b.locationName} | Lot: ${b.lotNumber} (Dispo: $qty)$fefoTag',
                    style: TextStyle(
                      fontSize: 13,
                      fontWeight: b.batchId == item.batchId ? FontWeight.bold : FontWeight.normal,
                      color: b.isRecommended ? const Color(0xFF155724) : Colors.black87,
                    ),
                    overflow: TextOverflow.ellipsis,
                  ),
                );
              }).toList(),
              onChanged: (newBatchId) {
                if (newBatchId == null) return;
                final selectedBatch = item.availableBatches.firstWhere((b) => b.batchId == newBatchId);
                setState(() {
                  item.updateBatch(selectedBatch, allowOverride: !selectedBatch.isRecommended);
                });
              },
            ),
            const SizedBox(height: 8),

            // 3. Avertissement FEFO contextuel
            if (hasFefoWarning) ...[
              Container(
                margin: const EdgeInsets.only(bottom: 8),
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                decoration: BoxDecoration(
                  color: const Color(0xFFFFF3CD),
                  borderRadius: BorderRadius.circular(6),
                  border: Border.all(color: const Color(0xFFFFEEBA)),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.warning_amber_rounded, color: Color(0xFFD35400), size: 16),
                    const SizedBox(width: 6),
                    const Expanded(
                      child: Text(
                        'Lot plus récent (FEFO non prioritaire)',
                        style: TextStyle(color: Color(0xFF856404), fontSize: 11, fontWeight: FontWeight.w600),
                      ),
                    ),
                    if (item.availableBatches.any((b) => b.isRecommended))
                      InkWell(
                        onTap: () {
                          final rec = item.availableBatches.firstWhere((b) => b.isRecommended);
                          setState(() => item.updateBatch(rec, allowOverride: false));
                        },
                        child: const Text(
                          'Choisir FEFO ⭐',
                          style: TextStyle(
                            color: Color(0xFF007572),
                            fontSize: 11,
                            fontWeight: FontWeight.bold,
                            decoration: TextDecoration.underline,
                          ),
                        ),
                      ),
                  ],
                ),
              ),
            ],

            // 4. Détails Lot et Date d'expiration
            Row(
              children: [
                Expanded(
                  child: Text(
                    'Lot : ${item.lotNumber}  •  Exp : ${item.expiryDate.isNotEmpty ? item.expiryDate : '---'}',
                    style: const TextStyle(color: Colors.black54, fontSize: 12, fontWeight: FontWeight.w500),
                  ),
                ),
                Text(
                  'Dispo : $maxQty',
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.bold,
                    color: maxQty < 5 ? const Color(0xFFC0392B) : const Color(0xFF27AE60),
                  ),
                ),
              ],
            ),
            const Divider(height: 16),

            // 5. Quantité à consommer ou transférer
            Row(
              children: [
                const Text('Quantité :', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
                const Spacer(),
                IconButton.filledTonal(
                  visualDensity: VisualDensity.compact,
                  onPressed: item.qty > 1 ? () => setState(() => item.qty--) : null,
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
                  onPressed: item.qty < maxQty ? () => setState(() => item.qty++) : null,
                  icon: const Icon(Icons.add, size: 16),
                ),
              ],
            ),

            // 6. Destination pour le mode Transfert
            if (_mode == 'transfer') ...[
              const SizedBox(height: 10),
              DropdownButtonFormField<int>(
                isExpanded: true,
                initialValue: item.targetLocationId,
                decoration: InputDecoration(
                  labelText: '📍 Destination pour cet article',
                  labelStyle: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
                  isDense: true,
                  contentPadding: const EdgeInsets.symmetric(horizontal: 10, vertical: 10),
                  filled: true,
                  fillColor: const Color(0xFFF0F9FF),
                  border: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: const BorderSide(color: Color(0xFFAED6F1))),
                ),
                items: _locations
                    .where((loc) => loc.locationId != item.locationId)
                    .map((loc) => DropdownMenuItem<int>(
                          value: loc.locationId,
                          child: Text(loc.fullPath, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 13)),
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
