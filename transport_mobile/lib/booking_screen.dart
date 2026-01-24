import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:image_picker/image_picker.dart';

import 'LoginScreen.dart';
import 'ui/ui_widgets.dart';
import 'ui/app_theme.dart';

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
  Uint8List? imageBytes;

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
      if (seats < 1) seats = 1;
      return;
    }
    if (seats > left) {
      seats = left;
      if (seats < 1) seats = 1;
    }
  }

  String _voyageLabel(Map<String, dynamic> v) {
    final label = v["label"];
    if (label != null && label.toString().trim().isNotEmpty) {
      return label.toString();
    }

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

    final left = _seatsLeft();
    if (left > 0 && seats > left) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text("Places insuffisantes. Disponible: $left")),
      );
      setState(() => seats = left);
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

      req.fields["user_id"] = widget.userId.toString();
      req.fields["client_id"] = widget.userId.toString();

      req.fields["voyage_id"] = selectedVoyageId.toString();
      req.fields["nb_sieges"] = seats.toString();
      req.fields["sieges"] = seats.toString();

      req.fields["expected_amount"] = _totalToPay().toStringAsFixed(1);

      final bytes = await pickedImage!.readAsBytes();

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
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text("Réservation envoyée ✅ En attente de validation par le gestionnaire."),
          ),
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
        maxWidth: 720,
        child: Column(
          children: [
            GradientHeader(
              title: "Réservation",
              subtitle: "Choisissez un voyage et envoyez votre preuve",
              icon: Icons.confirmation_number_outlined,
            ),
            const SizedBox(height: 14),

            SoftCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const SectionTitle(
                    "Détails",
                    subtitle: "Sélection • Sièges • Paiement",
                  ),

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

                            return DropdownMenuItem<int>(
                              value: id,
                              child: Text(
                                _voyageLabel(e),
                                maxLines: 2,
                                overflow: TextOverflow.ellipsis,
                              ),
                            );
                          }).toList(),
                          onChanged: (val) {
                            setState(() {
                              selectedVoyageId = val;
                              _clampSeatsToAvailable();
                            });
                          },
                          decoration: const InputDecoration(
                            labelText: "Voyage",
                            prefixIcon: Icon(Icons.alt_route_outlined),
                          ),
                        ),

                  const SizedBox(height: 10),

                  if (!loadingVoyages)
                    Row(
                      children: [
                        Icon(Icons.event_seat_outlined, size: 18, color: Colors.grey.shade700),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            left > 0 ? "Places disponibles : $left" : "Places disponibles : —",
                            style: TextStyle(
                              color: Colors.grey.shade700,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ),
                        if (left > 0)
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                            decoration: BoxDecoration(
                              color: AppTheme.primary.withOpacity(.10),
                              borderRadius: BorderRadius.circular(999),
                            ),
                            child: Text(
                              "OK",
                              style: TextStyle(
                                color: AppTheme.primary,
                                fontWeight: FontWeight.w900,
                              ),
                            ),
                          )
                      ],
                    ),

                  const SizedBox(height: 12),

                  // ✅ Seats selector
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(18),
                      border: Border.all(color: Colors.grey.shade200),
                      color: Colors.white,
                    ),
                    child: Row(
                      children: [
                        Container(
                          width: 42,
                          height: 42,
                          decoration: BoxDecoration(
                            color: Colors.black.withOpacity(.04),
                            borderRadius: BorderRadius.circular(14),
                          ),
                          child: const Icon(Icons.event_seat_outlined),
                        ),
                        const SizedBox(width: 12),
                        const Expanded(
                          child: Text(
                            "Nombre de sièges",
                            style: TextStyle(fontWeight: FontWeight.w900),
                          ),
                        ),
                        IconButton(
                          onPressed: seats > 1 ? () => setState(() => seats--) : null,
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

                  // ✅ Upload
                  InkWell(
                    onTap: _pickImage,
                    borderRadius: BorderRadius.circular(20),
                    child: Container(
                      height: 220,
                      width: double.infinity,
                      clipBehavior: Clip.antiAlias,
                      decoration: BoxDecoration(
                        borderRadius: BorderRadius.circular(20),
                        border: Border.all(color: Colors.grey.shade200),
                        color: Colors.white,
                      ),
                      child: (imageBytes == null)
                          ? Column(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                Container(
                                  width: 62,
                                  height: 62,
                                  decoration: BoxDecoration(
                                    color: AppTheme.primary.withOpacity(.10),
                                    borderRadius: BorderRadius.circular(20),
                                  ),
                                  child: Icon(Icons.add_a_photo_outlined, size: 28, color: AppTheme.primary),
                                ),
                                const SizedBox(height: 10),
                                const Text(
                                  "Ajouter la preuve de paiement",
                                  style: TextStyle(fontWeight: FontWeight.w900),
                                ),
                                const SizedBox(height: 4),
                                Text(
                                  "Cliquez pour choisir une image",
                                  style: TextStyle(color: Colors.grey.shade600, fontWeight: FontWeight.w600),
                                ),
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
                                      style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w800),
                                    ),
                                  ),
                                )
                              ],
                            ),
                    ),
                  ),

                  const SizedBox(height: 14),

                  PrimaryButton(
                    text: "Confirmer la réservation",
                    icon: Icons.send_outlined,
                    loading: submitting,
                    onPressed: _submit,
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
