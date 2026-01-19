import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'booking_screen.dart';
import 'MyReservations.dart';
import 'LoginScreen.dart';
import 'ui/ui_widgets.dart';

class DashboardScreen extends StatefulWidget {
  final int userId;
  final String username;

  const DashboardScreen({super.key, required this.userId, required this.username});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  int _index = 0;

  Future<void> _logout() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove("user_id");
    await prefs.remove("username");
    if (!mounted) return;
    Navigator.pushAndRemoveUntil(
      context,
      MaterialPageRoute(builder: (_) => const LoginScreen()),
      (_) => false,
    );
  }

  @override
  Widget build(BuildContext context) {
    final pages = [
      BookingScreen(userId: widget.userId, username: widget.username),
      MyReservationsScreen(userId: widget.userId),
    ];

    return Scaffold(
      appBar: AppBar(
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text("Bonjour, ${widget.username}", style: const TextStyle(fontWeight: FontWeight.w900)),
            Text("SGT Transport", style: TextStyle(color: Colors.grey.shade600, fontSize: 12)),
          ],
        ),
        actions: [
          IconButton(
            tooltip: "Déconnexion",
            onPressed: _logout,
            icon: const Icon(Icons.logout),
          ),
          const SizedBox(width: 6),
        ],
      ),
      body: pages[_index],
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: (i) => setState(() => _index = i),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.home_outlined), selectedIcon: Icon(Icons.home), label: "Accueil"),
          NavigationDestination(icon: Icon(Icons.history_outlined), selectedIcon: Icon(Icons.history), label: "Mes réservations"),
        ],
      ),
    );
  }
}
