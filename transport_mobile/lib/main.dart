import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'ui/app_theme.dart';
import 'LoginScreen.dart';
import 'DashboardScreen.dart';

void main() {
  runApp(const MyApp());
}

class MyApp extends StatefulWidget {
  const MyApp({super.key});

  @override
  State<MyApp> createState() => _MyAppState();
}

class _MyAppState extends State<MyApp> {
  Future<Map<String, dynamic>?> _loadSession() async {
    final prefs = await SharedPreferences.getInstance();
    final userId = prefs.getInt('user_id');
    final username = prefs.getString('username');
    if (userId == null || username == null) return null;
    return {"user_id": userId, "username": username};
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'SGT Transport',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.theme(),
      home: FutureBuilder<Map<String, dynamic>?>(
        future: _loadSession(),
        builder: (context, snap) {
          if (snap.connectionState != ConnectionState.done) {
            return const Scaffold(
              body: Center(
                child: CircularProgressIndicator(),
              ),
            );
          }
          if (snap.data == null) {
            return const LoginScreen();
          }
          return DashboardScreen(
            userId: snap.data!["user_id"] as int,
            username: snap.data!["username"] as String,
          );
        },
      ),
    );
  }
}
