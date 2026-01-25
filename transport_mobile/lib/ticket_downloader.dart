import 'dart:typed_data';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

// ✅ استيراد شرطي حسب المنصة
import 'ticket_downloader_io.dart'
    if (dart.library.html) 'ticket_downloader_web.dart' as platform;

class TicketDownloader {
  static Future<void> downloadAndOpenPdf({
    required BuildContext context,
    required String url,
    required String fileName,
  }) async {
    final res = await http.get(Uri.parse(url));

    if (res.statusCode != 200) {
      throw Exception("HTTP ${res.statusCode}");
    }

    final bytes = res.bodyBytes;

    // ✅ الويب: تنزيل مباشر
    if (kIsWeb) {
      await platform.handlePdf(bytes, fileName);
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text("Téléchargement lancé ✅")),
        );
      }
      return;
    }

    // ✅ Android/Windows: حفظ ثم فتح
    final opened = await platform.handlePdf(bytes, fileName);

    if (context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(opened ? "Ticket ouvert ✅" : "Ticket enregistré ✅"),
        ),
      );
    }
  }
}
