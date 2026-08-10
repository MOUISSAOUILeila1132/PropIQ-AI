// lib/pages/auth_page.dart
import 'dart:async';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';
import 'package:cloud_firestore/cloud_firestore.dart';

import '../context/auth_context.dart';
import '../services/api_service.dart';
import '../theme/app_theme.dart';
import '../widgets/bottom_nav_bar.dart';
import 'package:proptech_ai/config.dart';

enum EmailStatus { idle, checking, valid, invalid }

class AuthPage extends StatefulWidget {
  final String type;
  const AuthPage({super.key, required this.type});

  @override
  State<AuthPage> createState() => _AuthPageState();
}

class _AuthPageState extends State<AuthPage> {
  bool get isSignUp => widget.type == 'signup';

  final _fullNameController = TextEditingController();
  final _emailController    = TextEditingController();
  final _passwordController = TextEditingController();

  EmailStatus _emailStatus  = EmailStatus.idle;
  String      _emailMessage = '';
  Timer?      _debounce;
  bool        _isSubmitting = false;

  // Couleur principale accessible dans toute la classe (dialogs inclus)
  static const Color _primary = Color(0xFF2A7FC4);

  @override
  void initState() {
    super.initState();
    _emailController.addListener(_onEmailChanged);
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _fullNameController.dispose();
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  // ── Vérification email en temps réel ──────────────────────────
  void _onEmailChanged() {
    final email = _emailController.text;
    if (email.isEmpty) {
      setState(() { _emailStatus = EmailStatus.idle; _emailMessage = ''; });
      return;
    }
    final basicRegex = RegExp(r'^[^\s@]+@[^\s@]+\.[^\s@]+$');
    if (!basicRegex.hasMatch(email)) {
      setState(() {
        _emailStatus  = EmailStatus.invalid;
        _emailMessage = "Format d'email invalide.";
      });
      return;
    }
    setState(() => _emailStatus = EmailStatus.checking);
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 600), () async {
      try {
        final data = await ApiService.checkEmail(email);
        if (!mounted) return;
        if (data['valid'] == true) {
          setState(() { _emailStatus = EmailStatus.valid; _emailMessage = 'Email valide'; });
        } else {
          setState(() {
            _emailStatus  = EmailStatus.invalid;
            _emailMessage = data['reason'] ?? 'Invalid';
          });
        }
      } catch (_) {
        if (mounted) setState(() => _emailStatus = EmailStatus.idle);
      }
    });
  }

  // ── Redirection intelligente après login ──────────────────────
  Future<void> _redirectAfterLogin(String? uid) async {
    if (uid == null || !mounted) return;
    try {
      final doc = await FirebaseFirestore.instance
          .collection('users')
          .doc(uid)
          .get();
      final plan = doc.data()?['plan'] as String?;
      if (!mounted) return;
      if (plan == null || plan.isEmpty) {
        context.go('/plan-selection');
      } else {
        context.go('/');
      }
    } catch (_) {
      if (mounted) context.go('/');
    }
  }

  // ── Soumission du formulaire via Firebase ──────────────────────
  Future<void> _handleSubmit() async {
    if (isSignUp && _emailStatus != EmailStatus.valid) {
      _showSnack('Veuillez saisir un email valide avant de continuer.');
      return;
    }
    if (_passwordController.text.length < 6) {
      _showSnack('Le mot de passe doit contenir au moins 6 caractères.');
      return;
    }

    setState(() => _isSubmitting = true);
    final auth = context.read<AuthContext>();
    auth.clearError();

    bool success = false;

    if (isSignUp) {
      success = await auth.registerWithEmail(
        _emailController.text,
        _passwordController.text,
        _fullNameController.text,
      );
      if (success && mounted) {
        _showSnack('Compte créé ! Bienvenue 🎉', isSuccess: true);
        context.go('/plan-selection');
      }
    } else {
      success = await auth.loginWithEmail(
        _emailController.text,
        _passwordController.text,
      );
      if (success && mounted) {
        await _redirectAfterLogin(auth.uid);
      }
    }

    if (!success && mounted && auth.error != null) {
      _showSnack(auth.error!);
    }

    if (mounted) setState(() => _isSubmitting = false);
  }

  // ── Login Google ───────────────────────────────────────────────
  Future<void> _handleGoogleSignIn() async {
    setState(() => _isSubmitting = true);
    final auth = context.read<AuthContext>();
    auth.clearError();

    final success = await auth.loginWithGoogle();

    if (success && mounted) {
      await _redirectAfterLogin(auth.uid);
    } else if (!success && mounted && auth.error != null) {
      _showSnack(auth.error!);
    }

    if (mounted) setState(() => _isSubmitting = false);
  }

  // ── Mot de passe oublié — Dialog avec 2 états ─────────────────
  Future<void> _handleForgotPassword() async {
    // Pré-remplir avec l'email déjà saisi dans le formulaire
    final dialogEmailCtrl = TextEditingController(
      text: _emailController.text.trim(),
    );
    final auth = context.read<AuthContext>();

    await showDialog(
      context: context,
      barrierDismissible: true,
      builder: (ctx) {
        bool isSending = false;
        bool emailSent = false;
        String? errorMsg;

        return StatefulBuilder(
          builder: (_, setDialogState) {
            // ════════════════════════════════════════════════
            // ÉTAT SUCCÈS — Email envoyé
            // ════════════════════════════════════════════════
            if (emailSent) {
              return AlertDialog(
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(24),
                ),
                contentPadding: const EdgeInsets.fromLTRB(24, 32, 24, 24),
                content: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    // Icône succès
                    Container(
                      width: 80,
                      height: 80,
                      decoration: BoxDecoration(
                        color: _primary.withOpacity(0.1),
                        shape: BoxShape.circle,
                      ),
                      child: const Icon(
                        Icons.mark_email_read_outlined,
                        color: _primary,
                        size: 40,
                      ),
                    ),
                    const SizedBox(height: 20),
                    const Text(
                      'Email envoyé ! ✉️',
                      style: TextStyle(
                        fontSize: 20,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 10),
                    Text(
                      'Un lien de réinitialisation a été envoyé à :',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        fontSize: 13,
                        color: Colors.grey[600],
                        height: 1.5,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      dialogEmailCtrl.text.trim(),
                      textAlign: TextAlign.center,
                      style: const TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w600,
                        color: _primary,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'Vérifiez également vos spams.',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        fontSize: 12,
                        color: Colors.grey[400],
                        fontStyle: FontStyle.italic,
                      ),
                    ),
                    const SizedBox(height: 24),
                    // Bouton fermer
                    SizedBox(
                      width: double.infinity,
                      child: ElevatedButton(
                        onPressed: () => Navigator.pop(ctx),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: _primary,
                          padding: const EdgeInsets.symmetric(vertical: 14),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(50),
                          ),
                        ),
                        child: const Text(
                          'Compris !',
                          style: TextStyle(
                            color: Colors.white,
                            fontWeight: FontWeight.w600,
                            fontSize: 15,
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              );
            }

            // ════════════════════════════════════════════════
            // ÉTAT FORMULAIRE — Saisie email
            // ════════════════════════════════════════════════
            return AlertDialog(
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(24),
              ),
              contentPadding: const EdgeInsets.fromLTRB(24, 24, 24, 24),
              titlePadding: EdgeInsets.zero,
              content: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Titre avec icône
                  Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.all(8),
                        decoration: BoxDecoration(
                          color: _primary.withOpacity(0.1),
                          borderRadius: BorderRadius.circular(10),
                        ),
                        child: const Icon(
                          Icons.lock_reset_rounded,
                          color: _primary,
                          size: 22,
                        ),
                      ),
                      const SizedBox(width: 12),
                      const Text(
                        'Réinitialisation',
                        style: TextStyle(
                          fontSize: 17,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 14),
                  // Description
                  Text(
                    'Entrez votre email et nous vous enverrons un lien pour réinitialiser votre mot de passe.',
                    style: TextStyle(
                      fontSize: 13,
                      color: Colors.grey[600],
                      height: 1.5,
                    ),
                  ),
                  const SizedBox(height: 18),
                  // Champ email
                  TextField(
                    controller: dialogEmailCtrl,
                    keyboardType: TextInputType.emailAddress,
                    autofocus: dialogEmailCtrl.text.isEmpty,
                    onSubmitted: (_) async {
                      // Permettre de soumettre avec le clavier
                      final email = dialogEmailCtrl.text.trim();
                      if (email.isEmpty) {
                        setDialogState(() =>
                            errorMsg = 'Veuillez saisir votre email.');
                        return;
                      }
                      setDialogState(() { isSending = true; errorMsg = null; });
                      auth.clearError();
                      final result = await auth.sendPasswordResetEmail(email);
                      setDialogState(() {
                        isSending = false;
                        if (result) emailSent = true;
                        else errorMsg = auth.error ?? "Erreur lors de l'envoi.";
                      });
                    },
                    decoration: InputDecoration(
                      labelText: 'Adresse email',
                      prefixIcon: const Icon(
                        Icons.email_outlined,
                        color: _primary,
                      ),
                      errorText: errorMsg,
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                      focusedBorder: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(12),
                        borderSide: const BorderSide(
                          color: _primary,
                          width: 1.5,
                        ),
                      ),
                      errorBorder: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(12),
                        borderSide: const BorderSide(
                          color: Colors.red,
                          width: 1.5,
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(height: 20),
                  // Boutons Annuler / Envoyer
                  Row(
                    children: [
                      // Annuler
                      Expanded(
                        child: TextButton(
                          onPressed: isSending
                              ? null
                              : () => Navigator.pop(ctx),
                          child: Text(
                            'Annuler',
                            style: TextStyle(color: Colors.grey[600]),
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                      // Envoyer le lien
                      Expanded(
                        flex: 2,
                        child: ElevatedButton(
                          onPressed: isSending
                              ? null
                              : () async {
                                  final email = dialogEmailCtrl.text.trim();
                                  if (email.isEmpty) {
                                    setDialogState(() => errorMsg =
                                        'Veuillez saisir votre email.');
                                    return;
                                  }

                                  setDialogState(() {
                                    isSending = true;
                                    errorMsg = null;
                                  });

                                  auth.clearError();
                                  final result =
                                      await auth.sendPasswordResetEmail(email);

                                  setDialogState(() {
                                    isSending = false;
                                    if (result) {
                                      emailSent = true;
                                    } else {
                                      errorMsg = auth.error ??
                                          "Erreur lors de l'envoi.";
                                    }
                                  });
                                },
                          style: ElevatedButton.styleFrom(
                            backgroundColor: _primary,
                            disabledBackgroundColor:
                                _primary.withOpacity(0.45),
                            padding:
                                const EdgeInsets.symmetric(vertical: 14),
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(50),
                            ),
                          ),
                          child: isSending
                              ? const SizedBox(
                                  height: 18,
                                  width: 18,
                                  child: CircularProgressIndicator(
                                    color: Colors.white,
                                    strokeWidth: 2,
                                  ),
                                )
                              : const Text(
                                  'Envoyer le lien',
                                  style: TextStyle(
                                    color: Colors.white,
                                    fontWeight: FontWeight.w600,
                                  ),
                                ),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            );
          },
        );
      },
    );

    dialogEmailCtrl.dispose();
  }

  void _showSnack(String message, {bool isSuccess = false}) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: isSuccess ? const Color(0xFF2A7FC4) : null,
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      ),
    );
  }

  // ============================================================
  // BUILD
  // ============================================================
  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    const Color primary = Color(0xFF2A7FC4);

    final bgCard  = isDark ? AppColors.darkSurface : AppColors.lightSurface;
    final bgPage  = isDark ? AppColors.darkBg      : AppColors.lightBg;
    final text1   = isDark ? AppColors.darkText1   : AppColors.lightText1;
    final text2   = isDark ? AppColors.darkText2   : AppColors.lightText2;
    final borderC = isDark ? AppColors.darkBorder2 : AppColors.lightBorder;

    final isDisabled = _isSubmitting || (isSignUp && _emailStatus != EmailStatus.valid);

    return Column(
      children: [
        Expanded(
          child: Stack(
            children: [

              // ── Robot background ────────────────────────────────────
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

              // ── Formulaire ──────────────────────────────────────────
              SingleChildScrollView(
                child: Container(
                  constraints: BoxConstraints(
                    minHeight: MediaQuery.of(context).size.height - 130,
                  ),
                  color: Colors.transparent,
                  alignment: Alignment.center,
                  padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 60),
                  child: Container(
                    width: 480,
                    padding: const EdgeInsets.all(40),
                    decoration: BoxDecoration(
                      color: bgCard,
                      borderRadius: BorderRadius.circular(32),
                      border: Border.all(color: borderC, width: 0.5),
                      boxShadow: [
                        BoxShadow(
                          color: Colors.black.withOpacity(isDark ? 0.3 : 0.05),
                          blurRadius: 50,
                          offset: const Offset(0, 20),
                        ),
                      ],
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [

                        // ── Titre ──────────────────────────────────────
                        Text(
                          isSignUp ? 'Create Account' : 'Welcome Back',
                          style: GoogleFonts.playfairDisplay(
                            fontSize: 28,
                            fontWeight: FontWeight.w700,
                            color: text1,
                          ),
                        ),
                        const SizedBox(height: 32),

                        // ── Full Name (signup only) ────────────────────
                        if (isSignUp) ...[
                          _buildInputField(
                            'Full Name', _fullNameController,
                            TextInputType.name,
                            text1: text1, borderC: borderC, bgPage: bgPage,
                          ),
                          const SizedBox(height: 20),
                        ],

                        // ── Email ──────────────────────────────────────
                        Text('Email',
                            style: TextStyle(
                                fontWeight: FontWeight.w600,
                                fontSize: 14,
                                color: text1)),
                        const SizedBox(height: 8),
                        TextField(
                          controller: _emailController,
                          keyboardType: TextInputType.emailAddress,
                          style: TextStyle(color: text1),
                          decoration: InputDecoration(
                            filled: true,
                            fillColor: _emailStatus == EmailStatus.valid
                                ? (isDark
                                    ? const Color(0xFF0D1E35)
                                    : const Color(0xFFDBEEF9))
                                : _emailStatus == EmailStatus.invalid
                                    ? (isDark
                                        ? const Color(0xFF2A0F0F)
                                        : const Color(0xFFFEF2F2))
                                    : bgPage,
                            border: OutlineInputBorder(
                                borderRadius: BorderRadius.circular(12)),
                            enabledBorder: OutlineInputBorder(
                              borderRadius: BorderRadius.circular(12),
                              borderSide: BorderSide(
                                color: _emailStatus == EmailStatus.valid
                                    ? primary
                                    : _emailStatus == EmailStatus.invalid
                                        ? AppColors.error
                                        : borderC,
                                width: _emailStatus == EmailStatus.idle
                                    ? 0.5
                                    : 1.5,
                              ),
                            ),
                            focusedBorder: OutlineInputBorder(
                              borderRadius: BorderRadius.circular(12),
                              borderSide: BorderSide(
                                color: _emailStatus == EmailStatus.invalid
                                    ? AppColors.error
                                    : primary,
                                width: 2,
                              ),
                            ),
                          ),
                        ),

                        // Statut email
                        if (_emailController.text.isNotEmpty) ...[
                          const SizedBox(height: 6),
                          Text(
                            _emailStatus == EmailStatus.checking
                                ? '⏳ Vérification en cours...'
                                : _emailStatus == EmailStatus.valid
                                    ? '✅ $_emailMessage'
                                    : _emailStatus == EmailStatus.invalid
                                        ? '❌ $_emailMessage'
                                        : '',
                            style: TextStyle(
                              fontSize: 12,
                              fontWeight: FontWeight.w500,
                              color: _emailStatus == EmailStatus.invalid
                                  ? AppColors.error
                                  : primary,
                            ),
                          ),
                        ],
                        const SizedBox(height: 20),

                        // ── Password ───────────────────────────────────
                        _buildInputField(
                          'Password', _passwordController,
                          TextInputType.visiblePassword,
                          obscure: true,
                          text1: text1, borderC: borderC, bgPage: bgPage,
                        ),

                        // ── Mot de passe oublié (login only) ──────────
                        if (!isSignUp) ...[
                          const SizedBox(height: 8),
                          Align(
                            alignment: Alignment.centerRight,
                            child: GestureDetector(
                              onTap: _handleForgotPassword,
                              child: Text(
                                'Mot de passe oublié ?',
                                style: TextStyle(
                                  color: primary,
                                  fontSize: 13,
                                  fontWeight: FontWeight.w500,
                                ),
                              ),
                            ),
                          ),
                        ],
                        const SizedBox(height: 28),

                        // ── Bouton principal (Email/Password) ──────────
                        ElevatedButton(
                          onPressed: isDisabled ? null : _handleSubmit,
                          style: ElevatedButton.styleFrom(
                            backgroundColor: primary,
                            disabledBackgroundColor: primary.withOpacity(0.45),
                            padding: const EdgeInsets.symmetric(vertical: 16),
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(50),
                            ),
                          ),
                          child: _isSubmitting
                              ? const SizedBox(
                                  height: 20,
                                  width: 20,
                                  child: CircularProgressIndicator(
                                    color: Colors.white,
                                    strokeWidth: 2,
                                  ),
                                )
                              : Text(
                                  isSignUp ? 'Sign Up' : 'Sign In',
                                  style: const TextStyle(
                                    fontWeight: FontWeight.w700,
                                    fontSize: 16,
                                    color: Colors.white,
                                  ),
                                ),
                        ),
                        const SizedBox(height: 16),

                        // ── Séparateur ─────────────────────────────────
                        Row(
                          children: [
                            Expanded(child: Divider(color: borderC)),
                            Padding(
                              padding: const EdgeInsets.symmetric(horizontal: 12),
                              child: Text('ou',
                                  style: TextStyle(color: text2, fontSize: 13)),
                            ),
                            Expanded(child: Divider(color: borderC)),
                          ],
                        ),
                        const SizedBox(height: 16),

                        // ── Bouton Google Sign-In ──────────────────────
                        OutlinedButton.icon(
                          onPressed: _isSubmitting ? null : _handleGoogleSignIn,
                          icon: Image.network(
                            'https://www.google.com/favicon.ico',
                            width: 18,
                            height: 18,
                            errorBuilder: (_, __, ___) =>
                                const Icon(Icons.g_mobiledata, size: 20),
                          ),
                          label: Text(
                            isSignUp
                                ? 'Continuer avec Google'
                                : 'Se connecter avec Google',
                            style: TextStyle(
                              color: text1,
                              fontWeight: FontWeight.w600,
                              fontSize: 15,
                            ),
                          ),
                          style: OutlinedButton.styleFrom(
                            padding: const EdgeInsets.symmetric(vertical: 14),
                            side: BorderSide(color: borderC, width: 1),
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(50),
                            ),
                          ),
                        ),
                        const SizedBox(height: 20),

                        // ── Lien Sign In ↔ Sign Up ─────────────────────
                        Center(
                          child: GestureDetector(
                            onTap: () => context.go(
                                isSignUp ? '/signin' : '/signup'),
                            child: RichText(
                              text: TextSpan(
                                style: TextStyle(color: text2, fontSize: 14),
                                children: [
                                  TextSpan(
                                    text: isSignUp
                                        ? 'Already have an account? '
                                        : 'No account? ',
                                  ),
                                  const TextSpan(
                                    text: 'Sign In',
                                    style: TextStyle(
                                      color: primary,
                                      fontWeight: FontWeight.w700,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ),
                        ),

                      ],
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),

        const AppBottomNavBar(active: NavTab.home),
        const SizedBox(height: 20),
      ],
    );
  }

  // ── Input field builder ────────────────────────────────────────
  Widget _buildInputField(
    String label,
    TextEditingController ctrl,
    TextInputType type, {
    bool obscure = false,
    required Color text1,
    required Color borderC,
    required Color bgPage,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label,
            style: TextStyle(
                fontWeight: FontWeight.w600, fontSize: 14, color: text1)),
        const SizedBox(height: 8),
        TextField(
          controller: ctrl,
          keyboardType: type,
          obscureText: obscure,
          style: TextStyle(color: text1),
          decoration: InputDecoration(
            filled: true,
            fillColor: bgPage,
            border:
                OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
            enabledBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(12),
              borderSide: BorderSide(color: borderC, width: 0.5),
            ),
          ),
        ),
      ],
    );
  }
}
