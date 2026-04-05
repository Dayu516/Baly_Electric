import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/auth/auth_provider.dart';
import '../../../core/feature_flags.dart';
import '../../../core/router/app_router.dart';
import '../../../infrastructure/api/api_client.dart';
import '../../../core/widgets/product_info_card.dart';
import '../../settings/ui/attribute_template_panel.dart';
import '../../settings/ui/category_management_panel.dart';
import '../application/product_provider.dart';

class ProductPage extends ConsumerStatefulWidget {
  const ProductPage({super.key});

  @override
  ConsumerState<ProductPage> createState() => _ProductPageState();
}

class _ProductPageState extends ConsumerState<ProductPage> {
  @override
  void initState() {
    super.initState();
    Future.microtask(() {
      ref.read(categoryTreeProvider.notifier).load();
      ref.read(productListProvider.notifier).loadProducts();
    });
  }

  @override
  Widget build(BuildContext context) {
    final device = getDeviceClass(context);
    return switch (device) {
      DeviceClass.desktop => _ProductDesktopLayout(),
      DeviceClass.tablet => _ProductListPanel(),
      DeviceClass.phone => _ProductListPanel(),
    };
  }
}

// ═══════════════════════════════════════════════════════
// Desktop — 左側分類樹 + 右側品項列表
// ═══════════════════════════════════════════════════════
class _ProductDesktopLayout extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final auth = ref.watch(authProvider);
    final isOwner = auth.role == 'owner';

    final tabs = <Tab>[
      const Tab(icon: Icon(Icons.inventory_2), text: '商品列表'),
      if (isOwner) const Tab(icon: Icon(Icons.account_tree_outlined), text: '分類管理'),
      if (isOwner) const Tab(icon: Icon(Icons.category_outlined), text: '屬性模板'),
    ];

    final panels = <Widget>[
      const _ProductListPanel(),
      if (isOwner) const CategoryManagementPanel(),
      if (isOwner) const AttributeTemplatePanel(),
    ];

    return DefaultTabController(
      length: tabs.length,
      child: Row(
        children: [
          const SizedBox(width: 250, child: _CategoryTreePanel()),
          const VerticalDivider(width: 1),
          Expanded(
            child: Column(
              children: [
                TabBar(
                  tabs: tabs,
                  labelColor: Theme.of(context).colorScheme.primary,
                  isScrollable: tabs.length > 4,
                ),
                Expanded(
                  child: TabBarView(children: panels),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

// ── 分類樹面板 ────────────────────────────────────────
class _CategoryTreePanel extends ConsumerWidget {
  const _CategoryTreePanel();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final treeState = ref.watch(categoryTreeProvider);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              const Icon(Icons.folder_open, size: 20),
              const SizedBox(width: 8),
              Text('分類', style: Theme.of(context).textTheme.titleMedium),
            ],
          ),
        ),
        _CategoryTile(
          name: '全部品項', icon: Icons.inventory_2,
          selected: treeState.selectedCategoryId == null,
          onTap: () {
            ref.read(categoryTreeProvider.notifier).selectCategory(null);
            ref.read(productListProvider.notifier).loadProducts();
          },
        ),
        const Divider(height: 1),
        Expanded(
          child: treeState.loading
              ? const Center(child: CircularProgressIndicator())
              : ListView(
                  children: treeState.tree
                      .map((node) => _buildNode(context, ref, node, 0))
                      .expand((w) => w)
                      .toList(),
                ),
        ),
      ],
    );
  }

  List<Widget> _buildNode(BuildContext context, WidgetRef ref, CategoryNode node, int depth) {
    final treeState = ref.watch(categoryTreeProvider);
    final isSelected = treeState.selectedCategoryId == node.categoryId;
    final widgets = <Widget>[
      _CategoryTile(
        name: node.name, depth: depth, selected: isSelected,
        hasChildren: node.children.isNotEmpty,
        onTap: () {
          ref.read(categoryTreeProvider.notifier).selectCategory(node.categoryId);
          ref.read(productListProvider.notifier).search(node.name);
        },
      ),
    ];
    for (final child in node.children) {
      widgets.addAll(_buildNode(context, ref, child, depth + 1));
    }
    return widgets;
  }
}

class _CategoryTile extends StatelessWidget {
  final String name;
  final int depth;
  final bool selected;
  final bool hasChildren;
  final IconData? icon;
  final VoidCallback onTap;

  const _CategoryTile({
    required this.name, this.depth = 0, this.selected = false,
    this.hasChildren = false, this.icon, required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Material(
      color: selected ? Theme.of(context).colorScheme.primaryContainer.withOpacity(0.4) : Colors.transparent,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: EdgeInsets.only(left: 16.0 + depth * 20, top: 10, bottom: 10, right: 12),
          child: Row(
            children: [
              Icon(icon ?? (hasChildren ? Icons.folder : Icons.label_outline), size: 18,
                  color: selected ? Theme.of(context).colorScheme.primary : Theme.of(context).colorScheme.outline),
              const SizedBox(width: 8),
              Expanded(child: Text(name, style: TextStyle(fontSize: 14,
                  fontWeight: selected ? FontWeight.w600 : FontWeight.normal,
                  color: selected ? Theme.of(context).colorScheme.primary : null))),
            ],
          ),
        ),
      ),
    );
  }
}

// ── 品項列表面板 ──────────────────────────────────────
class _ProductListPanel extends ConsumerStatefulWidget {
  const _ProductListPanel();
  @override
  ConsumerState<_ProductListPanel> createState() => _ProductListPanelState();
}

class _ProductListPanelState extends ConsumerState<_ProductListPanel> {
  final _searchController = TextEditingController();

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final productState = ref.watch(productListProvider);

    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
          child: Row(
            children: [
              Text('品項管理', style: Theme.of(context).textTheme.titleLarge),
              const SizedBox(width: 8),
              Text('${productState.products.length} 筆',
                  style: TextStyle(color: Theme.of(context).colorScheme.outline)),
              const Spacer(),
              ElevatedButton.icon(
                onPressed: () => showProductInfoCard(context, ref, onSaved: () => ref.read(productListProvider.notifier).loadProducts()),
                icon: const Icon(Icons.add),
                label: const Text('新增品項'),
              ),
            ],
          ),
        ),
        Padding(
          padding: const EdgeInsets.all(12),
          child: TextField(
            controller: _searchController,
            decoration: InputDecoration(
              hintText: '搜尋品名、型號、條碼、別名...',
              prefixIcon: const Icon(Icons.search),
              suffixIcon: _searchController.text.isNotEmpty
                  ? IconButton(
                      icon: const Icon(Icons.clear),
                      onPressed: () {
                        _searchController.clear();
                        ref.read(productListProvider.notifier).loadProducts();
                        setState(() {});
                      },
                    )
                  : null,
            ),
            onSubmitted: (v) {
              ref.read(productListProvider.notifier).search(v);
              setState(() {});
            },
          ),
        ),
        Expanded(
          child: productState.loading
              ? const Center(child: CircularProgressIndicator())
              : productState.products.isEmpty
                  ? Center(child: Text('沒有品項資料',
                      style: TextStyle(fontSize: 16, color: Theme.of(context).colorScheme.outline)))
                  : ListView.builder(
                      itemCount: productState.products.length,
                      itemBuilder: (context, index) {
                        final item = productState.products[index];
                        return _ProductCard(
                          item: item,
                          onTap: () { final sid = (item['sku_id'] ?? '').toString(); final pid = (item['product_id'] ?? '').toString(); if (sid.isNotEmpty) showProductInfoCard(context, ref, skuId: sid, onSaved: () => ref.read(productListProvider.notifier).loadProducts()); else if (pid.isNotEmpty) showProductInfoCard(context, ref, productId: pid, onSaved: () => ref.read(productListProvider.notifier).loadProducts()); },
                        );
                      },
                    ),
        ),
      ],
    );
  }
}

// ═══════════════════════════════════════════════════════
// 品項新增/編輯表單（完整版 — 3 個 Tab）
// ═══════════════════════════════════════════════════════
void _showProductForm(BuildContext context, WidgetRef ref, {Map<String, dynamic>? existing}) {
  final isEdit = existing != null;
  final productId = existing?['product_id']?.toString();

  // 基本資料
  final nameCtrl = TextEditingController(text: existing?['name']?.toString() ?? '');
  final brandCtrl = TextEditingController(text: existing?['brand']?.toString() ?? '');
  final seriesCtrl = TextEditingController(text: existing?['series']?.toString() ?? '');
  final modelCtrl = TextEditingController(text: existing?['model_number']?.toString() ?? '');
  final descCtrl = TextEditingController(text: existing?['description']?.toString() ?? '');

  // SKU
  final barcodeCtrl = TextEditingController(text: existing?['barcode']?.toString() ?? '');
  final specCtrl = TextEditingController(text: existing?['spec']?.toString() ?? '');
  final unitCtrl = TextEditingController(text: existing?['unit']?.toString() ?? '個');
  final priceCtrl = TextEditingController(text: (existing?['sell_price'] ?? '').toString());
  final costCtrl = TextEditingController(text: (existing?['cost_price'] ?? '').toString());
  final minStockCtrl = TextEditingController(text: (existing?['min_stock'] ?? '').toString());
  final supplierCodeCtrl = TextEditingController(text: existing?['supplier_code']?.toString() ?? '');
  final internalCodeCtrl = TextEditingController(text: existing?['internal_code']?.toString() ?? '');

  // 別名
  final aliasCtrl = TextEditingController();
  final aliases = <String>[];

  // 品名自動組合（新增時）：品牌 型號 規格
  bool nameManuallyEdited = isEdit;
  void _autoName() {
    if (nameManuallyEdited) return;
    final parts = [brandCtrl.text, modelCtrl.text, specCtrl.text]
        .where((s) => s.trim().isNotEmpty)
        .toList();
    nameCtrl.text = parts.join(' ');
  }
  if (!isEdit) {
    for (final c in [brandCtrl, modelCtrl, specCtrl]) {
      c.addListener(_autoName);
    }
    nameCtrl.addListener(() {
      // 如果使用者手動改了品名，停止自動組合
      final auto = [brandCtrl.text, modelCtrl.text, specCtrl.text]
          .where((s) => s.trim().isNotEmpty).join(' ');
      if (nameCtrl.text != auto && nameCtrl.text.isNotEmpty) {
        nameManuallyEdited = true;
      }
    });
  }

  showDialog(
    context: context,
    builder: (ctx) => StatefulBuilder(
      builder: (ctx, setDialogState) => Dialog(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 700, maxHeight: 650),
          child: DefaultTabController(
            length: 3,
            child: Column(
              children: [
                // 標題
                Padding(
                  padding: const EdgeInsets.fromLTRB(24, 20, 16, 0),
                  child: Row(
                    children: [
                      Icon(isEdit ? Icons.edit : Icons.add_circle, size: 24),
                      const SizedBox(width: 8),
                      Text(isEdit ? '編輯品項' : '新增品項',
                          style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
                      const Spacer(),
                      IconButton(icon: const Icon(Icons.close), onPressed: () => Navigator.pop(ctx)),
                    ],
                  ),
                ),

                // Tabs
                const TabBar(
                  tabs: [
                    Tab(text: '基本資料'),
                    Tab(text: 'SKU / 規格'),
                    Tab(text: '別名'),
                  ],
                ),

                // Tab 內容
                Expanded(
                  child: TabBarView(
                    children: [
                      // ── Tab 1: 基本資料 ──────────────
                      SingleChildScrollView(
                        padding: const EdgeInsets.all(24),
                        child: Column(
                          children: [
                            TextField(controller: nameCtrl,
                                decoration: const InputDecoration(labelText: '品名 *', hintText: '標準格式：品牌 系列 類型 規格')),
                            const SizedBox(height: 16),
                            Row(children: [
                              Expanded(child: TextField(controller: brandCtrl,
                                  decoration: const InputDecoration(labelText: '品牌', hintText: '士林、東元、OMRON...'))),
                              const SizedBox(width: 12),
                              Expanded(child: TextField(controller: seriesCtrl,
                                  decoration: const InputDecoration(labelText: '系列', hintText: 'BH、MY2N...'))),
                            ]),
                            const SizedBox(height: 16),
                            TextField(controller: modelCtrl,
                                decoration: const InputDecoration(labelText: '型號', hintText: '完整型號')),
                            const SizedBox(height: 16),
                            TextField(controller: descCtrl, maxLines: 3,
                                decoration: const InputDecoration(labelText: '備註', hintText: '補充說明')),
                          ],
                        ),
                      ),

                      // ── Tab 2: SKU / 規格 ─────────────
                      SingleChildScrollView(
                        padding: const EdgeInsets.all(24),
                        child: Column(
                          children: [
                            Row(children: [
                              Expanded(child: TextField(controller: barcodeCtrl,
                                  decoration: const InputDecoration(labelText: '條碼', prefixIcon: Icon(Icons.qr_code)))),
                              const SizedBox(width: 12),
                              Expanded(child: TextField(controller: specCtrl,
                                  decoration: const InputDecoration(labelText: '規格', hintText: '2P 20A'))),
                            ]),
                            const SizedBox(height: 16),
                            Row(children: [
                              Expanded(child: TextField(controller: unitCtrl,
                                  decoration: const InputDecoration(labelText: '單位'))),
                              const SizedBox(width: 12),
                              Expanded(child: TextField(controller: priceCtrl,
                                  decoration: const InputDecoration(labelText: '售價', prefixText: '\$'),
                                  keyboardType: TextInputType.number)),
                              const SizedBox(width: 12),
                              Expanded(child: TextField(controller: costCtrl,
                                  decoration: const InputDecoration(labelText: '成本', prefixText: '\$'),
                                  keyboardType: TextInputType.number)),
                            ]),
                            const SizedBox(height: 16),
                            Row(children: [
                              Expanded(child: TextField(controller: minStockCtrl,
                                  decoration: const InputDecoration(labelText: '安全庫存'),
                                  keyboardType: TextInputType.number)),
                              const SizedBox(width: 12),
                              Expanded(child: TextField(controller: supplierCodeCtrl,
                                  decoration: const InputDecoration(labelText: '供應商料號'))),
                              const SizedBox(width: 12),
                              Expanded(child: TextField(controller: internalCodeCtrl,
                                  decoration: const InputDecoration(labelText: '內部編號（凌越）'))),
                            ]),
                          ],
                        ),
                      ),

                      // ── Tab 3: 別名 ──────────────────
                      Padding(
                        padding: const EdgeInsets.all(24),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text('客人可能怎麼叫這個品項？加入別名讓搜尋更容易找到。',
                                style: TextStyle(fontSize: 13, color: Colors.grey)),
                            const SizedBox(height: 12),
                            Row(children: [
                              Expanded(child: TextField(controller: aliasCtrl,
                                  decoration: const InputDecoration(labelText: '新增別名', hintText: '例如：跳起來的、NFB、無熔絲'),
                                  onSubmitted: (v) {
                                    if (v.trim().isNotEmpty) {
                                      setDialogState(() => aliases.add(v.trim()));
                                      aliasCtrl.clear();
                                    }
                                  })),
                              const SizedBox(width: 8),
                              IconButton(
                                icon: const Icon(Icons.add_circle, color: Colors.blue),
                                onPressed: () {
                                  if (aliasCtrl.text.trim().isNotEmpty) {
                                    setDialogState(() => aliases.add(aliasCtrl.text.trim()));
                                    aliasCtrl.clear();
                                  }
                                },
                              ),
                            ]),
                            const SizedBox(height: 12),
                            Wrap(
                              spacing: 8, runSpacing: 8,
                              children: aliases.map((a) => Chip(
                                label: Text(a),
                                deleteIcon: const Icon(Icons.close, size: 16),
                                onDeleted: () => setDialogState(() => aliases.remove(a)),
                              )).toList(),
                            ),
                            if (aliases.isEmpty)
                              Padding(
                                padding: const EdgeInsets.only(top: 20),
                                child: Center(child: Text('還沒有別名',
                                    style: TextStyle(color: Theme.of(ctx).colorScheme.outline))),
                              ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),

                // 底部按鈕
                const Divider(height: 1),
                Padding(
                  padding: const EdgeInsets.all(16),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.end,
                    children: [
                      TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('取消')),
                      const SizedBox(width: 8),
                      ElevatedButton.icon(
                        icon: Icon(isEdit ? Icons.save : Icons.add),
                        label: Text(isEdit ? '儲存' : '建立'),
                        onPressed: () async {
                          if (nameCtrl.text.trim().isEmpty) return;
                          final api = ref.read(apiClientProvider);

                          if (isEdit) {
                            // 更新品項
                            await api.put('/products/$productId', data: {
                              'name': nameCtrl.text.trim(),
                              'series': seriesCtrl.text.trim().isEmpty ? null : seriesCtrl.text.trim(),
                              'model_number': modelCtrl.text.trim().isEmpty ? null : modelCtrl.text.trim(),
                              'description': descCtrl.text.trim().isEmpty ? null : descCtrl.text.trim(),
                              'version': existing?['version'] ?? 1,
                            });
                          } else {
                            // 新增品項
                            final productRes = await api.post('/products/', data: {
                              'name': nameCtrl.text.trim(),
                              'series': seriesCtrl.text.trim().isEmpty ? null : seriesCtrl.text.trim(),
                              'model_number': modelCtrl.text.trim().isEmpty ? null : modelCtrl.text.trim(),
                              'description': descCtrl.text.trim().isEmpty ? null : descCtrl.text.trim(),
                            });
                            final newProductId = productRes.data['product_id'];

                            // 建立 SKU
                            if (priceCtrl.text.isNotEmpty || barcodeCtrl.text.isNotEmpty || specCtrl.text.isNotEmpty) {
                              await api.post('/products/skus', data: {
                                'product_id': newProductId,
                                'brand': brandCtrl.text.trim().isEmpty ? null : brandCtrl.text.trim(),
                                'barcode': barcodeCtrl.text.trim().isEmpty ? null : barcodeCtrl.text.trim(),
                                'supplier_code': supplierCodeCtrl.text.trim().isEmpty ? null : supplierCodeCtrl.text.trim(),
                                'internal_code': internalCodeCtrl.text.trim().isEmpty ? null : internalCodeCtrl.text.trim(),
                                'spec': specCtrl.text.trim().isEmpty ? null : specCtrl.text.trim(),
                                'unit': unitCtrl.text.trim(),
                                'sell_price': double.tryParse(priceCtrl.text) ?? 0,
                                'cost_price': double.tryParse(costCtrl.text),
                                'min_stock': int.tryParse(minStockCtrl.text),
                              });
                            }

                            // 建立別名（透過 DB 直接寫，之後改成 API）
                            // TODO: 加別名 API route
                          }

                          ref.read(productListProvider.notifier).loadProducts();
                          if (ctx.mounted) Navigator.pop(ctx);
                        },
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    ),
  );
}

// ── 品項卡片 ──────────────────────────────────────────
class _ProductCard extends StatelessWidget {
  final Map<String, dynamic> item;
  final VoidCallback? onTap;

  const _ProductCard({required this.item, this.onTap});

  @override
  Widget build(BuildContext context) {
    final name = (item['name'] ?? item['product_name'] ?? '').toString();
    final brand = (item['brand'] ?? '').toString();
    final series = (item['series'] ?? '').toString();
    final model = (item['model_number'] ?? '').toString();
    final spec = (item['spec'] ?? '').toString();
    final barcode = (item['barcode'] ?? '').toString();
    final price = item['sell_price'] ?? 0;
    final stock = item['current_stock'];
    final rawName = (item['raw_name'] ?? '').toString();

    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 3),
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(name, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w600)),
                    const SizedBox(height: 4),
                    Text(
                      [brand, series, model, spec].where((s) => s.isNotEmpty).join(' / '),
                      style: TextStyle(fontSize: 13, color: Theme.of(context).colorScheme.outline),
                    ),
                    if (barcode.isNotEmpty) ...[
                      const SizedBox(height: 2),
                      Text('條碼: $barcode',
                          style: TextStyle(fontSize: 12, color: Theme.of(context).colorScheme.outline)),
                    ],
                    if (rawName.isNotEmpty && rawName != name) ...[
                      const SizedBox(height: 2),
                      Text('原始: $rawName',
                          style: TextStyle(fontSize: 11, color: Theme.of(context).colorScheme.outline, fontStyle: FontStyle.italic)),
                    ],
                  ],
                ),
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text('\$$price',
                      style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Colors.blue)),
                  if (stock != null)
                    Text('庫存: $stock',
                        style: TextStyle(fontSize: 13,
                            color: (stock is num && stock <= 0) ? Colors.red : Theme.of(context).colorScheme.outline)),
                ],
              ),
              const SizedBox(width: 4),
              Icon(Icons.chevron_right, color: Theme.of(context).colorScheme.outline),
            ],
          ),
        ),
      ),
    );
  }
}