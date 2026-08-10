import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import '../theme/app_theme.dart';
import '../widgets/bottom_nav_bar.dart';
import '../services/api_service.dart';


class HomePage extends StatelessWidget {
  const HomePage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Theme.of(context).colorScheme.background,
      bottomNavigationBar: const AppBottomNavBar(active: NavTab.home),
      body: SafeArea(
        child: Stack(
          children: [
            Positioned.fill(
              child: IgnorePointer(
                child: Opacity(
                  opacity: 0.22,
                  child: Image.asset(
                    'assets/images/robot_assistant.png',
                    fit: BoxFit.cover,
                    alignment: Alignment.center,
                  ),
                ),
              ),
            ),

            SingleChildScrollView(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: const [
                  _HeroSection(),
                  _StatsRow(),
                  SizedBox(height: 22),
                  _NeighborhoodSection(),
                  SizedBox(height: 24),
                  _ArSection(),
                  SizedBox(height: 32),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _HeroSection extends StatelessWidget {
  const _HeroSection();

  @override
  Widget build(BuildContext context) {
    final provider  = context.watch<ThemeProvider>();
    final font      = provider.font;
    const Color btnPrimary = Color(0xFF2A7FC4);

    return Container(
      height: 320,
      decoration: const BoxDecoration(color: Colors.transparent),
      child: Stack(
        children: [
          Positioned(
            top: -40,
            right: -40,
            child: Container(
              width: 180,
              height: 180,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                gradient: RadialGradient(colors: [
                  Colors.white.withValues(alpha: 0.18),
                  Colors.transparent,
                ]),
              ),
            ),
          ),

          Positioned(
            top: 0, left: 0, right: 0, bottom: 0,
            child: Padding(
              padding: const EdgeInsets.fromLTRB(20, 28, 20, 20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // ── Badge Dynamique (Affiche Premium ou Free) ──────
                  FutureBuilder<Map<String, dynamic>>(
                    future: ApiService.getSubscriptionStatus(),
                    builder: (context, snapshot) {
                      final plan = snapshot.data?['plan'] ?? 'free';
                      final isPremium = plan == 'premium';

                      return Container(
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                        decoration: BoxDecoration(
                          color: isPremium ? const Color(0xFFFFD700).withValues(alpha: 0.2) : const Color(0xAADBEEF9),
                          borderRadius: BorderRadius.circular(50),
                          border: Border.all(
                              color: isPremium ? const Color(0xFFD4A017) : const Color(0xFF2A7FC4),
                              width: 0.8),
                        ),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            _PulseDot(color: isPremium ? const Color(0xFFD4A017) : const Color(0xFF2A7FC4)),
                            const SizedBox(width: 5),
                            Text(
                              isPremium ? 'PropIQ PREMIUM MEMBER' : 'AI-Powered · Setúbal',
                              style: AppFonts.body(font,
                                  size: 11,
                                  weight: FontWeight.w600,
                                  color: isPremium ? const Color(0xFF7A5C00) : const Color(0xFF0D3B6E)),
                            ),
                          ],
                        ),
                      );
                    },
                  ),
                  const SizedBox(height: 14),

                  Text(
                    'Your AI\nReal Estate\nCopilot',
                    style: AppFonts.title(font,
                        size: 28,
                        weight: FontWeight.w800,
                        color: const Color(0xFF0D3B6E)),
                  ),
                  const Spacer(),

                  Row(
                    children: [
                      _HeroBtn(
                        label: 'Chat',
                        icon: Icons.chat_bubble_outline_rounded,
                        filled: true,
                        color: Colors.white,
                        textColor: btnPrimary,
                        onTap: () => context.go('/free-chat'),
                      ),
                      const SizedBox(width: 10),
                      _HeroBtn(
                        label: 'Map',
                        icon: Icons.map_outlined,
                        filled: false,
                        color: const Color(0xFF0D3B6E),
                        textColor: const Color(0xFF0D3B6E),
                        onTap: () => context.go('/quality-life'),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _HeroBtn extends StatelessWidget {
  final String label;
  final IconData icon;
  final bool filled;
  final Color color, textColor;
  final VoidCallback onTap;

  const _HeroBtn({
    required this.label,
    required this.icon,
    required this.filled,
    required this.color,
    required this.textColor,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 13),
        decoration: BoxDecoration(
          color: filled ? color : Colors.transparent,
          borderRadius: BorderRadius.circular(50),
          border: filled
              ? null
              : Border.all(color: color.withValues(alpha: 0.75), width: 1.2),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 15, color: textColor),
            const SizedBox(width: 6),
            Text(
              label,
              style: TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w600,
                color: textColor,
              ),
            ),
            if (filled) ...[
              const SizedBox(width: 4),
              Icon(Icons.arrow_forward_rounded,
                  size: 13, color: textColor.withValues(alpha: 0.75)),
            ],
          ],
        ),
      ),
    );
  }
}

class _PulseDot extends StatefulWidget {
  final Color color;
  const _PulseDot({required this.color});

  @override
  State<_PulseDot> createState() => _PulseDotState();
}

class _PulseDotState extends State<_PulseDot>
    with SingleTickerProviderStateMixin {
  late AnimationController _ctrl;
  late Animation<double> _anim;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
        vsync: this, duration: const Duration(seconds: 2))
      ..repeat(reverse: true);
    _anim = Tween(begin: 1.0, end: 0.3)
        .animate(CurvedAnimation(parent: _ctrl, curve: Curves.easeInOut));
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return FadeTransition(
      opacity: _anim,
      child: Container(
        width: 6,
        height: 6,
        decoration: BoxDecoration(color: widget.color, shape: BoxShape.circle),
      ),
    );
  }
}

class _StatsRow extends StatelessWidget {
  const _StatsRow();
  static const Color _blueAccent     = Color(0xFF4FB3D9);
  static const Color _blueAccentDark = Color(0xFF81CFE0);
  @override
  Widget build(BuildContext context) {
    final theme    = Theme.of(context);
    final isDark   = theme.brightness == Brightness.dark;
    final surface  = isDark ? AppColors.darkSurface  : AppColors.lightSurface;
    final border   = isDark ? AppColors.darkBorder2  : AppColors.lightBorder;
    final text1    = isDark ? AppColors.darkText1     : AppColors.lightText1;
    final text2    = isDark ? AppColors.darkText2     : AppColors.lightText2;
    final palette  = AccentPalette.all[context.watch<ThemeProvider>().accent]!;
    final propertiesAccent = isDark ? _blueAccentDark : _blueAccent;
    return Container(
      margin: const EdgeInsets.fromLTRB(18, 16, 18, 0),
      decoration: BoxDecoration(
        color: surface,
        border: Border.all(color: border, width: 0.5),
        borderRadius: BorderRadius.circular(16),
      ),
      child: IntrinsicHeight(
        child: Row(
          children: [
            _StatItem(number: '98%',   label: 'COMPLIANCE', accent: palette.primary,     text1: text1, text2: text2, border: border),
            Container(width: 0.5, color: border),
            _StatItem(number: '2.4k+', label: 'PROPERTIES', accent: propertiesAccent,    text1: text1, text2: text2, border: border),
            Container(width: 0.5, color: border),
            _StatItem(number: '<3min', label: 'ANALYSIS',   accent: AppColors.warning,   text1: text1, text2: text2, border: border),
          ],
        ),
      ),
    );
  }
}

class _StatItem extends StatelessWidget {
  final String number, label;
  final Color accent, text1, text2, border;
  const _StatItem({required this.number, required this.label, required this.accent, required this.text1, required this.text2, required this.border});
  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 10),
        child: Column(
          children: [
            RichText(
              text: TextSpan(
                style: TextStyle(fontSize: 20, fontWeight: FontWeight.w700, color: text1),
                children: [
                  TextSpan(text: number.replaceAll(RegExp(r'[^0-9.<]'), '')),
                  TextSpan(text: number.replaceAll(RegExp(r'[0-9.]'), ''), style: TextStyle(color: accent, fontSize: 14)),
                ],
              ),
            ),
            const SizedBox(height: 3),
            Text(label, style: TextStyle(fontSize: 9, fontWeight: FontWeight.w500, letterSpacing: 0.8, color: text2)),
          ],
        ),
      ),
    );
  }
}

class _NeighborhoodSection extends StatelessWidget {
  const _NeighborhoodSection();
  @override
  Widget build(BuildContext context) {
    final theme    = Theme.of(context);
    final isDark   = theme.brightness == Brightness.dark;
    final palette  = AccentPalette.all[context.watch<ThemeProvider>().accent]!;
    final surface  = isDark ? AppColors.darkSurface  : AppColors.lightSurface;
    final border   = isDark ? AppColors.darkBorder2  : AppColors.lightBorder;
    final text1    = isDark ? AppColors.darkText1     : AppColors.lightText1;
    final text2    = isDark ? AppColors.darkText2     : AppColors.lightText2;
    final chipBg   = isDark ? AppColors.darkSurface   : AppColors.lightSurface;
    final scoreBg  = isDark ? const Color(0xFF0D1E35) : const Color(0xFFDBEEF9);
    final scoreTxt = isDark ? const Color(0xFF81CFE0) : const Color(0xFF1A6CAA);

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _SectionHeader(
            title: 'Neighborhood Scores',
            linkLabel: 'View map ›',
            text1: text1,
            primary: palette.primary,
            onLink: () => context.go('/quality-life'),
          ),
          const SizedBox(height: 12),
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: surface,
              border: Border.all(color: border, width: 0.5),
              borderRadius: BorderRadius.circular(16),
            ),
            child: Column(
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('Setúbal Overall', style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: text1)),
                          const SizedBox(height: 2),
                          Text('Based on 4 key indicators', style: TextStyle(fontSize: 11, color: text2)),
                        ],
                      ),
                    ),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
                      decoration: BoxDecoration(color: scoreBg, borderRadius: BorderRadius.circular(50)),
                      child: Text('86 / 100', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: scoreTxt)),
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                ...List.generate(_kScores.length, (i) => Padding(
                  padding: EdgeInsets.only(bottom: i < _kScores.length - 1 ? 13 : 0),
                  child: _ScoreRow(data: _kScores[i], isDark: isDark, text1: text1, border: border),
                )),
              ],
            ),
          ),
          const SizedBox(height: 12),
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              children: [
                _NeighChip(label: '🌳 Green Spaces', chipBg: chipBg, border: border, text1: text1, onTap: () => context.go('/quality-life')),
                const SizedBox(width: 8),
                _NeighChip(label: '🏥 Healthcare',   chipBg: chipBg, border: border, text1: text1, onTap: () => context.go('/quality-life')),
                const SizedBox(width: 8),
                _NeighChip(label: '🌊 Waterfront',   chipBg: chipBg, border: border, text1: text1, onTap: () => context.go('/quality-life')),
                const SizedBox(width: 8),
                _NeighChip(label: '🔆 Nightlife',    chipBg: chipBg, border: border, text1: text1, onTap: () => context.go('/quality-life')),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _ScoreRow extends StatelessWidget {
  final _ScoreData data;
  final bool isDark;
  final Color text1, border;
  const _ScoreRow({required this.data, required this.isDark, required this.text1, required this.border});
  @override
  Widget build(BuildContext context) {
    final iconBg = isDark ? data.bgColorDark : data.bgColorLight;
    return Row(
      children: [
        Container(width: 30, height: 30, decoration: BoxDecoration(color: iconBg, borderRadius: BorderRadius.circular(9)), child: Icon(data.icon, size: 15, color: data.color)),
        const SizedBox(width: 10),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(data.label, style: TextStyle(fontSize: 12, fontWeight: FontWeight.w500, color: text1)),
                  Text('${data.score}', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: data.color)),
                ],
              ),
              const SizedBox(height: 5),
              ClipRRect(
                borderRadius: BorderRadius.circular(50),
                child: LinearProgressIndicator(value: data.score / 100, minHeight: 4, backgroundColor: border, valueColor: AlwaysStoppedAnimation<Color>(data.color)),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _NeighChip extends StatelessWidget {
  final String label;
  final Color chipBg, border, text1;
  final VoidCallback onTap;
  const _NeighChip({required this.label, required this.chipBg, required this.border, required this.text1, required this.onTap});
  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 13, vertical: 8),
        decoration: BoxDecoration(color: chipBg, border: Border.all(color: border, width: 0.5), borderRadius: BorderRadius.circular(50)),
        child: Text(label, style: TextStyle(fontSize: 12, fontWeight: FontWeight.w500, color: text1)),
      ),
    );
  }
}

class _SectionHeader extends StatelessWidget {
  final String title, linkLabel;
  final Color text1, primary;
  final VoidCallback onLink;
  const _SectionHeader({required this.title, required this.linkLabel, required this.text1, required this.primary, required this.onLink});
  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(title, style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: text1)),
        GestureDetector(onTap: onLink, child: Text(linkLabel, style: TextStyle(fontSize: 12, fontWeight: FontWeight.w500, color: primary))),
      ],
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
//  AR SECTION
// ─────────────────────────────────────────────────────────────────────────────

class _ArSection extends StatelessWidget {
  const _ArSection();

  @override
  Widget build(BuildContext context) {
    final theme   = Theme.of(context);
    final isDark  = theme.brightness == Brightness.dark;
    final surface = isDark ? AppColors.darkSurface  : AppColors.lightSurface;
    final border  = isDark ? AppColors.darkBorder2  : AppColors.lightBorder;
    final text1   = isDark ? AppColors.darkText1     : AppColors.lightText1;
    final text2   = isDark ? AppColors.darkText2     : AppColors.lightText2;

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // ── Header ──────────────────────────────────────────────
          Row(
            children: [
              Container(
                width: 28, height: 28,
                decoration: BoxDecoration(
                  color: const Color(0xFF0D3B6E),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Icon(Icons.view_in_ar_rounded,
                    color: Colors.white, size: 15),
              ),
              const SizedBox(width: 9),

              const Spacer(),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: const Color(0xFF0D3B6E).withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(50),
                  border: Border.all(
                      color: const Color(0xFF2A7FC4).withValues(alpha: 0.4),
                      width: 0.8),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),



          const SizedBox(height: 10),


        ],
      ),
    );
  }
}

class _ArCard extends StatelessWidget {
  final IconData icon;
  final Color iconColor, iconBg, tagColor, surface, border, text1, text2;
  final String title, subtitle, tag, btnLabel;
  final IconData btnIcon;
  final VoidCallback onTap;

  const _ArCard({
    required this.icon,
    required this.iconColor,
    required this.iconBg,
    required this.tagColor,
    required this.surface,
    required this.border,
    required this.text1,
    required this.text2,
    required this.title,
    required this.subtitle,
    required this.tag,
    required this.btnLabel,
    required this.btnIcon,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: surface,
        border: Border.all(color: border, width: 0.5),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 38, height: 38,
                decoration: BoxDecoration(
                    color: iconBg, borderRadius: BorderRadius.circular(11)),
                child: Icon(icon, color: iconColor, size: 19),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Text(title,
                    style: TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w700,
                        color: text1)),
              ),
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: tagColor.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(50),
                  border: Border.all(
                      color: tagColor.withValues(alpha: 0.35), width: 0.8),
                ),
                child: Text(tag,
                    style: TextStyle(
                        fontSize: 10,
                        fontWeight: FontWeight.w600,
                        color: tagColor)),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Text(subtitle,
              style: TextStyle(fontSize: 12, color: text2, height: 1.5)),
          const SizedBox(height: 14),
          GestureDetector(
            onTap: onTap,
            child: Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(vertical: 12),
              decoration: BoxDecoration(
                color: iconColor,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(btnIcon, color: Colors.white, size: 16),
                  const SizedBox(width: 7),
                  Text(btnLabel,
                      style: const TextStyle(
                          color: Colors.white,
                          fontSize: 13,
                          fontWeight: FontWeight.w600)),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _ScoreData {
  final IconData icon;
  final String label;
  final int score;
  final Color color, bgColorLight, bgColorDark;
  const _ScoreData({required this.icon, required this.label, required this.score, required this.color, required this.bgColorLight, required this.bgColorDark});
}

const _kScores = [
  _ScoreData(icon: Icons.shield_outlined, label: 'Safety', score: 92, color: Color(0xFF2A7FC4), bgColorLight: Color(0xFFDBEEF9), bgColorDark: Color(0xFF0D1E35)),
  _ScoreData(icon: Icons.school_outlined, label: 'Schools', score: 85, color: Color(0xFF4FB3D9), bgColorLight: Color(0xFFDCEAFD), bgColorDark: Color(0xFF0D1E35)),
  _ScoreData(icon: Icons.directions_bus_outlined, label: 'Transport', score: 78, color: AppColors.scoreTransport, bgColorLight: Color(0xFFFEF3C7), bgColorDark: Color(0xFF2A1F08)),
  _ScoreData(icon: Icons.storefront_outlined, label: 'Amenities', score: 88, color: AppColors.scoreAmenities, bgColorLight: Color(0xFFE8DAF9), bgColorDark: Color(0xFF2A1020)),
];
