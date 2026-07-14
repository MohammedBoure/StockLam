import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:stocklam_inventory_scanner/main.dart';

void main() {
  testWidgets('renders the mobile inventory scanner home', (tester) async {
    SharedPreferences.setMockInitialValues({});

    await tester.pumpWidget(const StockLamInventoryScannerApp());
    await tester.pump(const Duration(milliseconds: 100));

    expect(find.text('StockLam Scanner'), findsOneWidget);
    expect(find.text('Rechercher les ordinateurs StockLam'), findsOneWidget);
    expect(find.text('Vers ordinateur'), findsOneWidget);
    expect(find.text('Code-barres'), findsOneWidget);
  });
}
