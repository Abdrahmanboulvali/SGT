import 'dart:typed_data';
import 'dart:html' as html;

Future<bool> handlePdf(Uint8List bytes, String fileName) async {
  final blob = html.Blob([bytes], 'application/pdf');
  final url = html.Url.createObjectUrlFromBlob(blob);

  final anchor = html.AnchorElement(href: url)
    ..setAttribute("download", fileName)
    ..click();

  html.Url.revokeObjectUrl(url);
  // ignore: unused_local_variable
  final _ = anchor;

  return true;
}
