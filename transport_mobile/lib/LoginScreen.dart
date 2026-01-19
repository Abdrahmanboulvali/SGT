import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import 'DashboardScreen.dart';
import 'RegisterScreen.dart';
import 'ui/ui_widgets.dart';

class ApiConfig {
  // ✅ عدّل هذا حسب بيئتك
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

        final prefs = await SharedPreferences.getInstance();
        await prefs.setInt("user_id", userId);
        await prefs.setString("username", username);

        if (!mounted) return;
        Navigator.pushReplacement(
          context,
          MaterialPageRoute(
            builder: (_) => DashboardScreen(userId: userId, username: username),
          ),
        );
      } else {
        final msg = res.body.isNotEmpty ? res.body : "Identifiants invalides.";
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
  Widget build(BuildContext context) {
    return Scaffold(
      body: PageShell(
        maxWidth: 560,
        child: SoftCard(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const SectionTitle(
                "Connexion",
                subtitle: "Accédez à votre espace SGT",
              ),
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
              const SizedBox(height: 8),
              Align(
                alignment: Alignment.center,
                child: TextButton(
                  onPressed: () {
                    Navigator.push(
                      context,
                      MaterialPageRoute(builder: (_) => const RegisterScreen()),
                    );
                  },
                  child: const Text("Créer un compte"),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
