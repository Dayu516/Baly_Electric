import 'package:flutter/material.dart';

import '../../../infrastructure/api/api_client.dart';

class AlternativesTab extends StatefulWidget {
  final ApiClient api;
  final Map<String, dynamic> data;
  const AlternativesTab({super.key, required this.api, required this.data});

  @override
  State<AlternativesTab> createState() => _AlternativesTabState();
}

class _AlternativesTabState extends State<AlternativesTab> {
  Map<String, dynamic>? _result;
  bool _loading = false;
  String? _error;

  String get _productId => widget.data['product_id']?.toString() ?? '';
  String get _skuId => widget.data['sku_id']?.toString() ?? '';

  @override
  void initState() {
    super.initState();
    _search();
  }

  Future<void> _search() async {
    setState(() { _loading = true; _error = null; });
    try {
      final res = await widget.api.get('/products/$_productId/alternatives', queryParameters: {'sku_id': _skuId});
      final body = res.data as Map<String, dynamic>;
      if (body['success'] == true) {
        setState(() { _result = body['data'] as Map<String, dynamic>; _loading = false; });
      } else {
        setState(() { _error = body['message']?.toString() ?? '搜尋失敗'; _loading = false; });
      }
    } catch (e) {
      setState(() { _error = e.toString(); _loading = false; });
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_error != null) {
      return Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
        Icon(Icons.info_outline, size: 48, color: Theme.of(context).colorScheme.outline),
        const SizedBox(height: 8),
        Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.outline)),
        const SizedBox(height: 8),
        Text('需要先設定分類的屬性模板和品項屬性', style: TextStyle(fontSize: 12, color: Theme.of(context).colorScheme.outline)),
      ]));
    }

    final alternatives = (_result?['alternatives'] as List?) ?? [];
    final templates = (_result?['templates'] as List?) ?? [];

    if (alternatives.isEmpty) {
      return Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
        Icon(Icons.search_off, size: 48, color: Theme.of(context).colorScheme.outline),
        const SizedBox(height: 8),
        Text(templates.isEmpty ? '此分類尚未設定屬性模板' : '沒有找到有庫存的替代品',
          style: TextStyle(color: Theme.of(context).colorScheme.outline)),
      ]));
    }

    return ListView.builder(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      itemCount: alternatives.length,
      itemBuilder: (ctx, i) {
        final a = alternatives[i] as Map<String, dynamic>;
        final score = a['score'] as num? ?? 0;
        final matched = (a['matched'] as List?)?.cast<String>() ?? [];
        final mismatched = (a['mismatched'] as List?)?.cast<String>() ?? [];
        final stock = a['current_stock'] as num? ?? 0;

        return Card(
          color: i == 0 ? Colors.green.withValues(alpha: 0.05) : null,
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(children: [
                  if (i == 0)
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                      margin: const EdgeInsets.only(right: 8),
                      decoration: BoxDecoration(color: Colors.green, borderRadius: BorderRadius.circular(4)),
                      child: const Text('最佳', style: TextStyle(fontSize: 11, color: Colors.white, fontWeight: FontWeight.bold)),
                    ),
                  Expanded(child: Text(
                    '${a["brand"] ?? ""} ${a["name"]}',
                    style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
                  )),
                  Text('庫存 $stock', style: TextStyle(
                    fontSize: 13, fontWeight: FontWeight.w600,
                    color: stock > 0 ? Colors.green.shade700 : Colors.red,
                  )),
                ]),
                const SizedBox(height: 4),
                Row(children: [
                  Text(a['spec']?.toString() ?? '', style: TextStyle(fontSize: 13, color: Theme.of(ctx).colorScheme.outline)),
                  const Spacer(),
                  Text('\$${a["sell_price"]}', style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                ]),
                if (matched.isNotEmpty || mismatched.isNotEmpty) ...[
                  const SizedBox(height: 6),
                  Wrap(spacing: 4, runSpacing: 4, children: [
                    ...matched.map((m) => Container(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
                      decoration: BoxDecoration(color: Colors.green.withValues(alpha: 0.1), borderRadius: BorderRadius.circular(4)),
                      child: Text(m, style: TextStyle(fontSize: 11, color: Colors.green.shade700)),
                    )),
                    ...mismatched.map((m) => Container(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
                      decoration: BoxDecoration(color: Colors.orange.withValues(alpha: 0.1), borderRadius: BorderRadius.circular(4)),
                      child: Text(m, style: TextStyle(fontSize: 11, color: Colors.orange.shade700)),
                    )),
                  ]),
                ],
              ],
            ),
          ),
        );
      },
    );
  }
}
