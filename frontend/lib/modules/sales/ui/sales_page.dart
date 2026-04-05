import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/feature_flags.dart';
import '../../../core/router/app_router.dart';
import '../../../core/widgets/feature_locked_page.dart';
import '../../../core/widgets/status_badge.dart';
import '../../../infrastructure/api/api_client.dart';
import '../../procurement/application/quotation_provider.dart';
import '../application/sales_provider.dart';
import 'backorder_tab.dart';

class SalesPage extends ConsumerStatefulWidget {
  const SalesPage({super.key});
  @override
  ConsumerState<SalesPage> createState() => _SalesPageState();
}

class _SalesPageState extends ConsumerState<SalesPage> with SingleTickerProviderStateMixin {
  late TabController _tabCtrl;

  @override
  void initState() {
    super.initState();
    _tabCtrl = TabController(length: 3, vsync: this);
    Future.microtask(() {
      ref.read(quotationListProvider.notifier).load();
      ref.read(salesHistoryProvider.notifier).load();
    });
  }

  @override
  void dispose() { _tabCtrl.dispose(); super.dispose(); }

  @override
  Widget build(BuildContext context) {
    final device = getDeviceClass(context);
    if (FeatureFlags.getLevel('sales', device) == FeatureLevel.c) {
      return const FeatureLockedPage(featureName: '銷售管理', guidanceMessage: '請在桌面版操作');
    }
    return Column(children: [
      TabBar(controller: _tabCtrl, tabs: const [Tab(text: '報價單'), Tab(text: '銷售紀錄'), Tab(text: '欠貨待補')]),
      Expanded(child: TabBarView(controller: _tabCtrl, children: const [_QuotationTab(), _SalesHistoryTab(), BackorderTab()])),
    ]);
  }
}

// ═══════════════════════════════════════════════════════
// 報價單 Tab（從 procurement 搬過來）
// ═══════════════════════════════════════════════════════
class _QuotationTab extends ConsumerWidget {
  const _QuotationTab();
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return const Row(children: [
      Expanded(flex: 2, child: _QuotationListPanel()),
      VerticalDivider(width: 1),
      Expanded(flex: 3, child: _QuotationDetailPanel()),
    ]);
  }
}

class _QuotationListPanel extends ConsumerWidget {
  const _QuotationListPanel();
  static const _statusLabels = {'draft': '草稿', 'sent': '已送出', 'accepted': '已確認', 'converted': '已轉單', 'cancelled': '已取消'};
  static const _statusColors = {'draft': Colors.grey, 'sent': Colors.blue, 'accepted': Colors.orange, 'converted': Colors.green, 'cancelled': Colors.red};

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(quotationListProvider);
    return Column(children: [
      Padding(padding: const EdgeInsets.fromLTRB(16, 12, 16, 0), child: Row(children: [
        Text('報價單', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold)),
        const Spacer(),
        FilledButton.tonalIcon(onPressed: () => _showCreate(context, ref), icon: const Icon(Icons.add, size: 18), label: const Text('建立報價')),
      ])),
      const SizedBox(height: 8),
      if (state.loading) const LinearProgressIndicator(),
      Expanded(child: state.items.isEmpty ? Center(child: Text('沒有報價單', style: TextStyle(color: Theme.of(context).colorScheme.outline)))
        : ListView.builder(itemCount: state.items.length, itemBuilder: (ctx, i) {
          final q = state.items[i]; final s = q['status']?.toString() ?? '';
          return ListTile(dense: true,
            leading: CircleAvatar(radius: 16, backgroundColor: (_statusColors[s] ?? Colors.grey).withValues(alpha: 0.15),
              child: Icon(Icons.receipt_long_outlined, size: 16, color: _statusColors[s] ?? Colors.grey)),
            title: Text(q['title']?.toString() ?? '', style: const TextStyle(fontWeight: FontWeight.w600)),
            subtitle: Text('${q["customer_name"] ?? "散客"}  ·  ${_statusLabels[s] ?? s}  ·  \$${(q["total_amount"] as num?)?.toStringAsFixed(0) ?? "0"}',
              style: TextStyle(fontSize: 12, color: Theme.of(ctx).colorScheme.outline)),
            onTap: () => ref.read(quotationDetailProvider.notifier).load(q['quotation_id']?.toString() ?? ''),
          );
        })),
    ]);
  }

  void _showCreate(BuildContext context, WidgetRef ref) async {
    final api = ref.read(apiClientProvider);
    List<Map<String, dynamic>> customers = [];
    try { final res = await api.get('/customers/'); customers = ((res.data as Map)['data'] as List).cast<Map<String, dynamic>>(); } catch (_) {}
    String? custId; final titleCtrl = TextEditingController(); final noteCtrl = TextEditingController();
    if (!context.mounted) return;
    showDialog(context: context, builder: (ctx) => StatefulBuilder(builder: (ctx, ss) => AlertDialog(
      title: const Text('建立報價單'), content: SizedBox(width: 400, child: Column(mainAxisSize: MainAxisSize.min, children: [
        TextField(controller: titleCtrl, autofocus: true, decoration: const InputDecoration(labelText: '標題', border: OutlineInputBorder())),
        const SizedBox(height: 12),
        DropdownButtonFormField<String>(value: custId, decoration: const InputDecoration(labelText: '客戶（選填）', border: OutlineInputBorder()),
          items: [const DropdownMenuItem(value: null, child: Text('散客')), ...customers.map((c) => DropdownMenuItem(value: c['customer_id']?.toString(), child: Text(c['name']?.toString() ?? '')))],
          onChanged: (v) => ss(() => custId = v)),
        const SizedBox(height: 12),
        TextField(controller: noteCtrl, decoration: const InputDecoration(labelText: '備註', border: OutlineInputBorder())),
      ])), actions: [
        TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('取消')),
        FilledButton(onPressed: () async {
          if (titleCtrl.text.trim().isEmpty) return;
          try { await api.post('/quotations/', data: {'title': titleCtrl.text.trim(), 'customer_id': custId, 'note': noteCtrl.text.isEmpty ? null : noteCtrl.text});
            if (ctx.mounted) Navigator.pop(ctx); ref.read(quotationListProvider.notifier).load();
          } catch (e) { if (ctx.mounted) ScaffoldMessenger.of(ctx).showSnackBar(SnackBar(content: Text('失敗: $e'))); }
        }, child: const Text('建立')),
      ],
    )));
  }
}

class _QuotationDetailPanel extends ConsumerWidget {
  const _QuotationDetailPanel();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(quotationDetailProvider);
    if (state.loading) return const Center(child: CircularProgressIndicator());
    if (state.data == null) return Center(child: Text('選擇一張報價單', style: TextStyle(color: Theme.of(context).colorScheme.outline)));

    final q = state.data!; final id = q['quotation_id']?.toString() ?? ''; final s = q['status']?.toString() ?? '';
    final lines = (q['lines'] as List?) ?? [];
    final api = ref.read(apiClientProvider);
    final total = lines.fold<double>(0, (sum, l) => sum + ((l as Map)['quantity'] as num) * (l['unit_price'] as num));

    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Padding(padding: const EdgeInsets.fromLTRB(24, 16, 24, 0), child: Row(children: [
        Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(q['title']?.toString() ?? '', style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
          const SizedBox(height: 4),
          Row(children: [
            StatusBadge(status: s),
            const SizedBox(width: 12),
            Text(q['customer_name']?.toString() ?? '散客', style: TextStyle(fontSize: 13, color: Theme.of(context).colorScheme.outline)),
            const SizedBox(width: 12),
            Text('合計 \$${total.toStringAsFixed(0)}', style: const TextStyle(fontSize: 14, fontWeight: FontWeight.bold)),
          ]),
        ])),
        if (s == 'draft' || s == 'sent')
          FilledButton.tonalIcon(onPressed: () => _addLine(context, ref, api, id), icon: const Icon(Icons.add, size: 18), label: const Text('加品項')),
        if (s == 'draft') ...[
          const SizedBox(width: 8),
          FilledButton.tonal(onPressed: () async { await api.post('/quotations/$id/send'); ref.read(quotationDetailProvider.notifier).load(id); ref.read(quotationListProvider.notifier).load(); }, child: const Text('已送出')),
        ],
        if (s == 'sent') ...[
          const SizedBox(width: 8),
          FilledButton.tonal(onPressed: () async { await api.post('/quotations/$id/accept'); ref.read(quotationDetailProvider.notifier).load(id); ref.read(quotationListProvider.notifier).load(); }, child: const Text('客戶確認')),
        ],
        if (s != 'converted' && s != 'cancelled') ...[
          const SizedBox(width: 8),
          FilledButton.icon(onPressed: () => _confirmConvert(context, ref, api, id, q['title']?.toString() ?? '', total),
            icon: const Icon(Icons.point_of_sale), label: const Text('轉銷貨單')),
          const SizedBox(width: 8),
          TextButton(onPressed: () async { await api.post('/quotations/$id/cancel'); ref.read(quotationDetailProvider.notifier).load(id); ref.read(quotationListProvider.notifier).load(); },
            child: const Text('取消', style: TextStyle(color: Colors.red))),
        ],
      ])),
      const SizedBox(height: 8), const Divider(height: 1),
      Expanded(child: lines.isEmpty ? Center(child: Text('點「加品項」', style: TextStyle(color: Theme.of(context).colorScheme.outline)))
        : ListView.builder(padding: const EdgeInsets.all(12), itemCount: lines.length, itemBuilder: (ctx, i) {
          final l = lines[i] as Map<String, dynamic>;
          final lineTotal = (l['quantity'] as num) * (l['unit_price'] as num);
          return Card(child: Padding(padding: const EdgeInsets.all(12), child: Row(children: [
            Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('${l["brand"] ?? ""} ${l["product_name"] ?? ""}', style: const TextStyle(fontWeight: FontWeight.w600)),
              Text('${l["spec"] ?? ""}  ·  ${l["unit"] ?? "個"}', style: TextStyle(fontSize: 12, color: Theme.of(ctx).colorScheme.outline)),
            ])),
            Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
              Text('\$${l["unit_price"]} × ${l["quantity"]}', style: TextStyle(fontSize: 13, color: Theme.of(ctx).colorScheme.outline)),
              Text('\$${lineTotal.toStringAsFixed(0)}', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Colors.green.shade700)),
            ]),
          ])));
        })),
    ]);
  }

  void _confirmConvert(BuildContext context, WidgetRef ref, ApiClient api, String id, String title, double total) {
    showDialog(context: context, builder: (ctx) => AlertDialog(
      title: const Text('確認轉銷貨單'),
      content: Text('將報價單「$title」轉為銷貨結帳，金額 \$${total.toStringAsFixed(0)}。\n\n此操作會扣除庫存，確定要轉單嗎？'),
      actions: [
        TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('取消')),
        FilledButton(onPressed: () async {
          Navigator.pop(ctx);
          try {
            final res = await api.post('/quotations/$id/convert');
            final body = res.data as Map<String, dynamic>;
            ref.read(quotationDetailProvider.notifier).load(id);
            ref.read(quotationListProvider.notifier).load();
            if (context.mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(body['message']?.toString() ?? '已轉單')));
          } catch (e) { if (context.mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('轉單失敗: $e'))); }
        }, child: const Text('確認轉單')),
      ],
    ));
  }

  void _addLine(BuildContext context, WidgetRef ref, ApiClient api, String quotationId) {
    final searchCtrl = TextEditingController(); List<Map<String, dynamic>> results = [];
    showDialog(context: context, builder: (ctx) => StatefulBuilder(builder: (ctx, ss) => AlertDialog(
      title: const Text('搜尋品項'), content: SizedBox(width: 500, height: 400, child: Column(children: [
        TextField(controller: searchCtrl, autofocus: true, decoration: const InputDecoration(labelText: '搜尋品項', prefixIcon: Icon(Icons.search), border: OutlineInputBorder()),
          onSubmitted: (q) async { if (q.isEmpty) return; try { final res = await api.get('/products/search', queryParameters: {'q': q});
            ss(() => results = ((res.data as Map)['data'] as List).cast<Map<String, dynamic>>()); } catch (_) {} }),
        const SizedBox(height: 8),
        Expanded(child: ListView.builder(itemCount: results.length, itemBuilder: (ctx, i) {
          final item = results[i]; final stock = item['current_stock'] ?? 0;
          return ListTile(dense: true,
            title: Text('${item["brand"] ?? ""} ${item["name"]}'),
            subtitle: Text('${item["spec"] ?? ""}  ·  庫存: $stock'),
            trailing: Text('\$${item["sell_price"] ?? 0}', style: TextStyle(fontWeight: FontWeight.bold, color: Colors.green.shade700)),
            onTap: () {
              final qtyCtrl = TextEditingController(text: '1');
              final priceCtrl = TextEditingController(text: item['sell_price']?.toString() ?? '0');
              showDialog(context: ctx, builder: (c2) => AlertDialog(
                title: Text('${item["brand"] ?? ""} ${item["name"]}'),
                content: SizedBox(width: 300, child: Column(mainAxisSize: MainAxisSize.min, children: [
                  TextField(controller: qtyCtrl, autofocus: true, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: '數量', border: OutlineInputBorder())),
                  const SizedBox(height: 12),
                  TextField(controller: priceCtrl, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: '報價單價', prefixText: '\$', border: OutlineInputBorder())),
                  const SizedBox(height: 8),
                  Text('庫存: $stock  成本: \$${item["cost_price"] ?? "-"}', style: TextStyle(fontSize: 12, color: Theme.of(c2).colorScheme.outline)),
                ])),
                actions: [TextButton(onPressed: () => Navigator.pop(c2), child: const Text('取消')),
                  FilledButton(onPressed: () async {
                    try { await api.post('/quotations/$quotationId/lines', data: {'sku_id': item['sku_id'], 'quantity': int.tryParse(qtyCtrl.text) ?? 1, 'unit_price': double.tryParse(priceCtrl.text) ?? 0});
                      if (c2.mounted) Navigator.pop(c2); if (ctx.mounted) Navigator.pop(ctx); ref.read(quotationDetailProvider.notifier).load(quotationId);
                    } catch (e) { if (c2.mounted) ScaffoldMessenger.of(c2).showSnackBar(SnackBar(content: Text('失敗: $e'))); }
                  }, child: const Text('加入'))],
              ));
            });
        })),
      ])), actions: [TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('關閉'))],
    )));
  }
}

// ═══════════════════════════════════════════════════════
// 銷售紀錄 Tab
// ═══════════════════════════════════════════════════════
class _SalesHistoryTab extends ConsumerWidget {
  const _SalesHistoryTab();
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return const Row(children: [
      Expanded(flex: 2, child: _SalesListPanel()),
      VerticalDivider(width: 1),
      Expanded(flex: 3, child: _SaleDetailPanel()),
    ]);
  }
}

class _SalesListPanel extends ConsumerWidget {
  const _SalesListPanel();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(salesHistoryProvider);
    return Column(children: [
      Padding(padding: const EdgeInsets.fromLTRB(16, 12, 16, 8), child: Row(children: [
        Text('銷售紀錄', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold)),
        const Spacer(),
        Text('${state.total} 筆', style: TextStyle(color: Theme.of(context).colorScheme.outline)),
      ])),
      if (state.loading) const LinearProgressIndicator(),
      Expanded(child: state.items.isEmpty ? Center(child: Text('沒有銷售紀錄', style: TextStyle(color: Theme.of(context).colorScheme.outline)))
        : ListView.builder(itemCount: state.items.length, itemBuilder: (ctx, i) {
          final s = state.items[i];
          final isVoided = s['status'] == 'voided';
          final date = (s['created_at']?.toString() ?? '').length >= 16 ? s['created_at'].toString().substring(0, 16).replaceAll('T', ' ') : '';
          return ListTile(dense: true,
            leading: CircleAvatar(radius: 16,
              backgroundColor: isVoided ? Colors.red.withValues(alpha: 0.15) : Colors.green.withValues(alpha: 0.15),
              child: Icon(isVoided ? Icons.cancel_outlined : Icons.receipt_outlined, size: 16,
                color: isVoided ? Colors.red : Colors.green)),
            title: Text(s['customer_name']?.toString() ?? '散客', style: TextStyle(
              fontWeight: FontWeight.w600, decoration: isVoided ? TextDecoration.lineThrough : null)),
            subtitle: Text('$date  ·  ${s["line_count"]} 項  ·  ${s["payment_method"] == "monthly_credit" ? "月結" : "現金"}',
              style: TextStyle(fontSize: 12, color: Theme.of(ctx).colorScheme.outline)),
            trailing: Text('\$${(s["total"] as num?)?.toStringAsFixed(0) ?? "0"}',
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold,
                color: isVoided ? Colors.red : Colors.green.shade700,
                decoration: isVoided ? TextDecoration.lineThrough : null)),
            onTap: () => ref.read(saleDetailProvider.notifier).load(s['sale_id']?.toString() ?? ''),
          );
        })),
    ]);
  }
}

class _SaleDetailPanel extends ConsumerWidget {
  const _SaleDetailPanel();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(saleDetailProvider);
    if (state.loading) return const Center(child: CircularProgressIndicator());
    if (state.data == null) return Center(child: Text('選擇一筆交易查看明細', style: TextStyle(color: Theme.of(context).colorScheme.outline)));

    final s = state.data!;
    final lines = (s['lines'] as List?) ?? [];
    final isVoided = s['status'] == 'voided';

    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Padding(padding: const EdgeInsets.fromLTRB(24, 16, 24, 0), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Text(s['customer_name']?.toString() ?? '散客', style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
          const Spacer(),
          if (isVoided) StatusBadge(status: 'voided'),
        ]),
        const SizedBox(height: 4),
        Text('${(s["created_at"]?.toString() ?? "").replaceAll("T", " ").substring(0, 19)}  ·  ${s["payment_method"] == "monthly_credit" ? "月結" : "現金"}${s["tax_included"] == true ? "  ·  含稅" : ""}',
          style: TextStyle(fontSize: 13, color: Theme.of(context).colorScheme.outline)),
        const SizedBox(height: 8),
        Row(children: [
          Text('小計 \$${(s["subtotal"] as num).toStringAsFixed(0)}', style: TextStyle(color: Theme.of(context).colorScheme.outline)),
          if ((s['tax_amount'] as num?) != null && (s['tax_amount'] as num) > 0) ...[
            const SizedBox(width: 16),
            Text('稅額 \$${(s["tax_amount"] as num).toStringAsFixed(0)}', style: TextStyle(color: Theme.of(context).colorScheme.outline)),
          ],
          const SizedBox(width: 16),
          Text('合計 \$${(s["total"] as num).toStringAsFixed(0)}', style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
        ]),
        if (s['note']?.toString().isNotEmpty == true) ...[
          const SizedBox(height: 4),
          Text('備註：${s["note"]}', style: TextStyle(fontSize: 12, color: Theme.of(context).colorScheme.outline)),
        ],
      ])),
      const SizedBox(height: 8), const Divider(height: 1),
      Expanded(child: ListView.builder(padding: const EdgeInsets.all(12), itemCount: lines.length, itemBuilder: (ctx, i) {
        final l = lines[i] as Map<String, dynamic>;
        return Card(child: Padding(padding: const EdgeInsets.all(12), child: Row(children: [
          Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(l['product_name']?.toString() ?? '', style: const TextStyle(fontWeight: FontWeight.w600)),
            if (l['spec']?.toString().isNotEmpty == true) Text(l['spec'].toString(), style: TextStyle(fontSize: 12, color: Theme.of(ctx).colorScheme.outline)),
          ])),
          Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
            Text('\$${l["unit_price"]} × ${l["quantity"]}', style: TextStyle(fontSize: 13, color: Theme.of(ctx).colorScheme.outline)),
            Text('\$${(l["line_total"] as num).toStringAsFixed(0)}', style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
          ]),
        ])));
      })),
    ]);
  }
}

// StatusBadge 已抽到 core/widgets/status_badge.dart
