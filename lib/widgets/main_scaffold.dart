// lib/widgets/main_scaffold.dart
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';


import '../context/auth_context.dart';
import '../theme/app_theme.dart';

class MainScaffold extends StatelessWidget {
  final Widget child;
  const MainScaffold({super.key, required this.child});

  @override
  Widget build(BuildContext context) {
    final theme  = Theme.of(context);
    return Scaffold(
      backgroundColor: theme.colorScheme.background,
      body: Column(
        children: [
          const PropTechNavbar(),
          Expanded(child: child),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
//  TOP NAVBAR
// ─────────────────────────────────────────────────────────────────────────────

class PropTechNavbar extends StatelessWidget {
  const PropTechNavbar({super.key});

  @override
  Widget build(BuildContext context) {
    final theme    = Theme.of(context);
    final isDark   = theme.brightness == Brightness.dark;
    final provider = context.watch<ThemeProvider>();
    final palette  = AccentPalette.all[provider.accent]!;
    final auth     = context.watch<AuthContext>();
    final location = GoRouterState.of(context).matchedLocation;
    final isMobile = MediaQuery.of(context).size.width < 600;

    final bgColor     = isDark ? AppColors.darkSurface  : AppColors.lightSurface;
    final borderColor = isDark ? AppColors.darkBorder2  : AppColors.lightBorder;
    final textMain    = isDark ? AppColors.darkText1     : AppColors.lightText1;
    final textMuted   = isDark ? AppColors.darkText2     : AppColors.lightText2;
    final iconBg      = isDark ? AppColors.darkSurface2  : AppColors.lightBg;

    return Container(
      height: 64,
      decoration: BoxDecoration(
        color: bgColor,
        border: Border(
          bottom: BorderSide(color: borderColor, width: 0.5),
        ),
      ),
      padding: const EdgeInsets.symmetric(horizontal: 18),
      child: Row(
        children: [
          // ── Logo ──────────────────────────────────────────────────────
          GestureDetector(
            onTap: () => context.go('/'),
            child: Row(
              children: [
                Container(
                  width: 32,
                  height: 32,
                  decoration: BoxDecoration(
                    color: const Color(0xFF2A7FC4),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: const Icon(Icons.home_work_rounded,
                      color: Colors.white, size: 16),
                ),
                const SizedBox(width: 9),
                if (!isMobile || MediaQuery.of(context).size.width > 360)
                  Text(
                    'PropIQ',
                    style: TextStyle(
                      color: textMain,
                      fontWeight: FontWeight.w700,
                      fontSize: 15,
                      letterSpacing: 0.2,
                    ),
                  ),
              ],
            ),
          ),

          const Spacer(),

          // ── Desktop nav links ─────────────────────────────────────────
          if (!isMobile) ...[
            _NavLink(
                label: 'Home',
                path: '/',
                current: location,
                primary: const Color(0xFF2A7FC4),
                textMuted: textMuted),
            const SizedBox(width: 24),
            _NavLink(
                label: 'Quality Life',
                path: '/quality-life',
                current: location,
                primary: const Color(0xFF2A7FC4),
                textMuted: textMuted),
            const SizedBox(width: 24),
            _NavLink(
                label: 'Chat',
                path: '/free-chat',
                current: location,
                primary: const Color(0xFF2A7FC4),
                textMuted: textMuted),
            const SizedBox(width: 28),
          ],

          // ── Auth ──────────────────────────────────────────────────────
          if (auth.isAuthenticated) ...[
            _NavIconBtn(
              icon: Icons.history,
              tooltip: 'Historique',
              iconBg: iconBg,
              borderColor: borderColor,
              iconColor: textMuted,
              onTap: () => context.go('/history'),
            ),
            const SizedBox(width: 6),
            _NavIconBtn(
              icon: Icons.settings,
              tooltip: 'Apparence',
              iconBg: iconBg,
              borderColor: borderColor,
              iconColor: textMuted,
              onTap: () => context.go('/settings'),
            ),
            const SizedBox(width: 6),
            _NavIconBtn(
              icon: Icons.logout,
              tooltip: 'Déconnexion',
              iconBg: iconBg,
              borderColor: borderColor,
              iconColor: textMuted,
              onTap: () async {
                await auth.logout();
                if (context.mounted) context.go('/');
              },
            ),
            if (!isMobile) ...[
              const SizedBox(width: 10),
              // Avatar pill
              Container(
                padding: const EdgeInsets.fromLTRB(4, 4, 12, 4),
                decoration: BoxDecoration(
                  color: iconBg,
                  border: Border.all(color: borderColor, width: 0.5),
                  borderRadius: BorderRadius.circular(50),
                ),
                child: Row(
                  children: [
                    Container(
                      width: 24,
                      height: 24,
                      decoration: BoxDecoration(
                        color: const Color(0xFF2A7FC4),
                        shape: BoxShape.circle,
                      ),
                      child: Center(
                        child: Text(
                          auth.user!.firstName.substring(0, 1).toUpperCase(),
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 11,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(width: 7),
                    Text(
                      auth.user!.firstName,
                      style: TextStyle(
                        color: textMuted,
                        fontWeight: FontWeight.w500,
                        fontSize: 13,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ] else ...[
            GestureDetector(
              onTap: () => context.go('/signin'),
              child: Container(
                padding: EdgeInsets.symmetric(
                    horizontal: isMobile ? 12.0 : 16.0, vertical: 7),
                decoration: BoxDecoration(
                  color: Colors.transparent,
                  borderRadius: BorderRadius.circular(50),
                  border: Border.all(color: borderColor, width: 0.5),
                ),
                child: Text(
                  'Sign In',
                  style: TextStyle(
                    color: textMuted,
                    fontSize: 12,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ),
            ),
            const SizedBox(width: 8),
            GestureDetector(
              onTap: () => context.go('/signup'),
              child: Container(
                padding: EdgeInsets.symmetric(
                    horizontal: isMobile ? 12.0 : 16.0, vertical: 7),
                decoration: BoxDecoration(
                  color: const Color(0xFF2A7FC4),
                  borderRadius: BorderRadius.circular(50),
                ),
                child: const Text(
                  'Sign Up',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 12,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
//  HELPER WIDGETS
// ─────────────────────────────────────────────────────────────────────────────

class _NavIconBtn extends StatelessWidget {
  final IconData icon;
  final String tooltip;
  final Color iconBg, borderColor, iconColor;
  final VoidCallback onTap;

  const _NavIconBtn({
    required this.icon,
    required this.tooltip,
    required this.iconBg,
    required this.borderColor,
    required this.iconColor,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Tooltip(
      message: tooltip,
      child: GestureDetector(
        onTap: onTap,
        child: Container(
          width: 34,
          height: 34,
          decoration: BoxDecoration(
            color: iconBg,
            borderRadius: BorderRadius.circular(10),
            border: Border.all(color: borderColor, width: 0.5),
          ),
          child: Icon(icon, color: iconColor, size: 15),
        ),
      ),
    );
  }
}

class _NavLink extends StatelessWidget {
  final String label, path, current;
  final Color primary, textMuted;

  const _NavLink({
    required this.label,
    required this.path,
    required this.current,
    required this.primary,
    required this.textMuted,
  });

  @override
  Widget build(BuildContext context) {
    final isActive = current == path;
    return GestureDetector(
      onTap: () => context.go(path),
      child: Text(
        label,
        style: TextStyle(
          color: isActive ? primary : textMuted,
          fontWeight: isActive ? FontWeight.w600 : FontWeight.w500,
          fontSize: 14,
        ),
      ),
    );
  }
}
