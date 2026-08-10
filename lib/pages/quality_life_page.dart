// lib/pages/quality_life_page.dart
import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';


import '../services/api_service.dart';
import '../theme/app_theme.dart';
import '../widgets/bottom_nav_bar.dart';
import 'package:proptech_ai/config.dart';

class QualityLifePage extends StatefulWidget {
  const QualityLifePage({super.key});

  @override
  State<QualityLifePage> createState() => _QualityLifePageState();
}

class _QualityLifePageState extends State<QualityLifePage> {
  final _addressController = TextEditingController();
  Map<String, dynamic>? _results;
  bool _isLoading = false;

  // ── category config ──────────────────────────────────────────────────────
  static const _categoryConfig = {
    'schools':   {'emoji': '🎓', 'color': Color(0xFF3B82F6), 'label': 'Éducation'},
    'hospitals': {'emoji': '🏥', 'color': Color(0xFFEF4444), 'label': 'Santé'},
    'commerce':  {'emoji': '🛒', 'color': Color(0xFFF59E0B), 'label': 'Commerce'},
    'parks':     {'emoji': '🌳', 'color': Color(0xFF22C55E), 'label': 'Espaces verts'},
    'transport': {'emoji': '🚌', 'color': Color(0xFF8B5CF6), 'label': 'Transport'},
  };

  static const _scoreCards = [
    {'key': 'schools',   'label': 'Éducation',       'emoji': '🎓', 'color': 0xFF3B82F6},
    {'key': 'hospitals', 'label': 'Santé',            'emoji': '🏥', 'color': 0xFFEF4444},
    {'key': 'commerce',  'label': 'Commerce',         'emoji': '🛒', 'color': 0xFFF59E0B},
    {'key': 'parks',     'label': 'Espaces verts',    'emoji': '🌳', 'color': 0xFF22C55E},
    {'key': 'transport', 'label': 'Transport',        'emoji': '🚌', 'color': 0xFF8B5CF6},
    {'key': 'air',       'label': "Qualité de l'air", 'emoji': '💨', 'color': 0xFF06B6D4},
  ];

  // ── analyze ──────────────────────────────────────────────────────────────
  Future<void> _handleAnalyze() async {
    if (_addressController.text.trim().isEmpty) return;
    setState(() { _isLoading = true; _results = null; });
    try {
      final data = await ApiService.analyzeQualityLife(_addressController.text.trim());
      setState(() => _results = data);
    } catch (e) {
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(e.toString())));
    } finally {
      setState(() => _isLoading = false);
    }
  }

  // ── build ─────────────────────────────────────────────────────────────────
  @override
  Widget build(BuildContext context) {
    return Stack(
      children: [
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
        SingleChildScrollView(
          child: Column(
            children: [
              // ── Hero Header ──────────────────────────────────────────────
              Container(
                width: double.infinity,
                padding: const EdgeInsets.fromLTRB(24, 32, 24, 90),
                decoration: const BoxDecoration(
                  color: Color(0xFFFFFFFF),
                  border: Border(
                    bottom: BorderSide(color: Color(0xFFE8E4DF), width: 0.5),
                  ),
                ),
                child: Column(
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
                      decoration: BoxDecoration(
                        borderRadius: BorderRadius.circular(50),
                        border: Border.all(color: const Color(0xFFB0C4DE)),
                        color: const Color(0xFFE8EEF7),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: const [
                          Icon(Icons.location_on, color: Color(0xFF1E3A5F), size: 14),
                          SizedBox(width: 6),
                          Text('Location Intelligence',
                              style: TextStyle(
                                color: Color(0xFF1E3A5F),
                                fontSize: 12,
                                fontWeight: FontWeight.w500,
                              )),
                        ],
                      ),
                    ),
                    const SizedBox(height: 20),
                    RichText(
                      textAlign: TextAlign.center,
                      text: const TextSpan(
                        style: TextStyle(
                          fontSize: 28,
                          fontWeight: FontWeight.w700,
                          color: Color(0xFF1A1A2E),
                          height: 1.25,
                        ),
                        children: [
                          TextSpan(text: 'Quality of Life Around\n'),
                          TextSpan(
                            text: 'Your Property',
                            style: TextStyle(
                              color: Color(0xFF1E3A5F),
                              fontStyle: FontStyle.italic,
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 12),
                    const Text(
                      'Evaluate the neighborhood around a property based on education, '
                      'healthcare, commerce, green spaces, transport, and air quality.',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        color: Color(0xFF6B6B7E),
                        fontSize: 13,
                        height: 1.65,
                      ),
                    ),
                  ],
                ),
              ),

              // ── Search Card (floating) ───────────────────────────────────
              Transform.translate(
                offset: const Offset(0, -44),
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 18),
                  child: Container(
                    padding: const EdgeInsets.all(20),
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(20),
                      border: Border.all(color: const Color(0xFFE8E4DF), width: 0.5),
                      boxShadow: [
                        BoxShadow(
                          color: Colors.black.withOpacity(0.06),
                          blurRadius: 24,
                          offset: const Offset(0, 8),
                        ),
                      ],
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Container(
                              width: 32, height: 32,
                              decoration: BoxDecoration(
                                color: const Color(0xFFE8EEF7),
                                borderRadius: BorderRadius.circular(8),
                              ),
                              child: const Icon(Icons.location_on,
                                  color: Color(0xFF1E3A5F), size: 16),
                            ),
                            const SizedBox(width: 10),
                            const Text('Analyze Your Property Location',
                                style: TextStyle(
                                  fontSize: 15,
                                  fontWeight: FontWeight.w600,
                                  color: Color(0xFF1A1A2E),
                                )),
                          ],
                        ),
                        const SizedBox(height: 14),
                        Container(
                          decoration: BoxDecoration(
                            color: const Color(0xFFF7F5F2),
                            borderRadius: BorderRadius.circular(50),
                            border: Border.all(
                                color: const Color(0xFFD4D0C8), width: 0.5),
                          ),
                          padding: const EdgeInsets.symmetric(
                              horizontal: 4, vertical: 4),
                          child: Row(
                            children: [
                              Expanded(
                                child: TextField(
                                  controller: _addressController,
                                  onSubmitted: (_) => _handleAnalyze(),
                                  style: const TextStyle(
                                      fontSize: 13, color: Color(0xFF1A1A2E)),
                                  decoration: const InputDecoration(
                                    hintText: 'e.g. Avenida Luísa Todi 45, Setúbal',
                                    hintStyle: TextStyle(
                                        color: Color(0xFFAAAABC), fontSize: 13),
                                    prefixIcon: Icon(Icons.location_on,
                                        color: Color(0xFFAAAABC), size: 16),
                                    border: InputBorder.none,
                                    enabledBorder: InputBorder.none,
                                    focusedBorder: InputBorder.none,
                                    fillColor: Colors.transparent,
                                    filled: false,
                                    contentPadding:
                                        EdgeInsets.symmetric(vertical: 12),
                                  ),
                                ),
                              ),
                              ElevatedButton.icon(
                                onPressed: _isLoading ? null : _handleAnalyze,
                                icon: _isLoading
                                    ? const SizedBox(
                                        width: 14,
                                        height: 14,
                                        child: CircularProgressIndicator(
                                            strokeWidth: 2,
                                            color: Colors.white))
                                    : const Icon(Icons.search, size: 14),
                                label: Text(
                                    _isLoading ? 'Analyzing...' : 'Analyze Area',
                                    style: const TextStyle(
                                      fontSize: 13,
                                      fontWeight: FontWeight.w600,
                                    )),
                                style: ElevatedButton.styleFrom(
                                  backgroundColor: const Color(0xFF1E3A5F),
                                  foregroundColor: Colors.white,
                                  elevation: 0,
                                  padding: const EdgeInsets.symmetric(
                                      horizontal: 18, vertical: 12),
                                  shape: RoundedRectangleBorder(
                                      borderRadius: BorderRadius.circular(50)),
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),

              // ── Results / Empty State ────────────────────────────────────
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 18),
                child: _results == null
                    ? _buildEmptyState()
                    : _buildResults(_results!),
              ),
              const SizedBox(height: 20),
              AppBottomNavBar(active: NavTab.map),
              const SizedBox(height: 20),
            ],
          ),
        ),
      ],
    );
  }

  // ── Empty state ──────────────────────────────────────────────────────────
  Widget _buildEmptyState() {
    return Column(
      children: [
        const SizedBox(height: 32),
        Container(
          width: 88, height: 88,
          decoration: BoxDecoration(
            color: const Color(0xFFE8EEF7),
            borderRadius: BorderRadius.circular(24),
          ),
          child: const Icon(Icons.map, size: 40, color: Color(0xFF1E3A5F)),
        ),
        const SizedBox(height: 20),
        const Text('Enter an Address to Begin',
            style: TextStyle(
              fontSize: 20,
              fontWeight: FontWeight.w700,
              color: Color(0xFF1A1A2E),
            )),
        const SizedBox(height: 8),
        const Text(
          'Your quality of life assessment\nwill appear here.',
          textAlign: TextAlign.center,
          style:
              TextStyle(color: Color(0xFF6B6B7E), fontSize: 13, height: 1.6),
        ),
        const SizedBox(height: 48),
      ],
    );
  }

  // ── Results ──────────────────────────────────────────────────────────────
  Widget _buildResults(Map<String, dynamic> results) {
    final breakdown = results['breakdown'] as Map<String, dynamic>?;
    final lat    = (results['lat'] as num?)?.toDouble();
    final lon    = (results['lon'] as num?)?.toDouble();
    final radius = (results['radius_m'] as num?)?.toDouble() ?? 3000;

    return Column(
      children: [
        // ── Summary card ─────────────────────────────────────────────────
        Container(
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(20),
            border: Border.all(color: const Color(0xFFE8E4DF), width: 0.5),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withOpacity(0.04),
                blurRadius: 16,
                offset: const Offset(0, 6),
              )
            ],
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('Analysis Result',
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w700,
                    color: Color(0xFF1A1A2E),
                  )),
              const SizedBox(height: 4),
              Text(results['address'] ?? '',
                  style: const TextStyle(
                      color: Color(0xFF6B6B7E), fontSize: 13)),
              const SizedBox(height: 20),
              Row(
                children: [
                  RichText(
                    text: TextSpan(
                      children: [
                        TextSpan(
                          text: '${results['total'] ?? 0}',
                          style: const TextStyle(
                            fontSize: 52,
                            fontWeight: FontWeight.w800,
                            color: Color(0xFF1E3A5F),
                          ),
                        ),
                        const TextSpan(
                          text: ' / 100',
                          style: TextStyle(
                              fontSize: 18, color: Color(0xFFAAAABC)),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: 32),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text('Recommendation',
                            style: TextStyle(
                              fontWeight: FontWeight.w600,
                              fontSize: 12,
                              color: Color(0xFFAAAABC),
                              letterSpacing: 0.5,
                            )),
                        const SizedBox(height: 8),
                        Text(results['verdict_text'] ?? '',
                            style: TextStyle(
                              color: _parseColor(results['verdict_color']),
                              fontWeight: FontWeight.w600,
                              height: 1.5,
                            )),
                      ],
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
        const SizedBox(height: 24),

        // ── Map ──────────────────────────────────────────────────────────
        if (lat != null && lon != null)
          ClipRRect(
            borderRadius: BorderRadius.circular(16),
            child: SizedBox(
              height: 350,
              child: FlutterMap(
                options: MapOptions(
                  initialCenter: LatLng(lat, lon),
                  initialZoom: 15,
                ),
                children: [
                  TileLayer(
                    urlTemplate:
                        'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                    tileProvider: NetworkTileProvider(),
                    userAgentPackageName: 'com.propiq.app',
                  ),
                  CircleLayer(circles: [
                    CircleMarker(
                      point: LatLng(lat, lon),
                      radius: radius,
                      color: AppColors.primary.withOpacity(0.08),
                      borderColor: AppColors.primary,
                      borderStrokeWidth: 2,
                      useRadiusInMeter: true,
                    ),
                  ]),
                  MarkerLayer(markers: [
                    Marker(
                      point: LatLng(lat, lon),
                      child: const _HomeMarker(),
                    ),
                    if (breakdown != null) ..._buildPoiMarkers(breakdown),
                  ]),
                ],
              ),
            ),
          ),
        const SizedBox(height: 24),

        // ── Score cards grid (NEW design) ────────────────────────────────
        GridView.count(
          crossAxisCount: MediaQuery.of(context).size.width > 600 ? 3 : 2,
          crossAxisSpacing: 12,
          mainAxisSpacing: 12,
          childAspectRatio: 1.05,
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          children: _scoreCards.map((card) {
            final key   = card['key']! as String;
            final color = Color(card['color']! as int);
            final bd    = breakdown?[key] as Map<String, dynamic>?;
            final score = (bd?['score'] as num?)?.toInt() ?? 0;

            return _ScoreCard(
              emoji:    card['emoji']! as String,
              label:    card['label']! as String,
              score:    score,
              color:    color,
              subtitle: key == 'air'
                  ? (bd?['aqi_value'] != null
                      ? '${bd!['parameter']?.toString().toUpperCase()}: '
                        '${bd['aqi_value']} ${bd['unit']}'
                      : 'No data')
                  : '${bd?['count'] ?? 0} places found',
            );
          }).toList(),
        ),
      ],
    );
  }

  // ── Helpers ──────────────────────────────────────────────────────────────
  List<Marker> _buildPoiMarkers(Map<String, dynamic> breakdown) {
    final markers = <Marker>[];
    for (final entry in _categoryConfig.entries) {
      final items = (breakdown[entry.key]?['items'] as List?) ?? [];
      for (final poi in items) {
        final pLat = (poi['lat'] as num?)?.toDouble();
        final pLon = (poi['lon'] as num?)?.toDouble();
        if (pLat == null || pLon == null) continue;
        markers.add(Marker(
          point: LatLng(pLat, pLon),
          child: _PoiMarker(
            emoji: entry.value['emoji'] as String,
            color: entry.value['color'] as Color,
          ),
        ));
      }
    }
    return markers;
  }

  Color _parseColor(dynamic raw) {
    if (raw == null) return AppColors.textMuted;
    try {
      final hex = raw.toString().replaceAll('#', '');
      return Color(int.parse('FF$hex', radix: 16));
    } catch (_) {
      return AppColors.textMuted;
    }
  }
}

// ============================================================
// SCORE CARD — new design
// ============================================================

class _ScoreCard extends StatelessWidget {
  final String emoji;
  final String label;
  final int    score;
  final Color  color;
  final String subtitle;

  const _ScoreCard({
    required this.emoji,
    required this.label,
    required this.score,
    required this.color,
    required this.subtitle,
  });

  Color get _scoreColor {
    if (score >= 75) return const Color(0xFF22C55E);
    if (score >= 50) return const Color(0xFFF59E0B);
    if (score >= 25) return const Color(0xFFFB6340);
    return const Color(0xFFEF4444);
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(14, 14, 14, 12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: const Color(0xFFEEEAE4), width: 1),
        boxShadow: [
          BoxShadow(
            color: color.withOpacity(0.07),
            blurRadius: 12,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // ── Icon pill + score badge ──────────────────────────────
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Container(
                width: 36, height: 36,
                decoration: BoxDecoration(
                  color: color.withOpacity(0.12),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Center(
                  child: Text(emoji,
                      style: const TextStyle(fontSize: 18)),
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(
                    horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: _scoreColor.withOpacity(0.12),
                  borderRadius: BorderRadius.circular(50),
                ),
                child: Text(
                  '$score',
                  style: TextStyle(
                    color: _scoreColor,
                    fontSize: 12,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),

          // ── Label ───────────────────────────────────────────────
          Text(label,
              style: const TextStyle(
                fontWeight: FontWeight.w600,
                color: Color(0xFF1A1A2E),
                fontSize: 12,
              )),
          const SizedBox(height: 6),

          // ── Progress bar ─────────────────────────────────────────
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: score / 100,
              minHeight: 5,
              backgroundColor: const Color(0xFFF0EDE8),
              valueColor: AlwaysStoppedAnimation<Color>(_scoreColor),
            ),
          ),
          const SizedBox(height: 6),

          // ── Subtitle ────────────────────────────────────────────
          Text(
            subtitle,
            style: const TextStyle(
              color: Color(0xFFAAAABC),
              fontSize: 10,
            ),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
        ],
      ),
    );
  }
}

// ============================================================
// MAP MARKERS
// ============================================================

class _HomeMarker extends StatelessWidget {
  const _HomeMarker();
  @override
  Widget build(BuildContext context) {
    return Container(
      width: 36, height: 36,
      decoration: BoxDecoration(
        color: AppColors.primary,
        shape: BoxShape.circle,
        border: Border.all(color: Colors.white, width: 3),
        boxShadow: [
          BoxShadow(
            color: AppColors.primary.withOpacity(0.4),
            blurRadius: 10,
            offset: const Offset(0, 4),
          )
        ],
      ),
      child: const Center(
          child: Text('🏠', style: TextStyle(fontSize: 16))),
    );
  }
}

class _PoiMarker extends StatelessWidget {
  final String emoji;
  final Color  color;
  const _PoiMarker({required this.emoji, required this.color});
  @override
  Widget build(BuildContext context) {
    return Container(
      width: 30, height: 30,
      decoration: BoxDecoration(
        color: Colors.white,
        shape: BoxShape.circle,
        border: Border.all(color: color, width: 2),
        boxShadow: const [
          BoxShadow(
              color: Colors.black26,
              blurRadius: 6,
              offset: Offset(0, 2))
        ],
      ),
      child: Center(
          child: Text(emoji, style: const TextStyle(fontSize: 13))),
    );
  }
}
