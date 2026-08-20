// mobile_inventory_scanner/test/widget_test.dart

import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:stocklam_inventory_scanner/main.dart';

void main() {
  testWidgets('renders the modernstock mobile direct inventory app', (tester) async {
    SharedPreferences.setMockInitialValues({});

    await tester.pumpWidget(const ModernStockApp());
    await tester.pump(const Duration(milliseconds: 100));

    expect(find.text('MODERNSTOCK'), findsOneWidget);
    expect(find.text('Stock Direct'), findsOneWidget);
    expect(find.text('Pont Bureau'), findsOneWidget);
    expect(find.text('Code-barres ou N° Lot'), findsOneWidget);
  });
}
