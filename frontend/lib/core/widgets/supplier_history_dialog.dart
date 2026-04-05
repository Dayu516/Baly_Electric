import 'package:flutter/material.dart';

import '../../infrastructure/api/api_client.dart';

/// 供應商歷史交易 dialog。
void showSupplierHistory(BuildContext context, ApiClient api, {required String supplierId, required String supplierName}) {
  showDialog(
    context: context,
    builder: (ctx) => Dialog(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 600, maxHeight: 500),
        child: _SupplierHistoryContent(api: api, supplierId: supplierId, supplierName: supplierName),
      ),
    ),
  );
}

class _SupplierHistoryContent extends StatefulWidget {
  final ApiClient api;
  final String supplierId;
  final String supplierName;
  const _SupplierHistoryContent({required this.api, required this.supplierId, required this.supplierName});

  @override
  State<_SupplierHistoryContent> createState() => _SupplierHistoryContentState();
}

class _SupplierHistoryContentState extends State<_SupplierHistoryContent> {
  Map<String, dynamic>? _summary;
  List<Map<String, dynamic>> _history = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final res = await widget.api.get('/suppliers/${widget.supplierId}/history');
      final body = res.data as Map<String, dynamic>;
      final data = body['data'] as Map<String, dynamic>;
      setState(() {
        _summary = data['summary'] as Map<String, dynamic>;
        _history = (data['history'] as List).cast<Map<String, dynamic>>();
        _loading = false;
      });
    } catch (e) {
      setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(24, 16, 12, 0),
          child: Row(children: [
            Expanded(child: Text(widget.supplierName,
              style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold))),
            IconButton(icon: const Icon(Icons.close), onPressed: () => Navigator.pop(context)),
          ]),
        ),

        if (_loading) const Expanded(child: Center(child: CircularProgressIndicator()))
        else ...[
          // 摘要
          if (_summary != null)
            Container(
              margin: const EdgeInsets.fromLTRB(24, 12, 24, 0),
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Theme.of(context).colorScheme.surfaceContainerHighest.withValues(alpha: 0.5),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(children: [
                _stat('累計進貨', '${_summary!['total_receipts']} 次'),
                const SizedBox(width: 24),
                _stat('累計金額', '\$${_fmtAmount(_summary!['total_amount'])}'),
                const SizedBox(width: 24),
                _stat('累計數量', '${_summary!['total_quantity']} 件'),
                const SizedBox(width: 24),
                _stat('最近進貨', _summary!['last_receipt_date']?.toString() ?? '無'),
              ]),
            ),

          const SizedBox(height: 12),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 24),
            child: Align(
              alignment: Alignment.centerLeft,
              child: Text('進貨紀錄', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600,
                color: Theme.of(context).colorScheme.primary)),
            ),
          ),
          const SizedBox(height: 8),

          // 歷史列表
          Expanded(
            child: _history.isEmpty
                ? Center(child: Text('尚無進貨紀錄', style: TextStyle(color: Theme.of(context).colorScheme.outline)))
                : ListView.builder(
                    padding: const EdgeInsets.symmetric(horizontal: 16),
                    itemCount: _history.length,
                    itemBuilder: (ctx, i) {
                      final r = _history[i];
                      return ListTile(
                        dense: true,
                        leading: CircleAvatar(
                          radius: 16,
                          backgroundColor: Theme.of(ctx).colorScheme.primaryContainer,
                          child: Text('${r['line_count']}', style: TextStyle(
                            fontSize: 12, fontWeight: FontWeight.bold,
                            color: Theme.of(ctx).colorScheme.onPrimaryContainer)),
                        ),
                        title: Row(children: [
                          Text(r['date']?.toString() ?? ''),
                          const Spacer(),
                          Text('\$${(r['total_amount'] as num).toStringAsFixed(0)}',
                            style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Colors.green.shade700)),
                        ]),
                        subtitle: Text(
                          '${r['total_quantity']} 件${r['po_note'] != null ? '  ·  ${r['po_note']}' : ''}',
                          style: TextStyle(fontSize: 12, color: Theme.of(ctx).colorScheme.outline),
                        ),
                      );
                    },
                  ),
          ),
        ],
      ],
    );
  }

  Widget _stat(String label, String value) {
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(label, style: TextStyle(fontSize: 11, color: Theme.of(context).colorScheme.outline)),
      Text(value, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.bold)),
    ]);
  }

  String _fmtAmount(dynamic v) {
    if (v == null) return '0';
    final n = v is num ? v : num.tryParse(v.toString()) ?? 0;
    if (n >= 10000) return '${(n / 10000).toStringAsFixed(1)}萬';
    return n.toStringAsFixed(0);
  }
}
