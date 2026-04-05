import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../infrastructure/api/api_client.dart';
import '../../../core/widgets/product_info_card.dart';
import '../application/pos_provider.dart';

// ═══════════════════════════════════════════════════════
// 搜尋面板 — 掃碼自動加入 + 關鍵字搜尋
// ═══════════════════════════════════════════════════════
class ProductSearchPanel extends ConsumerStatefulWidget {
  const ProductSearchPanel({super.key});

  @override
  ConsumerState<ProductSearchPanel> createState() => ProductSearchPanelState();
}

class ProductSearchPanelState extends ConsumerState<ProductSearchPanel> {
  final _searchController = TextEditingController();
  final _focusNode = FocusNode();
  bool _isBarcodeScan = false; // 掃碼器輸入很快，用來判斷

  @override
  void initState() {
    super.initState();
    _searchController.addListener(_onTextChanged);
  }

  @override
  void dispose() {
    _searchController.removeListener(_onTextChanged);
    _searchController.dispose();
    _focusNode.dispose();
    super.dispose();
  }

  // Debounce 即時搜尋
  DateTime? _lastInputTime;

  void _onTextChanged() {
    final now = DateTime.now();
    final text = _searchController.text.trim();

    if (text.isEmpty) {
      ref.read(posSearchProvider.notifier).clear();
      return;
    }

    // 偵測掃碼器：短時間內大量字元輸入
    if (_lastInputTime != null && now.difference(_lastInputTime!).inMilliseconds < 50) {
      _isBarcodeScan = true;
    } else {
      _isBarcodeScan = false;
    }
    _lastInputTime = now;

    // Debounce: 300ms 沒新輸入才搜尋（手動打字）
    // 掃碼器會直接觸發 onSubmitted，不走這裡
    Future.delayed(const Duration(milliseconds: 300), () {
      if (_searchController.text.trim() == text && text.length >= 2) {
        _doSearch(autoAdd: false);
      }
    });
  }

  Future<void> _doSearch({bool autoAdd = true}) async {
    final keyword = _searchController.text.trim();
    if (keyword.isEmpty) return;

    final customerId = ref.read(posProvider).customerId;
    await ref.read(posSearchProvider.notifier).search(keyword, customerId: customerId);

    // 掃碼場景（Enter 觸發）：只有一筆結果 → 自動加入購物車
    if (autoAdd) {
      final results = ref.read(posSearchProvider).results;
      if (results.length == 1) {
        _addToCart(results[0]);
      }
    }
  }

  void _quickAddProduct(BuildContext context) {
    final nameCtrl = TextEditingController(text: _searchController.text.trim());
    final priceCtrl = TextEditingController();
    final specCtrl = TextEditingController();
    final unitCtrl = TextEditingController(text: '個');

    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('快速新增品項'),
        content: SizedBox(
          width: 400,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(controller: nameCtrl, autofocus: true,
                  decoration: const InputDecoration(labelText: '品名 *', hintText: '例如：工業擦拭布 白色 25kg/包'),
                  style: const TextStyle(fontSize: 18)),
              const SizedBox(height: 14),
              Row(children: [
                Expanded(child: TextField(controller: priceCtrl,
                    decoration: const InputDecoration(labelText: '售價 *', prefixText: '\$'),
                    keyboardType: TextInputType.number, style: const TextStyle(fontSize: 18))),
                const SizedBox(width: 12),
                Expanded(child: TextField(controller: specCtrl,
                    decoration: const InputDecoration(labelText: '規格', hintText: '白色 25kg'))),
              ]),
            ],
          ),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('取消')),
          ElevatedButton.icon(
            icon: const Icon(Icons.add_shopping_cart),
            label: const Text('建立並加入購物車'),
            onPressed: () async {
              final name = nameCtrl.text.trim();
              final price = double.tryParse(priceCtrl.text) ?? 0;
              if (name.isEmpty || price <= 0) return;

              try {
                final api = ref.read(apiClientProvider);
                // 建立 Product
                final pRes = await api.post('/products/', data: {'name': name});
                final productId = pRes.data['product_id'];

                // 建立 SKU
                final sRes = await api.post('/products/skus', data: {
                  'product_id': productId,
                  'spec': specCtrl.text.trim().isEmpty ? null : specCtrl.text.trim(),
                  'unit': unitCtrl.text.trim(),
                  'sell_price': price,
                });
                final skuId = sRes.data['sku_id'];

                // 建立 ReviewTask（待整理）
                try {
                  await api.post('/reviews/', data: {
                    'review_type': 'product_confirm',
                    'title': '快速新增品項待整理：$name',
                    'detail': '售價 $price，規格：${specCtrl.text.trim().isEmpty ? "無" : specCtrl.text.trim()}',
                    'reference_type': 'product',
                    'reference_id': productId,
                  });
                } catch (_) {} // 失敗不影響結帳

                // 加入購物車
                ref.read(posProvider.notifier).addItem(CartItem(
                  skuId: skuId,
                  productName: name,
                  spec: specCtrl.text.trim().isEmpty ? null : specCtrl.text.trim(),
                  unitPrice: price,
                ));

                // 清搜尋
                _searchController.clear();
                ref.read(posSearchProvider.notifier).clear();
                _focusNode.requestFocus();

                if (ctx.mounted) Navigator.pop(ctx);
              } catch (e) {
                ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(content: Text('建立失敗: $e')));
              }
            },
          ),
        ],
      ),
    );
  }

    void _addToCart(Map<String, dynamic> item) {
    final skuId = (item['sku_id'] ?? '').toString();
    if (skuId.isEmpty) return;

    ref.read(posProvider.notifier).addItem(CartItem(
      skuId: skuId,
      productName: (item['name'] ?? '').toString(),
      spec: item['spec']?.toString(),
      unitPrice: (item['sell_price'] as num?)?.toDouble() ?? 0,
    ));

    _searchController.clear();
    ref.read(posSearchProvider.notifier).clear();
    _focusNode.requestFocus();
  }

  @override
  Widget build(BuildContext context) {
    final searchState = ref.watch(posSearchProvider);

    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.all(12),
          child: TextField(
            controller: _searchController,
            focusNode: _focusNode,
            autofocus: true,
            decoration: const InputDecoration(
              hintText: '掃碼或輸入品名搜尋... (掃碼自動加入)',
              prefixIcon: Icon(Icons.qr_code_scanner, size: 28),
              contentPadding: EdgeInsets.symmetric(horizontal: 16, vertical: 18),
            ),
            style: const TextStyle(fontSize: 20),
            onSubmitted: (_) => _doSearch(autoAdd: true),
          ),
        ),
        Expanded(
          child: searchState.loading
              ? const Center(child: CircularProgressIndicator())
              : searchState.results.isEmpty
                  ? Center(
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          if (_searchController.text.trim().isEmpty) ...[
                            Icon(Icons.qr_code_scanner, size: 64,
                                color: Theme.of(context).colorScheme.outline.withOpacity(0.3)),
                            const SizedBox(height: 12),
                            Text('掃碼自動加入購物車',
                                style: TextStyle(fontSize: 16, color: Theme.of(context).colorScheme.outline)),
                            const SizedBox(height: 4),
                            Text('或輸入品名 Enter 搜尋',
                                style: TextStyle(fontSize: 14, color: Theme.of(context).colorScheme.outline.withOpacity(0.6))),
                          ] else ...[
                            const Icon(Icons.search_off, size: 48, color: Colors.grey),
                            const SizedBox(height: 12),
                            Text('找不到「${_searchController.text.trim()}」',
                                style: const TextStyle(fontSize: 16, color: Colors.grey)),
                            const SizedBox(height: 16),
                            ElevatedButton.icon(
                              icon: const Icon(Icons.add),
                              label: const Text('快速新增品項'),
                              onPressed: () => _quickAddProduct(context),
                              style: ElevatedButton.styleFrom(minimumSize: const Size(200, 48)),
                            ),
                          ],
                        ],
                      ),
                    )
                  : Column(
                      children: [
                        Expanded(
                          child: ListView.builder(
                            itemCount: searchState.results.length,
                            itemBuilder: (context, index) {
                              final item = searchState.results[index];
                              return SearchResultTile(item: item, onTap: () => _addToCart(item));
                            },
                          ),
                        ),
                        // 列表底部也有快速新增
                        Padding(
                          padding: const EdgeInsets.all(8),
                          child: TextButton.icon(
                            icon: const Icon(Icons.add, size: 16),
                            label: const Text('找不到？快速新增品項'),
                            onPressed: () => _quickAddProduct(context),
                          ),
                        ),
                      ],
                    ),
        ),
      ],
    );
  }
}

class SearchResultTile extends StatelessWidget {
  final Map<String, dynamic> item;
  final VoidCallback onTap;

  const SearchResultTile({super.key, required this.item, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final name = item['name'] ?? '';
    final brand = item['brand'] ?? '';
    final spec = item['spec'] ?? '';
    final barcode = item['barcode'] ?? '';
    final price = (item['sell_price'] as num?)?.toDouble() ?? 0;
    final cost = (item['cost_price'] as num?)?.toDouble();
    final stock = item['current_stock'] ?? 0;
    final itemType = item['item_type']?.toString() ?? 'finished';
    final customerLastPrice = (item['customer_last_price'] as num?)?.toDouble();
    final customerLastSoldAt = item['customer_last_sold_at']?.toString();

    // 毛利率計算
    final margin = (cost != null && cost > 0 && price > 0)
        ? ((price - cost) / price * 100).toStringAsFixed(0)
        : null;

    // 成本警告：客戶上次價 < 現在成本
    final costWarning = customerLastPrice != null && cost != null && customerLastPrice < cost;

    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 3),
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
          child: Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(name.toString(), style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w600)),
                    const SizedBox(height: 4),
                    Text(
                      [brand, spec, if (barcode.toString().isNotEmpty) barcode]
                          .where((s) => s.toString().isNotEmpty).join(' / '),
                      style: TextStyle(fontSize: 13, color: Theme.of(context).colorScheme.outline),
                    ),
                    // 客戶歷史售價
                    if (customerLastPrice != null) ...[
                      const SizedBox(height: 4),
                      Row(
                        children: [
                          Icon(costWarning ? Icons.warning_amber : Icons.history,
                              size: 14, color: costWarning ? Colors.red : Colors.orange),
                          const SizedBox(width: 4),
                          Text(
                            '上次: \$${customerLastPrice.toStringAsFixed(0)}'
                            '${customerLastSoldAt != null ? " (${customerLastSoldAt!.substring(0, 10)})" : ""}',
                            style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600,
                                color: costWarning ? Colors.red : Colors.orange),
                          ),
                          if (costWarning) ...[
                            const SizedBox(width: 4),
                            Text('低於成本!', style: TextStyle(fontSize: 11, color: Colors.red, fontWeight: FontWeight.bold)),
                          ],
                        ],
                      ),
                    ],
                  ],
                ),
              ),
              // 價格 + 成本 + 庫存
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text('\$${price.toStringAsFixed(0)}',
                      style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: Colors.blue)),
                  if (cost != null)
                    Text('成本 \$${cost.toStringAsFixed(0)}${margin != null ? " ($margin%)" : ""}',
                        style: TextStyle(fontSize: 12, color: Theme.of(context).colorScheme.outline)),
                  Text('庫存: $stock', style: TextStyle(fontSize: 12,
                      color: (stock as num) <= 0 ? Colors.red : Theme.of(context).colorScheme.outline)),
                  if (itemType == 'assembly' && (stock as num) <= 0)
                    Text('可由零件組成', style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: Colors.purple.shade400)),
                ],
              ),
              const SizedBox(width: 8),
              Icon(Icons.add_circle, size: 32, color: Theme.of(context).colorScheme.primary),
            ],
          ),
        ),
      ),
    );
  }
}
