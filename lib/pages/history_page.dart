// lib/pages/history_page.dart
import 'package:flutter/material.dart';

import 'package:provider/provider.dart';
import 'package:go_router/go_router.dart';

import '../context/auth_context.dart';
import '../services/api_service.dart';
import '../theme/app_theme.dart';
import '../widgets/bottom_nav_bar.dart';

class HistoryPage extends StatefulWidget {
  const HistoryPage({super.key});
  @override
  State<HistoryPage> createState() => _HistoryPageState();
}

class _HistoryPageState extends State<HistoryPage> {
  List<dynamic> _items = [];
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadHistory();
  }

  Future<void> _loadHistory() async {
    final user = context.read<AuthContext>().user;
    if (user == null) return;
    try {
      final data = await ApiService.getHistory(user.id);
      setState(() { _items = data; _isLoading = false; });
    } catch (_) { setState(() => _isLoading = false); }
  }

  void _showHistoryDetail(BuildContext context, Map item) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => DraggableScrollableSheet(
        initialChildSize: 0.75,
        maxChildSize: 0.95,
        minChildSize: 0.4,
        builder: (_, controller) => Container(
          decoration: const BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
          ),
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // ── Handle ──
              Center(
                child: Container(
                  width: 40, height: 4,
                  margin: const EdgeInsets.only(bottom: 16),
                  decoration: BoxDecoration(
                    color: Colors.grey[300],
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              ),
              // ── Header ──
              Row(
                children: [
                  const Icon(Icons.description, size: 20),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      item['property_label'] ?? 'Consultation',
                      style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 4),
              Text(
                item['timestamp']?.split('T')[0] ?? '',
                style: TextStyle(fontSize: 12, color: Colors.grey[500]),
              ),
              const Divider(height: 24),
              // ── Contenu ──
              Expanded(
                child: ListView(
                  controller: controller,
                  children: [
                    Text(
                      item['content'] ?? 'No content available.',
                      style: const TextStyle(fontSize: 14, height: 1.6),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      bottomNavigationBar: const AppBottomNavBar(active: NavTab.history),
      body: SafeArea(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.all(20),
              child: Row(
                children: [
                  const Text('History', style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold)),
                  const Spacer(),
                  IconButton(icon: const Icon(Icons.refresh, size: 18), onPressed: _loadHistory),
                ],
              ),
            ),

            // ── BANDEAU QUOTA ──
            _QuotaInfoBanner(),

            Expanded(
              child: _isLoading
                  ? const Center(child: CircularProgressIndicator())
                  : _items.isEmpty
                  ? const Center(child: Text('No history found.'))
                  : ListView.builder(
                itemCount: _items.length,
                itemBuilder: (context, i) {
                  final item = _items[i];
                  return ListTile(
                    leading: const Icon(Icons.description),
                    title: Text(item['property_label'] ?? 'Consultation'),
                    subtitle: Text(item['timestamp']?.split('T')[0] ?? ''),
                    trailing: const Icon(Icons.chevron_right, size: 16, color: Colors.grey),
                    onTap: () => _showHistoryDetail(context, item),
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _QuotaInfoBanner extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return FutureBuilder<Map<String, dynamic>>(
      future: ApiService.getSubscriptionStatus(),
      builder: (context, snapshot) {
        if (!snapshot.hasData) return const SizedBox.shrink();
        final limits = snapshot.data!['limits'] as Map;
        final usage = snapshot.data!['usage'] as Map;
        final left = (limits['requests_per_day'] ?? 10) - (usage['requests'] ?? 0);

        return Container(
          margin: const EdgeInsets.symmetric(horizontal: 20),
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(color: Colors.blue[50], borderRadius: BorderRadius.circular(12), border: Border.all(color: Colors.blue[100]!)),
          child: Row(
            children: [
              const Icon(Icons.info, size: 16, color: Colors.blue),
              const SizedBox(width: 10),
              Text("You have $left requests left for today.", style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: Colors.blue)),
              const Spacer(),
              if (snapshot.data!['plan'] == 'free') GestureDetector(onTap: () => context.push('/plan-selection'), child: const Text('Upgrade', style: TextStyle(color: Colors.blue, fontWeight: FontWeight.bold, decoration: TextDecoration.underline, fontSize: 12))),
            ],
          ),
        );
      },
    );
  }
}
