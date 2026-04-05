import 'package:flutter/material.dart';

import '../../../infrastructure/api/api_client.dart';

class BasicInfoTab extends StatefulWidget {
  final ApiClient api;
  final Map<String, dynamic> data;
  const BasicInfoTab({super.key, required this.api, required this.data});

  @override
  State<BasicInfoTab> createState() => _BasicInfoTabState();
}

class _BasicInfoTabState extends State<BasicInfoTab> {
  List<Map<String, dynamic>> _templates = [];
  Map<String, String> _attrValues = {};
  bool _attrsLoading = true;
  bool _attrsDirty = false;
  bool _saving = false;

  Map<String, dynamic> get data => widget.data;
  String get _productId => data['product_id']?.toString() ?? '';
  String? get _categoryId => data['category_id']?.toString();

  @override
  void initState() {
    super.initState();
    _loadAttributes();
  }

  Future<void> _loadAttributes() async {
    if (_categoryId == null || _categoryId!.isEmpty) {
      setState(() => _attrsLoading = false);
      return;
    }
    try {
      final tmplFuture = widget.api.get('/attributes/templates/$_categoryId');
      final attrFuture = widget.api.get('/attributes/product/$_productId');
      final results = await Future.wait([tmplFuture, attrFuture]);

      final tmplBody = results[0].data as Map<String, dynamic>;
      final attrBody = results[1].data as Map<String, dynamic>;

      final templates = (tmplBody['data'] as List).cast<Map<String, dynamic>>();
      final attrs = (attrBody['data'] as List).cast<Map<String, dynamic>>();

      final values = <String, String>{};
      for (final a in attrs) {
        values[a['key']?.toString() ?? ''] = a['value']?.toString() ?? '';
      }

      setState(() { _templates = templates; _attrValues = values; _attrsLoading = false; });
    } catch (e) {
      setState(() => _attrsLoading = false);
    }
  }

  Future<void> _saveAttributes() async {
    setState(() => _saving = true);
    try {
      final attrs = _attrValues.entries
          .where((e) => e.value.isNotEmpty)
          .map((e) {
            final tmpl = _templates.where((t) => t['key'] == e.key);
            return {'key': e.key, 'value': e.value, 'unit': tmpl.isNotEmpty ? tmpl.first['unit'] : null};
          }).toList();

      await widget.api.put('/attributes/product/$_productId', data: attrs);
      setState(() { _attrsDirty = false; _saving = false; });
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('屬性已儲存'), duration: Duration(seconds: 2)),
        );
      }
    } catch (e) {
      setState(() => _saving = false);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('儲存失敗: $e')));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final aliases = (data['aliases'] as List?) ?? [];
    final movements = (data['recent_movements'] as List?) ?? [];

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Wrap(spacing: 20, runSpacing: 8, children: [
            if (_has('series')) _infoRow('系列', data['series']),
            if (_has('model_number')) _infoRow('型號', data['model_number']),
            if (_has('barcode')) _infoRow('條碼', data['barcode']),
            if (_has('internal_code')) _infoRow('內部編號', data['internal_code']),
            if (_has('supplier_code')) _infoRow('供應商料號', data['supplier_code']),
            if (data['min_stock'] != null) _infoRow('安全庫存', '${data["min_stock"]}'),
          ]),

          if (_attrsLoading)
            const Padding(padding: EdgeInsets.only(top: 16), child: LinearProgressIndicator())
          else if (_templates.isNotEmpty) ...[
            const SizedBox(height: 16),
            Row(children: [
              Text('品項屬性', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: Theme.of(context).colorScheme.primary)),
              const Spacer(),
              if (_attrsDirty)
                FilledButton.tonalIcon(
                  onPressed: _saving ? null : _saveAttributes,
                  icon: _saving
                      ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                      : const Icon(Icons.save, size: 16),
                  label: const Text('儲存屬性'),
                ),
            ]),
            const SizedBox(height: 8),
            Wrap(
              spacing: 12,
              runSpacing: 12,
              children: _templates.map((t) {
                final key = t['key']?.toString() ?? '';
                final options = (t['options'] as List?)?.cast<String>();
                final unit = t['unit']?.toString();
                final currentValue = _attrValues[key] ?? '';
                final matchType = t['match_type']?.toString();

                return SizedBox(
                  width: 170,
                  child: options != null && options.isNotEmpty
                      ? DropdownButtonFormField<String>(
                          value: options.contains(currentValue) ? currentValue : null,
                          decoration: InputDecoration(
                            labelText: '$key${unit != null ? " ($unit)" : ""}',
                            border: const OutlineInputBorder(),
                            isDense: true,
                            suffixIcon: matchType == 'must'
                                ? Tooltip(message: '替代品必須一致', child: Icon(Icons.lock, size: 14, color: Colors.red.shade300))
                                : null,
                          ),
                          items: [
                            const DropdownMenuItem(value: '', child: Text('—', style: TextStyle(color: Colors.grey))),
                            ...options.map((o) => DropdownMenuItem(value: o, child: Text(o))),
                          ],
                          onChanged: (v) => setState(() {
                            _attrValues[key] = v ?? '';
                            _attrsDirty = true;
                          }),
                        )
                      : TextFormField(
                          initialValue: currentValue,
                          decoration: InputDecoration(
                            labelText: '$key${unit != null ? " ($unit)" : ""}',
                            border: const OutlineInputBorder(),
                            isDense: true,
                          ),
                          onChanged: (v) {
                            _attrValues[key] = v;
                            if (!_attrsDirty) setState(() => _attrsDirty = true);
                          },
                        ),
                );
              }).toList(),
            ),
          ] else if (_categoryId != null && _categoryId!.isNotEmpty) ...[
            const SizedBox(height: 16),
            Text('此分類尚未設定屬性模板', style: TextStyle(fontSize: 12, color: Theme.of(context).colorScheme.outline)),
          ],

          if (aliases.isNotEmpty) ...[
            const SizedBox(height: 16),
            Text('別名', style: TextStyle(fontSize: 13, color: Theme.of(context).colorScheme.outline)),
            const SizedBox(height: 4),
            Wrap(spacing: 6, runSpacing: 6, children: aliases.map((a) => Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
              decoration: BoxDecoration(color: Colors.indigo.withValues(alpha: 0.08), borderRadius: BorderRadius.circular(10)),
              child: Text(a['alias']?.toString() ?? '', style: const TextStyle(fontSize: 12)),
            )).toList()),
          ],

          if (movements.isNotEmpty) ...[
            const SizedBox(height: 16),
            Text('最近異動', style: TextStyle(fontSize: 13, color: Theme.of(context).colorScheme.outline)),
            const SizedBox(height: 4),
            ...movements.take(5).map((m) {
              final qty = m['quantity'] as num? ?? 0;
              final type = switch (m['type']?.toString()) {
                'sale' => '銷售', 'purchase_receive' => '進貨', 'adjustment' => '調整',
                'return' => '退貨', _ => m['type']?.toString() ?? '',
              };
              return Text(
                '${m["date"]}  ${qty >= 0 ? "+" : ""}$qty ($type)',
                style: TextStyle(fontSize: 12, color: qty >= 0 ? Colors.green : Colors.red),
              );
            }),
          ],
        ],
      ),
    );
  }

  bool _has(String key) {
    final v = data[key];
    return v != null && v.toString().isNotEmpty;
  }

  Widget _infoRow(String label, String? value) {
    return Row(mainAxisSize: MainAxisSize.min, children: [
      Text('$label ', style: TextStyle(fontSize: 13, color: Theme.of(context).colorScheme.outline)),
      Text(value ?? '', style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
    ]);
  }
}
