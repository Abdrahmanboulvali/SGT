import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

import 'LoginScreen.dart';
import 'ui/ui_widgets.dart';

class RegisterScreen extends StatefulWidget {
  const RegisterScreen({super.key});

  @override
  State<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends State<RegisterScreen> {
  final prenom = TextEditingController();
  final nom = TextEditingController();
  final telephone = TextEditingController();
  final email = TextEditingController();
  final username = TextEditingController();
  final password = TextEditingController();
  final password2 = TextEditingController();

  bool loading = false;

  Future<void> _register() async {
    if (loading) return;

    final data = {
      "prenom": prenom.text.trim(),
      "nom": nom.text.trim(),
      "telephone": telephone.text.trim(),
      "email": email.text.trim(),
      "username": username.text.trim(),
      "password": password.text.trim(),
      "password2": password2.text.trim(),
    };

    if (data.values.any((v) => v.isEmpty)) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("Veuillez remplir tous les champs.")),
      );
      return;
    }
    if (data["password"] != data["password2"]) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text("Les mots de passe ne correspondent pas.")),
      );
      return;
    }

    setState(() => loading = true);
    try {
      final url = Uri.parse("${ApiConfig.baseUrl}/api/mobile/register/");
      final res = await http.post(
        url,
        headers: {"Content-Type": "application/json"},
        body: jsonEncode(data),
      );

      if (res.statusCode == 201 || res.statusCode == 200) {
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text("Compte créé avec succès. Vous pouvez vous connecter.")),
        );
        Navigator.pop(context);
      } else {
        final msg = res.body.isNotEmpty ? res.body : "Erreur lors de l'inscription.";
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
      }
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text("Erreur réseau: $e")));
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text("Créer un compte")),
      body: SafeArea(
        child: SingleChildScrollView(
          child: PageShell(
            maxWidth: 720,
            child: Column(
              children: [
                GradientHeader(
                  title: "Inscription",
                  subtitle: "Rejoignez la plateforme SGT",
                  icon: Icons.person_add_alt_1,
                ),
                const SizedBox(height: 14),

                SoftCard(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const SectionTitle("Informations", subtitle: "Remplissez les champs ci-dessous"),
                      Row(
                        children: [
                          Expanded(
                            child: TextField(
                              controller: prenom,
                              decoration: const InputDecoration(
                                labelText: "Prénom",
                                prefixIcon: Icon(Icons.badge_outlined),
                              ),
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: TextField(
                              controller: nom,
                              decoration: const InputDecoration(
                                labelText: "Nom",
                                prefixIcon: Icon(Icons.badge_outlined),
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 12),
                      Row(
                        children: [
                          Expanded(
                            child: TextField(
                              controller: telephone,
                              keyboardType: TextInputType.phone,
                              decoration: const InputDecoration(
                                labelText: "Téléphone",
                                prefixIcon: Icon(Icons.phone_outlined),
                              ),
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: TextField(
                              controller: email,
                              keyboardType: TextInputType.emailAddress,
                              decoration: const InputDecoration(
                                labelText: "Email",
                                prefixIcon: Icon(Icons.email_outlined),
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 12),
                      TextField(
                        controller: username,
                        decoration: const InputDecoration(
                          labelText: "Nom d'utilisateur",
                          prefixIcon: Icon(Icons.person_outline),
                        ),
                      ),
                      const SizedBox(height: 12),
                      Row(
                        children: [
                          Expanded(
                            child: TextField(
                              controller: password,
                              obscureText: true,
                              decoration: const InputDecoration(
                                labelText: "Mot de passe",
                                prefixIcon: Icon(Icons.lock_outline),
                              ),
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: TextField(
                              controller: password2,
                              obscureText: true,
                              decoration: const InputDecoration(
                                labelText: "Confirmation",
                                prefixIcon: Icon(Icons.verified_outlined),
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 18),
                      PrimaryButton(
                        text: "Créer mon compte",
                        icon: Icons.person_add_alt_1,
                        loading: loading,
                        onPressed: _register,
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
