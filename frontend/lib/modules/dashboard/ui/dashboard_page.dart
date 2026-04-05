import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/auth/auth_provider.dart';
import '../../../core/feature_flags.dart';
import '../../../core/router/app_router.dart';
import '../../../core/widgets/feature_locked_page.dart';
import '../application/dashboard_provider.dart';

class DashboardPage extends ConsumerStatefulWidget {
  const DashboardPage({super.key});

  @override
  ConsumerState<DashboardPage> createState() => _DashboardPageState();
}

class _DashboardPageState extends ConsumerState<DashboardPage> {
  @override
  void initState() {
    super.initState();
    Future.microtask(() => ref.read(dashboardProvider.notifier).load());
  }

  @override
  Widget build(BuildContext context) {
    final device = getDeviceClass(context);
    final level = FeatureFlags.getLevel('dashboard', device);

    if (level == FeatureLevel.c) {
      return const FeatureLockedPage(
        featureName: '首頁',
        guidanceMessage: '請在桌面版檢視首頁',
      );
    }

    final state = ref.watch(dashboardProvider);
    final auth = ref.watch(authProvider);

    if (state.loading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (state.error != null) {
      return Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
        Text('載入失敗', style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: 8),
        Text(state.error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
        const SizedBox(height: 16),
        FilledButton.tonalIcon(
          onPressed: () => ref.read(dashboardProvider.notifier).load(),
          icon: const Icon(Icons.refresh),
          label: const Text('重試'),
        ),
      ]));
    }

    final stats = state.stats ?? {};

    return RefreshIndicator(
      onRefresh: () => ref.read(dashboardProvider.notifier).load(),
      child: SingleChildScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // 標題
            Row(children: [
              Text('你好，${auth.displayName ?? auth.username ?? ''}',
                style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.bold)),
              const Spacer(),
              FilledButton.tonalIcon(
                onPressed: () => ref.read(dashboardProvider.notifier).load(),
                icon: const Icon(Icons.refresh, size: 18),
                label: const Text('更新'),
              ),
            ]),
            const SizedBox(height: 24),

            // 摘要卡片
            _StatsRow(stats: stats, onTap: _navigate),
            const SizedBox(height: 24),

            // 兩欄：今日銷售 + 低庫存
            LayoutBuilder(builder: (context, constraints) {
              if (constraints.maxWidth >= 800) {
                return Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(child: _TodaySalesCard(sales: state.todaySales)),
                    const SizedBox(width: 24),
                    Expanded(child: _LowStockCard(items: state.lowStockItems)),
                  ],
                );
              }
              return Column(children: [
                _TodaySalesCard(sales: state.todaySales),
                const SizedBox(height: 24),
                _LowStockCard(items: state.lowStockItems),
              ]);
            }),
          ],
        ),
      ),
    );
  }

  void _navigate(String path) {
    GoRouter.of(context).go(path);
  }
}

// ═══════════════════════════════════════════════════════
// 摘要數字卡片列
// ═══════════════════════════════════════════════════════
class _StatsRow extends StatelessWidget {
  final Map<String, dynamic> stats;
  final void Function(String path) onTap;
  const _StatsRow({required this.stats, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: 16,
      runSpacing: 16,
      children: [
        _StatCard(
          icon: Icons.point_of_sale, color: Colors.green,
          title: '今日營業額',
          value: '\$${_fmt(stats['today_sales_total'])}',
          subtitle: '${stats['today_sales_count'] ?? 0} 筆',
          onTap: () => onTap('/sales'),
        ),
        _StatCard(
          icon: Icons.calendar_month, color: Colors.blue,
          title: '本月營業額',
          value: '\$${_fmt(stats['month_sales_total'])}',
          subtitle: '${stats['month_sales_count'] ?? 0} 筆',
          onTap: () => onTap('/sales'),
        ),
        _StatCard(
          icon: Icons.warning_amber, color: Colors.orange,
          title: '低庫存',
          value: '${stats['low_stock_count'] ?? 0}',
          subtitle: '品項需補貨',
          onTap: () {},
        ),
        _StatCard(
          icon: Icons.checklist, color: Colors.purple,
          title: '待審核',
          value: '${stats['pending_reviews'] ?? 0}',
          subtitle: '筆待處理',
          onTap: () => onTap('/reviews'),
        ),
        _StatCard(
          icon: Icons.notifications_active, color: Colors.red,
          title: '未讀警示',
          value: '${stats['unread_alerts'] ?? 0}',
          subtitle: '筆通知',
          onTap: () => onTap('/alerts'),
        ),
        _StatCard(
          icon: Icons.local_shipping, color: Colors.teal,
          title: '進行中採購',
          value: '${stats['active_purchase_orders'] ?? 0}',
          subtitle: '張採購單',
          onTap: () => onTap('/procurement'),
        ),
        _StatCard(
          icon: Icons.account_balance_wallet, color: Colors.indigo,
          title: '應收帳款',
          value: '\$${_fmt(stats['ar_outstanding'])}',
          subtitle: '未收款',
          onTap: () => onTap('/customers'),
        ),
        if ((stats['backorder_total_active'] ?? 0) > 0)
          _StatCard(
            icon: Icons.pending_actions, color: Colors.deepOrange,
            title: '欠貨待補',
            value: '${stats['backorder_total_active'] ?? 0}',
            subtitle: '到貨 ${stats['backorder_ready_pickup'] ?? 0} 筆',
            onTap: () => onTap('/sales'),
          ),
      ],
    );
  }

  String _fmt(dynamic v) {
    if (v == null) return '0';
    final n = v is num ? v : num.tryParse(v.toString()) ?? 0;
    if (n >= 10000) return '${(n / 10000).toStringAsFixed(1)}萬';
    return n.toStringAsFixed(0);
  }
}

class _StatCard extends StatelessWidget {
  final IconData icon;
  final Color color;
  final String title;
  final String value;
  final String subtitle;
  final VoidCallback onTap;

  const _StatCard({
    required this.icon, required this.color, required this.title,
    required this.value, required this.subtitle, required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 160,
      child: Card(
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(icon, color: color, size: 24),
                const SizedBox(height: 12),
                Text(value, style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold, color: color)),
                const SizedBox(height: 4),
                Text(title, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
                Text(subtitle, style: TextStyle(fontSize: 12, color: Theme.of(context).colorScheme.outline)),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════
// 今日銷售卡片
// ═══════════════════════════════════════════════════════
class _TodaySalesCard extends StatelessWidget {
  final List<Map<String, dynamic>> sales;
  const _TodaySalesCard({required this.sales});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(children: [
              Icon(Icons.receipt_long, size: 20, color: Theme.of(context).colorScheme.primary),
              const SizedBox(width: 8),
              Text('今日銷售', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600)),
            ]),
            const SizedBox(height: 12),
            if (sales.isEmpty)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 24),
                child: Center(child: Text('今天還沒有銷售', style: TextStyle(color: Theme.of(context).colorScheme.outline))),
              )
            else
              ...sales.map((s) {
                final time = s['created_at']?.toString() ?? '';
                final displayTime = time.length >= 16 ? time.substring(11, 16) : time;
                final method = s['payment_method'] == 'monthly_credit' ? '月結' : '現金';
                return Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: Row(children: [
                    Text(displayTime, style: TextStyle(fontSize: 13, color: Theme.of(context).colorScheme.outline)),
                    const SizedBox(width: 12),
                    Expanded(child: Text(s['customer_name']?.toString() ?? '散客', style: const TextStyle(fontSize: 14))),
                    Text(method, style: TextStyle(fontSize: 12, color: Theme.of(context).colorScheme.outline)),
                    const SizedBox(width: 12),
                    Text('\$${(s['total'] as num?)?.toStringAsFixed(0) ?? '0'}',
                      style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold, color: Colors.green.shade700)),
                  ]),
                );
              }),
          ],
        ),
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════
// 低庫存卡片
// ═══════════════════════════════════════════════════════
class _LowStockCard extends ConsumerWidget {
  final List<Map<String, dynamic>> items;
  const _LowStockCard({required this.items});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(children: [
              Icon(Icons.warning_amber, size: 20, color: Colors.orange.shade700),
              const SizedBox(width: 8),
              Text('低庫存品項', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600)),
              const Spacer(),
              if (items.isNotEmpty)
                FilledButton.tonalIcon(
                  onPressed: () => _autoPO(context, ref),
                  icon: const Icon(Icons.add_shopping_cart, size: 18),
                  label: const Text('一鍵建採購單'),
                ),
            ]),
            const SizedBox(height: 12),
            if (items.isEmpty)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 24),
                child: Center(child: Text('所有品項庫存充足', style: TextStyle(color: Theme.of(context).colorScheme.outline))),
              )
            else
              ...items.take(10).map((item) {
                final shortage = item['shortage'] as num? ?? 0;
                return Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: Row(children: [
                    Expanded(child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('${item['brand'] ?? ''} ${item['name']}',
                          style: const TextStyle(fontSize: 14), overflow: TextOverflow.ellipsis),
                        Text('${item['spec'] ?? ''}  ${item['unit'] ?? ''}',
                          style: TextStyle(fontSize: 12, color: Theme.of(context).colorScheme.outline)),
                      ],
                    )),
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.end,
                      children: [
                        Text('庫存 ${item['current_stock']}', style: TextStyle(
                          fontSize: 14, fontWeight: FontWeight.bold, color: Colors.red.shade700)),
                        Text('需補 $shortage', style: TextStyle(fontSize: 12, color: Colors.orange.shade700)),
                      ],
                    ),
                  ]),
                );
              }),
          ],
        ),
      ),
    );
  }

  void _autoPO(BuildContext context, WidgetRef ref) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('一鍵建採購單'),
        content: Text('系統將根據 ${items.length} 個低庫存品項的首選供應商，自動建立採購單草稿。\n\n沒有設定首選供應商的品項會被跳過。'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('取消')),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('建立')),
        ],
      ),
    );
    if (confirmed != true) return;

    final msg = await ref.read(dashboardProvider.notifier).autoCreatePurchaseOrders();
    if (context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(msg ?? '建立失敗，請確認品項有設定首選供應商')),
      );
    }
  }
}
