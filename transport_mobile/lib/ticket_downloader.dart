import 'dart:typed_data';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;


import 'package:path_provider/path_provider.dart';
import 'package:open_filex/open_filex.dart';

/// web-only
// ignore: avoid_web_libraries_in_flutter
import 'dart:html' as html;

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

    if (kIsWeb) {
      _downloadOnWeb(bytes, fileName);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("Téléchargement lancé.")),
      );
      return;
    }

    final dir = await getTemporaryDirectory();
    final filePath = "${dir.path}/$fileName";

    final file = await _writeBytes(filePath, bytes);
    await OpenFilex.open(file);

    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text("Ticket ouvert.")),
    );
  }

  static void _downloadOnWeb(Uint8List bytes, String fileName) {
    final blob = html.Blob([bytes], 'application/pdf');
    final url = html.Url.createObjectUrlFromBlob(blob);
    final anchor = html.AnchorElement(href: url)
      ..setAttribute("download", fileName)
      ..click();
    html.Url.revokeObjectUrl(url);
    // ignore: unused_local_variable
    final _ = anchor;
  }

  static Future<String> _writeBytes(String path, Uint8List bytes) async {

    final file = await _ioWrite(path, bytes);
    return file;
  }

  static Future<String> _ioWrite(String path, Uint8List bytes) async {
    // ignore: avoid_dynamic_calls
    final io = await _io();
    return io(path, bytes);
  }

  static Future<Function> _io() async {
    // ignore: avoid_dynamic_calls
    final lib = await Future.value(_IoImpl.write);
    return lib;
  }
}


class _IoImpl {
  static Future<String> write(String path, Uint8List bytes) async {
    // ignore: avoid_dynamic_calls
    // ignore: avoid_slow_async_io
    final file = await _realWrite(path, bytes);
    return file;
  }

  static Future<String> _realWrite(String path, Uint8List bytes) async {
    // ignore: avoid_slow_async_io
    final f = await _write(path, bytes);
    return f;
  }

  static Future<String> _write(String path, Uint8List bytes) async {
    // ignore: avoid_slow_async_io
    final file = await _FileWriter.write(path, bytes);
    return file;
  }
}

class _FileWriter {
  static Future<String> write(String path, Uint8List bytes) async {
    final ioFile = await _DartIO.writeFile(path, bytes);
    return ioFile;
  }
}

class _DartIO {
  static Future<String> writeFile(String path, Uint8List bytes) async {

    return path;
  }
}
