// lib/widgets/bottom_nav_bar.dart
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import '../theme/app_theme.dart';

enum NavTab { home, chat, map, ar, history, settings }

class AppBottomNavBar extends StatelessWidget {
  final NavTab active;
  const AppBottomNavBar({super.key, required this.active});

  @override
  Widget build(BuildContext context) {
    final theme    = Theme.of(context);
    final isDark   = theme.brightness == Brightness.dark;
    final provider = context.watch<ThemeProvider>();
    final palette  = AccentPalette.all[provider.accent]!;

    final bgColor       = isDark ? AppColors.darkSurface : AppColors.lightSurface;
    final borderColor   = isDark ? AppColors.darkBorder2  : AppColors.lightBorder;
    const activeColor   = Color(0xFF2A7FC4);                        // bleu principal
    final activeBg      = isDark
        ? const Color(0xFF0D1E35)                                   // bleu très foncé dark
        : const Color(0xFFDBEEF9);                                  // bleu très clair light
    final inactiveColor = isDark ? AppColors.darkText3    : AppColors.lightText3;

    return Container(
      margin: const EdgeInsets.fromLTRB(16, 0, 16, 18),
      padding: const EdgeInsets.all(5),
      decoration: BoxDecoration(
        color: bgColor,
        border: Border.all(color: borderColor, width: 0.5),
        borderRadius: BorderRadius.circular(22),
        boxShadow: isDark
            ? []
            : [
                BoxShadow(
                  color: Colors.black.withOpacity(0.06),
                  blurRadius: 16,
                  offset: const Offset(0, 4),
                ),
              ],
      ),
      child: Row(
        children: [
          _BNavItem(
            icon: Icons.home_rounded,
            label: 'Home',
            isActive: active == NavTab.home,
            activeColor: activeColor,
            activeBg: activeBg,
            inactiveColor: inactiveColor,
            onTap: () => context.go('/'),
          ),
          _BNavItem(
            icon: Icons.chat_bubble_outline_rounded,
            label: 'Chat',
            isActive: active == NavTab.chat,
            activeColor: activeColor,
            activeBg: activeBg,
            inactiveColor: inactiveColor,
            onTap: () => context.go('/free-chat'),
          ),
          _BNavItem(
            icon: Icons.location_on_outlined,
            label: 'Map',
            isActive: active == NavTab.map,
            activeColor: activeColor,
            activeBg: activeBg,
            inactiveColor: inactiveColor,
            onTap: () => context.go('/quality-life'),
          ),

          _BNavItem(
            icon: Icons.history_rounded,
            label: 'History',
            isActive: active == NavTab.history,
            activeColor: activeColor,
            activeBg: activeBg,
            inactiveColor: inactiveColor,
            onTap: () => context.go('/history'),
          ),
          _BNavItem(
            icon: Icons.settings_outlined,         // ← icône settings
            label: 'Settings',                      // ← label Settings
            isActive: active == NavTab.settings,
            activeColor: activeColor,
            activeBg: activeBg,
            inactiveColor: inactiveColor,
            onTap: () => context.go('/settings'),   // ← route /settings
          ),
        ],
      ),
    );
  }
}

class _BNavItem extends StatelessWidget {
  final IconData icon;
  final String label;
  final bool isActive;
  final Color activeColor;
  final Color activeBg;
  final Color inactiveColor;
  final VoidCallback onTap;

  const _BNavItem({
    required this.icon,
    required this.label,
    required this.isActive,
    required this.activeColor,
    required this.activeBg,
    required this.inactiveColor,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: GestureDetector(
        onTap: onTap,
        behavior: HitTestBehavior.opaque,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 220),
          curve: Curves.easeInOut,
          padding: const EdgeInsets.symmetric(vertical: 8),
          decoration: BoxDecoration(
            color: isActive ? activeBg : Colors.transparent,
            borderRadius: BorderRadius.circular(16),
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              AnimatedScale(
                scale: isActive ? 1.12 : 1.0,
                duration: const Duration(milliseconds: 200),
                child: Icon(
                  icon,
                  color: isActive ? activeColor : inactiveColor,
                  size: 19,
                ),
              ),
              const SizedBox(height: 4),
              AnimatedDefaultTextStyle(
                duration: const Duration(milliseconds: 200),
                style: TextStyle(
                  fontSize: 10,
                  fontWeight: isActive ? FontWeight.w600 : FontWeight.w400,
                  color: isActive ? activeColor : inactiveColor,
                  letterSpacing: 0.2,
                ),
                child: Text(label),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
