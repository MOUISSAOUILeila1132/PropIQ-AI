// lib/context/auth_context.dart
import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:http/http.dart' as http;
import 'package:proptech_ai/config.dart'; // ✅ Pour AppConfig.baseUrl (ngrok / prod)

// ============================================================
// USER MODEL
// ============================================================
class UserModel {
  final String uid;
  final String fullName;
  final String email;
  final String? photoUrl;
  final String? idToken;

  int get id => uid.hashCode;

  UserModel({
    required this.uid,
    required this.fullName,
    required this.email,
    this.photoUrl,
    this.idToken,
  });

  factory UserModel.fromFirebase(User firebaseUser, {String? idToken}) =>
      UserModel(
        uid:      firebaseUser.uid,
        fullName: firebaseUser.displayName ?? firebaseUser.email ?? 'Utilisateur',
        email:    firebaseUser.email ?? '',
        photoUrl: firebaseUser.photoURL,
        idToken:  idToken,
      );

  factory UserModel.fromJson(Map<String, dynamic> json) => UserModel(
    uid:      json['uid'] ?? json['id']?.toString() ?? '',
    fullName: json['full_name'] ?? '',
    email:    json['email'] ?? '',
    photoUrl: json['photo_url'],
    idToken:  json['id_token'],
  );

  Map<String, dynamic> toJson() => {
    'uid':       uid,
    'full_name': fullName,
    'email':     email,
    'photo_url': photoUrl,
    'id_token':  idToken,
  };

  String get firstName => fullName.split(' ').first;

  UserModel copyWith({String? idToken}) => UserModel(
    uid:      uid,
    fullName: fullName,
    email:    email,
    photoUrl: photoUrl,
    idToken:  idToken ?? this.idToken,
  );
}

// ============================================================
// AUTH CONTEXT
// ============================================================
class AuthContext extends ChangeNotifier {
  UserModel? _user;
  bool _isLoading = false;
  String? _error;
  bool _disposed = false;                          // ✅ AJOUT : guard anti-crash

  static const _storageKey = 'propiq_user';

  final FirebaseAuth _firebaseAuth = FirebaseAuth.instance;
  final GoogleSignIn _googleSignIn = GoogleSignIn();
  StreamSubscription<User?>? _authStateSubscription; // ✅ AJOUT : gestion explicite

  AuthContext() {
    _init();
  }

  UserModel? get user            => _user;
  bool       get isAuthenticated => _user != null;
  bool       get isLoading       => _isLoading;
  String?    get error           => _error;

  // ── AJOUT DES GETTERS POUR CORRIGER LES ERREURS ──
  String? get uid   => _user?.uid;
  String? get email => _user?.email;

  void _init() {
    // ✅ On sauvegarde la souscription pour pouvoir l'annuler dans dispose()
    _authStateSubscription = _firebaseAuth.authStateChanges().listen((firebaseUser) async {
      if (firebaseUser == null) {
        await _clearStorage();
        if (_disposed) return;               // ✅ guard async
        _user = null;
        notifyListeners();
      } else {
        await _syncFromFirebase(firebaseUser);
      }
    });
  }

  Future<void> _syncFromFirebase(User firebaseUser) async {
    try {
      final idToken = await firebaseUser.getIdToken(true);
      if (_disposed) return;                     // ✅ guard : await peut prendre du temps
      _user = UserModel.fromFirebase(firebaseUser, idToken: idToken);
      await _saveToStorage(_user!);
      if (_disposed) return;                     // ✅ guard : deuxième await
      notifyListeners();
    } catch (e) {
      debugPrint('[AuthContext] Erreur sync Firebase : $e');
    }
  }

  Future<void> _loadFromStorage() async {
    final prefs = await SharedPreferences.getInstance();
    final saved = prefs.getString(_storageKey);
    if (saved != null) {
      try {
        _user = UserModel.fromJson(jsonDecode(saved));
        notifyListeners();
      } catch (_) {
        await _clearStorage();
      }
    }
  }

  Future<void> _saveToStorage(UserModel u) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_storageKey, jsonEncode(u.toJson()));
  }

  Future<void> _clearStorage() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_storageKey);
  }

  Future<String?> getValidToken() async {
    final firebaseUser = _firebaseAuth.currentUser;
    if (firebaseUser == null) return null;
    try {
      final token = await firebaseUser.getIdToken(false);
      if (_disposed) return token;             // ✅ guard : ne pas modifier l'état
      _user = _user?.copyWith(idToken: token);
      return token;
    } catch (e) {
      debugPrint('[AuthContext] Impossible de rafraîchir le token : $e');
      return null;
    }
  }

  Future<Map<String, String>> getAuthHeaders() async {
    final token = await getValidToken();
    return {
      'Content-Type':  'application/json',
      if (token != null) 'Authorization': 'Bearer $token',
    };
  }

  // ============================================================
  // LOGIN — Email / Mot de passe
  // ============================================================
  Future<bool> loginWithEmail(String email, String password) async {
    _setLoading(true);
    try {
      final credential = await _firebaseAuth.signInWithEmailAndPassword(
        email:    email.trim(),
        password: password,
      );
      if (credential.user != null) {
        await _syncFromFirebase(credential.user!);
        await _verifyWithBackend();
        return true;
      }
      return false;
    } on FirebaseAuthException catch (e) {
      _setError(_mapFirebaseError(e.code));
      return false;
    } catch (e) {
      _setError('Erreur inattendue : $e');
      return false;
    } finally {
      _setLoading(false);
    }
  }

  // ============================================================
  // REGISTER — Email / Mot de passe
  // ============================================================
  Future<bool> registerWithEmail(
      String email,
      String password,
      String fullName,
      ) async {
    _setLoading(true);
    try {
      final credential = await _firebaseAuth.createUserWithEmailAndPassword(
        email:    email.trim(),
        password: password,
      );
      await credential.user?.updateDisplayName(fullName.trim());
      await credential.user?.reload();

      if (credential.user != null) {
        await _syncFromFirebase(_firebaseAuth.currentUser!);
        return true;
      }
      return false;
    } on FirebaseAuthException catch (e) {
      _setError(_mapFirebaseError(e.code));
      return false;
    } catch (e) {
      _setError('Erreur inattendue : $e');
      return false;
    } finally {
      _setLoading(false);
    }
  }

  // ============================================================
  // LOGIN — Google Sign-In
  // ============================================================
  Future<bool> loginWithGoogle() async {
    _setLoading(true);
    try {
      final googleAccount = await _googleSignIn.signIn();
      if (googleAccount == null) {
        _setLoading(false);
        return false;
      }

      final googleAuth = await googleAccount.authentication;
      final credential = GoogleAuthProvider.credential(
        accessToken: googleAuth.accessToken,
        idToken:     googleAuth.idToken,
      );

      final userCredential =
      await _firebaseAuth.signInWithCredential(credential);

      if (userCredential.user != null) {
        await _syncFromFirebase(userCredential.user!);
        await _verifyWithBackend();
        return true;
      }
      return false;
    } on FirebaseAuthException catch (e) {
      _setError(_mapFirebaseError(e.code));
      return false;
    } catch (e) {
      _setError('Erreur Google Sign-In : $e');
      return false;
    } finally {
      _setLoading(false);
    }
  }

  // ============================================================
  // RÉINITIALISATION MOT DE PASSE
  // ============================================================
  Future<bool> sendPasswordResetEmail(String email) async {
    _setLoading(true);
    try {
      await _firebaseAuth.sendPasswordResetEmail(email: email.trim());
      debugPrint('[AuthContext] ✅ Email de reset envoyé à : $email');
      return true;
    } on FirebaseAuthException catch (e) {
      debugPrint('[AuthContext] ❌ FirebaseAuthException reset (${e.code}) : ${e.message}');
      _setError(_mapFirebaseError(e.code));
      return false;
    } catch (e) {
      debugPrint('[AuthContext] ❌ Erreur inattendue reset : $e');
      _setError("Erreur lors de l'envoi du mail de réinitialisation.");
      return false;
    } finally {
      _setLoading(false);
    }
  }

  // ============================================================
  // LOGOUT — ✅ CORRIGÉ : Google signOut ignoré si non configuré
  // ============================================================
  Future<void> logout() async {
    _setLoading(true);
    try {
      // ✅ Google Sign-Out : ignoré si non configuré sur Web
      try {
        await _googleSignIn.signOut();
      } catch (e) {
        debugPrint('[AuthContext] Google signOut ignoré : $e');
      }

      // ✅ Firebase Sign-Out : toujours exécuté
      await _firebaseAuth.signOut();
      if (_disposed) return;                     // ✅ guard après await
      _user = null;
      await _clearStorage();
      // notifyListeners() est déjà appelé par _setLoading(false) dans finally
    } catch (e) {
      debugPrint('[AuthContext] Erreur logout : $e');
    } finally {
      _setLoading(false);
    }
  }

  // ============================================================
  // VÉRIFICATION BACKEND (optionnel)
  // ============================================================
  Future<void> _verifyWithBackend() async {
    try {
      final headers = await getAuthHeaders();
      final response = await http.get(
        Uri.parse('${AppConfig.baseUrl}/api/auth/firebase/verify'), // ✅ ngrok ou prod
        headers: headers,
      );
      if (response.statusCode == 200) {
        debugPrint('[AuthContext] ✅ Session confirmée par le backend');
      } else {
        debugPrint('[AuthContext] ⚠️ Backend a rejeté le token : ${response.body}');
      }
    } catch (e) {
      debugPrint('[AuthContext] ⚠️ Vérification backend inaccessible : $e');
    }
  }

  // ============================================================
  // HELPERS INTERNES
  // ============================================================
  void _setLoading(bool value) {
    if (_disposed) return;                       // ✅ guard
    _isLoading = value;
    notifyListeners();
  }

  void _setError(String message) {
    if (_disposed) return;                       // ✅ guard
    _error = message;
    notifyListeners();
  }

  void clearError() {
    if (_disposed) return;                       // ✅ guard
    _error = null;
    notifyListeners();
  }

  // ============================================================
  // DISPOSE — ✅ CRITIQUE : annuler la souscription au stream
  // ============================================================
  @override
  void dispose() {
    _disposed = true;
    _authStateSubscription?.cancel();  // ✅ évite notifyListeners() post-dispose
    debugPrint('[AuthContext] dispose() — souscription annulée');
    super.dispose();
  }

  String _mapFirebaseError(String code) {
    switch (code) {
      case 'user-not-found':
        return 'Aucun compte trouvé avec cet email.';
      case 'wrong-password':
        return 'Mot de passe incorrect.';
      case 'email-already-in-use':
        return 'Cet email est déjà utilisé.';
      case 'invalid-email':
        return 'Adresse email invalide.';
      case 'weak-password':
        return 'Mot de passe trop faible (minimum 6 caractères).';
      case 'user-disabled':
        return 'Ce compte a été désactivé.';
      case 'too-many-requests':
        return 'Trop de tentatives. Réessayez plus tard.';
      case 'network-request-failed':
        return 'Pas de connexion internet.';
      case 'invalid-credential':
        return 'Identifiants invalides. Vérifiez votre email et mot de passe.';
      case 'missing-email':                           // reset sans email
        return 'Veuillez saisir une adresse email.';
      case 'auth/user-not-found':                     // variante SDK Web
        return 'Aucun compte trouvé avec cet email.';
      default:
        return "Erreur d'authentification ($code).";
    }
  }
}
