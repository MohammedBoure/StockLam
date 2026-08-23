// mobile_inventory_scanner/lib/views/scanner_camera_widget.dart

import 'dart:async';
import 'package:flutter/material.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

class ScannerCameraWidget extends StatefulWidget {
  const ScannerCameraWidget({
    super.key,
    required this.onCodeDetected,
    required this.onClose,
  });

  final ValueChanged<String> onCodeDetected;
  final VoidCallback onClose;

  @override
  State<ScannerCameraWidget> createState() => ScannerCameraWidgetState();
}

class ScannerCameraWidgetState extends State<ScannerCameraWidget>
    with WidgetsBindingObserver {
  late final MobileScannerController _controller;
  CameraFacing _cameraFacing = CameraFacing.back;
  bool _starting = false;
  bool _hasDetected = false;

  void resume() {
    if (mounted) {
      setState(() {
        _hasDetected = false;
      });
    }
  }

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _controller = MobileScannerController(
      autoStart: false,
      facing: CameraFacing.back,
      detectionSpeed: DetectionSpeed.normal,
      detectionTimeoutMs: 500,
    );
    unawaited(_startCamera());
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    unawaited(_controller.dispose());
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (!_controller.value.isInitialized) return;
    switch (state) {
      case AppLifecycleState.detached:
      case AppLifecycleState.hidden:
      case AppLifecycleState.paused:
      case AppLifecycleState.inactive:
        unawaited(_controller.stop());
      case AppLifecycleState.resumed:
        unawaited(_startCamera());
    }
  }

  String _cameraErrorMessage(MobileScannerException error) {
    final details = error.errorDetails;
    final technicalDetails = [details?.message, details?.code]
        .whereType<String>()
        .where((value) => value.trim().isNotEmpty)
        .join(' - ');
    final reason = technicalDetails.isEmpty ? error.errorCode.name : technicalDetails;
    return 'Impossible d\'ouvrir la caméra.\n$reason\n\nVérifiez les autorisations de l\'application.';
  }

  Future<void> _startCamera() async {
    if (_starting) return;
    _starting = true;
    try {
      await _controller.start(cameraDirection: _cameraFacing);
    } catch (_) {
    } finally {
      _starting = false;
      if (mounted) setState(() {});
    }
  }

  Future<void> _switchCamera() async {
    if (_starting) return;
    try {
      await _controller.switchCamera();
      if (!mounted) return;
      final actualFacing = _controller.value.cameraDirection;
      setState(() {
        _cameraFacing = actualFacing;
      });
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    final isBack = _cameraFacing == CameraFacing.back;
    return SizedBox(
      height: 350,
      child: ClipRRect(
        borderRadius: BorderRadius.circular(12),
        child: Stack(
          children: [
            MobileScanner(
              controller: _controller,
              onDetect: (capture) {
                if (_hasDetected) return;
                final barcodes = capture.barcodes;
                if (barcodes.isNotEmpty && barcodes.first.rawValue != null) {
                  final code = barcodes.first.rawValue!.trim();
                  if (code.isNotEmpty) {
                    _hasDetected = true;
                    widget.onCodeDetected(code);
                  }
                }
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
                          onPressed: _starting ? null : () => unawaited(_startCamera()),
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
                onPressed: widget.onClose,
                icon: const Icon(Icons.close),
              ),
            ),
            Positioned(
              top: 8,
              right: 8,
              child: IconButton.filled(
                tooltip: isBack ? 'Caméra avant' : 'Caméra arrière',
                onPressed: () => unawaited(_switchCamera()),
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
                    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                    child: Text(
                      isBack ? '🔴 Visez le code-barres (Caméra arrière)' : 'Caméra avant',
                      style: const TextStyle(color: Colors.white, fontSize: 12),
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
}
