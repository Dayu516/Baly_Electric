import 'package:flutter/material.dart';

import '../../../infrastructure/api/api_client.dart';

class PriceQuoteHistoryTab extends StatefulWidget {
  final ApiClient api;
  final Map<String, dynamic> data;
  const PriceQuoteHistoryTab({super.key, required this.api, required this.data});

  @override
  State<PriceQuoteHistoryTab> createState() => _PriceQuoteHistoryTabState();
}

class _PriceQuoteHistoryTabState extends State<PriceQuoteHistoryTab> {
  List<Map<String, dynamic>> _quotes = [];
  List<Map<String, dynamic>> _comparison = [];
  bool _loading = true;
  bool _showCompare = false;

  String get _productId => widget.data['product_id']?.toString() ?? '';

  @override
  void initState() {
    super.initState();
    _loadQuotes();
  }

  Future<void> _loadQuotes() async {
    setState(() => _loading = true);
    try {
      final res = await widget.api.get('/products/$_productId/supplier-prices');
      final body = res.data as Map<String, dynamic>;
      final data = (body['data'] as List).cast<Map<String, dynamic>>();

      final cmpRes = await widget.api.get('/products/$_productId/compare-prices');
      final cmpBody = cmpRes.data as Map<String, dynamic>;
      final cmpData = (cmpBody['data'] as List).cast<Map<String, dynamic>>();

      setState(() { _quotes = data; _comparison = cmpData; _loading = false; });
    } catch (e) {
      setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) return const Center(child: CircularProgressIndicator());

    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
          child: Row(children: [
            ChoiceChip(label: const Text('歷史紀錄'), selected: !_showCompare,
              onSelected: (_) => setState(() => _showCompare = false)),
            const SizedBox(width: 8),
            ChoiceChip(label: const Text('比價'), selected: _showCompare,
              onSelected: (_) => setState(() => _showCompare = true)),
            const Spacer(),
            FilledButton.tonalIcon(
              onPressed: () => _showAddQuoteDialog(context),
              icon: const Icon(Icons.add, size: 18),
              label: const Text('記錄報價'),
            ),
          ]),
        ),
        const SizedBox(height: 8),
        Expanded(child: _showCompare ? _buildComparison(context) : _buildHistory(context)),
      ],
    );
  }

  Widget _buildHistory(BuildContext context) {
    if (_quotes.isEmpty) {
      return Center(child: Text('尚無報價紀錄', style: TextStyle(color: Theme.of(context).colorScheme.outline)));
    }

    return ListView.builder(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      itemCount: _quotes.length,
      itemBuilder: (ctx, i) {
        final q = _quotes[i];
        final date = q['quoted_at']?.toString() ?? '';
        final displayDate = date.length >= 10 ? date.substring(0, 10) : date;

        return ListTile(
          dense: true,
          leading: CircleAvatar(
            radius: 16,
            backgroundColor: Theme.of(ctx).colorScheme.primaryContainer,
            child: Text('\$', style: TextStyle(
              fontSize: 14, fontWeight: FontWeight.bold,
              color: Theme.of(ctx).colorScheme.onPrimaryContainer)),
          ),
          title: Row(children: [
            Text(q['supplier_name']?.toString() ?? '', style: const TextStyle(fontWeight: FontWeight.w600)),
            const Spacer(),
            Text('\$${q["unit_price"]}', style: TextStyle(
              fontSize: 16, fontWeight: FontWeight.bold, color: Colors.green.shade700)),
            if (q['unit'] != null) Text(' /${q["unit"]}', style: TextStyle(fontSize: 12, color: Theme.of(ctx).colorScheme.outline)),
          ]),
          subtitle: Row(children: [
            Text(displayDate, style: TextStyle(fontSize: 12, color: Theme.of(ctx).colorScheme.outline)),
            if (q['note']?.toString().isNotEmpty == true) ...[
              const SizedBox(width: 8),
              Expanded(child: Text(q['note'].toString(),
                style: TextStyle(fontSize: 12, color: Theme.of(ctx).colorScheme.outline),
                overflow: TextOverflow.ellipsis)),
            ],
          ]),
        );
      },
    );
  }

  Widget _buildComparison(BuildContext context) {
    if (_comparison.isEmpty) {
      return Center(child: Text('尚無報價紀錄可比較', style: TextStyle(color: Theme.of(context).colorScheme.outline)));
    }

    final lowest = _comparison.first['unit_price'] as num;

    return ListView.builder(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      itemCount: _comparison.length,
      itemBuilder: (ctx, i) {
        final c = _comparison[i];
        final price = c['unit_price'] as num;
        final isLowest = price == lowest;
        final preferred = c['is_preferred'] == true;
        final date = c['quoted_at']?.toString() ?? '';
        final displayDate = date.length >= 10 ? date.substring(0, 10) : date;

        return Card(
          color: isLowest ? Colors.green.withValues(alpha: 0.05) : null,
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Row(children: [
              if (isLowest)
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                  decoration: BoxDecoration(color: Colors.green, borderRadius: BorderRadius.circular(4)),
                  child: const Text('最低', style: TextStyle(fontSize: 11, color: Colors.white, fontWeight: FontWeight.bold)),
                ),
              if (preferred && !isLowest)
                const Icon(Icons.star, size: 16, color: Colors.orange),
              if (isLowest || preferred) const SizedBox(width: 8),
              Expanded(child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(c['supplier_name']?.toString() ?? '',
                      style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600)),
                  Text('報價日 $displayDate',
                      style: TextStyle(fontSize: 12, color: Theme.of(ctx).colorScheme.outline)),
                ],
              )),
              Text('\$${c["unit_price"]}',
                  style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold,
                      color: isLowest ? Colors.green.shade700 : null)),
              if (c['unit'] != null)
                Text(' /${c["unit"]}', style: TextStyle(fontSize: 12, color: Theme.of(ctx).colorScheme.outline)),
            ]),
          ),
        );
      },
    );
  }

  void _showAddQuoteDialog(BuildContext context) async {
    List<Map<String, dynamic>> supplierOptions = [];
    try {
      final res = await widget.api.get('/suppliers/');
      final body = res.data as Map<String, dynamic>;
      supplierOptions = (body['data'] as List).cast<Map<String, dynamic>>();
    } catch (_) {}

    if (supplierOptions.isEmpty || !mounted) return;

    String? selectedSupplierId;
    final priceCtrl = TextEditingController();
    final unitCtrl = TextEditingController(text: widget.data['unit']?.toString() ?? '個');
    final noteCtrl = TextEditingController();
    final dateCtrl = TextEditingController(text: DateTime.now().toIso8601String().substring(0, 10));

    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDialogState) {
          return AlertDialog(
            title: const Text('記錄供應商報價'),
            content: SizedBox(
              width: 400,
              child: SingleChildScrollView(
                child: Column(mainAxisSize: MainAxisSize.min, children: [
                  DropdownButtonFormField<String>(
                    value: selectedSupplierId,
                    decoration: const InputDecoration(labelText: '供應商', border: OutlineInputBorder()),
                    items: supplierOptions.map((s) => DropdownMenuItem(
                      value: s['supplier_id']?.toString(),
                      child: Text(s['name']?.toString() ?? ''),
                    )).toList(),
                    onChanged: (v) => setDialogState(() => selectedSupplierId = v),
                  ),
                  const SizedBox(height: 12),
                  Row(children: [
                    Expanded(flex: 2, child: TextField(
                      controller: priceCtrl,
                      keyboardType: TextInputType.number,
                      decoration: const InputDecoration(labelText: '報價單價', prefixText: '\$', border: OutlineInputBorder()),
                    )),
                    const SizedBox(width: 12),
                    Expanded(child: TextField(
                      controller: unitCtrl,
                      decoration: const InputDecoration(labelText: '單位', border: OutlineInputBorder()),
                    )),
                  ]),
                  const SizedBox(height: 12),
                  TextField(controller: dateCtrl,
                    decoration: const InputDecoration(labelText: '報價日期', border: OutlineInputBorder(), hintText: 'YYYY-MM-DD')),
                  const SizedBox(height: 12),
                  TextField(controller: noteCtrl,
                    decoration: const InputDecoration(labelText: '備註', border: OutlineInputBorder())),
                ]),
              ),
            ),
            actions: [
              TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('取消')),
              FilledButton(
                onPressed: () async {
                  if (selectedSupplierId == null || priceCtrl.text.isEmpty) return;
                  try {
                    await widget.api.post('/products/$_productId/supplier-prices', data: {
                      'supplier_id': selectedSupplierId,
                      'sku_id': widget.data['sku_id'],
                      'unit_price': double.parse(priceCtrl.text),
                      'unit': unitCtrl.text.isEmpty ? null : unitCtrl.text,
                      'quoted_at': dateCtrl.text,
                      'note': noteCtrl.text.isEmpty ? null : noteCtrl.text,
                    });
                    if (ctx.mounted) Navigator.pop(ctx);
                    _loadQuotes();
                  } catch (e) {
                    if (ctx.mounted) {
                      ScaffoldMessenger.of(ctx).showSnackBar(SnackBar(content: Text('記錄失敗: $e')));
                    }
                  }
                },
                child: const Text('記錄'),
              ),
            ],
          );
        },
      ),
    );
  }
}
