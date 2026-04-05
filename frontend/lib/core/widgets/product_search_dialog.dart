import 'package:flutter/material.dart';

import '../../infrastructure/api/api_client.dart';

/// 品項搜尋 dialog — 共用元件。
/// 搜尋後選取品項，回傳選取的品項資料。
///
/// 用法：
/// ```dart
/// final item = await showProductSearchDialog(context, api, title: '搜尋品項');
/// if (item != null) { /* 處理選取結果 */ }
/// ```
Future<Map<String, dynamic>?> showProductSearchDialog(
  BuildContext context,
  ApiClient api, {
  String title = '搜尋品項',
}) {
  return showDialog<Map<String, dynamic>>(
    context: context,
    builder: (ctx) => _ProductSearchDialog(api: api, title: title),
  );
}

class _ProductSearchDialog extends StatefulWidget {
  final ApiClient api;
  final String title;
  const _ProductSearchDialog({required this.api, required this.title});

  @override
  State<_ProductSearchDialog> createState() => _ProductSearchDialogState();
}

class _ProductSearchDialogState extends State<_ProductSearchDialog> {
  final _searchCtrl = TextEditingController();
  List<Map<String, dynamic>> _results = [];
  bool _loading = false;

  @override
  void dispose() { _searchCtrl.dispose(); super.dispose(); }

  Future<void> _search(String query) async {
    if (query.isEmpty) return;
    setState(() => _loading = true);
    try {
      final res = await widget.api.get('/products/search', queryParameters: {'q': query});
      setState(() {
        _results = ((res.data as Map)['data'] as List).cast<Map<String, dynamic>>();
        _loading = false;
      });
    } catch (_) {
      setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text(widget.title),
      content: SizedBox(
        width: 500,
        height: 400,
        child: Column(children: [
          TextField(
            controller: _searchCtrl,
            autofocus: true,
            decoration: const InputDecoration(
              labelText: '搜尋品項',
              prefixIcon: Icon(Icons.search),
              border: OutlineInputBorder(),
            ),
            onSubmitted: _search,
          ),
          const SizedBox(height: 8),
          if (_loading) const LinearProgressIndicator(),
          Expanded(
            child: ListView.builder(
              itemCount: _results.length,
              itemBuilder: (ctx, i) {
                final item = _results[i];
                return ListTile(
                  dense: true,
                  title: Text('${item["brand"] ?? ""} ${item["name"]}'),
                  subtitle: Text(item['spec']?.toString() ?? ''),
                  trailing: Text('\$${item["sell_price"] ?? 0}'),
                  onTap: () => Navigator.pop(context, item),
                );
              },
            ),
          ),
        ]),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('關閉')),
      ],
    );
  }
}
