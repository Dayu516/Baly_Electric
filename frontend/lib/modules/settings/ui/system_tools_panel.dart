import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../infrastructure/api/api_client.dart';

class SystemToolsPanel extends ConsumerStatefulWidget {
  const SystemToolsPanel({super.key});
  @override
  ConsumerState<SystemToolsPanel> createState() => _SystemToolsPanelState();
}

class _SystemToolsPanelState extends ConsumerState<SystemToolsPanel> {
  bool _recalcLoading = false;
  String? _recalcResult;
  bool _reportLoading = false;
  Map<String, dynamic>? _reportData;
  String _reportPeriod = '';

  @override
  void initState() {
    super.initState();
    final now = DateTime.now();
    _reportPeriod = '${now.year}-${now.month.toString().padLeft(2, '0')}';
  }

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 600),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('系統工具', style: Theme.of(context).textTheme.headlineSmall),
            const SizedBox(height: 24),

            // 庫存重算
            Card(child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                const Text('庫存數量重整', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
                const SizedBox(height: 4),
                Text('根據所有庫存異動紀錄重新計算庫存餘額。如果發現庫存數字不對可以用這個修正。',
                  style: TextStyle(fontSize: 13, color: Theme.of(context).colorScheme.onSurfaceVariant)),
                const SizedBox(height: 12),
                if (_recalcResult != null)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 12),
                    child: Text(_recalcResult!, style: TextStyle(color: Colors.green.shade700)),
                  ),
                FilledButton.tonalIcon(
                  onPressed: _recalcLoading ? null : _doRecalc,
                  icon: _recalcLoading
                      ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                      : const Icon(Icons.refresh),
                  label: const Text('執行重算'),
                ),
              ]),
            )),

            const SizedBox(height: 24),

            // 供應商月度統計
            Card(child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                const Text('供應商月度統計', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
                const SizedBox(height: 4),
                Text('查看某月份跟各供應商的進貨總額。',
                  style: TextStyle(fontSize: 13, color: Theme.of(context).colorScheme.onSurfaceVariant)),
                const SizedBox(height: 12),
                Row(children: [
                  SizedBox(width: 150, child: TextField(
                    controller: TextEditingController(text: _reportPeriod),
                    decoration: const InputDecoration(labelText: '月份 (YYYY-MM)', border: OutlineInputBorder(), isDense: true),
                    onChanged: (v) => _reportPeriod = v,
                  )),
                  const SizedBox(width: 12),
                  FilledButton.tonalIcon(
                    onPressed: _reportLoading ? null : _loadReport,
                    icon: _reportLoading
                        ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                        : const Icon(Icons.bar_chart),
                    label: const Text('查詢'),
                  ),
                ]),
                if (_reportData != null) ...[
                  const SizedBox(height: 16),
                  Text('${_reportData!["period"]} 總計 \$${(_reportData!["total_amount"] as num).toStringAsFixed(0)}',
                    style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                  const SizedBox(height: 8),
                  ...(_reportData!['suppliers'] as List).map((s) {
                    final sup = s as Map<String, dynamic>;
                    return Padding(
                      padding: const EdgeInsets.only(bottom: 8),
                      child: Row(children: [
                        Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                          Text(sup['supplier_name']?.toString() ?? '', style: const TextStyle(fontWeight: FontWeight.w600)),
                          Text('${sup["receipt_count"]} 筆驗收 · ${sup["total_quantity"]} 件',
                            style: TextStyle(fontSize: 12, color: Theme.of(context).colorScheme.outline)),
                        ])),
                        Text('\$${(sup["total_amount"] as num).toStringAsFixed(0)}',
                          style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Colors.green.shade700)),
                      ]),
                    );
                  }),
                  if ((_reportData!['suppliers'] as List).isEmpty)
                    Text('此月份沒有進貨紀錄', style: TextStyle(color: Theme.of(context).colorScheme.outline)),
                ],
              ]),
            )),
          ],
        ),
      ),
    );
  }

  Future<void> _doRecalc() async {
    setState(() { _recalcLoading = true; _recalcResult = null; });
    final api = ref.read(apiClientProvider);
    try {
      final res = await api.post('/inventory/recalc-all');
      final body = res.data as Map<String, dynamic>;
      setState(() { _recalcLoading = false; _recalcResult = body['message']?.toString(); });
    } catch (e) {
      setState(() { _recalcLoading = false; _recalcResult = '重算失敗: $e'; });
    }
  }

  Future<void> _loadReport() async {
    if (_reportPeriod.length != 7) return;
    setState(() { _reportLoading = true; _reportData = null; });
    final api = ref.read(apiClientProvider);
    try {
      final res = await api.get('/reports/supplier-monthly', queryParameters: {'period': _reportPeriod});
      final body = res.data as Map<String, dynamic>;
      setState(() { _reportLoading = false; _reportData = body['data'] as Map<String, dynamic>; });
    } catch (e) {
      setState(() { _reportLoading = false; });
    }
  }
}
