import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../modules/customer/application/customer_provider.dart';
import '../../../infrastructure/api/api_client.dart';
import '../application/pos_provider.dart';
import 'pos_cart_item_tile.dart';
import 'pos_checkout_success.dart';

// ═══════════════════════════════════════════════════════
// 購物車面板 — 快捷鍵 + 數量直接輸入 + 改價
// ═══════════════════════════════════════════════════════
class CartPanel extends ConsumerStatefulWidget {
  const CartPanel({super.key});

  @override
  ConsumerState<CartPanel> createState() => CartPanelState();
}

class CartPanelState extends ConsumerState<CartPanel> {
  final _shortcutFocus = FocusNode();

  @override
  void dispose() {
    _shortcutFocus.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final pos = ref.watch(posProvider);
    final notifier = ref.read(posProvider.notifier);

    // 結帳成功 → 顯示明細
    if (pos.checkoutSuccess) {
      return CheckoutSuccessView(pos: pos, onNext: () => notifier.clearCart());
    }

    return KeyboardListener(
      focusNode: _shortcutFocus,
      autofocus: true,
      onKeyEvent: (event) {
        if (event is KeyDownEvent) {
          // F12 = 結帳
          if (event.logicalKey == LogicalKeyboardKey.f12 && pos.cart.isNotEmpty) {
            notifier.checkout();
          }
          // Escape = 清空
          if (event.logicalKey == LogicalKeyboardKey.escape && pos.cart.isNotEmpty) {
            notifier.clearCart();
          }
        }
      },
      child: Column(
        children: [
          // 標題
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 12, 12, 4),
            child: Row(
              children: [
                const Icon(Icons.shopping_cart, size: 24),
                const SizedBox(width: 8),
                Text('購物車 (${pos.itemCount})',
                    style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
                const Spacer(),
                if (pos.cart.isNotEmpty)
                  TextButton.icon(
                    icon: const Icon(Icons.delete_outline, size: 18),
                    label: const Text('清空'),
                    onPressed: () => notifier.clearCart(),
                  ),
              ],
            ),
          ),
          // 客戶選擇器
          const _CustomerSelector(),
          // 快捷鍵提示
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12),
            child: Text('F12 結帳 / Esc 清空',
                style: TextStyle(fontSize: 11, color: Theme.of(context).colorScheme.outline)),
          ),
          const Divider(height: 8),

          // 購物車列表
          Expanded(
            child: pos.cart.isEmpty
                ? Center(child: Text('搜尋品項加入購物車',
                    style: TextStyle(fontSize: 16, color: Theme.of(context).colorScheme.outline)))
                : ListView.builder(
                    itemCount: pos.cart.length,
                    itemBuilder: (context, index) {
                      final item = pos.cart[index];
                      return CartItemTile(
                        item: item,
                        onQuantityChanged: (qty) => notifier.updateQuantity(index, qty),
                        onPriceChanged: (price) {
                          item.unitPrice = price;
                          notifier.updateQuantity(index, item.quantity); // trigger rebuild
                        },
                        onRemove: () => notifier.removeItem(index),
                      );
                    },
                  ),
          ),

          // 底部：付款 + 合計 + 結帳
          if (pos.cart.isNotEmpty) ...[
            const Divider(height: 1),
            Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                children: [
                  // 付款方式
                  Row(
                    children: [
                      const Text('付款：', style: TextStyle(fontSize: 16)),
                      const SizedBox(width: 8),
                      Expanded(
                        child: SegmentedButton<String>(
                          segments: const [
                            ButtonSegment(value: 'cash', label: Text('現金')),
                            ButtonSegment(value: 'transfer', label: Text('轉帳')),
                            ButtonSegment(value: 'monthly_credit', label: Text('月結')),
                          ],
                          selected: {pos.paymentMethod},
                          onSelectionChanged: (s) => notifier.setPaymentMethod(s.first),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  // 含稅切換
                  Row(
                    children: [
                      const Text('稅別：', style: TextStyle(fontSize: 16)),
                      const SizedBox(width: 8),
                      SegmentedButton<String>(
                        segments: const [
                          ButtonSegment(value: 'none', label: Text('未稅')),
                          ButtonSegment(value: 'included', label: Text('含稅')),
                          ButtonSegment(value: 'extra', label: Text('稅外加')),
                        ],
                        selected: {pos.taxMode},
                        onSelectionChanged: (s) => notifier.setTaxMode(s.first),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  // 合計
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                    decoration: BoxDecoration(
                      color: Theme.of(context).colorScheme.primaryContainer.withOpacity(0.2),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Column(
                      children: [
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Text('${pos.cart.length} 項 / ${pos.itemCount} 個',
                                style: TextStyle(fontSize: 14, color: Theme.of(context).colorScheme.outline)),
                            Text('\$${pos.total.toStringAsFixed(0)}',
                                style: const TextStyle(fontSize: 36, fontWeight: FontWeight.bold, color: Colors.blue)),
                          ],
                        ),
                        if (pos.taxMode != 'none') ...[
                          const SizedBox(height: 4),
                          Row(
                            mainAxisAlignment: MainAxisAlignment.end,
                            children: [
                              Text('${pos.taxMode == "included" ? "含稅" : "外加"}  未稅 \$${pos.netAmount.toStringAsFixed(0)}  稅 \$${pos.taxAmount.toStringAsFixed(0)}  合計 \$${pos.total.toStringAsFixed(0)}',
                                  style: TextStyle(fontSize: 13, color: Theme.of(context).colorScheme.outline)),
                            ],
                          ),
                        ],
                      ],
                    ),
                  ),
                  const SizedBox(height: 12),
                  // 結帳按鈕
                  SizedBox(
                    width: double.infinity,
                    height: 60,
                    child: ElevatedButton.icon(
                      onPressed: pos.loading ? null : () => notifier.checkout(),
                      icon: pos.loading ? const SizedBox.shrink() : const Icon(Icons.check_circle, size: 28),
                      label: pos.loading
                          ? const CircularProgressIndicator(color: Colors.white)
                          : const Text('結帳 (F12)'),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.green,
                        foregroundColor: Colors.white,
                        textStyle: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
                      ),
                    ),
                  ),
                  if (pos.error != null) ...[
                    const SizedBox(height: 8),
                    Text(pos.error!, style: const TextStyle(color: Colors.red)),
                  ],
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }
}

// CartItemTile 已抽到 pos_cart_item_tile.dart

// ═══════════════════════════════════════════════════════
// ═══════════════════════════════════════════════════════
// 客戶選擇器
// ═══════════════════════════════════════════════════════
class _CustomerSelector extends ConsumerStatefulWidget {
  const _CustomerSelector();
  @override
  ConsumerState<_CustomerSelector> createState() => _CustomerSelectorState();
}

class _CustomerSelectorState extends ConsumerState<_CustomerSelector> {
  bool _showSearch = false;
  final _searchCtrl = TextEditingController();
  List<Map<String, dynamic>> _filtered = [];

  @override
  void initState() {
    super.initState();
    Future.microtask(() => ref.read(customerListProvider.notifier).load());
  }

  @override
  void dispose() { _searchCtrl.dispose(); super.dispose(); }

  void _selectCustomer(Map<String, dynamic>? customer) {
    final notifier = ref.read(posProvider.notifier);
    if (customer == null) {
      notifier.setCustomerId(null);
      notifier.setTaxMode('none');
    } else {
      notifier.setCustomerId(customer['customer_id']?.toString());
      final payTerms = (customer['payment_terms'] ?? '').toString();
      if (payTerms == 'monthly_credit') {
        notifier.setPaymentMethod('monthly_credit');
        notifier.setTaxMode('included');
      }
    }
    setState(() => _showSearch = false);
    _searchCtrl.clear();
  }

  @override
  Widget build(BuildContext context) {
    final pos = ref.watch(posProvider);
    final custState = ref.watch(customerListProvider);
    final selectedId = pos.customerId;

    String? selectedName;
    if (selectedId != null) {
      final found = custState.customers.where(
          (c) => c['customer_id']?.toString() == selectedId).toList();
      if (found.isNotEmpty) selectedName = found[0]['name']?.toString();
    }

    // 已選客戶 → 顯示名稱 + 清除按鈕
    if (selectedName != null) {
      return Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
          decoration: BoxDecoration(
            color: Theme.of(context).colorScheme.primaryContainer.withOpacity(0.2),
            borderRadius: BorderRadius.circular(8),
          ),
          child: Row(children: [
            const Icon(Icons.person, size: 20, color: Colors.blue),
            const SizedBox(width: 8),
            Expanded(child: Text(selectedName, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600))),
            InkWell(onTap: () => _selectCustomer(null),
                child: const Icon(Icons.close, size: 18, color: Colors.grey)),
          ]),
        ),
      );
    }

    // 未選客戶 → 直接輸入框
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
      child: Column(children: [
        TextField(
          controller: _searchCtrl,
          decoration: InputDecoration(
            hintText: '輸入客戶名稱（留空 = 現金散客）',
            prefixIcon: const Icon(Icons.person_search, size: 20),
            isDense: true,
            contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
            suffixIcon: _searchCtrl.text.isNotEmpty
                ? IconButton(icon: const Icon(Icons.clear, size: 16),
                    onPressed: () { _searchCtrl.clear(); setState(() { _filtered = []; _showSearch = false; }); })
                : null,
          ),
          onTap: () => setState(() => _showSearch = true),
          onChanged: (v) {
            final all = ref.read(customerListProvider).customers;
            setState(() {
              _showSearch = true;
              _filtered = v.trim().isEmpty ? []
                  : all.where((c) {
                      final name = (c['name'] ?? '').toString().toLowerCase();
                      final phone = (c['phone'] ?? '').toString();
                      return name.contains(v.toLowerCase()) || phone.contains(v);
                    }).toList();
            });
          },
        ),
        if (_filtered.isNotEmpty)
          ConstrainedBox(
            constraints: const BoxConstraints(maxHeight: 180),
            child: Card(
              margin: const EdgeInsets.only(top: 2),
              child: ListView(shrinkWrap: true, padding: EdgeInsets.zero,
                children: _filtered.take(8).map((c) {
                  final name = (c['name'] ?? '').toString();
                  final phone = (c['phone'] ?? '').toString();
                  final isMonthly = c['payment_terms'] == 'monthly_credit';
                  return ListTile(dense: true, visualDensity: VisualDensity.compact,
                    title: Text(name, style: const TextStyle(fontSize: 14)),
                    subtitle: phone.isNotEmpty ? Text(phone, style: const TextStyle(fontSize: 12)) : null,
                    trailing: isMonthly ? const Text('月結', style: TextStyle(fontSize: 11, color: Colors.blue)) : null,
                    onTap: () => _selectCustomer(c));
                }).toList()),
            ),
          ),
      ]),
    );
  }
}
