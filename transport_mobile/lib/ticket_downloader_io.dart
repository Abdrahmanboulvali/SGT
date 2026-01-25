import 'dart:io';
import 'dart:typed_data';

import 'package:open_filex/open_filex.dart';
import 'package:path_provider/path_provider.dart';

Future<bool> handlePdf(Uint8List bytes, String fileName) async {
  final dir = await getTemporaryDirectory();
  final filePath = "${dir.path}/$fileName";

  final file = File(filePath);
  await file.writeAsBytes(bytes, flush: true);

  // ✅ محاولة فتح الملف
  final result = await OpenFilex.open(filePath);

  // بعض الأنظمة ترجع "done" أو "ok"
  final ok = result.type.toString().toLowerCase().contains("done") ||
      result.type.toString().toLowerCase().contains("ok");

  return ok;
}
