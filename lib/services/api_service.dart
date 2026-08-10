// lib/services/api_service.dart
import 'dart:convert';
import 'dart:typed_data';
import 'package:http/http.dart' as http;
import 'package:firebase_auth/firebase_auth.dart';
import 'package:proptech_ai/config.dart';

class ApiService {
  static String get baseUrl => AppConfig.baseUrl;

  // ── HELPER : Headers avec Token Firebase pour la sécurité ──
  static Future<Map<String, String>> _getAuthHeaders() async {
    final user = FirebaseAuth.instance.currentUser;
    final token = await user?.getIdToken();
    return {
      'Content-Type': 'application/json',
      if (token != null) 'Authorization': 'Bearer $token',
    };
  }

  // ── AUTH ──────────────────────────────────────────────

  static Future<Map<String, dynamic>> register(
      String fullName, String email, String password) async {
    final res = await http.post(
      Uri.parse('$baseUrl/api/auth/register'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'full_name': fullName, 'email': email, 'password': password}),
    );
    return _decode(res);
  }

  static Future<Map<String, dynamic>> login(String email, String password) async {
    final res = await http.post(
      Uri.parse('$baseUrl/api/auth/login'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'email': email, 'password': password}),
    );
    return _decode(res);
  }

  static Future<Map<String, dynamic>> checkEmail(String email) async {
    final res = await http.get(
      Uri.parse('$baseUrl/api/auth/check-email?email=${Uri.encodeComponent(email)}'),
    );
    return _decode(res);
  }

  // ── SUBSCRIPTION & PAYMENT (Stripe / Konnect) ──────────

  static Future<Map<String, dynamic>> createPayment({required String uid, required String email}) async {
    final headers = await _getAuthHeaders();
    final res = await http.post(
      Uri.parse('$baseUrl/api/subscription/select-plan'),
      headers: headers,
      body: jsonEncode({
        'plan':  'premium',
        'uid':   uid,    // ✅ FIX: envoyé au backend
        'email': email,  // ✅ FIX: requis par Stripe
      }),
    );
    return _decode(res);
  }

  // ✅ NOUVEAU : Récupère le plan actuel depuis Firestore via backend
  static Future<Map<String, dynamic>> getUserPlan() async {
    final headers = await _getAuthHeaders();
    final res = await http.get(
      Uri.parse('$baseUrl/api/subscription/plan'),
      headers: headers,
    );
    return _decode(res);
  }

  static Future<Map<String, dynamic>> getSubscriptionStatus() async {
    final headers = await _getAuthHeaders();
    final res = await http.get(
      Uri.parse('$baseUrl/api/subscription/plan'),
      headers: headers,
    );
    return _decode(res);
  }

  /// Vérifie le statut du paiement après redirection Stripe
  static Future<Map<String, dynamic>> verifyPayment(String paymentRef) async {
    final headers = await _getAuthHeaders();
    // On passe le paymentRef (sessionId) au backend pour validation
    final res = await http.get(
      Uri.parse('$baseUrl/api/payment/verify/$paymentRef'),
      headers: headers,
    );
    return _decode(res);
  }

  // ── CHAT ─────────────────────────────────────────────

  static Future<Map<String, dynamic>> sendChat({
    required String question,
    required String propertyType,
    required String llmModel,
    int? userId,
    required List<Map<String, String>> chatHistory,
  }) async {
    final headers = await _getAuthHeaders();
    final res = await http.post(
      Uri.parse('$baseUrl/api/chat'),
      headers: headers,
      body: jsonEncode({
        'question': question,
        'property_type': propertyType,
        'llm_model': llmModel,
        'user_id': userId,
        'chat_history': chatHistory,
      }),
    );
    return _decode(res);
  }

  // ── IMAGE UPLOAD / DOCUMENT ANALYSIS ──────────────────

  static Future<Map<String, dynamic>> uploadImage(
      Uint8List imageBytes,
      String fileName,
      String propertyType, {
        String? llmModel,
        String? userQuestion,
        int? userId,
      }) async {
    final user = FirebaseAuth.instance.currentUser;
    final token = await user?.getIdToken();

    final request = http.MultipartRequest(
      'POST',
      Uri.parse('$baseUrl/api/upload-document'),
    );

    if (token != null) {
      request.headers['Authorization'] = 'Bearer $token';
    }

    request.fields['property_type'] = propertyType;
    if (llmModel != null && llmModel.isNotEmpty) {
      request.fields['llm_model_req'] = llmModel;
    }
    if (userQuestion != null && userQuestion.isNotEmpty) {
      request.fields['user_question'] = userQuestion;
    }
    if (userId != null) {
      request.fields['user_id'] = userId.toString();
    }
    request.files.add(http.MultipartFile.fromBytes(
      'file',
      imageBytes,
      filename: fileName,
    ));
    final streamed = await request.send();
    final res = await http.Response.fromStream(streamed);
    return _decode(res);
  }

  // ── QUALITY LIFE ──────────────────────────────────────

  static Future<Map<String, dynamic>> analyzeQualityLife(String address) async {
    final headers = await _getAuthHeaders();
    final res = await http.post(
      Uri.parse('$baseUrl/api/quality-life'),
      headers: headers,
      body: jsonEncode({'address': address}),
    );
    return _decode(res);
  }

  // ── CREDITS ──────────────────────────────────────────

  static Future<Map<String, dynamic>> getCreditsStatus({int? userId, String? userPlan}) async {
    final headers = await _getAuthHeaders();
    final params = <String, String>{};
    if (userId != null) params['user_id'] = '$userId';
    if (userPlan != null) params['user_plan'] = userPlan;
    final uri = Uri.parse('$baseUrl/api/credits/status')
        .replace(queryParameters: params.isNotEmpty ? params : null);
    final res = await http.get(uri, headers: headers);
    return _decode(res);
  }

  // ── HISTORY ──────────────────────────────────────────

  static Future<List<dynamic>> getHistory(int userId) async {
    final headers = await _getAuthHeaders();
    final res = await http.get(
      Uri.parse('$baseUrl/api/history/$userId'),
      headers: headers,
    );
    if (res.statusCode == 200) return jsonDecode(res.body) as List;
    throw Exception('Failed to load history');
  }

  // ── HELPER ───────────────────────────────────────────

  static Map<String, dynamic> _decode(http.Response res) {
    final body = jsonDecode(res.body) as Map<String, dynamic>;
    if (res.statusCode >= 400) {
      final rawDetail = body['detail'];
      final message = rawDetail is String
          ? rawDetail
          : (rawDetail is Map ? (rawDetail['message'] ?? 'Unknown error') : 'Unknown error');
      throw ApiException(message as String, res.statusCode, detail: rawDetail);
    }
    return body;
  }
}

class ApiException implements Exception {
  final String message;
  final dynamic detail;
  final int statusCode;
  ApiException(this.message, this.statusCode, {this.detail});
  @override
  String toString() => message;
}
