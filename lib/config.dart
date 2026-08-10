import 'package:flutter/foundation.dart';

class AppConfig {
  /// URL de base de l'API selon la plateforme :
  ///   - Web (Chrome)        → localhost:8000
  ///   - Émulateur Android   → 10.0.2.2:8000
  ///   - Appareil physique   → ngrok tunnel
  static String get baseUrl {
    if (kIsWeb) {
      // Flutter Web (Chrome, Edge…) → le backend tourne sur le même PC
      return 'http://localhost:8000';
    }
    // Appareil physique → tunnel ngrok
    return 'https://yesterday-bleach-mold.ngrok-free.dev';

    // 👇 Émulateur Android :
    // return 'http://10.0.2.2:8000';

    // 👇 Appareil physique sur même réseau (si pas de client isolation) :
    // return 'http://10.91.231.153:8000';
  }
}
