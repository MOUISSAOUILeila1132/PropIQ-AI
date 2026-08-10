// lib/pages/settings_page.dart
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'package:go_router/go_router.dart';

import '../theme/app_theme.dart';
import '../widgets/bottom_nav_bar.dart';
import '../services/api_service.dart';

class SettingsPage extends StatefulWidget {
  const SettingsPage({super.key});
  @override
  State<SettingsPage> createState() => _SettingsPageState();
}

class _SettingsPageState extends State<SettingsPage> {
  bool _notifications = true;

  @override
  Widget build(BuildContext context) {
    final isDark   = Theme.of(context).brightness == Brightness.dark;
    final provider = context.watch<ThemeProvider>();
    final surface = isDark ? AppColors.darkSurface : AppColors.lightSurface;
    final text1   = isDark ? AppColors.darkText1   : AppColors.lightText1;

    return Scaffold(
      bottomNavigationBar: const AppBottomNavBar(active: NavTab.settings),
      body: Stack(
        children: [
          Positioned.fill(child: Opacity(opacity: 0.1, child: Image.asset('assets/images/robot_assistant.png', fit: BoxFit.contain))),
          SafeArea(
            child: ListView(
              padding: const EdgeInsets.all(20),
              children: [
                Text('Settings', style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold, color: text1)),
                const SizedBox(height: 20),

                // ── SECTION ABONNEMENT ──
                _SubscriptionSection(surface: surface, text1: text1),

                const SizedBox(height: 20),
                const Text('Appearance', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
                const SizedBox(height: 10),
                Container(
                  decoration: BoxDecoration(color: surface, borderRadius: BorderRadius.circular(15)),
                  child: SwitchListTile(
                    title: const Text('Dark Mode'),
                    value: isDark,
                    onChanged: (v) => provider.setThemeMode(v ? ThemeMode.dark : ThemeMode.light),
                  ),
                ),
                const SizedBox(height: 20),
                const Text('App', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
                const SizedBox(height: 10),
                Container(
                  decoration: BoxDecoration(color: surface, borderRadius: BorderRadius.circular(15)),
                  child: SwitchListTile(
                    title: const Text('Notifications'),
                    value: _notifications,
                    onChanged: (v) => setState(() => _notifications = v),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _SubscriptionSection extends StatelessWidget {
  final Color surface, text1;
  const _SubscriptionSection({required this.surface, required this.text1});

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<Map<String, dynamic>>(
      future: ApiService.getSubscriptionStatus(),
      builder: (context, snapshot) {
        if (!snapshot.hasData) return const Center(child: CircularProgressIndicator());
        final data = snapshot.data!;
        final plan = data['plan'] ?? 'free';
        final isPremium = plan == 'premium';
        final usage = data['usage'] as Map;
        final limits = data['limits'] as Map;

        return Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: surface, border: Border.all(color: isPremium ? Colors.amber : Colors.transparent),
            borderRadius: BorderRadius.circular(16),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(isPremium ? 'PREMIUM ⭐' : 'FREE PLAN', style: TextStyle(fontWeight: FontWeight.w900, color: isPremium ? Colors.amber[800] : text1)),
                  if (!isPremium) ElevatedButton(onPressed: () => context.push('/plan-selection'), style: ElevatedButton.styleFrom(backgroundColor: Colors.amber), child: const Text('UPGRADE', style: TextStyle(color: Colors.white))),
                ],
              ),
              const SizedBox(height: 20),
              _ProgressRow(label: 'Chat Requests', used: usage['requests'] ?? 0, limit: limits['requests_per_day'] ?? 10),
              const SizedBox(height: 15),
              _ProgressRow(label: 'Document Analysis', used: (usage['images'] ?? 0) + (usage['pdfs'] ?? 0), limit: (limits['images_per_day'] ?? 1) + (limits['pdfs_per_day'] ?? 1)),
            ],
          ),
        );
      },
    );
  }
}

class _ProgressRow extends StatelessWidget {
  final String label; final int used, limit;
  const _ProgressRow({required this.label, required this.used, required this.limit});
  @override
  Widget build(BuildContext context) {
    final ratio = (used / limit).clamp(0.0, 1.0);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [Text(label, style: const TextStyle(fontSize: 12)), Text('$used/$limit')]),
        const SizedBox(height: 5),
        ClipRRect(borderRadius: BorderRadius.circular(10), child: LinearProgressIndicator(value: ratio, minHeight: 6, color: ratio >= 0.8 ? Colors.orange : AppColors.primary)),
      ],
    );
  }
}
