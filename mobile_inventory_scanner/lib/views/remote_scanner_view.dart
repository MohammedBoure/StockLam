// mobile_inventory_scanner/lib/views/remote_scanner_view.dart

import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../api_client.dart';
import '../models.dart';
import 'scanner_camera_widget.dart';

class RemoteScannerView extends StatefulWidget {
  const RemoteScannerView({
    super.key,
    required this.api,
    required this.connected,
    required this.selectedDevice,
    required this.recentScans,
    required this.onScanSent,
    this.currentUser,
  });

  final ApiClient api;
  final bool connected;
  final DesktopDevice? selectedDevice;
  final List<ScanEntry> recentScans;
  final ValueChanged<ScanEntry> onScanSent;
  final AuthUser? currentUser;

  @override
  State<RemoteScannerView> createState() => _RemoteScannerViewState();
}

class _RemoteScannerViewState extends State<RemoteScannerView> {
  final TextEditingController _barcodeController = TextEditingController();
  final FocusNode _barcodeFocus = FocusNode();

  bool _loading = false;
  bool _cameraOpen = false;
  String? _status;

  @override
  void dispose() {
    _barcodeController.dispose();
    _barcodeFocus.dispose();
    super.dispose();
  }

  Future<void> _sendRemoteBarcode([String? value]) async {
    final barcode = (value ?? _barcodeController.text).trim();
    if (!widget.connected) {
      setState(() => _status = 'Connectez d’abord un ordinateur ModernStock.');
      return;
    }
    if (barcode.isEmpty) {
      _barcodeFocus.requestFocus();
      return;
    }

    setState(() {
      _loading = true;
      _status = 'Envoi du code vers ${widget.selectedDevice?.name ?? 'l’ordinateur'}...';
    });

    try {
      await widget.api.sendRemoteBarcode(
        barcode,
        userId: widget.currentUser?.userId,
        userName: widget.currentUser?.fullName ?? widget.currentUser?.username,
      );
      if (!mounted) return;
      HapticFeedback.mediumImpact();
      final entry = ScanEntry(
        barcode: barcode,
        message: 'Envoyé à ${widget.selectedDevice?.name ?? 'ModernStock'}',
        time: DateTime.now(),
      );
      widget.onScanSent(entry);
      setState(() {
        _status = '✅ Code $barcode envoyé à l’ordinateur.';
        _barcodeController.clear();
      });
      _barcodeFocus.requestFocus();
    } catch (error) {
      if (mounted) setState(() => _status = 'Erreur d’envoi : $error');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  void _onCameraDetected(String code) {
    _barcodeController.text = code;
    setState(() => _cameraOpen = false);
    unawaited(_sendRemoteBarcode(code));
  }

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(12),
      children: [
        if (_cameraOpen) ...[
          ScannerCameraWidget(
            onCodeDetected: _onCameraDetected,
            onClose: () => setState(() => _cameraOpen = false),
          ),
          const SizedBox(height: 10),
        ],
        Card(
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const Text(
                  '📱 Pont de Saisie Bureau',
                  style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                ),
                const SizedBox(height: 4),
                const Text(
                  'Positionnez le curseur dans n’importe quel champ de saisie sur le PC, puis scannez.',
                  style: TextStyle(color: Colors.black54, fontSize: 13),
                ),
                const SizedBox(height: 12),
                Row(
                  children: [
                    Expanded(
                      child: TextField(
                        controller: _barcodeController,
                        focusNode: _barcodeFocus,
                        decoration: const InputDecoration(
                          labelText: 'Code-barres',
                          prefixIcon: Icon(Icons.qr_code_2),
                        ),
                        textInputAction: TextInputAction.send,
                        onSubmitted: (val) => unawaited(_sendRemoteBarcode(val)),
                      ),
                    ),
                    const SizedBox(width: 8),
                    SizedBox(
                      height: 56,
                      width: 56,
                      child: IconButton.filledTonal(
                        onPressed: widget.connected
                            ? () => setState(() => _cameraOpen = !_cameraOpen)
                            : null,
                        tooltip: 'Caméra arrière',
                        icon: Icon(_cameraOpen ? Icons.close : Icons.camera_alt),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                FilledButton.icon(
                  onPressed: _loading || !widget.connected
                      ? null
                      : () => unawaited(_sendRemoteBarcode()),
                  icon: const Icon(Icons.send),
                  label: Text('Transmettre à ${widget.selectedDevice?.name ?? 'l’ordinateur'}'),
                ),
                if (_status != null) ...[
                  const SizedBox(height: 10),
                  Text(
                    _status!,
                    style: TextStyle(
                      color: _status!.startsWith('Erreur') ? Colors.red : const Color(0xFF007572),
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ],
              ],
            ),
          ),
        ),
        const SizedBox(height: 10),
        Card(
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
                if (widget.recentScans.isEmpty)
                  const Text('Aucun code envoyé récemment.', style: TextStyle(color: Colors.black54))
                else
                  ...widget.recentScans.map(
                    (scan) => ListTile(
                      dense: true,
                      contentPadding: EdgeInsets.zero,
                      title: Text(scan.barcode, style: const TextStyle(fontWeight: FontWeight.bold)),
                      subtitle: Text(
                        '${scan.time.hour.toString().padLeft(2, '0')}:${scan.time.minute.toString().padLeft(2, '0')} • ${scan.message}',
                      ),
                      trailing: const Icon(Icons.check_circle, color: Color(0xFF27AE60)),
                    ),
                  ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}
