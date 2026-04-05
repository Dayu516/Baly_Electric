import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/widgets/product_info_card.dart';
import '../../../infrastructure/api/api_client.dart';
import '../application/pos_provider.dart';

class CartItemTile extends ConsumerWidget {
  final CartItem item;
  final ValueChanged<int> onQuantityChanged;
  final ValueChanged<double> onPriceChanged;
  final VoidCallback onRemove;

  const CartItemTile({
    super.key,
    required this.item,
    required this.onQuantityChanged,
    required this.onPriceChanged,
    required this.onRemove,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Dismissible(
      key: ValueKey(item.skuId),
      direction: DismissDirection.endToStart,
      onDismissed: (_) => onRemove(),
      background: Container(
        color: Colors.red, alignment: Alignment.centerRight,
        padding: const EdgeInsets.only(right: 20),
        child: const Icon(Icons.delete, color: Colors.white),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
        child: Card(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            child: Row(
              children: [
                Expanded(
                  flex: 3,
                  child: InkWell(
                    onTap: () => showProductInfoCard(context, ref, skuId: item.skuId),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(item.productName,
                            style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w500),
                            overflow: TextOverflow.ellipsis),
                        if (item.spec != null)
                          Text(item.spec!,
                              style: TextStyle(fontSize: 12, color: Theme.of(context).colorScheme.outline)),
                      ],
                    ),
                  ),
                ),
                InkWell(
                  onTap: () => _editPrice(context),
                  borderRadius: BorderRadius.circular(6),
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      border: Border.all(color: Theme.of(context).colorScheme.outline.withOpacity(0.3)),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Text('\$${item.unitPrice.toStringAsFixed(0)}',
                        style: const TextStyle(fontSize: 14)),
                  ),
                ),
                const SizedBox(width: 4),
                const Text('×', style: TextStyle(fontSize: 14, color: Colors.grey)),
                const SizedBox(width: 4),
                InkWell(
                  onTap: () => _editQuantity(context),
                  borderRadius: BorderRadius.circular(6),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      InkWell(
                        onTap: () => onQuantityChanged(item.quantity - 1),
                        child: const Padding(
                          padding: EdgeInsets.all(4),
                          child: Icon(Icons.remove_circle_outline, size: 24),
                        ),
                      ),
                      Container(
                        width: 40, alignment: Alignment.center,
                        padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 4),
                        decoration: BoxDecoration(
                          color: Theme.of(context).colorScheme.primaryContainer.withOpacity(0.3),
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: Text('${item.quantity}',
                            style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
                      ),
                      InkWell(
                        onTap: () => onQuantityChanged(item.quantity + 1),
                        child: const Padding(
                          padding: EdgeInsets.all(4),
                          child: Icon(Icons.add_circle_outline, size: 24),
                        ),
                      ),
                    ],
                  ),
                ),
                SizedBox(
                  width: 70,
                  child: Text('\$${item.lineTotal.toStringAsFixed(0)}',
                      style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                      textAlign: TextAlign.right),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  void _editQuantity(BuildContext context) {
    final ctrl = TextEditingController(text: '${item.quantity}');
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(item.productName, style: const TextStyle(fontSize: 16)),
        content: TextField(
          controller: ctrl,
          autofocus: true,
          keyboardType: TextInputType.number,
          decoration: const InputDecoration(labelText: '數量'),
          style: const TextStyle(fontSize: 24),
          onSubmitted: (v) {
            final qty = int.tryParse(v) ?? item.quantity;
            onQuantityChanged(qty);
            Navigator.pop(ctx);
          },
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('取消')),
          ElevatedButton(
            onPressed: () {
              final qty = int.tryParse(ctrl.text) ?? item.quantity;
              onQuantityChanged(qty);
              Navigator.pop(ctx);
            },
            child: const Text('確定'),
          ),
        ],
      ),
    );
  }

  void _editPrice(BuildContext context) {
    final ctrl = TextEditingController(text: '${item.unitPrice.toStringAsFixed(0)}');
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(item.productName, style: const TextStyle(fontSize: 16)),
        content: TextField(
          controller: ctrl,
          autofocus: true,
          keyboardType: TextInputType.number,
          decoration: const InputDecoration(labelText: '單價', prefixText: '\$'),
          style: const TextStyle(fontSize: 24),
          onSubmitted: (v) {
            final price = double.tryParse(v) ?? item.unitPrice;
            onPriceChanged(price);
            Navigator.pop(ctx);
          },
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('取消')),
          ElevatedButton(
            onPressed: () {
              final price = double.tryParse(ctrl.text) ?? item.unitPrice;
              onPriceChanged(price);
              Navigator.pop(ctx);
            },
            child: const Text('確定'),
          ),
        ],
      ),
    );
  }
}
