// lib/pages/plan_selection_page.dart
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:url_launcher/url_launcher.dart';

import '../context/auth_context.dart';
import '../services/api_service.dart';
import '../theme/app_theme.dart';

// ─────────────────────────────────────────────
// Couleurs locales (cohérentes avec splash)
// ─────────────────────────────────────────────
const Color _accent   = Color(0xFF2A7FC4);
const Color _accent2  = Color(0xFF4F46E5);
const Color _gold     = Color(0xFFD4A017);
const Color _goldLight= Color(0xFFF5C842);

class PlanSelectionPage extends StatefulWidget {
  const PlanSelectionPage({super.key});

  @override
  State<PlanSelectionPage> createState() => _PlanSelectionPageState();
}

class _PlanSelectionPageState extends State<PlanSelectionPage>
    with SingleTickerProviderStateMixin {

  bool _loadingFree    = false;
  bool _loadingPremium = false;

  late AnimationController _fadeCtrl;
  late Animation<double>   _fadeAnim;

  @override
  void initState() {
    super.initState();
    _fadeCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 600),
    )..forward();
    _fadeAnim = CurvedAnimation(parent: _fadeCtrl, curve: Curves.easeOut);
  }

  @override
  void dispose() {
    _fadeCtrl.dispose();
    super.dispose();
  }

  // ── Choisir le plan Free ─────────────────────────────────────────
  Future<void> _chooseFree() async {
    final auth = context.read<AuthContext>();
    final uid  = auth.uid;
    if (uid == null) return;

    setState(() => _loadingFree = true);
    try {
      await FirebaseFirestore.instance
          .collection('users')
          .doc(uid)
          .set({
        'plan': 'free',
        'updated_at': DateTime.now().toIso8601String()
      }, SetOptions(merge: true));

      if (mounted) context.go('/');
    } catch (e) {
      _showError('Erreur lors de la sélection du plan gratuit.');
    } finally {
      if (mounted) setState(() => _loadingFree = false);
    }
  }

  // ── Lancer le paiement (Stripe / Konnect) ────────────────────────
  Future<void> _choosePremium() async {
    final auth  = context.read<AuthContext>();
    final uid   = auth.uid;
    final email = auth.email ?? '';
    if (uid == null) return;

    setState(() => _loadingPremium = true);
    try {
      // 1. Demande de l'URL + payment_ref au backend
      final result     = await ApiService.createPayment(uid: uid, email: email);
      final paymentUrl = result['payment_url'] as String?;
      final paymentRef = result['payment_ref'] as String?;

      if (paymentUrl == null || paymentUrl.isEmpty) {
        _showError('Impossible d\'obtenir l\'URL de paiement.');
        return;
      }

      // 2. ✅ FIX : Ouverture directe sans canLaunchUrl (peu fiable Android 11+)
      final Uri url = Uri.parse(paymentUrl);
      try {
        final launched = await launchUrl(
          url,
          mode: LaunchMode.externalApplication,
        );
        if (!launched) {
          _showError('Impossible d\'ouvrir la page de paiement.');
          return;
        }
        // 3. Dialog de confirmation au retour
        if (mounted) {
          _showPaymentReturnDialog(uid, paymentRef);
        }
      } catch (e) {
        _showError('Impossible d\'ouvrir la page de paiement : $e');
      }

    } catch (e) {
      _showError('Erreur lors de la création du paiement : $e');
    } finally {
      if (mounted) setState(() => _loadingPremium = false);
    }
  }

  // ── Dialog affiché au retour du navigateur ───────────────────────
  void _showPaymentReturnDialog(String uid, String? paymentRef) {
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (_) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        title: const Text('Paiement effectué ?'),
        content: const Text('Avez-vous complété le paiement sur la page de paiement ?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Non, annuler'),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: _gold),
            onPressed: () async {
              Navigator.pop(context);
              await _verifyAndActivatePremium(uid, paymentRef);
            },
            child: const Text('Oui, vérifier', style: TextStyle(color: Colors.black87)),
          ),
        ],
      ),
    );
  }

  // ── Vérifie le paiement et met à jour le plan ────────────────────
  Future<void> _verifyAndActivatePremium(String uid, String? paymentRef) async {
    if (paymentRef == null) {
      _showError('Référence de paiement manquante.');
      return;
    }
    setState(() => _loadingPremium = true);
    try {
      final verification = await ApiService.verifyPayment(paymentRef);
      final status       = verification['status'] as String? ?? '';

      if (status == 'completed') {
        await FirebaseFirestore.instance
            .collection('users')
            .doc(uid)
            .set({
          'plan':             'premium',
          'updated_at':       DateTime.now().toIso8601String(),
          'last_payment_ref': paymentRef,
        }, SetOptions(merge: true));

        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: const Text('🎉 Plan Premium activé avec succès !'),
              backgroundColor: _gold,
              behavior: SnackBarBehavior.floating,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            ),
          );
          context.go('/');
        }
      } else {
        _showError('Paiement non confirmé. Statut : $status. Réessayez dans quelques instants.');
      }
    } catch (e) {
      _showError('Erreur lors de la vérification : $e');
    } finally {
      if (mounted) setState(() => _loadingPremium = false);
    }
  }

  void _showError(String msg) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(msg),
        backgroundColor: Colors.redAccent,
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final isDark  = Theme.of(context).brightness == Brightness.dark;
    final bgPage  = isDark ? AppColors.darkBg      : const Color(0xFFF0F4FF);
    final bgCard  = isDark ? AppColors.darkSurface : Colors.white;
    final text1   = isDark ? AppColors.darkText1   : AppColors.lightText1;
    final text2   = isDark ? AppColors.darkText2   : AppColors.lightText2;

    return Scaffold(
      backgroundColor: bgPage,
      body: FadeTransition(
        opacity: _fadeAnim,
        child: SafeArea(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 32),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                const SizedBox(height: 8),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 5),
                  decoration: BoxDecoration(
                    color: _accent.withOpacity(0.12),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Text(
                    'CHOISISSEZ VOTRE PLAN',
                    style: GoogleFonts.poppins(
                      color: _accent2,
                      fontSize: 11,
                      fontWeight: FontWeight.w600,
                      letterSpacing: 1.8,
                    ),
                  ),
                ),
                const SizedBox(height: 20),
                Text(
                  'PropIQ Premium',
                  style: GoogleFonts.playfairDisplay(
                    fontSize: 32,
                    fontWeight: FontWeight.w800,
                    color: text1,
                  ),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 12),
                Text(
                  'Accédez à toutes les fonctionnalités\npour votre assistant immobilier.',
                  textAlign: TextAlign.center,
                  style: GoogleFonts.poppins(
                    fontSize: 13,
                    color: text2,
                    height: 1.5,
                  ),
                ),
                const SizedBox(height: 40),

                _PlanCard(
                  isPremium : false,
                  bgCard    : bgCard,
                  text1     : text1,
                  text2     : text2,
                  loading   : _loadingFree,
                  onTap     : _loadingFree || _loadingPremium ? null : _chooseFree,
                ),
                const SizedBox(height: 20),

                _PlanCard(
                  isPremium : true,
                  bgCard    : bgCard,
                  text1     : text1,
                  text2     : text2,
                  loading   : _loadingPremium,
                  onTap     : _loadingFree || _loadingPremium ? null : _choosePremium,
                ),
                const SizedBox(height: 32),

                Text(
                  '🔒 Paiement international sécurisé · EUR · Résiliable à tout moment',
                  textAlign: TextAlign.center,
                  style: GoogleFonts.poppins(fontSize: 11, color: text2),
                ),
                const SizedBox(height: 16),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Widget carte de plan
// ─────────────────────────────────────────────────────────────────────────────
class _PlanCard extends StatelessWidget {
  final bool          isPremium;
  final Color         bgCard;
  final Color         text1;
  final Color         text2;
  final bool          loading;
  final VoidCallback? onTap;

  const _PlanCard({
    required this.isPremium,
    required this.bgCard,
    required this.text1,
    required this.text2,
    required this.loading,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final List<_Feature> features = isPremium
        ? [
      _Feature('20 requêtes / jour',           Icons.chat_bubble_outline_rounded),
      _Feature('10 analyses d\'images / jour',  Icons.image_outlined),
      _Feature('5 PDFs / jour',                 Icons.picture_as_pdf_outlined),
      _Feature('Accès prioritaire',             Icons.bolt_rounded),
      _Feature('Support Premium',               Icons.headset_mic_outlined),
    ]
        : [
      _Feature('10 requêtes / jour',            Icons.chat_bubble_outline_rounded),
      _Feature('1 analyse d\'image / jour',     Icons.image_outlined),
      _Feature('1 PDF / jour',                  Icons.picture_as_pdf_outlined),
      _Feature('Accès standard',                Icons.speed_outlined),
    ];

    final Color cardBorder = isPremium ? _gold              : _accent.withOpacity(0.3);
    final Color btnColor   = isPremium ? _gold              : _accent;
    final Color btnText    = isPremium ? Colors.black87     : Colors.white;
    final String label     = isPremium ? 'Passer Premium — 9,90€ / mois' : 'Continuer gratuitement';
    final String badge     = isPremium ? '⭐ RECOMMANDÉ'   : 'GRATUIT';

    return Container(
      decoration: BoxDecoration(
        color: bgCard,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: cardBorder, width: isPremium ? 2 : 1),
        boxShadow: [
          BoxShadow(
            color: (isPremium ? _gold : _accent).withOpacity(0.10),
            blurRadius: 24,
            offset: const Offset(0, 6),
          ),
        ],
      ),
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                  decoration: BoxDecoration(
                    color: (isPremium ? _gold : _accent).withOpacity(0.13),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Text(
                    badge,
                    style: GoogleFonts.poppins(
                      fontSize: 11,
                      fontWeight: FontWeight.w700,
                      color: isPremium ? _gold : _accent,
                      letterSpacing: 1.2,
                    ),
                  ),
                ),
                if (isPremium)
                  Text(
                    '9,90 €',
                    style: GoogleFonts.poppins(
                      fontSize: 22,
                      fontWeight: FontWeight.w800,
                      color: _gold,
                    ),
                  )
                else
                  Text(
                    '0 €',
                    style: GoogleFonts.poppins(
                      fontSize: 22,
                      fontWeight: FontWeight.w800,
                      color: _accent,
                    ),
                  ),
              ],
            ),
            const SizedBox(height: 6),
            Text(
              isPremium ? 'Premium' : 'Free',
              style: GoogleFonts.poppins(
                fontSize: 20,
                fontWeight: FontWeight.w700,
                color: text1,
              ),
            ),
            Text(
              isPremium ? 'Tout ce dont vous avez besoin' : 'Pour découvrir PropIQ',
              style: GoogleFonts.poppins(fontSize: 13, color: text2),
            ),
            const SizedBox(height: 20),
            ...features.map((f) => _FeatureRow(feature: f, isPremium: isPremium)),
            const SizedBox(height: 24),
            SizedBox(
              width: double.infinity,
              height: 52,
              child: ElevatedButton(
                onPressed: onTap,
                style: ElevatedButton.styleFrom(
                  backgroundColor: btnColor,
                  disabledBackgroundColor: btnColor.withOpacity(0.45),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(50),
                  ),
                ),
                child: loading
                    ? SizedBox(
                  height: 20,
                  width: 20,
                  child: CircularProgressIndicator(
                    color: btnText,
                    strokeWidth: 2,
                  ),
                )
                    : Text(
                  label,
                  style: GoogleFonts.poppins(
                    color: btnText,
                    fontWeight: FontWeight.w700,
                    fontSize: 14,
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Widget ligne de feature
// ─────────────────────────────────────────────────────────────────────────────
class _FeatureRow extends StatelessWidget {
  final _Feature feature;
  final bool     isPremium;
  const _FeatureRow({required this.feature, required this.isPremium});

  @override
  Widget build(BuildContext context) {
    final color = isPremium ? _gold : _accent;
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Row(
        children: [
          Container(
            width: 30,
            height: 30,
            decoration: BoxDecoration(
              color: color.withOpacity(0.12),
              shape: BoxShape.circle,
            ),
            child: Icon(feature.icon, size: 16, color: color),
          ),
          const SizedBox(width: 12),
          Text(
            feature.label,
            style: GoogleFonts.poppins(fontSize: 13, fontWeight: FontWeight.w500),
          ),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Modèle feature
// ─────────────────────────────────────────────────────────────────────────────
class _Feature {
  final String   label;
  final IconData icon;
  const _Feature(this.label, this.icon);
}
