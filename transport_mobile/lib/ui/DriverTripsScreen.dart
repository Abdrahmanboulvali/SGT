import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:url_launcher/url_launcher.dart';

import '../LoginScreen.dart';
import 'ui_widgets.dart';
import 'app_theme.dart';

class DriverTripsScreen extends StatefulWidget {
  const DriverTripsScreen({super.key});

  @override
  State<DriverTripsScreen> createState() => _DriverTripsScreenState();
}

class _DriverTripsScreenState extends State<DriverTripsScreen> {
  // ========= config =========
  static const String _baseUrl = "http://127.0.0.1:8000";

  // ========= state =========
  bool loading = true;
  String? errorMsg;

  List<Map<String, dynamic>> trips = [];

  // pagination (client-side)
  int page = 1;
  final int pageSize = 5;

  // whatsapp admin
  String whatsappDigits = "";

  @override
  void initState() {
    super.initState();
    _fetchWhatsappNumber();
    _fetchTrips();
  }

  // =========================
  // Helpers: session
  // =========================
  Future<String?> _getToken() async {
    final prefs = await SharedPreferences.getInstance();
    final t = prefs.getString("token");
    if (t == null || t.trim().isEmpty) return null;
    return t.trim();
  }

  Future<String> _getUsername() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString("username") ?? "chauffeur";
  }

  // =========================
  // Logout
  // =========================
  Future<void> _logout() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove("user_id");
    await prefs.remove("username");
    await prefs.remove("role");
    await prefs.remove("token");

    if (!mounted) return;
    Navigator.pushAndRemoveUntil(
      context,
      MaterialPageRoute(builder: (_) => const LoginScreen()),
      (_) => false,
    );
  }

  // =========================
  // WhatsApp admin number
  // =========================
  String _digitsOnly(String s) => s.replaceAll(RegExp(r"[^0-9]"), "");

  Future<void> _fetchWhatsappNumber() async {
    try {
      final url = Uri.parse("$_baseUrl/api/mobile/payment-options/");
      final res = await http.get(url);
      if (res.statusCode == 200) {
        final data = jsonDecode(res.body);
        final raw = (data["whatsapp_number"] ?? "").toString();
        final digits = _digitsOnly(raw);
        if (mounted) setState(() => whatsappDigits = digits);
      }
    } catch (_) {
      // not critical
    }
  }

  Future<void> _openWhatsAppAdmin() async {
    final digits = whatsappDigits.trim();
    if (digits.isEmpty) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("Le numéro WhatsApp de l'administration est incorrect.")),
      );
      return;
    }

    final username = await _getUsername();
    final msg = "Bonjour, je suis le chauffeur ($username). J’ai besoin d’aide.";

    final appUri = Uri.parse(
      "whatsapp://send?phone=$digits&text=${Uri.encodeComponent(msg)}",
    );
    final okApp = await launchUrl(appUri, mode: LaunchMode.externalApplication);
    if (okApp) return;

    final webUri = Uri.parse(
      "https://api.whatsapp.com/send?phone=$digits&text=${Uri.encodeComponent(msg)}",
    );
    final okWeb = await launchUrl(webUri, mode: LaunchMode.externalApplication);
    if (!okWeb && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("WhatsApp n'a pas pu être ouvert.")),
      );
    }
  }

  // =========================
  // ✅ Extract list from API response (List OR Map)
  // =========================
  List<dynamic> _extractList(dynamic decoded) {
    if (decoded is List) return decoded;

    if (decoded is Map) {
      final keys = ["results", "data", "voyages", "items", "trips"];
      for (final k in keys) {
        final v = decoded[k];
        if (v is List) return v;
      }

      return [];
    }

    return [];
  }

  bool _looksLikeHtml(String body) {
    final t = body.trimLeft();
    return t.startsWith("<!DOCTYPE html") || t.startsWith("<html") || t.contains("<title>");
  }

  // =========================
  // API fetch trips
  // =========================
  Future<void> _fetchTrips() async {
    setState(() {
      loading = true;
      errorMsg = null;
    });

    try {
      final token = await _getToken();
      if (token == null) {
        setState(() {
          loading = false;
          errorMsg = "Token introuvable. Reconnectez-vous.";
        });
        return;
      }

      final url = Uri.parse("$_baseUrl/api/mobile/chauffeur/voyages/");
      final res = await http.get(
        url,
        headers: {
          "Authorization": "Token $token",
          "Content-Type": "application/json",
        },
      );

      if (res.statusCode == 200) {
        if (_looksLikeHtml(res.body)) {
          setState(() {
            loading = false;
            errorMsg = "Erreur serveur: Django a renvoyé une page HTML.";
          });
          return;
        }

        final decoded = jsonDecode(res.body);
        final rawList = _extractList(decoded);

        final list = rawList
            .where((e) => e is Map)
            .map((e) => Map<String, dynamic>.from(e as Map))
            .toList();

        setState(() {
          trips = list;
          loading = false;
          page = 1; // reset pagination
        });


        if (trips.isEmpty && decoded is Map) {
          final keys = decoded.keys.map((e) => e.toString()).join(", ");
          setState(() {
            errorMsg = "Format JSON inattendu. Keys: $keys";
          });
        }
      } else if (res.statusCode == 401 || res.statusCode == 403) {
        setState(() {
          loading = false;
          errorMsg = "Session expirée. Reconnectez-vous.";
        });
      } else {
        setState(() {
          loading = false;
          errorMsg = "Erreur serveur: ${res.statusCode}";
        });
      }
    } catch (e) {
      setState(() {
        loading = false;
        errorMsg = "Erreur réseau: $e";
      });
    }
  }

  // =========================
  // UI helpers (trip fields)
  // =========================
  String _val(Map<String, dynamic> m, List<String> keys, [String fallback = "—"]) {
    for (final k in keys) {
      final v = m[k];
      if (v != null && v.toString().trim().isNotEmpty) return v.toString();
    }
    return fallback;
  }

  Widget _miniInfo(IconData icon, String text) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 18, color: Colors.grey.shade700),
        const SizedBox(width: 6),
        Text(
          text,
          style: TextStyle(
            color: Colors.grey.shade800,
            fontWeight: FontWeight.w800,
          ),
        ),
      ],
    );
  }

  // =========================
  // Pagination (client-side)
  // =========================
  int get _totalPages {
    if (trips.isEmpty) return 1;
    final t = (trips.length / pageSize).ceil();
    return t < 1 ? 1 : t;
  }

  List<Map<String, dynamic>> get _pagedTrips {
    final start = (page - 1) * pageSize;
    if (start >= trips.length) return [];
    final end = start + pageSize;
    return trips.sublist(start, end > trips.length ? trips.length : end);
  }

  void _nextPage() {
    if (page < _totalPages) setState(() => page++);
  }

  void _prevPage() {
    if (page > 1) setState(() => page--);
  }

  @override
  Widget build(BuildContext context) {
    final paged = _pagedTrips;

    return Scaffold(
      body: SafeArea(
        child: SingleChildScrollView(
          child: PageShell(
            maxWidth: 780,
            child: Column(
              children: [
                GradientHeader(
                  title: "Mes voyages (Chauffeur)",
                  subtitle: "Uniquement les voyages qui vous sont assignés",
                  icon: Icons.directions_bus,
                ),
                const SizedBox(height: 12),

                Row(
                  mainAxisAlignment: MainAxisAlignment.end,
                  children: [
                    IconButton(
                      tooltip: "Rafraîchir",
                      onPressed: loading ? null : _fetchTrips,
                      icon: const Icon(Icons.refresh),
                    ),
                    const SizedBox(width: 6),
                    TextButton.icon(
                      onPressed: _openWhatsAppAdmin,
                      icon: const Icon(Icons.chat_bubble_outline),
                      label: const Text("WhatsApp Gestion"),
                    ),
                    const SizedBox(width: 10),
                    TextButton.icon(
                      onPressed: _logout,
                      icon: const Icon(Icons.logout),
                      label: const Text("Déconnexion"),
                    ),
                  ],
                ),

                const SizedBox(height: 10),

                if (loading)
                  const Padding(
                    padding: EdgeInsets.symmetric(vertical: 30),
                    child: Center(child: CircularProgressIndicator()),
                  )
                else if (errorMsg != null)
                  SoftCard(
                    child: Column(
                      children: [
                        const SizedBox(height: 10),
                        Icon(Icons.error_outline, size: 56, color: Colors.red.shade400),
                        const SizedBox(height: 10),
                        Text(
                          "Erreur: $errorMsg",
                          textAlign: TextAlign.center,
                          style: const TextStyle(fontWeight: FontWeight.w800),
                        ),
                        const SizedBox(height: 14),
                        PrimaryButton(
                          text: "Se reconnecter",
                          icon: Icons.login,
                          onPressed: _logout,
                        ),
                      ],
                    ),
                  )
                else if (trips.isEmpty)
                  SoftCard(
                    child: Column(
                      children: const [
                        SizedBox(height: 12),
                        Icon(Icons.inbox_outlined, size: 52),
                        SizedBox(height: 10),
                        Text(
                          "Aucun voyage assigné pour le moment.",
                          style: TextStyle(fontWeight: FontWeight.w800),
                        ),
                        SizedBox(height: 6),
                        Text("Essayez de rafraîchir plus tard."),
                      ],
                    ),
                  )
                else
                  Column(
                    children: [
                      for (final t in paged)
                        Padding(
                          padding: const EdgeInsets.only(bottom: 12),
                          child: SoftCard(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  "${_val(t, ["depart", "ville_depart", "from"])} → ${_val(t, ["arrivee", "ville_arrivee", "to"])}",
                                  style: const TextStyle(
                                    fontWeight: FontWeight.w900,
                                    fontSize: 18,
                                  ),
                                ),
                                const SizedBox(height: 10),
                                Wrap(
                                  spacing: 16,
                                  runSpacing: 8,
                                  children: [
                                    _miniInfo(Icons.calendar_month_outlined,
                                        _val(t, ["date_depart", "date", "date_voyage"])),
                                    _miniInfo(Icons.access_time, _val(t, ["heure_depart", "heure", "time"])),
                                    _miniInfo(Icons.directions_car_filled_outlined,
                                        _val(t, ["vehicule", "vehicule_matricule", "matricule", "car"])),
                                    _miniInfo(Icons.flag_outlined, _val(t, ["statut", "status"], "OUVERT")),
                                  ],
                                ),
                              ],
                            ),
                          ),
                        ),

                      const SizedBox(height: 8),

                      SoftCard(
                        child: Row(
                          children: [
                            Expanded(
                              child: Text(
                                "Page $page / $_totalPages",
                                style: const TextStyle(fontWeight: FontWeight.w900),
                              ),
                            ),
                            OutlinedButton.icon(
                              onPressed: page > 1 ? _prevPage : null,
                              icon: const Icon(Icons.chevron_left),
                              label: const Text("Précédent"),
                            ),
                            const SizedBox(width: 8),
                            OutlinedButton.icon(
                              onPressed: page < _totalPages ? _nextPage : null,
                              icon: const Icon(Icons.chevron_right),
                              label: const Text("Suivant"),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),

                const SizedBox(height: 22),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
