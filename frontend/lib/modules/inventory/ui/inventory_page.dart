import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/feature_flags.dart';
import '../../../core/router/app_router.dart';
import '../../../modules/pos/application/pos_provider.dart';
import '../../../infrastructure/api/api_client.dart';
import '../application/inventory_provider.dart';

class InventoryPage extends ConsumerStatefulWidget {
  const InventoryPage({super.key});

  @override
  ConsumerState<InventoryPage> createState() => _InventoryPageState();
}

class _InventoryPageState extends ConsumerState<InventoryPage> {
  @override
  void initState() {
    super.initState();
    Future.microtask(() => ref.read(inventoryProvider.notifier).load());
  }

  @override
  Widget build(BuildContext context) {
    final device = getDeviceClass(context);
    return switch (device) {
      DeviceClass.desktop => _InventoryDesktopLayout(),
      DeviceClass.tablet => _InventoryDesktopLayout(),
      DeviceClass.phone => const _InventoryListTab(),
    };
  }
}

class _InventoryDesktopLayout extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return DefaultTabController(
      length: 2,
      child: Row(
        children: [
          Expanded(
            flex: 3,
            child: Column(
              children: const [
                TabBar(tabs: [
                  Tab(icon: Icon(Icons.warehouse), text: '庫存查詢'),
                  Tab(icon: Icon(Icons.fact_check), text: '盤點'),
                ]),
                Expanded(child: TabBarView(children: [
                  _InventoryListTab(),
                  CountTab(),
                ])),
              ],
            ),
          ),
          const VerticalDivider(width: 1),
          const Expanded(flex: 2, child: _MovementPanel()),
        ],
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════
// Tab 1: 庫存查詢
// ═══════════════════════════════════════════════════════
class _InventoryListTab extends ConsumerStatefulWidget {
  const _InventoryListTab();
  @override
  ConsumerState<_InventoryListTab> createState() => _InventoryListTabState();
}

class _InventoryListTabState extends ConsumerState<_InventoryListTab> {
  final _searchCtrl = TextEditingController();
  bool _lowStockOnly = false;

  @override
  void dispose() { _searchCtrl.dispose(); super.dispose(); }

  void _doSearch() {
    ref.read(inventoryProvider.notifier).load(
      keyword: _searchCtrl.text.trim().isEmpty ? null : _searchCtrl.text.trim(),
      lowStockOnly: _lowStockOnly,
    );
  }

  @override
  Widget build(BuildContext context) {
    final invState = ref.watch(inventoryProvider);
    final selectedSku = ref.watch(movementsProvider).selectedSkuId;
    final summary = invState.summary;

    return Column(
      children: [
        // 摘要列
        if (summary != null)
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
            color: Theme.of(context).colorScheme.surfaceContainerHighest.withValues(alpha: 0.5),
            child: Row(children: [
              _SummaryChip(label: '品項數', value: '${summary['total_items'] ?? 0}'),
              const SizedBox(width: 16),
              _SummaryChip(label: '庫存總值', value: '\$${_fmt(summary['total_value'])}'),
              const SizedBox(width: 16),
              _SummaryChip(label: '低庫存', value: '${summary['low_stock_count'] ?? 0}', color: Colors.orange),
              const SizedBox(width: 16),
              _SummaryChip(label: '零庫存', value: '${summary['zero_stock_count'] ?? 0}', color: Colors.red),
            ]),
          ),
        // 搜尋列
        Padding(
          padding: const EdgeInsets.all(12),
          child: Row(children: [
            Expanded(child: TextField(
              controller: _searchCtrl,
              decoration: InputDecoration(
                hintText: '搜尋品名、品牌、規格、條碼...',
                prefixIcon: const Icon(Icons.search),
                suffixIcon: _searchCtrl.text.isNotEmpty
                    ? IconButton(icon: const Icon(Icons.clear), onPressed: () {
                        _searchCtrl.clear(); _doSearch(); setState(() {});
                      })
                    : null,
                border: const OutlineInputBorder(), isDense: true,
              ),
              onSubmitted: (_) { _doSearch(); setState(() {}); },
            )),
            const SizedBox(width: 8),
            FilterChip(
              label: const Text('僅低庫存'),
              selected: _lowStockOnly,
              onSelected: (v) { setState(() => _lowStockOnly = v); _doSearch(); },
            ),
            const SizedBox(width: 8),
            IconButton(icon: const Icon(Icons.refresh), onPressed: _doSearch),
          ]),
        ),
        Container(
          color: Theme.of(context).colorScheme.surfaceContainerHighest,
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          child: const Row(children: [
            Expanded(flex: 3, child: Text('品名', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 13))),
            Expanded(flex: 1, child: Text('規格', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 13))),
            SizedBox(width: 70, child: Text('售價', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 13), textAlign: TextAlign.right)),
            SizedBox(width: 70, child: Text('庫存', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 13), textAlign: TextAlign.right)),
          ]),
        ),
        Expanded(
          child: invState.loading
              ? const Center(child: CircularProgressIndicator())
              : ListView.builder(
                  itemCount: invState.items.length,
                  itemBuilder: (context, index) {
                    final item = invState.items[index];
                    final skuId = (item['sku_id'] ?? '').toString();
                    final isSelected = skuId == selectedSku;
                    final stock = item['current_stock'] as num? ?? 0;
                    final minStock = item['min_stock'] as num?;
                    final isLow = minStock != null && stock <= minStock;

                    return Material(
                      color: isSelected ? Theme.of(context).colorScheme.primaryContainer.withOpacity(0.3) : null,
                      child: InkWell(
                        onTap: () => ref.read(movementsProvider.notifier).loadForSku(skuId),
                        child: Padding(
                          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                          child: Row(children: [
                            Expanded(flex: 3, child: Text((item['product_name'] ?? '').toString(), style: const TextStyle(fontSize: 15))),
                            Expanded(flex: 1, child: Text((item['spec'] ?? '').toString(),
                                style: TextStyle(fontSize: 13, color: Theme.of(context).colorScheme.outline))),
                            SizedBox(width: 70, child: Text('\$${item['sell_price'] ?? 0}',
                                textAlign: TextAlign.right, style: const TextStyle(fontSize: 14))),
                            SizedBox(width: 70, child: Text('$stock', textAlign: TextAlign.right,
                                style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold,
                                    color: isLow ? Colors.red : (stock <= 0 ? Colors.orange : null)))),
                          ]),
                        ),
                      ),
                    );
                  },
                ),
        ),
      ],
    );
  }
}

// ═══════════════════════════════════════════════════════
// Tab 2: 進貨驗收
// ═══════════════════════════════════════════════════════
class ReceiveTab extends ConsumerStatefulWidget {
  const ReceiveTab();
  @override
  ConsumerState<ReceiveTab> createState() => _ReceiveTabState();
}

class _ReceiveTabState extends ConsumerState<ReceiveTab> {
  final _searchCtrl = TextEditingController();

  @override
  void dispose() { _searchCtrl.dispose(); super.dispose(); }

  void _showSupplierAndSubmit(BuildContext context, WidgetRef ref) {
    final api = ref.read(apiClientProvider);
    showDialog(
      context: context,
      builder: (ctx) => FutureBuilder(
        future: api.get('/suppliers/'),
        builder: (ctx, snapshot) {
          if (!snapshot.hasData) return const AlertDialog(content: Center(child: CircularProgressIndicator()));
          final suppliers = ((snapshot.data!.data as Map)['data'] as List).cast<Map<String, dynamic>>();
          if (suppliers.isEmpty) {
            return AlertDialog(title: const Text('沒有供應商'), content: const Text('請先在系統設定中新增供應商'),
              actions: [TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('關閉'))]);
          }
          return AlertDialog(
            title: const Text('選擇供應商'),
            content: SizedBox(width: 300, height: 300,
              child: ListView(children: suppliers.map((s) => ListTile(
                title: Text(s['name']?.toString() ?? ''),
                subtitle: Text(s['phone']?.toString() ?? ''),
                onTap: () {
                  Navigator.pop(ctx);
                  ref.read(receiveProvider.notifier).submit(s['supplier_id'].toString());
                },
              )).toList())),
          );
        },
      ),
    );
  }

  Future<void> _searchAndAdd() async {
    final keyword = _searchCtrl.text.trim();
    if (keyword.isEmpty) return;
    await ref.read(posSearchProvider.notifier).search(keyword);
    final results = ref.read(posSearchProvider).results;
    if (results.length == 1) {
      _addLine(results[0]);
      _searchCtrl.clear();
      ref.read(posSearchProvider.notifier).clear();
    }
  }

  void _addLine(Map<String, dynamic> item) {
    ref.read(receiveProvider.notifier).addLine(ReceiveLine(
      skuId: (item['sku_id'] ?? '').toString(),
      productName: (item['name'] ?? '').toString(),
    ));
  }

  @override
  Widget build(BuildContext context) {
    final rcvState = ref.watch(receiveProvider);
    final searchState = ref.watch(posSearchProvider);

    if (rcvState.successMessage != null) {
      return Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
        const Icon(Icons.check_circle, size: 72, color: Colors.green),
        const SizedBox(height: 12),
        Text(rcvState.successMessage!, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
        const SizedBox(height: 24),
        ElevatedButton(onPressed: () {
          ref.read(receiveProvider.notifier).clear();
          ref.read(inventoryProvider.notifier).load();
        }, child: const Text('繼續驗收')),
      ]));
    }

    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.all(12),
          child: TextField(controller: _searchCtrl,
            decoration: const InputDecoration(hintText: '掃碼或搜尋品項加入驗收單...', prefixIcon: Icon(Icons.qr_code_scanner)),
            onSubmitted: (_) => _searchAndAdd()),
        ),
        if (searchState.results.length > 1)
          SizedBox(height: 120, child: ListView(
            children: searchState.results.map((item) => ListTile(dense: true,
              title: Text((item['name'] ?? '').toString()),
              subtitle: Text((item['spec'] ?? '').toString()),
              trailing: const Icon(Icons.add_circle, color: Colors.blue),
              onTap: () { _addLine(item); _searchCtrl.clear(); ref.read(posSearchProvider.notifier).clear(); },
            )).toList(),
          )),
        const Divider(height: 1),
        Expanded(
          child: rcvState.lines.isEmpty
              ? Center(child: Text('掃碼或搜尋品項加入驗收單',
                  style: TextStyle(color: Theme.of(context).colorScheme.outline)))
              : ListView.builder(
                  itemCount: rcvState.lines.length,
                  itemBuilder: (context, index) {
                    final line = rcvState.lines[index];
                    return ListTile(
                      title: Text(line.productName),
                      trailing: Row(mainAxisSize: MainAxisSize.min, children: [
                        IconButton(icon: const Icon(Icons.remove_circle_outline),
                            onPressed: () => ref.read(receiveProvider.notifier).updateQuantity(index, line.quantity - 1)),
                        Container(width: 40, alignment: Alignment.center,
                          padding: const EdgeInsets.symmetric(vertical: 4),
                          decoration: BoxDecoration(
                            color: Theme.of(context).colorScheme.primaryContainer.withOpacity(0.3),
                            borderRadius: BorderRadius.circular(6)),
                          child: Text('${line.quantity}', style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold))),
                        IconButton(icon: const Icon(Icons.add_circle_outline),
                            onPressed: () => ref.read(receiveProvider.notifier).updateQuantity(index, line.quantity + 1)),
                        IconButton(icon: const Icon(Icons.delete_outline, color: Colors.red),
                            onPressed: () => ref.read(receiveProvider.notifier).removeLine(index)),
                      ]),
                    );
                  }),
        ),
        if (rcvState.lines.isNotEmpty)
          Padding(padding: const EdgeInsets.all(16), child: SizedBox(width: double.infinity, height: 52,
            child: ElevatedButton.icon(icon: const Icon(Icons.check),
              label: Text('確認入庫 (${rcvState.lines.length} 筆)'),
              style: ElevatedButton.styleFrom(backgroundColor: Colors.green, foregroundColor: Colors.white),
              onPressed: rcvState.loading ? null : () =>
                  _showSupplierAndSubmit(context, ref)))),
        if (rcvState.error != null)
          Padding(padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Text(rcvState.error!, style: const TextStyle(color: Colors.red))),
      ],
    );
  }
}

// ═══════════════════════════════════════════════════════
// Tab 3: 盤點
// ═══════════════════════════════════════════════════════
class CountTab extends ConsumerWidget {
  const CountTab();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final countState = ref.watch(countProvider);
    final invState = ref.watch(inventoryProvider);

    if (countState.result != null) {
      final discrepancies = (countState.result!['discrepancies'] as List?) ?? [];
      return Padding(padding: const EdgeInsets.all(24), child: Column(children: [
        Icon(discrepancies.isEmpty ? Icons.check_circle : Icons.warning_amber,
            size: 64, color: discrepancies.isEmpty ? Colors.green : Colors.orange),
        const SizedBox(height: 12),
        Text(discrepancies.isEmpty ? '帳實相符！' : '${discrepancies.length} 筆差異，已建立審核待辦',
            style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
        if (discrepancies.isNotEmpty) ...[
          const SizedBox(height: 16),
          ...discrepancies.map((d) => Padding(padding: const EdgeInsets.symmetric(vertical: 4),
            child: Text('帳面 ${d['book_quantity']} → 實際 ${d['actual_quantity']} (差 ${d['difference']})'))),
        ],
        const SizedBox(height: 24),
        ElevatedButton(onPressed: () => ref.read(countProvider.notifier).clear(), child: const Text('完成')),
      ]));
    }

    return Column(
      children: [
        Padding(padding: const EdgeInsets.all(12), child: Row(children: [
          Text('盤點', style: Theme.of(context).textTheme.titleMedium),
          const Spacer(),
          if (countState.lines.isEmpty)
            ElevatedButton.icon(icon: const Icon(Icons.play_arrow), label: const Text('開始盤點'),
              onPressed: invState.items.isEmpty ? null : () =>
                  ref.read(countProvider.notifier).loadFromInventory(invState.items)),
        ])),
        if (countState.lines.isEmpty)
          Expanded(child: Center(child: Text('點「開始盤點」載入庫存品項',
              style: TextStyle(color: Theme.of(context).colorScheme.outline))))
        else ...[
          Container(
            color: Theme.of(context).colorScheme.surfaceContainerHighest,
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            child: const Row(children: [
              Expanded(flex: 3, child: Text('品名', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 13))),
              SizedBox(width: 70, child: Text('帳面', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 13), textAlign: TextAlign.center)),
              SizedBox(width: 90, child: Text('實際', style: TextStyle(fontWeight: FontWeight.w600, fontSize: 13), textAlign: TextAlign.center)),
            ]),
          ),
          Expanded(child: ListView.builder(
            itemCount: countState.lines.length,
            itemBuilder: (context, index) {
              final line = countState.lines[index];
              final diff = (line.actualQuantity ?? line.bookQuantity) - line.bookQuantity;
              return Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
                child: Row(children: [
                  Expanded(flex: 3, child: Text(line.productName, style: const TextStyle(fontSize: 14))),
                  SizedBox(width: 70, child: Text('${line.bookQuantity}', textAlign: TextAlign.center,
                      style: TextStyle(color: Theme.of(context).colorScheme.outline))),
                  SizedBox(width: 90, child: TextField(
                    keyboardType: TextInputType.number, textAlign: TextAlign.center,
                    decoration: InputDecoration(hintText: '${line.bookQuantity}',
                      contentPadding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
                      border: const OutlineInputBorder(),
                      fillColor: diff != 0 ? Colors.orange.withOpacity(0.1) : null, filled: diff != 0),
                    style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold,
                        color: diff != 0 ? Colors.orange : null),
                    onChanged: (v) {
                      final qty = int.tryParse(v);
                      if (qty != null) ref.read(countProvider.notifier).setActualQuantity(index, qty);
                    },
                  )),
                ]),
              );
            },
          )),
          Padding(padding: const EdgeInsets.all(16), child: Row(children: [
            TextButton(onPressed: () => ref.read(countProvider.notifier).clear(), child: const Text('取消')),
            const Spacer(),
            ElevatedButton.icon(icon: const Icon(Icons.check), label: const Text('提交盤點'),
              style: ElevatedButton.styleFrom(backgroundColor: Colors.blue, foregroundColor: Colors.white),
              onPressed: countState.loading ? null : () => ref.read(countProvider.notifier).submit()),
          ])),
        ],
      ],
    );
  }
}

// ═══════════════════════════════════════════════════════
// 右側：異動紀錄
// ═══════════════════════════════════════════════════════
class _MovementPanel extends ConsumerWidget {
  const _MovementPanel();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final mvState = ref.watch(movementsProvider);

    if (mvState.selectedSkuId == null) {
      return Center(child: Text('點擊品項查看異動紀錄',
          style: TextStyle(fontSize: 16, color: Theme.of(context).colorScheme.outline)));
    }

    return Column(
      children: [
        Padding(padding: const EdgeInsets.all(16), child: Row(children: [
          const Icon(Icons.history, size: 20), const SizedBox(width: 8),
          Text('異動紀錄', style: Theme.of(context).textTheme.titleMedium),
          const Spacer(),
          IconButton(icon: const Icon(Icons.close, size: 18),
              onPressed: () => ref.read(movementsProvider.notifier).clear()),
        ])),
        const Divider(height: 1),
        Expanded(
          child: mvState.loading
              ? const Center(child: CircularProgressIndicator())
              : mvState.movements.isEmpty
                  ? const Center(child: Text('沒有異動紀錄'))
                  : ListView.builder(
                      itemCount: mvState.movements.length,
                      itemBuilder: (context, index) {
                        final m = mvState.movements[index];
                        final qty = m['quantity'] as num? ?? 0;
                        final type = (m['movement_type'] ?? '').toString();
                        final note = (m['note'] ?? '').toString();
                        final createdAt = (m['created_at'] ?? '').toString();
                        final typeLabel = switch (type) {
                          'sale' => '銷售出庫', 'purchase_receive' => '進貨入庫',
                          'adjustment' => '盤點調整', 'return' => '退貨入庫', 'initial' => '初始庫存', _ => type,
                        };
                        return ListTile(
                          leading: Icon(qty >= 0 ? Icons.add_circle : Icons.remove_circle,
                              color: qty >= 0 ? Colors.green : Colors.red),
                          title: Text('${qty >= 0 ? "+" : ""}$qty  $typeLabel',
                              style: TextStyle(fontWeight: FontWeight.w600, color: qty >= 0 ? Colors.green : Colors.red)),
                          subtitle: Text(note.isNotEmpty ? note :
                              (createdAt.length >= 19 ? createdAt.substring(0, 19).replaceFirst('T', ' ') : ''),
                              style: const TextStyle(fontSize: 12)),
                          trailing: Text(createdAt.length >= 10 ? createdAt.substring(0, 10) : '',
                              style: TextStyle(fontSize: 12, color: Theme.of(context).colorScheme.outline)),
                        );
                      }),
        ),
      ],
    );
  }
}

// ── 摘要 chip ────────────────────────────────────────
class _SummaryChip extends StatelessWidget {
  final String label;
  final String value;
  final Color? color;
  const _SummaryChip({required this.label, required this.value, this.color});

  @override
  Widget build(BuildContext context) {
    return Row(mainAxisSize: MainAxisSize.min, children: [
      Text('$label ', style: TextStyle(fontSize: 12, color: Theme.of(context).colorScheme.outline)),
      Text(value, style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold, color: color)),
    ]);
  }
}

String _fmt(dynamic v) {
  if (v == null) return '0';
  final n = v is num ? v : num.tryParse(v.toString()) ?? 0;
  if (n >= 10000) return '${(n / 10000).toStringAsFixed(1)}萬';
  return n.toStringAsFixed(0);
}