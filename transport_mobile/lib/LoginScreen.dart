import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import 'DashboardScreen.dart';
import 'RegisterScreen.dart';
import 'ui/ui_widgets.dart';
import 'ui/app_theme.dart';
import 'ui/DriverTripsScreen.dart'; // صفحة السائق

class ApiConfig {
  static const String baseUrl = "http://127.0.0.1:8000";
}

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _username = TextEditingController();
  final _password = TextEditingController();
  bool _loading = false;

  Future<void> _login() async {
    final u = _username.text.trim();
    final p = _password.text.trim();

    if (u.isEmpty || p.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("Veuillez remplir les champs.")),
      );
      return;
    }

    setState(() => _loading = true);
    try {
      final url = Uri.parse("${ApiConfig.baseUrl}/api/mobile/login/");
      final res = await http.post(
        url,
        headers: {"Content-Type": "application/json"},
        body: jsonEncode({"username": u, "password": p}),
      );

      if (res.statusCode == 200) {
        final data = jsonDecode(res.body);

        final userId = data["user_id"] as int;
        final username = (data["username"] ?? u).toString();
        final role = (data["role"] ?? "CLIENT").toString();
        final token = (data["token"] ?? "").toString(); // ✅ مهم

        final prefs = await SharedPreferences.getInstance();
        await prefs.setInt("user_id", userId);
        await prefs.setString("username", username);
        await prefs.setString("role", role);

        // ✅ حفظ التوكن إذا موجود
        if (token.trim().isNotEmpty) {
          await prefs.setString("token", token.trim());
        } else {
          await prefs.remove("token");
        }

        if (!mounted) return;

        // ✅ redirect حسب role
        if (role == "CHAUFFEUR") {
          Navigator.pushReplacement(
            context,
            MaterialPageRoute(builder: (_) => const DriverTripsScreen()),
          );
        } else {
          Navigator.pushReplacement(
            context,
            MaterialPageRoute(
              builder: (_) => DashboardScreen(userId: userId, username: username),
            ),
          );
        }
      } else {
        String msg = "Identifiants invalides.";
        try {
          final decoded = jsonDecode(res.body);
          if (decoded is Map && decoded["message"] != null) {
            msg = decoded["message"].toString();
          } else if (decoded is Map && decoded["detail"] != null) {
            msg = decoded["detail"].toString();
          }
        } catch (_) {
          if (res.body.isNotEmpty) msg = res.body;
        }

        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
      }
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text("Erreur réseau: $e")),
      );
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  void dispose() {
    _username.dispose();
    _password.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: PageShell(
          maxWidth: 560,
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              GradientHeader(
                title: "SGT Transport",
                subtitle: "Connectez-vous à votre espace",
                icon: Icons.directions_bus,
              ),
              const SizedBox(height: 14),

              SoftCard(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const SectionTitle("Connexion", subtitle: "Accédez à votre espace SGT"),

                    TextField(
                      controller: _username,
                      decoration: const InputDecoration(
                        labelText: "Nom d'utilisateur",
                        prefixIcon: Icon(Icons.person_outline),
                      ),
                    ),
                    const SizedBox(height: 12),

                    TextField(
                      controller: _password,
                      obscureText: true,
                      decoration: const InputDecoration(
                        labelText: "Mot de passe",
                        prefixIcon: Icon(Icons.lock_outline),
                      ),
                    ),

                    const SizedBox(height: 18),

                    PrimaryButton(
                      text: "Se connecter",
                      icon: Icons.login,
                      loading: _loading,
                      onPressed: _login,
                    ),

                    const SizedBox(height: 10),

                    Center(
                      child: TextButton(
                        onPressed: () {
                          Navigator.push(
                            context,
                            MaterialPageRoute(builder: (_) => const RegisterScreen()),
                          );
                        },
                        child: Text(
                          "Créer un compte",
                          style: TextStyle(
                            color: AppTheme.primary,
                            fontWeight: FontWeight.w900,
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
