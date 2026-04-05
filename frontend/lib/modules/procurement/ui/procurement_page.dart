import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/feature_flags.dart';
import '../../../core/router/app_router.dart';
import '../../../core/widgets/feature_locked_page.dart';
import '../../../core/widgets/status_badge.dart';
import '../../../core/widgets/supplier_history_dialog.dart';
import '../../../infrastructure/api/api_client.dart';
import '../../inventory/ui/inventory_page.dart';
import '../application/procurement_provider.dart';
import '../application/inquiry_provider.dart';
import 'inquiry_compare_table.dart';

class ProcurementPage extends ConsumerStatefulWidget {
  const ProcurementPage({super.key});

  @override
  ConsumerState<ProcurementPage> createState() => _ProcurementPageState();
}

class _ProcurementPageState extends ConsumerState<ProcurementPage> with SingleTickerProviderStateMixin {
  late TabController _tabCtrl;

  @override
  void initState() {
    super.initState();
    _tabCtrl = TabController(length: 3, vsync: this);
    Future.microtask(() {
      ref.read(poListProvider.notifier).load();
      ref.read(inquiryListProvider.notifier).load();
    });
  }

  @override
  void dispose() { _tabCtrl.dispose(); super.dispose(); }

  @override
  Widget build(BuildContext context) {
    final device = getDeviceClass(context);
    final level = FeatureFlags.getLevel('procurement', device);
    if (level == FeatureLevel.c) {
      return const FeatureLockedPage(featureName: '採購進貨', guidanceMessage: '請在桌面版操作');
    }

    return Column(
      children: [
        TabBar(controller: _tabCtrl, tabs: const [
          Tab(text: '採購單'),
          Tab(text: '詢價單'),
          Tab(text: '進貨驗收'),
        ]),
        Expanded(child: TabBarView(controller: _tabCtrl, children: const [
          _POTab(),
          _InquiryTab(),
          ReceiveTab(),
        ])),
      ],
    );
  }
}

// ═══════════════════════════════════════════════════════
// Tab 1: 採購單
// ═══════════════════════════════════════════════════════
class _POTab extends ConsumerWidget {
  const _POTab();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return const Row(
      children: [
        Expanded(flex: 2, child: _POListPanel()),
        VerticalDivider(width: 1),
        Expanded(flex: 3, child: _PODetailPanel()),
      ],
    );
  }
}

// ═══════════════════════════════════════════════════════
// Tab 2: 詢價單
// ═══════════════════════════════════════════════════════
class _InquiryTab extends ConsumerWidget {
  const _InquiryTab();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return const Row(
      children: [
        Expanded(flex: 2, child: _InquiryListPanel()),
        VerticalDivider(width: 1),
        Expanded(flex: 3, child: _InquiryDetailPanel()),
      ],
    );
  }
}

// ─── PO List ───────────────────────────────────────────
class _POListPanel extends ConsumerStatefulWidget {
  const _POListPanel();
  @override
  ConsumerState<_POListPanel> createState() => _POListPanelState();
}

class _POListPanelState extends ConsumerState<_POListPanel> {
  static const _statusLabels = {'': '全部', 'draft': '草稿', 'ordered': '已下單', 'partial_received': '部分到貨', 'received': '已完成', 'cancelled': '已取消'};
  static const _statusColors = {'draft': Colors.grey, 'ordered': Colors.blue, 'partial_received': Colors.orange, 'received': Colors.green, 'cancelled': Colors.red};
  String _filter = '';

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(poListProvider);
    return Column(children: [
      Padding(padding: const EdgeInsets.fromLTRB(16, 12, 16, 0), child: Row(children: [
        Text('採購單', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold)),
        const Spacer(),
        FilledButton.tonalIcon(onPressed: () => _showCreatePO(context), icon: const Icon(Icons.add, size: 18), label: const Text('建立')),
      ])),
      Padding(padding: const EdgeInsets.fromLTRB(12, 8, 12, 4), child: SingleChildScrollView(scrollDirection: Axis.horizontal, child: Row(
        children: _statusLabels.entries.map((e) => Padding(padding: const EdgeInsets.symmetric(horizontal: 3), child: ChoiceChip(
          label: Text(e.value, style: const TextStyle(fontSize: 12)), selected: e.key == _filter,
          onSelected: (_) { setState(() => _filter = e.key); ref.read(poListProvider.notifier).load(status: e.key.isEmpty ? null : e.key); },
        ))).toList(),
      ))),
      if (state.loading) const LinearProgressIndicator(),
      Expanded(child: state.orders.isEmpty ? Center(child: Text('沒有採購單', style: TextStyle(color: Theme.of(context).colorScheme.outline)))
        : ListView.builder(itemCount: state.orders.length, itemBuilder: (ctx, i) {
          final po = state.orders[i]; final s = po['status']?.toString() ?? '';
          return ListTile(dense: true,
            leading: CircleAvatar(radius: 16, backgroundColor: (_statusColors[s] ?? Colors.grey).withValues(alpha: 0.15),
              child: Icon(Icons.description_outlined, size: 16, color: _statusColors[s] ?? Colors.grey)),
            title: Text(po['supplier_name']?.toString() ?? '', style: const TextStyle(fontWeight: FontWeight.w600)),
            subtitle: Text('${_statusLabels[s] ?? s}  ·  ${po["line_count"]} 項  ·  \$${(po["total_amount"] as num?)?.toStringAsFixed(0) ?? "0"}',
              style: TextStyle(fontSize: 12, color: Theme.of(ctx).colorScheme.outline)),
            trailing: Text((po['created_at']?.toString() ?? '').length >= 10 ? po['created_at'].toString().substring(0, 10) : '',
              style: TextStyle(fontSize: 11, color: Theme.of(ctx).colorScheme.outline)),
            onTap: () => ref.read(poDetailProvider.notifier).load(po['po_id']?.toString() ?? ''),
          );
        })),
    ]);
  }

  void _showCreatePO(BuildContext context) async {
    final api = ref.read(apiClientProvider);
    List<Map<String, dynamic>> suppliers = [];
    try { final res = await api.get('/suppliers/'); suppliers = ((res.data as Map)['data'] as List).cast<Map<String, dynamic>>(); } catch (_) {}
    if (!mounted) return;
    if (suppliers.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('請先建立供應商')));
      return;
    }
    String? supId; final noteCtrl = TextEditingController();
    showDialog(context: context, builder: (ctx) => StatefulBuilder(builder: (ctx, ss) => AlertDialog(
      title: const Text('建立採購單'), content: SizedBox(width: 400, child: Column(mainAxisSize: MainAxisSize.min, children: [
        DropdownButtonFormField<String>(value: supId, decoration: const InputDecoration(labelText: '供應商', border: OutlineInputBorder()),
          items: suppliers.map((s) => DropdownMenuItem(value: s['supplier_id']?.toString(), child: Text(s['name']?.toString() ?? ''))).toList(),
          onChanged: (v) => ss(() => supId = v)),
        const SizedBox(height: 12), TextField(controller: noteCtrl, decoration: const InputDecoration(labelText: '備註', border: OutlineInputBorder())),
      ])), actions: [
        TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('取消')),
        FilledButton(onPressed: () async {
          if (supId == null) return;
          try { await api.post('/purchase-orders/', data: {'supplier_id': supId, 'note': noteCtrl.text.isEmpty ? null : noteCtrl.text, 'lines': []});
            if (ctx.mounted) Navigator.pop(ctx); ref.read(poListProvider.notifier).load();
          } catch (e) { if (ctx.mounted) ScaffoldMessenger.of(ctx).showSnackBar(SnackBar(content: Text('失敗: $e'))); }
        }, child: const Text('建立')),
      ],
    )));
  }
}

// ─── PO Detail ─────────────────────────────────────────
class _PODetailPanel extends ConsumerWidget {
  const _PODetailPanel();
  static const _statusLabels = {'draft': '草稿', 'ordered': '已下單', 'partial_received': '部分到貨', 'received': '已完成', 'cancelled': '已取消'};

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(poDetailProvider);
    if (state.loading) return const Center(child: CircularProgressIndicator());
    if (state.data == null) return Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
      Icon(Icons.touch_app, size: 48, color: Theme.of(context).colorScheme.outline.withValues(alpha: 0.4)),
      const SizedBox(height: 12),
      Text('點左側列表選擇一張採購單', style: TextStyle(fontSize: 16, color: Theme.of(context).colorScheme.outline)),
    ]));

    final po = state.data!; final poId = po['po_id']?.toString() ?? ''; final s = po['status']?.toString() ?? '';
    final lines = (po['lines'] as List?) ?? [];

    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Padding(padding: const EdgeInsets.fromLTRB(24, 16, 24, 0), child: Row(children: [
        Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          InkWell(
            onTap: () {
              final api = ref.read(apiClientProvider);
              showSupplierHistory(context, api,
                supplierId: po['supplier_id']?.toString() ?? '',
                supplierName: po['supplier_name']?.toString() ?? '');
            },
            child: Row(mainAxisSize: MainAxisSize.min, children: [
              Text(po['supplier_name']?.toString() ?? '', style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
              const SizedBox(width: 4),
              Icon(Icons.history, size: 16, color: Theme.of(context).colorScheme.outline),
            ]),
          ),
          const SizedBox(height: 4),
          Row(children: [StatusBadge(status: s), const SizedBox(width: 12),
            Text('${lines.length} 項', style: TextStyle(fontSize: 13, color: Theme.of(context).colorScheme.outline)),
            const SizedBox(width: 12),
            Text('訂購 \$${(po['ordered_total'] as num?)?.toStringAsFixed(0) ?? '0'}',
              style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: Colors.blue.shade700)),
            if ((po['received_total'] as num?) != null && (po['received_total'] as num) > 0) ...[
              const SizedBox(width: 8),
              Text('已收 \$${(po['received_total'] as num).toStringAsFixed(0)}',
                style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: Colors.green.shade700)),
            ],
          ]),
        ])),
        if (s == 'draft') ...[
          FilledButton.tonalIcon(onPressed: () => _addLine(context, ref, poId), icon: const Icon(Icons.add, size: 18), label: const Text('加品項')),
          const SizedBox(width: 8),
          FilledButton(onPressed: () async { await ref.read(poDetailProvider.notifier).confirm(poId); ref.read(poListProvider.notifier).load(); }, child: const Text('確認下單')),
          const SizedBox(width: 8),
          TextButton(onPressed: () async { await ref.read(poDetailProvider.notifier).cancel(poId); ref.read(poListProvider.notifier).load(); },
            child: const Text('取消', style: TextStyle(color: Colors.red))),
        ],
        if (s == 'ordered' || s == 'partial_received')
          FilledButton.icon(onPressed: () => _receive(context, ref, poId, lines), icon: const Icon(Icons.check_circle_outline), label: const Text('驗收')),
        if (s == 'cancelled')
          TextButton.icon(
            icon: const Icon(Icons.delete_outline, size: 18),
            label: const Text('刪除'),
            style: TextButton.styleFrom(foregroundColor: Colors.red),
            onPressed: () async {
              final confirmed = await showDialog<bool>(context: context, builder: (ctx) => AlertDialog(
                title: const Text('確認刪除'),
                content: const Text('刪除後無法恢復，確定要刪除這張採購單嗎？'),
                actions: [
                  TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('取消')),
                  FilledButton(style: FilledButton.styleFrom(backgroundColor: Colors.red),
                    onPressed: () => Navigator.pop(ctx, true), child: const Text('刪除')),
                ],
              ));
              if (confirmed == true) {
                final api = ref.read(apiClientProvider);
                try {
                  await api.delete('/purchase-orders/$poId');
                  ref.read(poDetailProvider.notifier).clear();
                  ref.read(poListProvider.notifier).load();
                } catch (e) {
                  if (context.mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('刪除失敗: $e')));
                }
              }
            },
          ),
      ])),
      if (state.error != null) Padding(padding: const EdgeInsets.fromLTRB(24, 8, 24, 0), child: Text(state.error!, style: TextStyle(color: Colors.red.shade700, fontSize: 13))),
      const SizedBox(height: 8), const Divider(height: 1),
      Expanded(child: lines.isEmpty ? Center(child: Text(s == 'draft' ? '點「加品項」' : '無明細', style: TextStyle(color: Theme.of(context).colorScheme.outline)))
        : ListView.builder(padding: const EdgeInsets.all(12), itemCount: lines.length, itemBuilder: (ctx, i) {
          final l = lines[i] as Map<String, dynamic>; final ordered = l['ordered_quantity'] as num? ?? 0; final received = l['received_quantity'] as num? ?? 0;
          final done = received >= ordered;
          return Card(color: done ? Colors.green.withValues(alpha: 0.03) : null, child: Padding(padding: const EdgeInsets.all(12), child: Row(children: [
            Icon(done ? Icons.check_circle : Icons.radio_button_unchecked, size: 20, color: done ? Colors.green : Colors.grey),
            const SizedBox(width: 12),
            Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('${l["brand"] ?? ""} ${l["product_name"] ?? ""}', style: const TextStyle(fontWeight: FontWeight.w600)),
              Text('${l["spec"] ?? ""}  ·  ${l["unit"] ?? "個"}', style: TextStyle(fontSize: 12, color: Theme.of(ctx).colorScheme.outline)),
            ])),
            Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
              Text('訂 $ordered / 收 $received', style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: done ? Colors.green.shade700 : null)),
              if (l['unit_cost'] != null) Text('\$${l["unit_cost"]} × $ordered = \$${((l["line_total"] as num?) ?? 0).toStringAsFixed(0)}',
                style: TextStyle(fontSize: 12, color: Theme.of(ctx).colorScheme.outline)),
            ]),
          ])));
        })),
    ]);
  }

  void _addLine(BuildContext context, WidgetRef ref, String poId) {
    final searchCtrl = TextEditingController(); List<Map<String, dynamic>> results = [];
    final api = ref.read(apiClientProvider);
    showDialog(context: context, builder: (ctx) => StatefulBuilder(builder: (ctx, ss) => AlertDialog(
      title: const Text('搜尋品項'), content: SizedBox(width: 500, height: 400, child: Column(children: [
        TextField(controller: searchCtrl, autofocus: true, decoration: const InputDecoration(labelText: '搜尋', prefixIcon: Icon(Icons.search), border: OutlineInputBorder()),
          onSubmitted: (q) async { if (q.isEmpty) return; try { final res = await api.get('/products/search', queryParameters: {'q': q});
            ss(() => results = ((res.data as Map)['data'] as List).cast<Map<String, dynamic>>()); } catch (_) {} }),
        const SizedBox(height: 8),
        Expanded(child: ListView.builder(itemCount: results.length, itemBuilder: (ctx, i) {
          final item = results[i];
          return ListTile(dense: true, title: Text('${item["brand"] ?? ""} ${item["name"]}'), subtitle: Text(item['spec']?.toString() ?? ''),
            trailing: Text('\$${item["sell_price"] ?? 0}'), onTap: () {
              final qtyCtrl = TextEditingController(text: '1'); final costCtrl = TextEditingController(text: item['cost_price']?.toString() ?? '');
              showDialog(context: ctx, builder: (c2) => AlertDialog(title: Text('${item["name"]}'), content: SizedBox(width: 300, child: Column(mainAxisSize: MainAxisSize.min, children: [
                TextField(controller: qtyCtrl, autofocus: true, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: '數量', border: OutlineInputBorder())),
                const SizedBox(height: 12), TextField(controller: costCtrl, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: '單價', prefixText: '\$', border: OutlineInputBorder())),
              ])), actions: [TextButton(onPressed: () => Navigator.pop(c2), child: const Text('取消')),
                FilledButton(onPressed: () async { try { await api.put('/purchase-orders/$poId', data: {'new_lines': [{'sku_id': item['sku_id'], 'ordered_quantity': int.tryParse(qtyCtrl.text) ?? 1, 'unit_cost': double.tryParse(costCtrl.text)}]});
                  if (c2.mounted) Navigator.pop(c2); if (ctx.mounted) Navigator.pop(ctx); ref.read(poDetailProvider.notifier).load(poId); ref.read(poListProvider.notifier).load();
                } catch (e) { if (c2.mounted) ScaffoldMessenger.of(c2).showSnackBar(SnackBar(content: Text('失敗: $e'))); } }, child: const Text('加入'))],
              ));
            });
        })),
      ])), actions: [TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('關閉'))],
    )));
  }

  void _receive(BuildContext context, WidgetRef ref, String poId, List lines) {
    final pending = lines.where((l) { final m = l as Map; return (m['received_quantity'] as num? ?? 0) < (m['ordered_quantity'] as num? ?? 0); }).toList();
    if (pending.isEmpty) { ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('已全部驗收'))); return; }
    final ctrls = pending.map((l) { final m = l as Map; return TextEditingController(text: ((m['ordered_quantity'] as num) - (m['received_quantity'] as num)).toInt().toString()); }).toList();
    final noteCtrl = TextEditingController();
    showDialog(context: context, builder: (ctx) => AlertDialog(title: const Text('驗收到貨'), content: SizedBox(width: 500, child: SingleChildScrollView(child: Column(mainAxisSize: MainAxisSize.min, children: [
      ...pending.asMap().entries.map((e) { final l = e.value as Map<String, dynamic>;
        return Padding(padding: const EdgeInsets.only(bottom: 12), child: Row(children: [
          Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('${l["brand"] ?? ""} ${l["product_name"]}', style: const TextStyle(fontWeight: FontWeight.w600)),
            Text('訂 ${l["ordered_quantity"]} / 已收 ${l["received_quantity"]}', style: TextStyle(fontSize: 12, color: Theme.of(ctx).colorScheme.outline)),
          ])), SizedBox(width: 80, child: TextField(controller: ctrls[e.key], keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: '本次收', border: OutlineInputBorder(), isDense: true))),
        ])); }),
      const SizedBox(height: 8), TextField(controller: noteCtrl, decoration: const InputDecoration(labelText: '備註', border: OutlineInputBorder())),
    ]))), actions: [
      TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('取消')),
      FilledButton(onPressed: () async {
        final rl = <Map<String, dynamic>>[]; for (var i = 0; i < pending.length; i++) { final q = int.tryParse(ctrls[i].text) ?? 0; if (q > 0) rl.add({'po_line_id': (pending[i] as Map)['po_line_id'], 'received_quantity': q}); }
        if (rl.isEmpty) return; final ok = await ref.read(poDetailProvider.notifier).receive(poId, rl, noteCtrl.text.isEmpty ? null : noteCtrl.text);
        if (ok && ctx.mounted) { Navigator.pop(ctx); ref.read(poListProvider.notifier).load(); ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('驗收完成'))); }
      }, child: const Text('確認驗收')),
    ]));
  }
}

// ─── Inquiry List ──────────────────────────────────────
class _InquiryListPanel extends ConsumerWidget {
  const _InquiryListPanel();
  static const _statusLabels = {'draft': '草稿', 'quoting': '詢價中', 'decided': '已決定', 'converted': '已轉單', 'cancelled': '已取消'};
  static const _statusColors = {'draft': Colors.grey, 'quoting': Colors.blue, 'decided': Colors.orange, 'converted': Colors.green, 'cancelled': Colors.red};

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(inquiryListProvider);
    return Column(children: [
      Padding(padding: const EdgeInsets.fromLTRB(16, 12, 16, 0), child: Row(children: [
        Text('詢價單', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold)),
        const Spacer(),
        FilledButton.tonalIcon(onPressed: () => _showCreate(context, ref), icon: const Icon(Icons.add, size: 18), label: const Text('建立詢價')),
      ])),
      const SizedBox(height: 8),
      if (state.loading) const LinearProgressIndicator(),
      Expanded(child: state.inquiries.isEmpty ? Center(child: Text('沒有詢價單', style: TextStyle(color: Theme.of(context).colorScheme.outline)))
        : ListView.builder(itemCount: state.inquiries.length, itemBuilder: (ctx, i) {
          final inq = state.inquiries[i]; final s = inq['status']?.toString() ?? '';
          return ListTile(dense: true,
            leading: CircleAvatar(radius: 16, backgroundColor: (_statusColors[s] ?? Colors.grey).withValues(alpha: 0.15),
              child: Icon(Icons.request_quote_outlined, size: 16, color: _statusColors[s] ?? Colors.grey)),
            title: Text(inq['title']?.toString() ?? '', style: const TextStyle(fontWeight: FontWeight.w600)),
            subtitle: Text('${_statusLabels[s] ?? s}  ·  ${inq["line_count"]} 品項  ·  ${inq["quote_count"]} 筆報價',
              style: TextStyle(fontSize: 12, color: Theme.of(ctx).colorScheme.outline)),
            onTap: () => ref.read(inquiryDetailProvider.notifier).load(inq['inquiry_id']?.toString() ?? ''),
          );
        })),
    ]);
  }

  void _showCreate(BuildContext context, WidgetRef ref) {
    final titleCtrl = TextEditingController(); final noteCtrl = TextEditingController();
    showDialog(context: context, builder: (ctx) => AlertDialog(
      title: const Text('建立詢價單'), content: SizedBox(width: 400, child: Column(mainAxisSize: MainAxisSize.min, children: [
        TextField(controller: titleCtrl, autofocus: true, decoration: const InputDecoration(labelText: '標題（如：4月電線詢價）', border: OutlineInputBorder())),
        const SizedBox(height: 12), TextField(controller: noteCtrl, decoration: const InputDecoration(labelText: '備註', border: OutlineInputBorder())),
      ])), actions: [
        TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('取消')),
        FilledButton(onPressed: () async {
          if (titleCtrl.text.trim().isEmpty) return;
          final api = ref.read(apiClientProvider);
          try { await api.post('/inquiries/', data: {'title': titleCtrl.text.trim(), 'note': noteCtrl.text.isEmpty ? null : noteCtrl.text});
            if (ctx.mounted) Navigator.pop(ctx); ref.read(inquiryListProvider.notifier).load();
          } catch (e) { if (ctx.mounted) ScaffoldMessenger.of(ctx).showSnackBar(SnackBar(content: Text('失敗: $e'))); }
        }, child: const Text('建立')),
      ],
    ));
  }
}

// ─── Inquiry Detail ────────────────────────────────────
class _InquiryDetailPanel extends ConsumerStatefulWidget {
  const _InquiryDetailPanel();
  @override
  ConsumerState<_InquiryDetailPanel> createState() => _InquiryDetailPanelState();
}

class _InquiryDetailPanelState extends ConsumerState<_InquiryDetailPanel> {
  bool _showTable = false;
  static const _statusLabels = {'draft': '草稿', 'quoting': '詢價中', 'decided': '已決定', 'converted': '已轉單', 'cancelled': '已取消'};

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(inquiryDetailProvider);
    if (state.loading) return const Center(child: CircularProgressIndicator());
    if (state.data == null) return Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
      Icon(Icons.touch_app, size: 48, color: Theme.of(context).colorScheme.outline.withValues(alpha: 0.4)),
      const SizedBox(height: 12),
      Text('點左側列表選擇一張詢價單', style: TextStyle(fontSize: 16, color: Theme.of(context).colorScheme.outline)),
    ]));

    final inq = state.data!; final id = inq['inquiry_id']?.toString() ?? ''; final s = inq['status']?.toString() ?? '';
    final lines = (inq['lines'] as List?) ?? [];
    final api = ref.read(apiClientProvider);

    // 收集已選取的 quote IDs
    final selectedIds = <String>{};
    for (final l in lines) {
      for (final q in ((l as Map)['quotes'] as List?) ?? []) {
        if ((q as Map)['is_selected'] == true) selectedIds.add(q['quote_id'].toString());
      }
    }

    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Padding(padding: const EdgeInsets.fromLTRB(24, 16, 24, 0), child: Row(children: [
        Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(inq['title']?.toString() ?? '', style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
          const SizedBox(height: 4), StatusBadge(status: s),
        ])),
        // 比價表格切換
        if (lines.isNotEmpty) ...[
          ChoiceChip(label: const Text('清單'), selected: !_showTable,
            onSelected: (_) => setState(() => _showTable = false)),
          const SizedBox(width: 4),
          ChoiceChip(label: const Text('比價表'), selected: _showTable,
            onSelected: (_) => setState(() => _showTable = true)),
          const SizedBox(width: 12),
        ],
        if (s == 'draft' || s == 'quoting') ...[
          FilledButton.tonalIcon(onPressed: () => _addItem(context, ref, api, id), icon: const Icon(Icons.add, size: 18), label: const Text('加品項')),
          const SizedBox(width: 8),
        ],
        if (s == 'decided')
          FilledButton.icon(onPressed: () => _convert(context, ref, api, id), icon: const Icon(Icons.transform), label: const Text('轉採購單')),
        if (s != 'converted' && s != 'cancelled') ...[
          const SizedBox(width: 8),
          TextButton(onPressed: () async { await api.post('/inquiries/$id/cancel'); ref.read(inquiryDetailProvider.notifier).load(id); ref.read(inquiryListProvider.notifier).load(); },
            child: const Text('取消', style: TextStyle(color: Colors.red))),
        ],
      ])),
      const SizedBox(height: 8), const Divider(height: 1),

      // 比價表格 or 清單
      if (_showTable)
        Expanded(child: InquiryCompareTable(
          lines: lines,
          selectedQuoteIds: selectedIds,
          onToggleSelect: (s == 'quoting' || s == 'decided') ? (qid) {
            final toggled = Set<String>.from(selectedIds);
            if (toggled.contains(qid)) { toggled.remove(qid); } else { toggled.add(qid); }
            api.post('/inquiries/$id/select', data: {'quote_ids': toggled.toList()});
            ref.read(inquiryDetailProvider.notifier).load(id);
            ref.read(inquiryListProvider.notifier).load();
          } : null,
        ))
      else
      Expanded(child: lines.isEmpty ? Center(child: Text('點「加品項」新增要詢價的品項', style: TextStyle(color: Theme.of(context).colorScheme.outline)))
        : ListView.builder(padding: const EdgeInsets.all(12), itemCount: lines.length, itemBuilder: (ctx, i) {
          final l = lines[i] as Map<String, dynamic>;
          final quotes = (l['quotes'] as List?) ?? [];
          return Card(child: Padding(padding: const EdgeInsets.all(12), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('${l["brand"] ?? ""} ${l["product_name"] ?? ""}', style: const TextStyle(fontWeight: FontWeight.w600)),
                Text('${l["spec"] ?? ""}  ·  需求 ${l["quantity"]} ${l["unit"] ?? "個"}', style: TextStyle(fontSize: 12, color: Theme.of(ctx).colorScheme.outline)),
              ])),
              if (s == 'draft' || s == 'quoting')
                IconButton(icon: const Icon(Icons.add_circle_outline, size: 20), tooltip: '新增報價',
                  onPressed: () => _addQuote(context, ref, api, id, l['line_id']?.toString() ?? '')),
            ]),
            if (quotes.isNotEmpty) ...[
              const SizedBox(height: 8),
              ...quotes.map((q) {
                final qm = q as Map<String, dynamic>;
                final selected = qm['is_selected'] == true;
                final canSelect = s == 'quoting' || s == 'decided';
                return InkWell(
                  onTap: canSelect ? () => _toggleSelect(ref, api, id, inq, qm) : null,
                  child: Container(
                    margin: const EdgeInsets.only(bottom: 4),
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                    decoration: BoxDecoration(
                      color: selected ? Colors.green.withValues(alpha: 0.08) : Colors.grey.withValues(alpha: 0.04),
                      borderRadius: BorderRadius.circular(6),
                      border: selected ? Border.all(color: Colors.green.shade300) : null,
                    ),
                    child: Row(children: [
                      Icon(selected ? Icons.check_circle : Icons.radio_button_unchecked, size: 18, color: selected ? Colors.green : Colors.grey),
                      const SizedBox(width: 8),
                      Expanded(child: Text(qm['supplier_name']?.toString() ?? '')),
                      Text('\$${qm["unit_price"]}', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold,
                        color: selected ? Colors.green.shade700 : null)),
                      if (qm['note']?.toString().isNotEmpty == true)
                        Padding(padding: const EdgeInsets.only(left: 8), child: Text(qm['note'].toString(),
                          style: TextStyle(fontSize: 11, color: Theme.of(ctx).colorScheme.outline))),
                    ]),
                  ),
                );
              }),
            ],
          ])));
        })),
    ]);
  }

  void _addItem(BuildContext context, WidgetRef ref, ApiClient api, String inquiryId) {
    final searchCtrl = TextEditingController(); List<Map<String, dynamic>> results = [];
    showDialog(context: context, builder: (ctx) => StatefulBuilder(builder: (ctx, ss) => AlertDialog(
      title: const Text('搜尋品項加入詢價'), content: SizedBox(width: 500, height: 400, child: Column(children: [
        TextField(controller: searchCtrl, autofocus: true, decoration: const InputDecoration(labelText: '搜尋品項', prefixIcon: Icon(Icons.search), border: OutlineInputBorder()),
          onSubmitted: (q) async { if (q.isEmpty) return; try { final res = await api.get('/products/search', queryParameters: {'q': q});
            ss(() => results = ((res.data as Map)['data'] as List).cast<Map<String, dynamic>>()); } catch (_) {} }),
        const SizedBox(height: 8),
        Expanded(child: ListView.builder(itemCount: results.length, itemBuilder: (ctx, i) {
          final item = results[i];
          return ListTile(dense: true, title: Text('${item["brand"] ?? ""} ${item["name"]}'), subtitle: Text(item['spec']?.toString() ?? ''),
            onTap: () {
              final qtyCtrl = TextEditingController(text: '1');
              showDialog(context: ctx, builder: (c2) => AlertDialog(title: Text('${item["name"]}'), content: TextField(controller: qtyCtrl, autofocus: true,
                keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: '需求數量', border: OutlineInputBorder())),
                actions: [TextButton(onPressed: () => Navigator.pop(c2), child: const Text('取消')),
                  FilledButton(onPressed: () async { try { await api.post('/inquiries/$inquiryId/lines', data: {'sku_id': item['sku_id'], 'quantity': int.tryParse(qtyCtrl.text) ?? 1});
                    if (c2.mounted) Navigator.pop(c2); if (ctx.mounted) Navigator.pop(ctx); ref.read(inquiryDetailProvider.notifier).load(inquiryId);
                  } catch (e) { if (c2.mounted) ScaffoldMessenger.of(c2).showSnackBar(SnackBar(content: Text('失敗: $e'))); } }, child: const Text('加入'))],
              ));
            });
        })),
      ])), actions: [TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('關閉'))],
    )));
  }

  void _addQuote(BuildContext context, WidgetRef ref, ApiClient api, String inquiryId, String lineId) async {
    List<Map<String, dynamic>> suppliers = [];
    try { final res = await api.get('/suppliers/'); suppliers = ((res.data as Map)['data'] as List).cast<Map<String, dynamic>>(); } catch (_) {}
    if (suppliers.isEmpty) return;
    String? supId; final priceCtrl = TextEditingController(); final noteCtrl = TextEditingController();
    showDialog(context: context, builder: (ctx) => StatefulBuilder(builder: (ctx, ss) => AlertDialog(
      title: const Text('記錄供應商報價'), content: SizedBox(width: 400, child: Column(mainAxisSize: MainAxisSize.min, children: [
        DropdownButtonFormField<String>(value: supId, decoration: const InputDecoration(labelText: '供應商', border: OutlineInputBorder()),
          items: suppliers.map((s) => DropdownMenuItem(value: s['supplier_id']?.toString(), child: Text(s['name']?.toString() ?? ''))).toList(),
          onChanged: (v) => ss(() => supId = v)),
        const SizedBox(height: 12),
        TextField(controller: priceCtrl, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: '報價單價', prefixText: '\$', border: OutlineInputBorder())),
        const SizedBox(height: 12),
        TextField(controller: noteCtrl, decoration: const InputDecoration(labelText: '備註', border: OutlineInputBorder())),
      ])), actions: [
        TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('取消')),
        FilledButton(onPressed: () async {
          if (supId == null || priceCtrl.text.isEmpty) return;
          try { await api.post('/inquiries/$inquiryId/quotes', data: {'line_id': lineId, 'supplier_id': supId, 'unit_price': double.parse(priceCtrl.text), 'note': noteCtrl.text.isEmpty ? null : noteCtrl.text});
            if (ctx.mounted) Navigator.pop(ctx); ref.read(inquiryDetailProvider.notifier).load(inquiryId);
          } catch (e) { if (ctx.mounted) ScaffoldMessenger.of(ctx).showSnackBar(SnackBar(content: Text('失敗: $e'))); }
        }, child: const Text('記錄')),
      ],
    )));
  }

  void _toggleSelect(WidgetRef ref, ApiClient api, String inquiryId, Map<String, dynamic> inq, Map<String, dynamic> quote) async {
    // 收集當前所有 selected 的 quote_ids
    final lines = (inq['lines'] as List?) ?? [];
    final selectedIds = <String>{};
    for (final l in lines) {
      for (final q in ((l as Map)['quotes'] as List?) ?? []) {
        if ((q as Map)['is_selected'] == true) selectedIds.add(q['quote_id'].toString());
      }
    }

    final qid = quote['quote_id'].toString();
    if (selectedIds.contains(qid)) {
      selectedIds.remove(qid);
    } else {
      selectedIds.add(qid);
    }

    await api.post('/inquiries/$inquiryId/select', data: {'quote_ids': selectedIds.toList()});
    ref.read(inquiryDetailProvider.notifier).load(inquiryId);
    ref.read(inquiryListProvider.notifier).load();
  }

  void _convert(BuildContext context, WidgetRef ref, ApiClient api, String inquiryId) {
    showDialog(context: context, builder: (ctx) => AlertDialog(
      title: const Text('確認轉採購單'),
      content: const Text('將已選取的報價轉成採購單（按供應商分組）。\n\n確定要轉單嗎？'),
      actions: [
        TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('取消')),
        FilledButton(onPressed: () async {
          Navigator.pop(ctx);
          try {
            final res = await api.post('/inquiries/$inquiryId/convert');
            final body = res.data as Map<String, dynamic>;
            final poCount = (body['data']?['po_ids'] as List?)?.length ?? 0;
            ref.read(inquiryDetailProvider.notifier).load(inquiryId);
            ref.read(inquiryListProvider.notifier).load();
            ref.read(poListProvider.notifier).load();
            if (context.mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('已轉成 $poCount 張採購單，可切到「採購單」Tab 查看')));
          } catch (e) { if (context.mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('轉單失敗: $e'))); }
        }, child: const Text('確認轉單')),
      ],
    ));
  }
}

// StatusBadge 已抽到 core/widgets/status_badge.dart
