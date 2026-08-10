// lib/main.dart
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:firebase_core/firebase_core.dart';

import 'context/auth_context.dart';
import 'router/app_router.dart';
import 'theme/app_theme.dart';
import 'firebase_options.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Initialisation Firebase
  await Firebase.initializeApp(
    options: DefaultFirebaseOptions.currentPlatform,
  );

  runApp(
    MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => AuthContext()),
        ChangeNotifierProvider(create: (_) => ThemeProvider()),
      ],
      child: const PropTechApp(),
    ),
  );
}

class PropTechApp extends StatelessWidget {
  const PropTechApp({super.key});

  @override
  Widget build(BuildContext context) {
    final auth   = context.watch<AuthContext>();
    final themes = context.watch<ThemeProvider>();

    return MaterialApp.router(
      title: 'PropIQ',
      debugShowCheckedModeBanner: false,
      theme:     themes.lightTheme,
      darkTheme: themes.darkTheme,
      themeMode: themes.themeMode,
      routerConfig: AppRouter.createRouter(auth),
    );
  }
}
