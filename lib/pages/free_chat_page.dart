// lib/pages/free_chat_page.dart
import 'dart:io';
import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:flutter_sound/flutter_sound.dart';
import 'package:flutter_tts/flutter_tts.dart';
import 'package:file_picker/file_picker.dart';
import 'package:image_picker/image_picker.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:provider/provider.dart';
import 'package:http/http.dart' as http;
import 'package:path_provider/path_provider.dart';
import 'package:go_router/go_router.dart';

import '../context/auth_context.dart';
import '../services/api_service.dart';
import '../theme/app_theme.dart';
import '../widgets/bottom_nav_bar.dart';
import 'package:proptech_ai/config.dart';

// ── Pending attachment model ──
class _PendingAttachment {
  final Uint8List bytes;
  final String fileName;
  final bool isImage;
  final bool isPdf;
  const _PendingAttachment({required this.bytes, required this.fileName, required this.isImage, this.isPdf = false});
}

// ── Message model ──
class _Message {
  final String id;
  final String role;
  final String text;
  final bool isFile;
  final bool isVoice;
  final bool hasAttachment;
  final String? attachmentName;
  final Uint8List? attachmentThumb;
  final String? detectedLang;
  final String? transcription;

  _Message({
    String? id,
    required this.role,
    required this.text,
    this.isFile = false,
    this.isVoice = false,
    this.hasAttachment = false,
    this.attachmentName,
    this.attachmentThumb,
    this.detectedLang,
    this.transcription,
  }) : id = id ?? DateTime.now().microsecondsSinceEpoch.toString();
}

// ── Credits model ──
class _CreditsInfo {
  final int used;
  final int limit;
  final int remaining;
  final bool warning;
  final bool isAdmin;
  final String message;
  final String resetDate;
  final String userType;

  const _CreditsInfo({
    required this.used,
    required this.limit,
    required this.remaining,
    required this.warning,
    required this.isAdmin,
    required this.message,
    required this.resetDate,
    required this.userType,
  });

  factory _CreditsInfo.fromJson(Map<String, dynamic> json) {
    return _CreditsInfo(
      used:      (json['used']      as num?)?.toInt() ?? 0,
      limit:     (json['limit']     as num?)?.toInt() ?? 0,
      remaining: (json['remaining'] as num?)?.toInt() ?? 0,
      warning:   (json['warning']   as bool?) ?? false,
      isAdmin:   (json['is_admin']  as bool?) ?? false,
      message:   (json['message']   as String?) ?? '',
      resetDate: (json['reset_date'] as String?) ?? '',
      userType:  (json['user_type']  as String?) ?? 'free',
    );
  }

  double get ratio => (limit > 0 && !isAdmin) ? (remaining / limit).clamp(0.0, 1.0) : 1.0;

  Color get barColor {
    if (isAdmin) return const Color(0xFF8B5CF6);
    if (remaining == 0) return AppColors.error;
    if (warning) return const Color(0xFFF59E0B);
    return const Color(0xFF2A7FC4);
  }
}

enum _VoiceState { idle, recording, processing }

class FreeChatPage extends StatefulWidget {
  const FreeChatPage({super.key});
  @override
  State<FreeChatPage> createState() => _FreeChatPageState();
}

class _FreeChatPageState extends State<FreeChatPage> with SingleTickerProviderStateMixin {
  final _scrollController = ScrollController();
  final _inputController  = TextEditingController();
  final _inputFocusNode   = FocusNode();

  _PendingAttachment? _pendingAttachment;

  // ── TTS ──
  final FlutterTts _tts = FlutterTts();
  String? _speakingMessageId;

  // ── flutter_sound recorder (replaces record package) ──
  final FlutterSoundRecorder _recorder = FlutterSoundRecorder();
  bool _recorderReady = false;
  _VoiceState _voiceState = _VoiceState.idle;
  String?     _recordingPath;
  Timer?      _recordingTimer;
  int         _recordingSeconds = 0;
  late AnimationController _pulseController;
  late Animation<double>   _pulseAnimation;

  List<_Message> _messages = [
    _Message(role: 'bot', text: "Hello! I'm PropTech. Select a property type and ask any legal question, attach a file 📎, take a photo 📷, or use voice 🎙️."),
  ];

  String _propertyType = 'residencial';
  String _llmModel     = 'mistralai/mistral-large-2512';
  bool   _isLoading    = false;
  _CreditsInfo? _credits;
  bool _creditsLoading = true;
  String _userPlan = 'free';

  static const _models = [
    {'id': 'mistralai/mistral-large-2512',            'label': '⭐ Mistral Large'},
    {'id': 'qwen/qwen3-235b-a22b',                    'label': '🔬 Qwen3'},
    {'id': 'openai/gpt-4o',                           'label': '⚡ GPT-4o'},
    {'id': 'meta-llama/llama-3.3-70b-instruct',       'label': '🧠 Llama 3.3'},
    {'id': 'microsoft/phi-4',                         'label': '⚡ Phi4'},
    {'id': 'meta-llama/llama-3.2-11b-vision-instruct','label': 'Llama 3.2 Vision'},
    {'id': 'qwen/qwen3-vl-32b-instruct',              'label': 'Qwen3 Vision'},
  ];

  static const _propertyTypes = [
    {'value': 'residencial',      'label': '🏠 Residential'},
    {'value': 'comercial',        'label': '🏢 Commercial'},
    {'value': 'terreno',          'label': '🏗️ Land'},
    {'value': 'alojamento_local', 'label': '🏨 Tourist Rental'},
  ];

  @override
  void initState() {
    super.initState();
    _inputController.addListener(() => setState(() {}));
    WidgetsBinding.instance.addPostFrameCallback((_) => _loadCredits());
    _pulseController = AnimationController(
        vsync: this, duration: const Duration(milliseconds: 900))
      ..repeat(reverse: true);
    _pulseAnimation = Tween<double>(begin: 1.0, end: 1.2).animate(
        CurvedAnimation(parent: _pulseController, curve: Curves.easeInOut));
    _pulseController.stop();
    _initRecorder();
    _initTts();
  }

  Future<void> _initTts() async {
    await _tts.setLanguage('en-US');
    await _tts.setSpeechRate(0.5);
    await _tts.setVolume(1.0);
    await _tts.setPitch(1.0);
    _tts.setCompletionHandler(() {
      if (mounted) setState(() => _speakingMessageId = null);
    });
  }

  Future<void> _initRecorder() async {
    // Request microphone permission
    final status = await Permission.microphone.request();
    if (status != PermissionStatus.granted) return;
    await _recorder.openRecorder();
    setState(() => _recorderReady = true);
  }

  @override
  void dispose() {
    _scrollController.dispose();
    _inputController.dispose();
    _inputFocusNode.dispose();
    _recordingTimer?.cancel();
    _pulseController.dispose();
    if (_recorderReady) _recorder.closeRecorder();
    _tts.stop();
    super.dispose();
  }

  Future<void> _loadCredits() async {
    final user = context.read<AuthContext>().user;
    try {
      final results = await Future.wait([
        ApiService.getCreditsStatus(userId: user?.id),
        ApiService.getUserPlan(),
      ]);
      if (mounted) {
        setState(() {
          _credits        = _CreditsInfo.fromJson(results[0]);
          _userPlan       = results[1]['plan'] as String? ?? 'free';
          _creditsLoading = false;
        });
      }
    } catch (_) {
      if (mounted) setState(() => _creditsLoading = false);
    }
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  Future<void> _handleSend() async {
    final text = _inputController.text.trim();
    if ((text.isEmpty && _pendingAttachment == null) || _isLoading) return;
    if (_credits != null && _credits!.remaining <= 0 && !_credits!.isAdmin) {
      _showLimitDialog(); return;
    }
    if (_pendingAttachment != null) { await _sendAttachmentWithText(text); return; }

    final user = context.read<AuthContext>().user;
    setState(() {
      _messages.add(_Message(role: 'user', text: text));
      _inputController.clear();
      _isLoading = true;
    });
    _scrollToBottom();
    try {
      final data = await ApiService.sendChat(
        question: text, propertyType: _propertyType, llmModel: _llmModel, userId: user?.id,
        chatHistory: _messages.map((m) => {'role': m.role == 'bot' ? 'assistant' : 'user', 'content': m.text}).toList(),
      );
      setState(() => _messages.add(_Message(role: 'bot', text: data['response'] ?? '')));
      if (data['credits'] != null) setState(() => _credits = _CreditsInfo.fromJson(data['credits']));
    } on ApiException catch (e) {
      if (e.statusCode == 429) { _showLimitDialog(); }
      else { setState(() => _messages.add(_Message(role: 'bot', text: 'Error: ${e.message}'))); }
    } finally {
      setState(() => _isLoading = false);
      _scrollToBottom();
    }
  }

  Future<void> _sendAttachmentWithText(String userText) async {
    final attachment = _pendingAttachment!;
    setState(() {
      _messages.add(_Message(
        role: 'user',
        text: userText.isNotEmpty ? userText : attachment.fileName,
        isFile: true, hasAttachment: true,
        attachmentThumb: attachment.isImage ? attachment.bytes : null,
        attachmentName: attachment.fileName,
      ));
      _inputController.clear(); _pendingAttachment = null; _isLoading = true;
    });
    _scrollToBottom();
    final user = context.read<AuthContext>().user;
    try {
      final data = await ApiService.uploadImage(
        attachment.bytes, attachment.fileName, _propertyType,
        llmModel: _llmModel, userQuestion: userText, userId: user?.id,
      );
      setState(() => _messages.add(_Message(role: 'bot', text: data['analysis'] ?? '')));
      if (data['credits'] != null) setState(() => _credits = _CreditsInfo.fromJson(data['credits']));
    } catch (e) {
      if (e is ApiException && e.statusCode == 429) _showLimitDialog();
    } finally {
      setState(() => _isLoading = false);
      _scrollToBottom();
    }
  }

  // ── VOICE LOGIC (flutter_sound) ──────────────────────────────────────────
  Future<void> _startRecording() async {
    if (!_recorderReady) return;
    if (_credits != null && _credits!.remaining <= 0 && !_credits!.isAdmin) {
      _showLimitDialog(); return;
    }
    final dir  = await getTemporaryDirectory();
    final path = '${dir.path}/voice_${DateTime.now().millisecondsSinceEpoch}.aac';
    await _recorder.startRecorder(toFile: path, codec: Codec.aacADTS);
    _recordingPath = path;
    _recordingSeconds = 0;
    _recordingTimer = Timer.periodic(
      const Duration(seconds: 1),
      (_) => setState(() => _recordingSeconds++),
    );
    _pulseController.repeat(reverse: true);
    setState(() => _voiceState = _VoiceState.recording);
  }

  Future<void> _cancelRecording() async {
    _recordingTimer?.cancel();
    _pulseController.stop();
    await _recorder.stopRecorder();
    setState(() { _voiceState = _VoiceState.idle; _recordingSeconds = 0; });
  }

  Future<void> _stopAndSendRecording() async {
    _recordingTimer?.cancel();
    _pulseController.stop();
    final path = await _recorder.stopRecorder();
    if (path == null) { setState(() => _voiceState = _VoiceState.idle); return; }
    final bytes = await File(path).readAsBytes();
    final user = context.read<AuthContext>().user;
    setState(() {
      _messages.add(_Message(role: 'user', text: '🎙️ Voice message', isVoice: true));
      _isLoading = true;
      _voiceState = _VoiceState.processing;
    });
    try {
      final uri     = Uri.parse('${AppConfig.baseUrl}/api/voice-chat');
      final request = http.MultipartRequest('POST', uri);
      request.fields['property_type'] = _propertyType;
      request.fields['llm_model_req'] = _llmModel;
      if (user?.id != null) request.fields['user_id'] = user!.id.toString();
      request.files.add(http.MultipartFile.fromBytes('audio', bytes, filename: 'voice.aac'));
      final res  = await http.Response.fromStream(await request.send());
      final data = jsonDecode(res.body);
      if (res.statusCode == 429) {
        _showLimitDialog();
        setState(() => _messages.removeLast());
        return;
      }
      setState(() {
        _messages.removeLast();
        _messages.add(_Message(role: 'user', text: data['transcription'] ?? '🎙️', isVoice: true));
        _messages.add(_Message(role: 'bot', text: data['reply']));
      });
      if (data['credits'] != null) setState(() => _credits = _CreditsInfo.fromJson(data['credits']));
    } finally {
      setState(() { _isLoading = false; _voiceState = _VoiceState.idle; });
      _scrollToBottom();
    }
  }

  void _showLimitDialog() {
    final isFree = _userPlan == 'free';
    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        title: Row(children: [
          Icon(Icons.bolt, color: Colors.amber),
          const SizedBox(width: 10),
          const Text('Limit Reached'),
        ]),
        content: Text(isFree
            ? "You used your 10 free daily requests. Upgrade to Premium for 20 requests/day!"
            : "Premium limit reached. Quota resets tomorrow."),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Later')),
          if (isFree) ElevatedButton(
            onPressed: () async {
              Navigator.pop(context);
              await context.push('/plan-selection');
              _loadCredits();
            },
            style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFFD4A017)),
            child: const Text('UPGRADE', style: TextStyle(color: Colors.white)),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Stack(
        children: [
          Positioned.fill(child: Opacity(
            opacity: 0.15,
            child: Image.asset('assets/images/robot_assistant.png', fit: BoxFit.contain),
          )),
          Column(children: [
            _buildHeader(),
            _buildCreditsBar(),
            _buildMessageList(),
            _buildInputBar(),
            AppBottomNavBar(active: NavTab.chat),
          ]),
        ],
      ),
    );
  }

  Widget _buildHeader() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      decoration: const BoxDecoration(border: Border(bottom: BorderSide(color: AppColors.borderColor))),
      child: Row(children: [
        const Icon(Icons.smart_toy, color: Color(0xFF1E3A5F)),
        const SizedBox(width: 8),
        const Text('PropIQ Assistant', style: TextStyle(fontWeight: FontWeight.bold)),
        const Spacer(),
        DropdownButton<String>(
          value: _propertyType, underline: const SizedBox(), isDense: true,
          items: _propertyTypes.map((t) => DropdownMenuItem(
            value: t['value'], child: Text(t['label']!, style: const TextStyle(fontSize: 12)),
          )).toList(),
          onChanged: (v) => setState(() => _propertyType = v!),
        ),
        const SizedBox(width: 8),
        DropdownButton<String>(
          value: _llmModel, underline: const SizedBox(), isDense: true,
          items: _models.map((m) => DropdownMenuItem(
            value: m['id'], child: Text(m['label']!, style: const TextStyle(fontSize: 11, color: Color(0xFF3730A3))),
          )).toList(),
          onChanged: (v) => setState(() => _llmModel = v!),
        ),
      ]),
    );
  }

  Widget _buildCreditsBar() {
    if (_creditsLoading) return const LinearProgressIndicator(minHeight: 2, color: AppColors.primary);
    if (_credits == null) return const SizedBox.shrink();
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      color: _credits!.remaining == 0 ? Colors.red.withOpacity(0.05) : Colors.grey[50],
      child: Row(children: [
        Icon(Icons.bolt, size: 12, color: _credits!.barColor),
        const SizedBox(width: 8),
        Text('${_credits!.remaining} left', style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: _credits!.barColor)),
        const SizedBox(width: 10),
        Expanded(child: ClipRRect(
          borderRadius: BorderRadius.circular(10),
          child: LinearProgressIndicator(value: _credits!.ratio, minHeight: 4, color: _credits!.barColor, backgroundColor: Colors.grey[200]),
        )),
      ]),
    );
  }

  Future<void> _toggleSpeak(String messageId, String text) async {
    if (_speakingMessageId == messageId) {
      await _tts.stop();
      setState(() => _speakingMessageId = null);
    } else {
      if (_speakingMessageId != null) await _tts.stop();
      final cleanText = text
          .replaceAll(RegExp(r'\*+'), '')                        // **gras** → gras
          .replaceAll(RegExp(r'#+\s?'), '')                      // ## Titre → Titre
          .replaceAll(RegExp(r'[-–—]{2,}'), '')                  // --- → rien
          .replaceAll(RegExp(r'^[-*•]\s', multiLine: true), '')  // listes → sans tiret
          .replaceAll(RegExp(r'\[([^\]]+)\]\([^)]+\)'), r'$1')  // liens → texte seul
          .replaceAll(RegExp(r'`+'), '')                         // `code` → code
          .replaceAll(RegExp(r'_{1,2}'), '')                     // _italique_ → italique
          .replaceAll(RegExp(r'\n{2,}'), '. ')                   // double saut → pause
          .replaceAll('\n', ' ')                                  // saut simple → espace
          .replaceAll(RegExp(r'\s{2,}'), ' ')                    // espaces multiples → un seul
          .trim();
      setState(() => _speakingMessageId = messageId);
      await _tts.speak(cleanText);
    }
  }

  Widget _buildMessageList() {
    return Expanded(child: ListView.builder(
      controller: _scrollController,
      padding: const EdgeInsets.all(16),
      itemCount: _messages.length + (_isLoading ? 1 : 0),
      itemBuilder: (context, i) {
        if (_isLoading && i == _messages.length) return const _BotBubble(text: '...', messageId: '__loading__');
        final msg = _messages[i];
        if (msg.role == 'user') return _UserBubble(msg: msg);
        return _BotBubble(
          text: msg.text,
          messageId: msg.id,
          isSpeaking: _speakingMessageId == msg.id,
          onSpeak: () => _toggleSpeak(msg.id, msg.text),
        );
      },
    ));
  }

  Widget _buildInputBar() {
    final limit = _credits != null && _credits!.remaining <= 0 && !_credits!.isAdmin;
    final isRecording = _voiceState == _VoiceState.recording;
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: const BoxDecoration(border: Border(top: BorderSide(color: AppColors.borderColor))),
      child: Column(children: [
        if (limit) GestureDetector(
          onTap: _showLimitDialog,
          child: Container(
            padding: const EdgeInsets.all(8),
            margin: const EdgeInsets.only(bottom: 8),
            decoration: BoxDecoration(color: Colors.red[50], borderRadius: BorderRadius.circular(10)),
            child: const Text('Limit reached - Upgrade to Premium',
                style: TextStyle(color: Colors.red, fontWeight: FontWeight.bold, fontSize: 12)),
          ),
        ),
        if (isRecording) _RecordingBanner(
          seconds: _recordingSeconds,
          onCancel: _cancelRecording,
          onStop: _stopAndSendRecording,
          pulse: _pulseAnimation,
        ),
        if (!isRecording) _buildComposer(limit),
      ]),
    );
  }

  Widget _buildComposer(bool limit) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // ── Pending attachment preview ─────────────────────
        if (_pendingAttachment != null) ...[
          if (_pendingAttachment!.isImage)
            Stack(children: [
              Container(
                margin: const EdgeInsets.only(bottom: 8),
                decoration: BoxDecoration(borderRadius: BorderRadius.circular(12)),
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(12),
                  child: Image.memory(_pendingAttachment!.bytes, height: 120, width: 120, fit: BoxFit.cover),
                ),
              ),
              Positioned(top: 0, right: 0, child: GestureDetector(
                onTap: () => setState(() => _pendingAttachment = null),
                child: Container(
                  decoration: const BoxDecoration(color: Colors.red, shape: BoxShape.circle),
                  child: const Icon(Icons.close, size: 16, color: Colors.white),
                ),
              )),
            ])
          else if (_pendingAttachment!.isPdf)
            Container(
              margin: const EdgeInsets.only(bottom: 8),
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
              decoration: BoxDecoration(
                color: const Color(0xFFFFF5F5),
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: const Color(0xFFE53E3E).withOpacity(0.4)),
              ),
              child: Row(mainAxisSize: MainAxisSize.min, children: [
                const Icon(Icons.picture_as_pdf, color: Color(0xFFE53E3E), size: 18),
                const SizedBox(width: 8),
                Flexible(child: Text(
                  _pendingAttachment!.fileName,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w500, color: Color(0xFFE53E3E)),
                )),
                const SizedBox(width: 8),
                GestureDetector(
                  onTap: () => setState(() => _pendingAttachment = null),
                  child: const Icon(Icons.close, size: 16, color: Color(0xFFE53E3E)),
                ),
              ]),
            ),
          const SizedBox(height: 4),
        ],
        // ── Input row ──────────────────────────────────────
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 8),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(20),
            border: Border.all(color: AppColors.borderColor),
          ),
          child: Row(children: [
            IconButton(icon: const Icon(Icons.attach_file, size: 20), onPressed: limit ? null : _showAttachmentSheet),
            Expanded(child: TextField(
              controller: _inputController,
              enabled: !limit && !_isLoading,
              decoration: InputDecoration(
                hintText: _pendingAttachment?.isPdf == true
                    ? 'Ask a question about this document...'
                    : 'Ask anything...',
                border: InputBorder.none,
              ),
            )),
            if (_inputController.text.isNotEmpty || _pendingAttachment != null)
              IconButton(icon: const Icon(Icons.send, color: AppColors.primary), onPressed: _handleSend)
            else
              IconButton(icon: const Icon(Icons.mic, color: Color(0xFF1E3A5F)), onPressed: limit ? null : _startRecording),
          ]),
        ),
      ],
    );
  }

  void _showAttachmentSheet() {
    showModalBottomSheet(context: context, builder: (_) => Column(mainAxisSize: MainAxisSize.min, children: [
      ListTile(leading: const Icon(Icons.camera_alt), title: const Text('Camera'), onTap: () { Navigator.pop(context); _pickFromCamera(); }),
      ListTile(leading: const Icon(Icons.image),      title: const Text('Gallery'), onTap: () { Navigator.pop(context); _pickFromGallery(); }),
      ListTile(
        leading: const Icon(Icons.picture_as_pdf, color: Color(0xFFE53E3E)),
        title: const Text('PDF Document'),
        subtitle: const Text('Upload a contract, deed, permit...', style: TextStyle(fontSize: 11)),
        onTap: () { Navigator.pop(context); _pickPdf(); },
      ),
    ]));
  }

  Future<void> _pickFromCamera() async {
    final p = await ImagePicker().pickImage(source: ImageSource.camera);
    if (p != null) _setPendingAttachment(await p.readAsBytes(), p.name, isImage: true);
  }

  Future<void> _pickFromGallery() async {
    final p = await ImagePicker().pickImage(source: ImageSource.gallery);
    if (p != null) _setPendingAttachment(await p.readAsBytes(), p.name, isImage: true);
  }

  Future<void> _pickPdf() async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: ['pdf'],
      withData: true,
    );
    if (result != null && result.files.single.bytes != null) {
      final file = result.files.single;
      _setPendingAttachment(file.bytes!, file.name, isImage: false, isPdf: true);
    }
  }

  void _setPendingAttachment(Uint8List b, String n, {required bool isImage, bool isPdf = false}) {
    setState(() => _pendingAttachment = _PendingAttachment(bytes: b, fileName: n, isImage: isImage, isPdf: isPdf));
  }
}

// ── Widgets ──────────────────────────────────────────────────────────────────

class _UserBubble extends StatelessWidget {
  final _Message msg;
  const _UserBubble({required this.msg});
  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.centerRight,
      child: Container(
        margin: const EdgeInsets.only(bottom: 10, left: 50),
        padding: const EdgeInsets.all(8),
        decoration: const BoxDecoration(
          color: AppColors.primary,
          borderRadius: BorderRadius.all(Radius.circular(15)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.end,
          mainAxisSize: MainAxisSize.min,
          children: [
            if (msg.attachmentThumb != null)
              ClipRRect(
                borderRadius: BorderRadius.circular(10),
                child: Image.memory(msg.attachmentThumb!, width: 200, height: 200, fit: BoxFit.cover),
              ),
            // PDF chip (no thumbnail)
            if (msg.isFile && msg.attachmentThumb == null && msg.attachmentName != null)
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 5),
                margin: const EdgeInsets.only(bottom: 4),
                decoration: BoxDecoration(
                  color: Colors.white.withOpacity(0.15),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: Colors.white.withOpacity(0.4)),
                ),
                child: Row(mainAxisSize: MainAxisSize.min, children: [
                  const Icon(Icons.picture_as_pdf, color: Colors.white, size: 16),
                  const SizedBox(width: 6),
                  Flexible(child: Text(
                    msg.attachmentName!,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(color: Colors.white, fontSize: 12),
                  )),
                ]),
              ),
            if (msg.text.isNotEmpty && msg.text != msg.attachmentName)
              Padding(
                padding: EdgeInsets.only(top: msg.attachmentThumb != null ? 6 : 0, left: 4, right: 4, bottom: 4),
                child: Text(msg.text, style: const TextStyle(color: Colors.white)),
              ),
          ],
        ),
      ),
    );
  }
}

class _BotBubble extends StatelessWidget {
  final String text;
  final String messageId;
  final bool isSpeaking;
  final VoidCallback? onSpeak;
  const _BotBubble({
    required this.text,
    required this.messageId,
    this.isSpeaking = false,
    this.onSpeak,
  });
  @override
  Widget build(BuildContext context) {
    final isLoading = messageId == '__loading__';
    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.only(bottom: 10, right: 50),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(color: Colors.grey[200], borderRadius: BorderRadius.circular(15)),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            SelectionArea(child: MarkdownBody(data: text)),
            if (!isLoading) ...[
              const SizedBox(height: 6),
              Align(
                alignment: Alignment.centerRight,
                child: GestureDetector(
                  onTap: onSpeak,
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      color: isSpeaking ? const Color(0xFF1E3A5F) : Colors.white,
                      borderRadius: BorderRadius.circular(20),
                      border: Border.all(color: const Color(0xFF1E3A5F)),
                    ),
                    child: Row(mainAxisSize: MainAxisSize.min, children: [
                      Icon(
                        isSpeaking ? Icons.stop : Icons.volume_up,
                        size: 14,
                        color: isSpeaking ? Colors.white : const Color(0xFF1E3A5F),
                      ),
                      const SizedBox(width: 4),
                      Text(
                        isSpeaking ? 'Stop' : 'Listen',
                        style: TextStyle(
                          fontSize: 11,
                          color: isSpeaking ? Colors.white : const Color(0xFF1E3A5F),
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ]),
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _RecordingBanner extends StatelessWidget {
  final int seconds;
  final VoidCallback onCancel, onStop;
  final Animation<double> pulse;
  const _RecordingBanner({required this.seconds, required this.onCancel, required this.onStop, required this.pulse});
  @override
  Widget build(BuildContext context) {
    return Row(children: [
      ScaleTransition(scale: pulse, child: const Icon(Icons.circle, color: Colors.red, size: 12)),
      const SizedBox(width: 8),
      Text('Recording... $seconds s'),
      const Spacer(),
      TextButton(onPressed: onCancel, child: const Text('Cancel')),
      ElevatedButton(onPressed: onStop, child: const Text('Send')),
    ]);
  }
}

class _AttachmentChip extends StatelessWidget {
  final _PendingAttachment attachment;
  final VoidCallback onRemove;
  const _AttachmentChip({required this.attachment, required this.onRemove});
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(color: Colors.grey[200], borderRadius: BorderRadius.circular(10)),
      child: Row(children: [
        const Icon(Icons.file_present, size: 16),
        const SizedBox(width: 8),
        Expanded(child: Text(attachment.fileName, maxLines: 1)),
        IconButton(icon: const Icon(Icons.close, size: 16), onPressed: onRemove),
      ]),
    );
  }
}
