import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/widgets/status_badge.dart';
import '../../../infrastructure/api/api_client.dart';

/// 欠貨待補 Tab — 顯示有 backorder 的銷貨明細，可操作通知/補交
class BackorderTab extends ConsumerStatefulWidget {
  const BackorderTab({super.key});

  @override
  ConsumerState<BackorderTab> createState() => _BackorderTabState();
}

class _BackorderTabState extends ConsumerState<BackorderTab> {
  List<Map<String, dynamic>> _items = [];
  bool _loading = true;
  String? _statusFilter;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final api = ref.read(apiClientProvider);
      final params = <String, dynamic>{};
      if (_statusFilter != null) params['status'] = _statusFilter;
      final res = await api.get('/dashboard/backorder-worklist', queryParameters: params);
      final body = res.data as Map<String, dynamic>;
      setState(() {
        _items = (body['data'] as List).cast<Map<String, dynamic>>();
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
        _buildHeader(context),
        _buildFilters(context),
        if (_loading) const LinearProgressIndicator(),
        Expanded(child: _items.isEmpty
            ? Center(child: Text('沒有欠貨紀錄', style: TextStyle(color: Theme.of(context).colorScheme.outline)))
            : ListView.separated(
                padding: const EdgeInsets.all(8),
                itemCount: _items.length,
                separatorBuilder: (_, __) => const Divider(height: 1),
                itemBuilder: (_, i) => _BackorderTile(
                  item: _items[i],
                  onAction: _load,
                ),
              )),
      ],
    );
  }

  Widget _buildHeader(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
      child: Row(
        children: [
          Text('欠貨待補', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold)),
          const SizedBox(width: 8),
          Text('${_items.length} 筆', style: TextStyle(color: Theme.of(context).colorScheme.outline)),
          const Spacer(),
          IconButton(icon: const Icon(Icons.refresh), tooltip: '重新整理', onPressed: _load),
        ],
      ),
    );
  }

  Widget _buildFilters(BuildContext context) {
    const filters = [
      (null, '全部'), ('pending', '待採購'), ('ordered', '已下單'),
      ('partial_arrived', '部分到貨'), ('arrived', '已到貨'),
    ];
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: Row(
          children: filters.map((f) => Padding(
            padding: const EdgeInsets.only(right: 6),
            child: FilterChip(
              label: Text(f.$2, style: const TextStyle(fontSize: 12)),
              selected: _statusFilter == f.$1,
              onSelected: (_) { setState(() => _statusFilter = f.$1); _load(); },
              visualDensity: VisualDensity.compact,
            ),
          )).toList(),
        ),
      ),
    );
  }
}

class _BackorderTile extends ConsumerWidget {
  final Map<String, dynamic> item;
  final VoidCallback onAction;
  const _BackorderTile({required this.item, required this.onAction});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final name = item['product_name']?.toString() ?? '';
    final spec = item['spec']?.toString() ?? '';
    final customer = item['customer_name']?.toString() ?? '散客';
    final phone = item['customer_phone']?.toString() ?? '';
    final status = item['backorder_status']?.toString() ?? 'pending';
    final boQty = item['backorder_qty'] ?? 0;
    final boOrdered = item['backorder_ordered_qty'] ?? 0;
    final boArrived = item['backorder_arrived_qty'] ?? 0;
    final boDelivered = item['backorder_delivered_qty'] ?? 0;
    final notifyCount = item['notify_count'] ?? 0;
    final saleDate = item['sale_date']?.toString().substring(0, 10) ?? '';
    final saleLineId = item['sale_line_id']?.toString() ?? '';
    final saleId = item['sale_id']?.toString() ?? '';

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(name, style: const TextStyle(fontWeight: FontWeight.w600)),
                if (spec.isNotEmpty) Text(spec, style: TextStyle(fontSize: 12, color: Theme.of(context).colorScheme.outline)),
              ])),
              StatusBadge(status: status),
            ],
          ),
          const SizedBox(height: 4),
          Row(children: [
            Text('$customer', style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w500)),
            if (phone.isNotEmpty) Text(' $phone', style: TextStyle(fontSize: 11, color: Theme.of(context).colorScheme.outline)),
            const Spacer(),
            Text(saleDate, style: TextStyle(fontSize: 11, color: Theme.of(context).colorScheme.outline)),
          ]),
          const SizedBox(height: 4),
          Row(children: [
            _Qty('欠', boQty, Colors.red),
            _Qty('訂', boOrdered, Colors.blue),
            _Qty('到', boArrived, Colors.orange),
            _Qty('交', boDelivered, Colors.green),
            if (notifyCount > 0)
              Text('  通知$notifyCount次', style: TextStyle(fontSize: 11, color: Colors.blue.shade600)),
            const Spacer(),
            // 操作按鈕
            if (status == 'arrived' || status == 'partial_arrived')
              TextButton.icon(
                onPressed: () => _doNotify(ref, saleId, saleLineId),
                icon: const Icon(Icons.notifications_active, size: 16),
                label: const Text('通知'),
                style: TextButton.styleFrom(visualDensity: VisualDensity.compact),
              ),
            if (status == 'arrived' || status == 'partial_arrived' || status == 'partial_delivered')
              TextButton.icon(
                onPressed: () => _doDeliver(context, ref, saleLineId, boQty - boDelivered),
                icon: const Icon(Icons.local_shipping, size: 16),
                label: const Text('補交'),
                style: TextButton.styleFrom(visualDensity: VisualDensity.compact),
              ),
          ]),
        ],
      ),
    );
  }

  Future<void> _doNotify(WidgetRef ref, String saleId, String saleLineId) async {
    final api = ref.read(apiClientProvider);
    try {
      await api.post('/backorders/notify', data: {
        'sale_id': saleId, 'sale_line_id': saleLineId, 'channel': 'manual',
      });
      onAction();
    } catch (_) {}
  }

  Future<void> _doDeliver(BuildContext context, WidgetRef ref, String saleLineId, int maxQty) async {
    final controller = TextEditingController(text: maxQty.toString());
    final confirmed = await showDialog<int>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('補交'),
        content: TextField(
          controller: controller,
          decoration: InputDecoration(labelText: '補交數量（最多 $maxQty）'),
          keyboardType: TextInputType.number,
          autofocus: true,
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('取消')),
          FilledButton(onPressed: () {
            final val = int.tryParse(controller.text) ?? 0;
            if (val > 0) Navigator.pop(ctx, val);
          }, child: const Text('確認')),
        ],
      ),
    );
    if (confirmed != null && confirmed > 0) {
      final api = ref.read(apiClientProvider);
      try {
        await api.post('/backorders/deliver', data: {
          'sale_line_id': saleLineId, 'deliver_qty': confirmed,
        });
        onAction();
      } catch (_) {}
    }
  }
}

class _Qty extends StatelessWidget {
  final String label;
  final int qty;
  final Color color;
  const _Qty(this.label, this.qty, this.color);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(right: 8),
      child: Text('$label$qty', style: TextStyle(fontSize: 11, color: color, fontWeight: FontWeight.w500)),
    );
  }
}
