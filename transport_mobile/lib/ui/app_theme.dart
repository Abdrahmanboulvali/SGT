import 'package:flutter/material.dart';

class AppTheme {
  static const Color primary = Color(0xFF1E5BFF);
  static const Color navy = Color(0xFF0B1B4A);
  static const Color bg = Color(0xFFF6F7FB);

  static ThemeData theme() {
    final scheme = ColorScheme.fromSeed(
      seedColor: primary,
      brightness: Brightness.light,
    );

    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.light,
      scaffoldBackgroundColor: bg,
      colorScheme: scheme,

      // ✅ خطوط افتراضية ممتازة (تعمل بدون أي حزمة)
      fontFamily: null,

      appBarTheme: const AppBarTheme(
        elevation: 0,
        backgroundColor: Colors.transparent,
        foregroundColor: Colors.black,
        centerTitle: false,
      ),

      cardTheme: CardTheme(
        elevation: 0,
        color: Colors.white,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(22)),
      ),

      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: Colors.white,
        contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: BorderSide(color: Colors.grey.shade300),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: BorderSide(color: Colors.grey.shade300),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: const BorderSide(color: primary, width: 1.2),
        ),
      ),

      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          minimumSize: const Size.fromHeight(52),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
          textStyle: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700),
          backgroundColor: navy,
          foregroundColor: Colors.white,
        ),
      ),

      chipTheme: ChipThemeData(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(999)),
        labelStyle: const TextStyle(fontWeight: FontWeight.w700),
        side: BorderSide(color: Colors.grey.shade300),
      ),

      // ✅ تحسين عام للنصوص (اختياري لكنه يعطي شكل أجمل)
      textTheme: const TextTheme(
        headlineSmall: TextStyle(fontWeight: FontWeight.w900),
        titleMedium: TextStyle(fontWeight: FontWeight.w800),
        bodyMedium: TextStyle(fontWeight: FontWeight.w600),
      ),
    );
  }
}
