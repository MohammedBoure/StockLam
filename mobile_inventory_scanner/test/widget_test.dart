import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:stocklam_inventory_scanner/main.dart';

void main() {
  testWidgets('renders the mobile inventory scanner home', (tester) async {
    SharedPreferences.setMockInitialValues({});

    await tester.pumpWidget(const StockLamInventoryScannerApp());
    await tester.pumpAndSettle();

    expect(find.text('StockLam Inventaire'), findsOneWidget);
    expect(find.text('Serveur API'), findsOneWidget);
    expect(find.text('Session Inventaire'), findsOneWidget);
    expect(find.text('Code-barres'), findsOneWidget);
  });
}
