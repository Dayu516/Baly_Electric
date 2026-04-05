import 'package:flutter/material.dart';

class SupplierPricingTab extends StatelessWidget {
  final Map<String, dynamic> data;
  const SupplierPricingTab({super.key, required this.data});

  @override
  Widget build(BuildContext context) {
    final suppliers = (data['suppliers'] as List?) ?? [];

    if (suppliers.isEmpty) {
      return Center(child: Text('尚無供應商報價資料', style: TextStyle(color: Theme.of(context).colorScheme.outline)));
    }

    return ListView.builder(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      itemCount: suppliers.length,
      itemBuilder: (ctx, i) {
        final s = suppliers[i] as Map<String, dynamic>;
        final cost = s['unit_cost'];
        final preferred = s['is_preferred'] == true;

        return Card(
          color: preferred ? Colors.blue.withValues(alpha: 0.04) : null,
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Row(children: [
              if (preferred) ...[
                const Icon(Icons.star, size: 16, color: Colors.orange),
                const SizedBox(width: 4),
              ],
              Expanded(child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(s['supplier_name']?.toString() ?? '',
                      style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600)),
                  if (s['supplier_phone']?.toString().isNotEmpty == true)
                    Text(s['supplier_phone'].toString(),
                        style: TextStyle(fontSize: 12, color: Theme.of(ctx).colorScheme.outline)),
                  if (s['note']?.toString().isNotEmpty == true)
                    Text(s['note'].toString(),
                        style: TextStyle(fontSize: 12, color: Theme.of(ctx).colorScheme.outline)),
                ],
              )),
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text(cost != null ? '\$$cost' : '未報價',
                      style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold,
                          color: cost != null ? Colors.green.shade700 : Colors.grey)),
                  if (s['pack_unit']?.toString().isNotEmpty == true)
                    Text(s['pack_unit'].toString(), style: const TextStyle(fontSize: 12)),
                  if (s['min_order_qty'] != null)
                    Text('最少 ${s["min_order_qty"]}', style: TextStyle(fontSize: 12, color: Theme.of(ctx).colorScheme.outline)),
                  if (s['lead_days'] != null)
                    Text('${s["lead_days"]} 天到貨', style: TextStyle(fontSize: 12, color: Theme.of(ctx).colorScheme.outline)),
                ],
              ),
            ]),
          ),
        );
      },
    );
  }
}
