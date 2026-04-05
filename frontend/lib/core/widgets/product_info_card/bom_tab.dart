import 'package:flutter/material.dart';

import '../../../infrastructure/api/api_client.dart';

/// BOM 組成件 tab — 顯示成品的零件列表 + 零件被哪些成品使用。
class BomTab extends StatefulWidget {
  final ApiClient api;
  final Map<String, dynamic> data;
  const BomTab({super.key, required this.api, required this.data});

  @override
  State<BomTab> createState() => _BomTabState();
}

class _BomTabState extends State<BomTab> {
  Map<String, dynamic>? _bomData;
  bool _loading = true;

  String get _skuId => widget.data['sku_id']?.toString() ?? '';
  String get _itemType => widget.data['item_type']?.toString() ?? 'finished';

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final res = await widget.api.get('/skus/$_skuId/bom');
      final body = res.data as Map<String, dynamic>;
      setState(() { _bomData = body['data'] as Map<String, dynamic>; _loading = false; });
    } catch (e) {
      setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_bomData == null) return Center(child: Text('載入失敗', style: TextStyle(color: Theme.of(context).colorScheme.outline)));

    final children = (_bomData!['children'] as List?) ?? [];
    final parents = (_bomData!['parents'] as List?) ?? [];
    final hint = _bomData!['assembly_hint'] as Map<String, dynamic>?;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // 組成件（我由什麼組成）
          if (_itemType == 'assembly') ...[
            Row(children: [
              Icon(Icons.account_tree, size: 18, color: Theme.of(context).colorScheme.primary),
              const SizedBox(width: 8),
              Text('組成件', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: Theme.of(context).colorScheme.primary)),
              if (hint != null) ...[
                const Spacer(),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                  decoration: BoxDecoration(
                    color: hint['can_assemble'] == true ? Colors.green.withValues(alpha: 0.1) : Colors.orange.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(
                    hint['can_assemble'] == true ? '零件充足，可組裝' : '零件不足',
                    style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600,
                      color: hint['can_assemble'] == true ? Colors.green.shade700 : Colors.orange.shade700),
                  ),
                ),
              ],
            ]),
            const SizedBox(height: 8),
            if (children.isEmpty)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 16),
                child: Center(child: Text('尚未設定組成件', style: TextStyle(color: Theme.of(context).colorScheme.outline))),
              )
            else
              ...children.map((c) {
                final cm = c as Map<String, dynamic>;
                final stock = cm['current_stock'] as num? ?? 0;
                final need = cm['quantity'] as num? ?? 1;
                final enough = stock >= need;
                return Card(
                  child: Padding(
                    padding: const EdgeInsets.all(12),
                    child: Row(children: [
                      Icon(enough ? Icons.check_circle : Icons.warning_amber, size: 18,
                        color: enough ? Colors.green : Colors.orange),
                      const SizedBox(width: 12),
                      Expanded(child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('${cm["brand"] ?? ""} ${cm["product_name"] ?? ""}',
                            style: const TextStyle(fontWeight: FontWeight.w600)),
                          Text('${cm["spec"] ?? ""}  ·  ${cm["component_role"] ?? ""}',
                            style: TextStyle(fontSize: 12, color: Theme.of(context).colorScheme.outline)),
                        ],
                      )),
                      Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
                        Text('需 $need', style: const TextStyle(fontSize: 13)),
                        Text('庫存 $stock', style: TextStyle(fontSize: 12,
                          color: enough ? Colors.green.shade700 : Colors.orange.shade700,
                          fontWeight: FontWeight.w600)),
                      ]),
                    ]),
                  ),
                );
              }),
          ],

          // 被使用（我被哪些成品使用）
          if (parents.isNotEmpty) ...[
            if (_itemType == 'assembly') const SizedBox(height: 24),
            Row(children: [
              Icon(Icons.link, size: 18, color: Theme.of(context).colorScheme.primary),
              const SizedBox(width: 8),
              Text('被以下組合品使用', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: Theme.of(context).colorScheme.primary)),
            ]),
            const SizedBox(height: 8),
            ...parents.map((p) {
              final pm = p as Map<String, dynamic>;
              return ListTile(
                dense: true,
                leading: const Icon(Icons.inventory_2, size: 18),
                title: Text('${pm["brand"] ?? ""} ${pm["product_name"] ?? ""}'),
                subtitle: Text('${pm["spec"] ?? ""}  ·  角色：${pm["component_role"] ?? ""}',
                  style: TextStyle(fontSize: 12, color: Theme.of(context).colorScheme.outline)),
              );
            }),
          ],

          // 非組合品且非零件
          if (children.isEmpty && parents.isEmpty)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 32),
              child: Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
                Icon(Icons.info_outline, size: 48, color: Theme.of(context).colorScheme.outline.withValues(alpha: 0.4)),
                const SizedBox(height: 8),
                Text('此品項沒有 BOM 關係', style: TextStyle(color: Theme.of(context).colorScheme.outline)),
              ])),
            ),
        ],
      ),
    );
  }
}
