import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../context/auth_context.dart';
import '../pages/splash_screen.dart';
import '../pages/home_page.dart';
import '../pages/auth_page.dart';
import '../pages/free_chat_page.dart';
import '../pages/quality_life_page.dart';
import '../pages/history_page.dart';
import '../pages/settings_page.dart';
import '../pages/plan_selection_page.dart';
import '../pages/payment_webview_page.dart';
import '../pages/payment_success_page.dart'; // ← nouveau
import '../widgets/main_scaffold.dart';

class AppRouter {
  static GoRouter createRouter(AuthContext auth) {
    return GoRouter(
      initialLocation: '/splash',
      redirect: (context, state) {
        final isAuth = auth.isAuthenticated;
        final protectedRoutes = ['/free-chat', '/quality-life', '/history', '/plan-selection'];
        final isGoingToProtected =
        protectedRoutes.any((r) => state.matchedLocation.startsWith(r));

        if (state.matchedLocation == '/splash') return null;
        if (!isAuth && isGoingToProtected) return '/signin';
        return null;
      },
      routes: [
        GoRoute(
          path: '/splash',
          builder: (context, state) => const SplashScreen(),
        ),

        // ── Routes hors Shell (sans Navbar) ───────────────────────
        GoRoute(
          path: '/plan-selection',
          builder: (context, state) => const PlanSelectionPage(),
        ),

        GoRoute(
          path: '/success',
          builder: (context, state) {
            final sessionId = state.uri.queryParameters['session_id'] ?? '';
            final uid = state.uri.queryParameters['uid'] ?? '';
            return PaymentSuccessPage(sessionId: sessionId, uid: uid);
          },
        ),

        GoRoute(
          path: '/payment-webview',
          builder: (context, state) {
            final url = state.extra as String;
            return PaymentWebViewPage(url: url);
          },
        ),







        // ── Shell avec Navbar ─────────────────────────────────────
        ShellRoute(
          builder: (context, state, child) => MainScaffold(child: child),
          routes: [
            GoRoute(path: '/',             builder: (c, s) => const HomePage()),
            GoRoute(path: '/signin',       builder: (c, s) => const AuthPage(type: 'signin')),
            GoRoute(path: '/signup',       builder: (c, s) => const AuthPage(type: 'signup')),
            GoRoute(path: '/free-chat',    builder: (c, s) => const FreeChatPage()),
            GoRoute(path: '/quality-life', builder: (c, s) => const QualityLifePage()),
            GoRoute(path: '/history',      builder: (c, s) => const HistoryPage()),
            GoRoute(path: '/settings',     builder: (c, s) => const SettingsPage()),
          ],
        ),
      ],
    );
  }
}