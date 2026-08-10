import 'package:flutter/material.dart';
import 'package:webview_flutter/webview_flutter.dart';
import 'package:go_router/go_router.dart';

class PaymentWebViewPage extends StatefulWidget {
  final String url;
  const PaymentWebViewPage({super.key, required this.url});

  @override
  State<PaymentWebViewPage> createState() => _PaymentWebViewPageState();
}

class _PaymentWebViewPageState extends State<PaymentWebViewPage> {
  late final WebViewController _controller;
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _controller = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..setNavigationDelegate(
        NavigationDelegate(
          onPageStarted: (url) {
            setState(() => _isLoading = true);
            // On détecte l'URL de succès pour rediriger l'utilisateur
            if (url.contains('payment-success')) {
              _handleSuccess();
            } else if (url.contains('payment-fail')) {
              _handleFail();
            }
          },
          onPageFinished: (_) => setState(() => _isLoading = false),
        ),
      )
      ..loadRequest(Uri.parse(widget.url));
  }

  void _handleSuccess() {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text("Paiement validé ! Bienvenue Premium 🚀"),
        backgroundColor: Color(0xFF2A7FC4),
      ),
    );
    context.go('/');
  }

  void _handleFail() {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text("Le paiement a échoué ou a été annulé.")),
    );
    context.pop();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text("Paiement Sécurisé"),
        leading: IconButton(
          icon: const Icon(Icons.close),
          onPressed: () => context.pop(),
        ),
      ),
      body: Stack(
        children: [
          WebViewWidget(controller: _controller),
          if (_isLoading)
            const Center(child: CircularProgressIndicator(color: Color(0xFF2A7FC4))),
        ],
      ),
    );
  }
}
