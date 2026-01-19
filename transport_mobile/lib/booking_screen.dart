import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:image_picker/image_picker.dart';

import 'LoginScreen.dart';
import 'ui/ui_widgets.dart';

class BookingScreen extends StatefulWidget {
  final int userId;
  final String username;

  const BookingScreen({super.key, required this.userId, required this.username});

  @override
  State<BookingScreen> createState() => _BookingScreenState();
}

class _BookingScreenState extends State<BookingScreen> {
  bool loadingVoyages = true;
  bool submitting = false;

  List<Map<String, dynamic>> voyages = [];
  int? selectedVoyageId;

  int seats = 1;

  XFile? pickedImage;
  Uint8List? imageBytes; // عرض على الويب/الكمبيوتر

  @override
  void initState() {
    super.initState();
    _fetchVoyages();
  }

  Future<void> _fetchVoyages() async {
    setState(() => loadingVoyages = true);
    try {
      final url = Uri.parse("${ApiConfig.baseUrl}/api/mobile/voyages/");
      final res = await http.get(url);

      if (res.statusCode == 200) {
        final list = (jsonDecode(res.body) as List)
            .map((e) => Map<String, dynamic>.from(e))
            .toList();

        int? firstId;
        if (list.isNotEmpty) {
          final first = list.first;
          firstId = (first["id"] ?? first["id_voyage"]) is int
              ? (first["id"] ?? first["id_voyage"]) as int
              : int.tryParse((first["id"] ?? first["id_voyage"]).toString());
        }

        setState(() {
          voyages = list;
          selectedVoyageId = firstId;
          loadingVoyages = false;

          // ✅ ضبط المقاعد حسب المتاح
          _clampSeatsToAvailable();
        });
      } else {
        setState(() => loadingVoyages = false);
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text("Erreur chargement voyages: ${res.statusCode}")),
        );
      }
    } catch (e) {
      setState(() => loadingVoyages = false);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text("Erreur réseau: $e")),
      );
    }
  }

  Map<String, dynamic>? _selectedVoyage() {
    if (selectedVoyageId == null) return null;
    for (final v in voyages) {
      final id = v["id"] ?? v["id_voyage"];
      if (id == selectedVoyageId) return v;
      // في حال كان id في JSON نص
      if (id != null && id.toString() == selectedVoyageId.toString()) return v;
    }
    return null;
  }

  double _pricePerSeat() {
    final v = _selectedVoyage();
    if (v == null) return 0.0;
    final p = v["prix_par_siege"] ?? v["prix"] ?? v["price_per_seat"] ?? v["price"];
    return double.tryParse(p.toString()) ?? 0.0;
  }

  double _totalToPay() => _pricePerSeat() * seats;

  int _seatsLeft() {
    final v = _selectedVoyage();
    if (v == null) return 0;
    final raw = v["seats_left"] ?? v["places_dispo"] ?? v["available_seats"];
    if (raw == null) return 0;
    return int.tryParse(raw.toString()) ?? 0;
  }

  void _clampSeatsToAvailable() {
    final left = _seatsLeft();
    if (left <= 0) {
      // إذا لم يرسل السيرفر seats_left أو كانت 0، لا نكسر التطبيق
      if (seats < 1) seats = 1;
      return;
    }
    if (seats > left) {
      seats = left; // اجعلها تساوي المتاح
      if (seats < 1) seats = 1;
    }
  }

  String _voyageLabel(Map<String, dynamic> v) {
    // ✅ الأفضل: label جاهزة من السيرفر
    final label = v["label"];
    if (label != null && label.toString().trim().isNotEmpty) {
      return label.toString();
    }

    // fallback: نكوّنها هنا
    final depart = (v["depart"] ?? "").toString();
    final arrivee = (v["arrivee"] ?? "").toString();
    final trajet = (v["trajet"] ?? v["route"] ?? "Trajet").toString();

    final date = (v["date"] ?? "").toString();
    final heure = (v["heure"] ?? "").toString();

    final seatsLeft = int.tryParse((v["seats_left"] ?? "").toString()) ?? 0;
    final price = (v["prix_par_siege"] ?? v["prix"] ?? "0").toString();

    final routeText = (depart.isNotEmpty && arrivee.isNotEmpty)
        ? "$depart -> $arrivee"
        : trajet;

    final dateTimeText = (date.isNotEmpty || heure.isNotEmpty)
        ? "$date $heure".trim()
        : "";

    final dispoText = (seatsLeft > 0) ? "Places dispo: $seatsLeft" : "";

    final parts = <String>[
      routeText,
      if (dateTimeText.isNotEmpty) dateTimeText,
      if (dispoText.isNotEmpty) dispoText,
      "$price MRU",
    ];

    return parts.join(" | ");
  }

  Future<void> _pickImage() async {
    try {
      final picker = ImagePicker();
      final img = await picker.pickImage(source: ImageSource.gallery);
      if (img == null) return;

      final bytes = await img.readAsBytes();
      setState(() {
        pickedImage = img;
        imageBytes = bytes;
      });
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text("Erreur sélection image: $e")),
      );
    }
  }

  Future<void> _submit() async {
    if (submitting) return;

    if (selectedVoyageId == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("Veuillez sélectionner un voyage.")),
      );
      return;
    }

    // ✅ منع إرسال عدد مقاعد أكبر من المتاح (إذا السيرفر يرسله)
    final left = _seatsLeft();
    if (left > 0 && seats > left) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text("Places insuffisantes. Disponible: $left")),
      );
      setState(() {
        seats = left;
      });
      return;
    }

    if (pickedImage == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("Veuillez ajouter la preuve de paiement.")),
      );
      return;
    }

    setState(() => submitting = true);

    try {
      final url = Uri.parse("${ApiConfig.baseUrl}/api/mobile/reservations/");
      final req = http.MultipartRequest("POST", url);

      // ⚠️ انتبه: أسماؤك هنا يجب أن تطابق Django
      // عندك في Django: client_id / voyage_id / nb_sieges / preuve_paiement
      // بينما هنا كانت user_id / sieges / expected_amount / image
      // سأجعلها ترسل "الاثنين" لتعمل في كل الحالات بدون أن نكسر شيئًا.
      req.fields["user_id"] = widget.userId.toString();
      req.fields["client_id"] = widget.userId.toString();

      req.fields["voyage_id"] = selectedVoyageId.toString();
      req.fields["nb_sieges"] = seats.toString();
      req.fields["sieges"] = seats.toString();

      req.fields["expected_amount"] = _totalToPay().toStringAsFixed(1);

      final bytes = await pickedImage!.readAsBytes();

      // نرسل الملف باسمين كذلك (image + preuve_paiement) لأقصى توافق
      req.files.add(
        http.MultipartFile.fromBytes(
          "image",
          bytes,
          filename: pickedImage!.name,
        ),
      );
      req.files.add(
        http.MultipartFile.fromBytes(
          "preuve_paiement",
          bytes,
          filename: pickedImage!.name,
        ),
      );

      final streamed = await req.send();
      final body = await streamed.stream.bytesToString();

      if (streamed.statusCode == 200 || streamed.statusCode == 201) {
        final lower = body.toLowerCase();
        final ok = lower.contains("success") ||
            lower.contains("true") ||
            lower.contains("confirm") ||
            lower.contains("paye") ||
            lower.contains("payé");

        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(ok ? "Paiement reconnu ✅" : "Paiement non reconnu ❌")),
        );
      } else {
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text("Erreur (${streamed.statusCode}) : $body")),
        );
      }
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text("Erreur réseau: $e")),
      );
    } finally {
      if (mounted) setState(() => submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final v = _selectedVoyage();
    final trajet = (v?["trajet"] ?? v?["route"] ?? "—").toString();
    final left = _seatsLeft();

    return SingleChildScrollView(
      child: PageShell(
        child: SoftCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const SectionTitle(
                "Réservation",
                subtitle: "Choisissez un voyage et confirmez votre paiement",
              ),

              // Voyage dropdown
              loadingVoyages
                  ? const Padding(
                      padding: EdgeInsets.symmetric(vertical: 14),
                      child: Center(child: CircularProgressIndicator()),
                    )
                  : DropdownButtonFormField<int>(
                      value: selectedVoyageId,
                      isExpanded: true,
                      items: voyages.map((e) {
                        final idRaw = (e["id"] ?? e["id_voyage"]);
                        final id = (idRaw is int) ? idRaw : int.parse(idRaw.toString());

                        final label = _voyageLabel(e);

                        return DropdownMenuItem<int>(
                          value: id,
                          child: Text(
                            label,
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                          ),
                        );
                      }).toList(),
                      onChanged: (val) {
                        setState(() {
                          selectedVoyageId = val;

                          // ✅ عند تغيير الرحلة: اضبط المقاعد داخل المتاح
                          _clampSeatsToAvailable();
                        });
                      },
                      decoration: const InputDecoration(
                        labelText: "Voyage",
                        prefixIcon: Icon(Icons.alt_route_outlined),
                      ),
                    ),

              const SizedBox(height: 10),

              // ✅ عرض المقاعد المتاحة تحت القائمة (إذا موجودة)
              if (!loadingVoyages && left > 0)
                Padding(
                  padding: const EdgeInsets.only(bottom: 6),
                  child: Text(
                    "Places disponibles : $left",
                    style: TextStyle(
                      color: Colors.grey.shade700,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                ),

              const SizedBox(height: 12),

              // Seats selector (min 1)
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: Colors.grey.shade200),
                  color: Colors.white,
                ),
                child: Row(
                  children: [
                    const Icon(Icons.event_seat_outlined),
                    const SizedBox(width: 10),
                    const Expanded(
                      child: Text(
                        "Nombre de sièges",
                        style: TextStyle(fontWeight: FontWeight.w800),
                      ),
                    ),
                    IconButton(
                      onPressed: seats > 1
                          ? () {
                              setState(() {
                                seats--;
                              });
                            }
                          : null,
                      icon: const Icon(Icons.remove_circle_outline),
                    ),
                    SizedBox(
                      width: 36,
                      child: Center(
                        child: Text(
                          seats.toString(),
                          style: const TextStyle(fontWeight: FontWeight.w900, fontSize: 16),
                        ),
                      ),
                    ),
                    IconButton(
                      onPressed: () {
                        setState(() {
                          // ✅ لا تتجاوز المقاعد المتاحة إذا موجودة
                          if (left > 0 && seats >= left) {
                            ScaffoldMessenger.of(context).showSnackBar(
                              SnackBar(content: Text("Maximum disponible: $left")),
                            );
                            seats = left;
                          } else {
                            seats++;
                          }
                        });
                      },
                      icon: const Icon(Icons.add_circle_outline),
                    ),
                  ],
                ),
              ),

              const SizedBox(height: 12),

              MutedInfoBox(
                icon: Icons.payments_outlined,
                title: "Total à payer",
                subtitle: "${_pricePerSeat().toStringAsFixed(1)} MRU / siège  •  $seats siège(s)",
                value: "${_totalToPay().toStringAsFixed(1)} MRU",
              ),

              const SizedBox(height: 14),

              // Image picker block
              InkWell(
                onTap: _pickImage,
                borderRadius: BorderRadius.circular(18),
                child: Container(
                  height: 220,
                  width: double.infinity,
                  clipBehavior: Clip.antiAlias,
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(18),
                    border: Border.all(color: Colors.grey.shade200),
                    color: Colors.white,
                  ),
                  child: (imageBytes == null)
                      ? Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Icon(Icons.add_a_photo_outlined, size: 44, color: Colors.grey.shade500),
                            const SizedBox(height: 10),
                            const Text("Ajouter la preuve de paiement", style: TextStyle(fontWeight: FontWeight.w800)),
                            const SizedBox(height: 4),
                            Text("Cliquez pour choisir une image", style: TextStyle(color: Colors.grey.shade600)),
                          ],
                        )
                      : Stack(
                          fit: StackFit.expand,
                          children: [
                            Image.memory(imageBytes!, fit: BoxFit.cover),
                            Positioned(
                              left: 12,
                              bottom: 12,
                              child: Container(
                                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                                decoration: BoxDecoration(
                                  color: Colors.black.withOpacity(0.55),
                                  borderRadius: BorderRadius.circular(999),
                                ),
                                child: Text(
                                  "Trajet: $trajet",
                                  style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w700),
                                ),
                              ),
                            )
                          ],
                        ),
                ),
              ),

              const SizedBox(height: 14),

              PrimaryButton(
                text: "Confirmer et vérifier",
                icon: Icons.verified_outlined,
                loading: submitting,
                onPressed: _submit,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
