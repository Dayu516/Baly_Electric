import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../infrastructure/api/api_client.dart';
import 'product_info_card/alternatives_tab.dart';
import 'product_info_card/basic_info_tab.dart';
import 'product_info_card/bom_tab.dart';
import 'product_info_card/price_quote_history_tab.dart';
import 'product_info_card/supplier_pricing_tab.dart';

/// 品項資訊卡 — 統一的品項檢視/編輯 dialog。
/// 從品項管理或 POS 購物車都用這個。
///
/// [skuId] 或 [productId] 有值 → 檢視模式
/// 都沒有 → 新增模式
void showProductInfoCard(BuildContext context, WidgetRef ref, {String? skuId, String? productId, VoidCallback? onSaved}) {
  final api = ref.read(apiClientProvider);
  final hasId = skuId != null || productId != null;

  showDialog(
    context: context,
    builder: (ctx) => Dialog(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 750, maxHeight: 650),
        child: hasId
            ? _EditProductCard(api: api, skuId: skuId, productId: productId, onSaved: onSaved)
            : _NewProductCard(api: api, onSaved: onSaved),
      ),
    ),
  );
}

// ═══════════════════════════════════════════════════════
// 編輯/檢視品項（從 API 載入）
// ═══════════════════════════════════════════════════════
class _EditProductCard extends StatefulWidget {
  final ApiClient api;
  final String? skuId;
  final String? productId;
  final VoidCallback? onSaved;

  const _EditProductCard({required this.api, this.skuId, this.productId, this.onSaved});

  @override
  State<_EditProductCard> createState() => _EditProductCardState();
}

class _EditProductCardState extends State<_EditProductCard> with SingleTickerProviderStateMixin {
  Map<String, dynamic>? _data;
  bool _loading = true;
  String? _error;
  late TabController _tabCtrl;

  @override
  void initState() {
    super.initState();
    _tabCtrl = TabController(length: 5, vsync: this);
    _loadData();
  }

  @override
  void dispose() { _tabCtrl.dispose(); super.dispose(); }

  Future<void> _loadData() async {
    try {
      final path = widget.skuId != null ? '/skus/${widget.skuId}/detail' : '/skus/by-product/${widget.productId}';
      final response = await widget.api.get(path);
      final body = response.data as Map<String, dynamic>;
      if (body['success'] == true) {
        setState(() { _data = body['data'] as Map<String, dynamic>; _loading = false; });
      } else {
        setState(() { _error = '載入失敗'; _loading = false; });
      }
    } catch (e) {
      setState(() { _error = e.toString(); _loading = false; });
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_error != null || _data == null) {
      return Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
        Text(_error ?? '載入失敗'),
        const SizedBox(height: 12),
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('關閉')),
      ]));
    }

    final d = _data!;

    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(24, 16, 12, 0),
          child: Row(children: [
            Expanded(child: Row(children: [
              Flexible(child: Text(d['name']?.toString() ?? '',
                style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
                overflow: TextOverflow.ellipsis)),
              if (d['item_type'] != null && d['item_type'] != 'finished') ...[
                const SizedBox(width: 8),
                _ItemTypeBadge(type: d['item_type'].toString()),
              ],
            ])),
            IconButton(
              icon: const Icon(Icons.edit_outlined),
              tooltip: '編輯售價/成本/安全庫存',
              onPressed: () => _showQuickEdit(context, d),
            ),
            IconButton(icon: const Icon(Icons.close), onPressed: () => Navigator.pop(context)),
          ]),
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(24, 8, 24, 0),
          child: Wrap(spacing: 20, runSpacing: 8, children: [
            if (_has(d, 'brand')) _chip('品牌', d['brand']),
            if (_has(d, 'spec')) _chip('規格', d['spec']),
            _chip('售價', '\$${d["sell_price"]}'),
            if (d['cost_price'] != null) _chip('成本', '\$${d["cost_price"]}'),
            _chip('庫存', '${d["current_stock"]}', color: (d['current_stock'] as num?) != null && (d['current_stock'] as num) <= 0 ? Colors.red : null),
          ]),
        ),
        const SizedBox(height: 8),
        TabBar(controller: _tabCtrl, isScrollable: true, tabs: const [
          Tab(text: '基本資料'), Tab(text: '供應商報價'), Tab(text: '報價追蹤'), Tab(text: '找替代品'), Tab(text: '組成件'),
        ]),
        Expanded(
          child: TabBarView(controller: _tabCtrl, children: [
            BasicInfoTab(api: widget.api, data: d),
            SupplierPricingTab(data: d),
            PriceQuoteHistoryTab(api: widget.api, data: d),
            AlternativesTab(api: widget.api, data: d),
            BomTab(api: widget.api, data: d),
          ]),
        ),
      ],
    );
  }

  static const _itemTypeLabels = {
    'finished': '成品', 'assembly': '組合品', 'accessory': '配件', 'component': '可替換零件',
  };

  void _showQuickEdit(BuildContext context, Map<String, dynamic> d) {
    final skuId = d['sku_id']?.toString() ?? '';
    final priceCtrl = TextEditingController(text: d['sell_price']?.toString() ?? '');
    final costCtrl = TextEditingController(text: d['cost_price']?.toString() ?? '');
    final minStockCtrl = TextEditingController(text: d['min_stock']?.toString() ?? '');
    String itemType = d['item_type']?.toString() ?? 'finished';

    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(builder: (ctx, setDialogState) => AlertDialog(
        title: const Text('快速編輯'),
        content: SizedBox(
          width: 350,
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            TextField(controller: priceCtrl, keyboardType: TextInputType.number,
              decoration: const InputDecoration(labelText: '售價', prefixText: '\$', border: OutlineInputBorder())),
            const SizedBox(height: 12),
            TextField(controller: costCtrl, keyboardType: TextInputType.number,
              decoration: const InputDecoration(labelText: '成本', prefixText: '\$', border: OutlineInputBorder())),
            const SizedBox(height: 12),
            TextField(controller: minStockCtrl, keyboardType: TextInputType.number,
              decoration: const InputDecoration(labelText: '安全庫存', border: OutlineInputBorder())),
            const SizedBox(height: 12),
            DropdownButtonFormField<String>(
              value: itemType,
              decoration: const InputDecoration(labelText: '品項型態', border: OutlineInputBorder()),
              items: _itemTypeLabels.entries.map((e) =>
                DropdownMenuItem(value: e.key, child: Text(e.value))).toList(),
              onChanged: (v) { if (v != null) setDialogState(() => itemType = v); },
            ),
          ]),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('取消')),
          FilledButton(onPressed: () async {
            try {
              await widget.api.put('/products/skus/$skuId', data: {
                'sell_price': double.tryParse(priceCtrl.text),
                'cost_price': double.tryParse(costCtrl.text),
                'min_stock': int.tryParse(minStockCtrl.text),
                'item_type': itemType,
              });
              if (ctx.mounted) Navigator.pop(ctx);
              _loadData();
            } catch (e) {
              if (ctx.mounted) {
                ScaffoldMessenger.of(ctx).showSnackBar(SnackBar(content: Text('儲存失敗: $e')));
              }
            }
          }, child: const Text('儲存')),
        ],
      )),
    );
  }

  bool _has(Map<String, dynamic> d, String key) {
    final v = d[key];
    return v != null && v.toString().isNotEmpty;
  }

  Widget _chip(String label, String value, {Color? color}) {
    return Row(mainAxisSize: MainAxisSize.min, children: [
      Text('$label ', style: TextStyle(fontSize: 13, color: Theme.of(context).colorScheme.outline)),
      Text(value, style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: color)),
    ]);
  }
}

// ═══════════════════════════════════════════════════════
// 新增品項（空表單）
// ═══════════════════════════════════════════════════════
class _NewProductCard extends StatefulWidget {
  final ApiClient api;
  final VoidCallback? onSaved;
  const _NewProductCard({required this.api, this.onSaved});
  @override
  State<_NewProductCard> createState() => _NewProductCardState();
}

class _NewProductCardState extends State<_NewProductCard> {
  final _nameCtrl = TextEditingController();
  final _brandCtrl = TextEditingController();
  final _seriesCtrl = TextEditingController();
  final _modelCtrl = TextEditingController();
  final _specCtrl = TextEditingController();
  final _barcodeCtrl = TextEditingController();
  final _unitCtrl = TextEditingController(text: '個');
  final _priceCtrl = TextEditingController();
  final _costCtrl = TextEditingController();

  @override
  void dispose() {
    for (final c in [_nameCtrl, _brandCtrl, _seriesCtrl, _modelCtrl, _specCtrl, _barcodeCtrl, _unitCtrl, _priceCtrl, _costCtrl]) {
      c.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(24, 16, 12, 0),
          child: Row(children: [
            const Text('新增品項', style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
            const Spacer(),
            IconButton(icon: const Icon(Icons.close), onPressed: () => Navigator.pop(context)),
          ]),
        ),
        Expanded(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: Column(children: [
              TextField(controller: _nameCtrl, decoration: const InputDecoration(labelText: '品名 *', hintText: '品牌 系列 類型 規格')),
              const SizedBox(height: 14),
              Row(children: [
                Expanded(child: TextField(controller: _brandCtrl, decoration: const InputDecoration(labelText: '品牌'))),
                const SizedBox(width: 12),
                Expanded(child: TextField(controller: _seriesCtrl, decoration: const InputDecoration(labelText: '系列'))),
                const SizedBox(width: 12),
                Expanded(child: TextField(controller: _modelCtrl, decoration: const InputDecoration(labelText: '型號'))),
              ]),
              const SizedBox(height: 14),
              Row(children: [
                Expanded(child: TextField(controller: _specCtrl, decoration: const InputDecoration(labelText: '規格'))),
                const SizedBox(width: 12),
                Expanded(child: TextField(controller: _barcodeCtrl, decoration: const InputDecoration(labelText: '條碼'))),
              ]),
              const SizedBox(height: 14),
              Row(children: [
                Expanded(child: TextField(controller: _unitCtrl, decoration: const InputDecoration(labelText: '單位'))),
                const SizedBox(width: 12),
                Expanded(child: TextField(controller: _priceCtrl, decoration: const InputDecoration(labelText: '售價', prefixText: '\$'), keyboardType: TextInputType.number)),
                const SizedBox(width: 12),
                Expanded(child: TextField(controller: _costCtrl, decoration: const InputDecoration(labelText: '成本', prefixText: '\$'), keyboardType: TextInputType.number)),
              ]),
            ]),
          ),
        ),
        const Divider(height: 1),
        Padding(
          padding: const EdgeInsets.all(16),
          child: Row(mainAxisAlignment: MainAxisAlignment.end, children: [
            TextButton(onPressed: () => Navigator.pop(context), child: const Text('取消')),
            const SizedBox(width: 8),
            ElevatedButton.icon(
              icon: const Icon(Icons.add),
              label: const Text('建立'),
              onPressed: () async {
                if (_nameCtrl.text.trim().isEmpty) return;
                try {
                  final productRes = await widget.api.post('/products/', data: {
                    'name': _nameCtrl.text.trim(),
                    'series': _nullIfEmpty(_seriesCtrl.text),
                    'model_number': _nullIfEmpty(_modelCtrl.text),
                  });
                  final newProductId = productRes.data['product_id'];
                  if (_priceCtrl.text.isNotEmpty || _barcodeCtrl.text.isNotEmpty || _specCtrl.text.isNotEmpty) {
                    await widget.api.post('/products/skus', data: {
                      'product_id': newProductId,
                      'brand': _nullIfEmpty(_brandCtrl.text),
                      'barcode': _nullIfEmpty(_barcodeCtrl.text), 'spec': _nullIfEmpty(_specCtrl.text),
                      'unit': _unitCtrl.text.trim(),
                      'sell_price': double.tryParse(_priceCtrl.text) ?? 0,
                      'cost_price': double.tryParse(_costCtrl.text),
                    });
                  }
                  widget.onSaved?.call();
                  if (mounted) Navigator.pop(context);
                } catch (e) {
                  ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('建立失敗: $e')));
                }
              },
            ),
          ]),
        ),
      ],
    );
  }

  String? _nullIfEmpty(String s) => s.trim().isEmpty ? null : s.trim();
}


/// 品項型態 badge — 只在非 finished 時顯示
class _ItemTypeBadge extends StatelessWidget {
  final String type;
  const _ItemTypeBadge({required this.type});

  static const _labels = {
    'assembly': '組合品', 'accessory': '配件', 'component': '零件',
  };
  static const _colors = {
    'assembly': Colors.purple, 'accessory': Colors.teal, 'component': Colors.orange,
  };

  @override
  Widget build(BuildContext context) {
    final color = _colors[type] ?? Colors.grey;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(color: color.withValues(alpha: 0.15), borderRadius: BorderRadius.circular(4)),
      child: Text(_labels[type] ?? type, style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: color)),
    );
  }
}
