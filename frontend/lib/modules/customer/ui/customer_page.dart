import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/feature_flags.dart';
import '../../../core/router/app_router.dart';
import '../application/customer_provider.dart';
import 'customer_create_dialog.dart';

class CustomerPage extends ConsumerStatefulWidget {
  const CustomerPage({super.key});

  @override
  ConsumerState<CustomerPage> createState() => _CustomerPageState();
}

class _CustomerPageState extends ConsumerState<CustomerPage> {
  @override
  void initState() {
    super.initState();
    Future.microtask(() => ref.read(customerListProvider.notifier).load());
  }

  @override
  Widget build(BuildContext context) {
    final device = getDeviceClass(context);
    return switch (device) {
      DeviceClass.desktop => _CustomerDesktopLayout(),
      DeviceClass.tablet => _CustomerDesktopLayout(),
      DeviceClass.phone => const _CustomerListPanel(),
    };
  }
}

// ═══════════════════════════════════════════════════════
// Desktop — 左: 客戶列表  右: 詳情 + 月結
// ═══════════════════════════════════════════════════════
class _CustomerDesktopLayout extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return const Row(
      children: [
        Expanded(flex: 2, child: _CustomerListPanel()),
        VerticalDivider(width: 1),
        Expanded(flex: 3, child: _CustomerDetailPanel()),
      ],
    );
  }
}

// ── 客戶列表 ──────────────────────────────────────────
class _CustomerListPanel extends ConsumerStatefulWidget {
  const _CustomerListPanel();
  @override
  ConsumerState<_CustomerListPanel> createState() => _CustomerListPanelState();
}

class _CustomerListPanelState extends ConsumerState<_CustomerListPanel> {
  final _searchCtrl = TextEditingController();
  String _filter = '';

  @override
  void dispose() { _searchCtrl.dispose(); super.dispose(); }

  @override
  Widget build(BuildContext context) {
    final custState = ref.watch(customerListProvider);
    final selected = custState.selectedCustomerId;

    final filtered = _filter.isEmpty
        ? custState.customers
        : custState.customers.where((c) {
            final name = (c['name'] ?? '').toString().toLowerCase();
            final phone = (c['phone'] ?? '').toString();
            return name.contains(_filter.toLowerCase()) || phone.contains(_filter);
          }).toList();

    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
          child: Row(
            children: [
              Text('客戶管理', style: Theme.of(context).textTheme.titleLarge),
              const SizedBox(width: 8),
              Text('${filtered.length} 筆',
                  style: TextStyle(color: Theme.of(context).colorScheme.outline)),
              const Spacer(),
              ElevatedButton.icon(
                icon: const Icon(Icons.add),
                label: const Text('新增'),
                onPressed: () {
                  showDialog(context: context, builder: (_) => const CustomerCreateDialog())
                      .then((created) { if (created == true) ref.read(customerListProvider.notifier).load(); });
                },
              ),
            ],
          ),
        ),
        Padding(
          padding: const EdgeInsets.all(12),
          child: TextField(
            controller: _searchCtrl,
            decoration: const InputDecoration(
              hintText: '搜尋客戶名稱、電話...',
              prefixIcon: Icon(Icons.search),
              isDense: true,
            ),
            onChanged: (v) => setState(() => _filter = v),
          ),
        ),
        Expanded(
          child: custState.loading
              ? const Center(child: CircularProgressIndicator())
              : ListView.builder(
                  itemCount: filtered.length,
                  itemBuilder: (context, index) {
                    final c = filtered[index];
                    final cid = (c['customer_id'] ?? '').toString();
                    final isSelected = cid == selected;
                    final payTerms = c['payment_terms']?.toString() ?? 'cash';
                    final isMonthly = payTerms == 'monthly_credit';

                    return Material(
                      color: isSelected
                          ? Theme.of(context).colorScheme.primaryContainer.withOpacity(0.3) : null,
                      child: InkWell(
                        onTap: () {
                          ref.read(customerListProvider.notifier).select(c);
                          final cid = (c['customer_id'] ?? '').toString();
                          if (cid.isNotEmpty) {
                            ref.read(arListProvider.notifier).load(cid);
                          }
                        },
                        child: Padding(
                          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                          child: Row(
                            children: [
                              CircleAvatar(
                                radius: 18,
                                backgroundColor: isMonthly
                                    ? Colors.blue.withOpacity(0.15) : Colors.grey.withOpacity(0.1),
                                child: Text(
                                  (c['name'] ?? '?').toString()[0],
                                  style: TextStyle(fontWeight: FontWeight.bold,
                                      color: isMonthly ? Colors.blue : Colors.grey),
                                ),
                              ),
                              const SizedBox(width: 12),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text((c['name'] ?? '').toString(),
                                        style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w500)),
                                    Text((c['phone'] ?? '').toString(),
                                        style: TextStyle(fontSize: 12, color: Theme.of(context).colorScheme.outline)),
                                  ],
                                ),
                              ),
                              if (isMonthly)
                                Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                                  decoration: BoxDecoration(
                                    color: Colors.blue.withOpacity(0.1),
                                    borderRadius: BorderRadius.circular(10),
                                  ),
                                  child: const Text('月結', style: TextStyle(fontSize: 11, color: Colors.blue, fontWeight: FontWeight.w600)),
                                ),
                            ],
                          ),
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

// ── 客戶詳情 + 月結 ──────────────────────────────────
class _CustomerDetailPanel extends ConsumerWidget {
  const _CustomerDetailPanel();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final custState = ref.watch(customerListProvider);
    final customer = custState.selectedCustomer;

    if (customer == null) {
      return Center(child: Text('點擊左側客戶查看詳情',
          style: TextStyle(fontSize: 16, color: Theme.of(context).colorScheme.outline)));
    }

    final name = (customer['name'] ?? '').toString();
    final phone = (customer['phone'] ?? '').toString();
    final address = (customer['address'] ?? '').toString();
    final payTerms = (customer['payment_terms'] ?? '').toString();
    final note = (customer['note'] ?? '').toString();
    final isMonthly = payTerms == 'monthly_credit';
    final customerId = (customer['customer_id'] ?? '').toString();

    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // 標題
          Row(
            children: [
              CircleAvatar(
                radius: 28,
                backgroundColor: isMonthly ? Colors.blue.withOpacity(0.15) : Colors.grey.withOpacity(0.1),
                child: Text(name.isNotEmpty ? name[0] : '?',
                    style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold,
                        color: isMonthly ? Colors.blue : Colors.grey)),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(name, style: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold)),
                    Row(children: [
                      if (isMonthly)
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
                          margin: const EdgeInsets.only(right: 8),
                          decoration: BoxDecoration(
                            color: Colors.blue.withOpacity(0.1), borderRadius: BorderRadius.circular(12)),
                          child: const Text('月結客戶', style: TextStyle(fontSize: 12, color: Colors.blue, fontWeight: FontWeight.w600)),
                        ),
                      if (!isMonthly)
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
                          decoration: BoxDecoration(
                            color: Colors.grey.withOpacity(0.1), borderRadius: BorderRadius.circular(12)),
                          child: const Text('現金客戶', style: TextStyle(fontSize: 12, color: Colors.grey)),
                        ),
                    ]),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 24),
          const Divider(),

          // 基本資料
          const SizedBox(height: 16),
          Text('基本資料', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 12),
          _InfoRow(icon: Icons.phone, label: '電話', value: phone),
          _InfoRow(icon: Icons.location_on, label: '地址', value: address),
          _InfoRow(icon: Icons.note, label: '備註', value: note),
          const SizedBox(height: 24),

          // 月結功能（月結客戶才顯示）
          if (isMonthly) ...[
            const Divider(),
            const SizedBox(height: 16),
            Row(
              children: [
                Text('月結帳款', style: Theme.of(context).textTheme.titleMedium),
                const Spacer(),
                ElevatedButton.icon(
                  icon: const Icon(Icons.receipt_long, size: 18),
                  label: const Text('產生月結單'),
                  onPressed: () => _generateStatement(context, ref, customerId),
                ),
              ],
            ),
            const SizedBox(height: 12),
            _ArListWidget(customerId: customerId),
          ],
        ],
      ),
    );
  }

  void _generateStatement(BuildContext context, WidgetRef ref, String customerId) {
    final now = DateTime.now();
    final period = '${now.year}-${now.month.toString().padLeft(2, '0')}';
    final periodCtrl = TextEditingController(text: period);

    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('產生月結單'),
        content: TextField(
          controller: periodCtrl,
          decoration: const InputDecoration(labelText: '期間（YYYY-MM）', hintText: '2026-04'),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('取消')),
          ElevatedButton(
            onPressed: () async {
              final ok = await ref.read(arProvider.notifier).generateStatement(customerId, periodCtrl.text.trim());
              if (ctx.mounted) Navigator.pop(ctx);
              if (ok) {
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(content: Text(ref.read(arProvider).message ?? '月結單已生成')),
                );
              }
            },
            child: const Text('產生'),
          ),
        ],
      ),
    );
  }
}

class _ArListWidget extends ConsumerWidget {
  final String customerId;
  const _ArListWidget({required this.customerId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final arList = ref.watch(arListProvider);
    final arAction = ref.watch(arProvider);

    if (arAction.message != null) {
      // 操作成功提示
      Future.microtask(() {
        ref.read(arProvider.notifier).clear();
        ref.read(arListProvider.notifier).load(customerId);
      });
    }

    if (arList.loading) return const Center(child: CircularProgressIndicator());
    if (arList.items.isEmpty) {
      return Text('尚無月結紀錄', style: TextStyle(color: Theme.of(context).colorScheme.outline));
    }

    return Column(
      children: arList.items.map((ar) {
        final arId = (ar['ar_id'] ?? '').toString();
        final period = (ar['period'] ?? '').toString();
        final totalAmt = (ar['total_amount'] as num?)?.toDouble() ?? 0;
        final paidAmt = (ar['paid_amount'] as num?)?.toDouble() ?? 0;
        final status = (ar['status'] ?? '').toString();
        final remaining = totalAmt - paidAmt;

        final statusColor = switch (status) {
          'paid' => Colors.green,
          'overdue' => Colors.red,
          'partial_paid' => Colors.orange,
          _ => Colors.blue,
        };
        final statusLabel = switch (status) {
          'paid' => '已付清',
          'overdue' => '逾期',
          'partial_paid' => '部分付款',
          'open' => '未付',
          _ => status,
        };

        return Card(
          margin: const EdgeInsets.only(bottom: 8),
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Row(
              children: [
                // 期間
                Text(period, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                const SizedBox(width: 16),
                // 金額
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('應收 \${totalAmt.toStringAsFixed(0)}', style: const TextStyle(fontSize: 14)),
                      if (paidAmt > 0)
                        Text('已收 \${paidAmt.toStringAsFixed(0)}  剩餘 \${remaining.toStringAsFixed(0)}',
                            style: TextStyle(fontSize: 12, color: Theme.of(context).colorScheme.outline)),
                    ],
                  ),
                ),
                // 狀態
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: statusColor.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(statusLabel, style: TextStyle(fontSize: 12, color: statusColor, fontWeight: FontWeight.w600)),
                ),
                const SizedBox(width: 8),
                // 收款按鈕
                if (status != 'paid')
                  TextButton(
                    onPressed: () => _showPaymentDialog(context, ref, arId, remaining),
                    child: const Text('收款'),
                  ),
              ],
            ),
          ),
        );
      }).toList(),
    );
  }

  void _showPaymentDialog(BuildContext context, WidgetRef ref, String arId, double remaining) {
    final amtCtrl = TextEditingController(text: remaining.toStringAsFixed(0));
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('記錄收款'),
        content: TextField(
          controller: amtCtrl, autofocus: true,
          keyboardType: TextInputType.number,
          decoration: InputDecoration(labelText: '收款金額', prefixText: '\$', hintText: remaining.toStringAsFixed(0)),
          style: const TextStyle(fontSize: 24),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('取消')),
          ElevatedButton(
            onPressed: () async {
              final amt = double.tryParse(amtCtrl.text) ?? 0;
              if (amt <= 0) return;
              await ref.read(arProvider.notifier).recordPayment(arId, amt);
              if (ctx.mounted) Navigator.pop(ctx);
              ref.read(arListProvider.notifier).load(customerId);
            },
            child: const Text('確認收款'),
          ),
        ],
      ),
    );
  }
}

class _InfoRow extends StatelessWidget {
  final IconData icon;
  final String label;
  final String value;

  const _InfoRow({required this.icon, required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    if (value.isEmpty) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: 18, color: Theme.of(context).colorScheme.outline),
          const SizedBox(width: 8),
          SizedBox(width: 50, child: Text(label,
              style: TextStyle(fontSize: 13, color: Theme.of(context).colorScheme.outline))),
          const SizedBox(width: 8),
          Expanded(child: Text(value, style: const TextStyle(fontSize: 15))),
        ],
      ),
    );
  }
}