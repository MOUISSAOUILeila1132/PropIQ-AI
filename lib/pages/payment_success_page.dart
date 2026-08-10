// lib/pages/payment_success_page.dart
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:google_fonts/google_fonts.dart';


import '../services/api_service.dart';
import '../theme/app_theme.dart';

class PaymentSuccessPage extends StatefulWidget {
  final String sessionId;
  final String uid;

  const PaymentSuccessPage({
    super.key,
    required this.sessionId,
    required this.uid,
  });

  @override
  State<PaymentSuccessPage> createState() => _PaymentSuccessPageState();
}

class _PaymentSuccessPageState extends State<PaymentSuccessPage> {
  bool _isVerifying = true;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _verifyPayment();
  }

  // ── Appelle le backend pour valider la session Stripe ───────
  Future<void> _verifyPayment() async {
    try {
      // On envoie le session_id et l'uid au backend
      final res = await ApiService.verifyPayment(widget.sessionId);

      // Si le backend confirme le paiement
      if (res['status'] == 'completed') {
        if (mounted) {
          setState(() {
            _isVerifying = false;
            _errorMessage = null;
          });
        }
      } else {
        setState(() {
          _isVerifying = false;
          _errorMessage = "Le paiement n'a pas pu être vérifié.";
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _isVerifying = false;
          _errorMessage = "Erreur de connexion au serveur.";
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final text1  = isDark ? AppColors.darkText1 : AppColors.lightText1;
    final text2  = isDark ? AppColors.darkText2 : AppColors.lightText2;

    return Scaffold(
      body: Stack(
        children: [
          // ── Background Robot ────────────────────────────────
          Positioned.fill(
            child: Opacity(
              opacity: 0.15,
              child: Image.asset(
                'assets/images/robot_assistant.png',
                fit: BoxFit.contain,
                alignment: Alignment.center,
              ),
            ),
          ),

          // ── Contenu Central ─────────────────────────────────
          Center(
            child: Padding(
              padding: const EdgeInsets.all(32.0),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  if (_isVerifying) ...[
                    const CircularProgressIndicator(color: Color(0xFF2A7FC4)),
                    const SizedBox(height: 24),
                    Text(
                      "Vérification de votre paiement...",
                      style: GoogleFonts.poppins(color: text1, fontSize: 16),
                    ),
                  ] else if (_errorMessage != null) ...[
                    const Icon(Icons.error_outline, color: Colors.redAccent, size: 80),
                    const SizedBox(height: 24),
                    Text(
                      "Oups !",
                      style: GoogleFonts.playfairDisplay(
                        fontSize: 32, fontWeight: FontWeight.w700, color: text1,
                      ),
                    ),
                    const SizedBox(height: 12),
                    Text(
                      _errorMessage!,
                      textAlign: TextAlign.center,
                      style: GoogleFonts.poppins(color: text2, fontSize: 15),
                    ),
                    const SizedBox(height: 40),
                    ElevatedButton(
                      onPressed: () => context.go('/plan-selection'),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFF2A7FC4),
                        padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 16),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(50)),
                      ),
                      child: const Text("Réessayer"),
                    ),
                  ] else ...[
                    // ── SUCCÈS ──
                    const Icon(Icons.check_circle_outline, color: Color(0xFF22C55E), size: 100),
                    const SizedBox(height: 32),
                    Text(
                      "Paiement Réussi !",
                      textAlign: TextAlign.center,
                      style: GoogleFonts.playfairDisplay(
                        fontSize: 34, fontWeight: FontWeight.w800, color: text1,
                      ),
                    ),
                    const SizedBox(height: 12),
                    Text(
                      "Bienvenue chez PropIQ Premium.\nVotre compte a été activé avec succès.",
                      textAlign: TextAlign.center,
                      style: GoogleFonts.poppins(
                        color: text2, fontSize: 16, height: 1.5,
                      ),
                    ),
                    const SizedBox(height: 48),
                    Container(
                      width: double.infinity,
                      constraints: const BoxConstraints(maxWidth: 300),
                      child: ElevatedButton(
                        onPressed: () => context.go('/'),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: const Color(0xFF2A7FC4),
                          padding: const EdgeInsets.symmetric(vertical: 18),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(50)),
                          elevation: 8,
                          shadowColor: const Color(0xFF2A7FC4).withOpacity(0.4),
                        ),
                        child: Text(
                          "Commencer l'expérience",
                          style: GoogleFonts.poppins(
                            fontWeight: FontWeight.w700, fontSize: 16, color: Colors.white,
                          ),
                        ),
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
