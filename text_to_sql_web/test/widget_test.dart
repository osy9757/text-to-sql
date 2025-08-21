// This is a basic Flutter widget test.
//
// To perform an interaction with a widget in your test, use the WidgetTester
// utility in the flutter_test package. For example, you can send tap and scroll
// gestures. You can also use WidgetTester to find child widgets in the widget
// tree, read text, and verify that the values of widget properties are correct.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:text_to_sql_web/main.dart';

void main() {
  testWidgets('Text-to-SQL app loads correctly', (WidgetTester tester) async {
    // Build our app and trigger a frame.
    await tester.pumpWidget(const TextToSQLApp());

    // Verify that our main title is present.
    expect(find.text('Text-to-SQL'), findsOneWidget);
    expect(find.text('자연어로 데이터베이스를 쿼리하세요 🚀'), findsOneWidget);

    // Verify that the input card is present
    expect(find.text('질문을 입력하세요'), findsOneWidget);
    expect(find.text('쿼리 실행'), findsOneWidget);
  });
}
