import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../infrastructure/api/api_client.dart';
import '../application/pos_provider.dart';

// 結帳成功 — 顯示明細 + 5 秒自動回到搜尋
// ═══════════════════════════════════════════════════════
class CheckoutSuccessView extends ConsumerStatefulWidget {
  final PosState pos;
  final VoidCallback onNext;

  const CheckoutSuccessView({super.key, required this.pos, required this.onNext});

  @override
  ConsumerState<CheckoutSuccessView> createState() => _CheckoutSuccessViewState();
}

class _CheckoutSuccessViewState extends ConsumerState<CheckoutSuccessView> {
  int _countdown = 5;
  late final _timer = Stream.periodic(const Duration(seconds: 1), (i) => 4 - i);

  @override
  void initState() {
    super.initState();
    _startCountdown();
  }

  void _startCountdown() {
    _timer.take(5).listen((remaining) {
      if (mounted) {
        setState(() => _countdown = remaining);
        if (remaining <= 0) widget.onNext();
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final saleId = widget.pos.lastSaleId;

    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        children: [
          const Icon(Icons.check_circle, size: 64, color: Colors.green),
          const SizedBox(height: 8),
          const Text('結帳成功！', style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold)),
          if (saleId != null)
            Text('單號: ${saleId.substring(0, 8)}',
                style: TextStyle(fontSize: 13, color: Theme.of(context).colorScheme.outline)),

          const SizedBox(height: 16),

          // 出貨單預覽
          if (saleId != null)
            Expanded(child: _ReceiptPreview(saleId: saleId)),

          const SizedBox(height: 12),

          // 操作按鈕
          Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: saleId != null ? () => _printReceipt(context, saleId) : null,
                  icon: const Icon(Icons.print),
                  label: const Text('列印出貨單'),
                  style: OutlinedButton.styleFrom(minimumSize: const Size(0, 52)),
                ),
              ),
              const SizedBox(width: 12),
              if (saleId != null)
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: () => _showBackorderDialog(context, ref, saleId),
                    icon: const Icon(Icons.pending_actions, size: 20),
                    label: const Text('建立欠貨'),
                    style: OutlinedButton.styleFrom(
                      minimumSize: const Size(0, 52),
                      foregroundColor: Colors.orange.shade700,
                    ),
                  ),
                ),
              const SizedBox(width: 12),
              Expanded(
                flex: 2,
                child: ElevatedButton.icon(
                  onPressed: widget.onNext,
                  icon: const Icon(Icons.add_shopping_cart),
                  label: Text('下一筆交易 ($_countdown)'),
                  style: ElevatedButton.styleFrom(
                    minimumSize: const Size(0, 52),
                    textStyle: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  void _showBackorderDialog(BuildContext context, WidgetRef ref, String saleId) async {
    final api = ref.read(apiClientProvider);
    final res = await api.get('/sales/history/$saleId');
    final data = res.data as Map<String, dynamic>;
    final lines = ((data['data']?['lines'] ?? []) as List).cast<Map<String, dynamic>>();
    if (lines.isEmpty || !context.mounted) return;

    showDialog(
      context: context,
      builder: (ctx) => _BackorderDialog(api: api, saleId: saleId, lines: lines),
    );
  }

  void _printReceipt(BuildContext context, String saleId) {
    // TODO: 接實際印表機。目前顯示預覽。
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('列印功能將在門市接印表機後啟用')),
    );
  }
}

class _ReceiptPreview extends ConsumerWidget {
  final String saleId;
  const _ReceiptPreview({required this.saleId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final api = ref.watch(apiClientProvider);

    return FutureBuilder(
      future: api.get('/receipts/$saleId/text'),
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snapshot.hasError) {
          return Center(child: Text('載入失敗', style: TextStyle(color: Theme.of(context).colorScheme.outline)));
        }
        final data = snapshot.data?.data as Map<String, dynamic>?;
        final text = data?['text'] ?? '';

        return Container(
          width: double.infinity,
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: Colors.grey.shade50,
            border: Border.all(color: Colors.grey.shade300),
            borderRadius: BorderRadius.circular(8),
          ),
          child: SingleChildScrollView(
            child: Text(
              text,
              style: const TextStyle(
                fontFamily: 'Courier New',
                fontSize: 13,
                height: 1.4,
              ),
            ),
          ),
        );
      },
    );
  }
}


// ═══════════════════════════════════════════════════════
// 建立欠貨 Dialog — 店員輸入每筆實交數量
// ═══════════════════════════════════════════════════════
class _BackorderDialog extends StatefulWidget {
  final ApiClient api;
  final String saleId;
  final List<Map<String, dynamic>> lines;
  const _BackorderDialog({required this.api, required this.saleId, required this.lines});

  @override
  State<_BackorderDialog> createState() => _BackorderDialogState();
}

class _BackorderDialogState extends State<_BackorderDialog> {
  late final Map<String, TextEditingController> _controllers;
  bool _loading = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _controllers = {
      for (final line in widget.lines)
        line['sale_line_id'].toString(): TextEditingController(
          text: (line['quantity'] ?? 0).toString(),
        ),
    };
  }

  @override
  void dispose() {
    for (final c in _controllers.values) { c.dispose(); }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('建立欠貨'),
      content: SizedBox(
        width: 480,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('輸入每筆品項的實際交付數量，差額會自動變成欠貨。',
                style: TextStyle(fontSize: 13, color: Theme.of(context).colorScheme.outline)),
            const SizedBox(height: 12),
            ...widget.lines.map((line) {
              final lineId = line['sale_line_id'].toString();
              final name = line['product_name']?.toString() ?? '';
              final qty = line['quantity'] ?? 0;
              return Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Row(
                  children: [
                    Expanded(flex: 3, child: Text('$name x$qty', style: const TextStyle(fontSize: 13))),
                    const SizedBox(width: 8),
                    SizedBox(
                      width: 80,
                      child: TextField(
                        controller: _controllers[lineId],
                        decoration: const InputDecoration(
                          labelText: '實交',
                          border: OutlineInputBorder(),
                          isDense: true,
                        ),
                        keyboardType: TextInputType.number,
                      ),
                    ),
                  ],
                ),
              );
            }),
            if (_error != null)
              Text(_error!, style: TextStyle(color: Colors.red.shade700, fontSize: 13)),
          ],
        ),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('取消')),
        FilledButton(
          onPressed: _loading ? null : _submit,
          child: _loading
              ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
              : const Text('確認建立'),
        ),
      ],
    );
  }

  Future<void> _submit() async {
    setState(() { _loading = true; _error = null; });

    int created = 0;
    for (final line in widget.lines) {
      final lineId = line['sale_line_id'].toString();
      final qty = line['quantity'] ?? 0;
      final delivered = int.tryParse(_controllers[lineId]?.text ?? '') ?? qty;
      if (delivered < qty) {
        try {
          await widget.api.post('/backorders/create', data: {
            'sale_line_id': lineId,
            'delivered_qty': delivered,
          });
          created++;
        } catch (e) {
          setState(() { _loading = false; _error = '建立失敗: $e'; });
          return;
        }
      }
    }

    if (mounted) {
      Navigator.pop(context);
      if (created > 0) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('已建立 $created 筆欠貨')),
        );
      }
    }
  }
}
