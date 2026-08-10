// lib/pages/splash_screen.dart
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:video_player/video_player.dart';

class SplashScreen extends StatefulWidget {
  const SplashScreen({super.key});

  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen>
    with TickerProviderStateMixin {

  // ── Video ──────────────────────────────────────────────────────────────────
  late VideoPlayerController _videoController;
  bool _videoInitialized = false;
  bool _videoFinished    = false;

  // ── Continue button animation ──────────────────────────────────────────────
  late AnimationController _buttonController;
  late Animation<double>   _buttonOpacity;
  late Animation<Offset>   _buttonSlide;

  // ── Exit animation ─────────────────────────────────────────────────────────
  late AnimationController _exitController;
  late Animation<double>   _exitOpacity;

  // ── Navigation flags ───────────────────────────────────────────────────────
  bool _canContinue    = false;
  bool _autoNavigating = false;

  // ── Colors ─────────────────────────────────────────────────────────────────
  static const Color _accent  = Color(0xFF5B8DEF);
  static const Color _accent2 = Color(0xFF4F46E5);

  // ──────────────────────────────────────────────────────────────────────────
  @override
  void initState() {
    super.initState();

    // Force landscape + fullscreen for the video
    SystemChrome.setEnabledSystemUIMode(SystemUiMode.immersiveSticky);

    _setupAnimations();
    _initVideo();
    _checkFirebaseSession();
  }

  // ── Animations setup ──────────────────────────────────────────────────────
  void _setupAnimations() {
    _buttonController = AnimationController(
        vsync: this, duration: const Duration(milliseconds: 700));

    _buttonOpacity = Tween<double>(begin: 0, end: 1).animate(
        CurvedAnimation(parent: _buttonController, curve: Curves.easeOut));

    _buttonSlide = Tween<Offset>(
        begin: const Offset(0, 0.5), end: Offset.zero).animate(
        CurvedAnimation(parent: _buttonController, curve: Curves.easeOut));

    _exitController = AnimationController(
        vsync: this, duration: const Duration(milliseconds: 600));

    _exitOpacity = Tween<double>(begin: 1, end: 0).animate(
        CurvedAnimation(parent: _exitController, curve: Curves.easeInOut));
  }

  // ── Video init ────────────────────────────────────────────────────────────
  Future<void> _initVideo() async {
    _videoController =
        VideoPlayerController.asset('assets/images/Pika.mp4');

    await _videoController.initialize();

    // Listen for video completion
    _videoController.addListener(_onVideoProgress);

    if (!mounted) return;
    setState(() => _videoInitialized = true);

    // Autoplay
    await _videoController.play();
  }

  void _onVideoProgress() {
    if (!mounted) return;
    final ctrl = _videoController;
    if (ctrl.value.isInitialized &&
        !ctrl.value.isPlaying &&
        ctrl.value.position >= ctrl.value.duration &&
        !_videoFinished) {
      setState(() => _videoFinished = true);
      // Show continue button once video ends (if not already navigating)
      if (!_autoNavigating) {
        _buttonController.forward();
      }
    }
  }

  // ── Firebase session check ────────────────────────────────────────────────
  Future<void> _checkFirebaseSession() async {
    // Wait a bit so the video has time to start
    await Future.delayed(const Duration(milliseconds: 1800));
    if (!mounted) return;

    final firebaseUser = FirebaseAuth.instance.currentUser;

    if (firebaseUser != null) {
      try {
        await firebaseUser.reload();
        debugPrint(
          '[Splash] ✅ Session Firebase active — '
              'uid=${firebaseUser.uid} | email=${firebaseUser.email}',
        );
        if (!mounted) return;

        // Wait for video to finish before auto-navigating
        if (!_videoFinished) {
          // Show continue button immediately for logged-in users
          setState(() {
            _canContinue    = true;
            _autoNavigating = true;
          });
          _buttonController.forward();
          return; // Will navigate on button tap
        }

        setState(() => _autoNavigating = true);
        await _navigate(firebaseUser);
      } catch (e) {
        debugPrint('[Splash] ⚠️ Session Firebase invalide : $e');
        await FirebaseAuth.instance.signOut();
        if (mounted) {
          setState(() => _canContinue = true);
          if (_videoFinished) _buttonController.forward();
        }
      }
    } else {
      debugPrint('[Splash] ℹ️ Aucune session — affichage bouton Continue');
      if (mounted) setState(() => _canContinue = true);
      // Button shown when video ends (see _onVideoProgress)
    }
  }

  // ── Navigation vers l'accueil ou la sélection de plan ─────────────────────
  // ✅ FIX : try/catch autour de la lecture Firestore pour éviter l'écran noir
  // en cas d'erreur (permissions, réseau, doc absent, etc.)
  Future<void> _navigate(User firebaseUser) async {
    await _exitController.forward();
    if (!mounted) return;

    String? plan;
    try {
      final doc = await FirebaseFirestore.instance
          .collection('users')
          .doc(firebaseUser.uid)
          .get();
      plan = doc.data()?['plan'] as String?;
    } catch (e) {
      debugPrint(
        '[Splash] ⚠️ Erreur lecture Firestore (users/${firebaseUser.uid}) : $e',
      );
      // On ne bloque JAMAIS l'utilisateur sur un écran noir : en cas
      // d'échec (permissions, réseau, doc absent) on l'envoie choisir
      // un plan par défaut plutôt que de rester figé.
      plan = null;
    }

    if (!mounted) return;
    SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge);
    if (plan == null || plan.isEmpty) {
      context.go('/plan-selection');
    } else {
      context.go('/');
    }
  }

  // ── Continue button tap ───────────────────────────────────────────────────
  Future<void> _onContinue() async {
    if (!_videoFinished) return; // Ignore taps before video ends
    setState(() => _canContinue = false);

    await _videoController.pause();

    if (_autoNavigating) {
      final firebaseUser = FirebaseAuth.instance.currentUser;
      if (firebaseUser != null) {
        await _navigate(firebaseUser);
      }
    } else {
      await _exitController.forward();
      if (mounted) {
        SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge);
        context.go('/signin');
      }
    }
  }

  // ── Dispose ───────────────────────────────────────────────────────────────
  @override
  void dispose() {
    _videoController.removeListener(_onVideoProgress);
    _videoController.dispose();
    _buttonController.dispose();
    _exitController.dispose();
    SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge);
    super.dispose();
  }

  // ── Build ──────────────────────────────────────────────────────────────────
  @override
  Widget build(BuildContext context) {
    return FadeTransition(
      opacity: _exitOpacity,
      child: Scaffold(
        backgroundColor: Colors.black,
        body: Stack(
          fit: StackFit.expand,
          children: [
            // ── Full-screen video ──────────────────────────────────────────
            if (_videoInitialized)
              SizedBox.expand(
                child: FittedBox(
                  fit: BoxFit.cover,
                  child: SizedBox(
                    width:  _videoController.value.size.width,
                    height: _videoController.value.size.height,
                    child: VideoPlayer(_videoController),
                  ),
                ),
              )
            else
            // Loading placeholder while video initializes
              const Center(
                child: CircularProgressIndicator(
                  color: Color(0xFF5B8DEF),
                  strokeWidth: 2.5,
                ),
              ),

            // ── Gradient overlay (bottom) ──────────────────────────────────
            Positioned(
              left: 0, right: 0, bottom: 0,
              height: 220,
              child: DecoratedBox(
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.topCenter,
                    end: Alignment.bottomCenter,
                    colors: [
                      Colors.transparent,
                      Colors.black.withOpacity(0.75),
                    ],
                  ),
                ),
              ),
            ),

            // ── Continue button ────────────────────────────────────────────
            Positioned(
              left: 0, right: 0, bottom: 52,
              child: AnimatedBuilder(
                animation: _buttonController,
                builder: (_, __) => FadeTransition(
                  opacity: _buttonOpacity,
                  child: SlideTransition(
                    position: _buttonSlide,
                    child: Center(
                      child: GestureDetector(
                        onTap: _onContinue,
                        child: Container(
                          width: 300,
                          height: 56,
                          decoration: BoxDecoration(
                            gradient: const LinearGradient(
                              colors: [_accent, _accent2],
                              begin: Alignment.centerLeft,
                              end: Alignment.centerRight,
                            ),
                            borderRadius: BorderRadius.circular(28),
                            boxShadow: [
                              BoxShadow(
                                color: _accent.withOpacity(0.45),
                                blurRadius: 24,
                                offset: const Offset(0, 8),
                              ),
                            ],
                          ),
                          child: Row(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Text(
                                'Continuer',
                                style: GoogleFonts.poppins(
                                  color: Colors.white,
                                  fontSize: 16,
                                  fontWeight: FontWeight.w600,
                                  letterSpacing: 0.4,
                                ),
                              ),
                              const SizedBox(width: 12),
                              Container(
                                width: 32,
                                height: 32,
                                decoration: BoxDecoration(
                                  color: Colors.white.withOpacity(0.25),
                                  shape: BoxShape.circle,
                                ),
                                child: const Icon(
                                  Icons.arrow_forward_rounded,
                                  color: Colors.white,
                                  size: 18,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                    ),
                  ),
                ),
              ),
            ),

            // ── Auto-navigate spinner (si session active) ──────────────────
            if (_autoNavigating && !_videoFinished)
              const Positioned(
                top: 48,
                right: 24,
                child: CircularProgressIndicator(
                  color: Colors.white54,
                  strokeWidth: 2,
                ),
              ),
          ],
        ),
      ),
    );
  }
}