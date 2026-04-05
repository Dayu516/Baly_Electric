import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/feature_flags.dart';
import '../../../core/router/app_router.dart';
import '../application/alert_provider.dart';

class AlertCenterPage extends ConsumerStatefulWidget {
  const AlertCenterPage({super.key});

  @override
  ConsumerState<AlertCenterPage> createState() => _AlertCenterPageState();
}

class _AlertCenterPageState extends ConsumerState<AlertCenterPage> {
  @override
  void initState() {
    super.initState();
    Future.microtask(() => ref.read(alertListProvider.notifier).load());
  }

  @override
  Widget build(BuildContext context) {
    final alertState = ref.watch(alertListProvider);

    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              Text('通知中心', style: Theme.of(context).textTheme.titleLarge),
              const SizedBox(width: 8),
              Text('${alertState.alerts.length} 筆',
                  style: TextStyle(color: Theme.of(context).colorScheme.outline)),
              const Spacer(),
              IconButton(
                icon: const Icon(Icons.refresh),
                onPressed: () => ref.read(alertListProvider.notifier).load(),
              ),
            ],
          ),
        ),
        Expanded(
          child: alertState.loading
              ? const Center(child: CircularProgressIndicator())
              : alertState.alerts.isEmpty
                  ? Center(
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(Icons.notifications_none, size: 64,
                              color: Theme.of(context).colorScheme.outline.withOpacity(0.3)),
                          const SizedBox(height: 12),
                          Text('沒有未讀通知',
                              style: TextStyle(fontSize: 16, color: Theme.of(context).colorScheme.outline)),
                        ],
                      ),
                    )
                  : ListView.builder(
                      itemCount: alertState.alerts.length,
                      itemBuilder: (context, index) {
                        final alert = alertState.alerts[index];
                        final alertId = (alert['alert_id'] ?? '').toString();
                        final type = (alert['alert_type'] ?? '').toString();
                        final severity = (alert['severity'] ?? 'info').toString();
                        final title = (alert['title'] ?? '').toString();
                        final detail = (alert['detail'] ?? '').toString();
                        final createdAt = (alert['created_at'] ?? '').toString();

                        final severityColor = switch (severity) {
                          'critical' => Colors.red,
                          'warning' => Colors.orange,
                          _ => Colors.blue,
                        };

                        final typeIcon = switch (type) {
                          'low_stock' => Icons.inventory,
                          'overdue' => Icons.schedule,
                          'backup_failed' => Icons.cloud_off,
                          'sync_failed' => Icons.sync_problem,
                          'stock_inconsistency' => Icons.warning,
                          _ => Icons.notifications,
                        };

                        final typeLabel = switch (type) {
                          'low_stock' => '低庫存',
                          'overdue' => '逾期',
                          'backup_failed' => '備份失敗',
                          'sync_failed' => '同步失敗',
                          'stock_inconsistency' => '庫存不一致',
                          _ => type,
                        };

                        return Card(
                          margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
                          child: ListTile(
                            leading: CircleAvatar(
                              backgroundColor: severityColor.withOpacity(0.1),
                              child: Icon(typeIcon, color: severityColor, size: 22),
                            ),
                            title: Text(title, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w500)),
                            subtitle: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                if (detail.isNotEmpty)
                                  Text(detail, maxLines: 2, overflow: TextOverflow.ellipsis,
                                      style: TextStyle(fontSize: 13, color: Theme.of(context).colorScheme.outline)),
                                const SizedBox(height: 4),
                                Row(
                                  children: [
                                    Container(
                                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                                      decoration: BoxDecoration(
                                        color: severityColor.withOpacity(0.1),
                                        borderRadius: BorderRadius.circular(8),
                                      ),
                                      child: Text(typeLabel, style: TextStyle(fontSize: 11,
                                          color: severityColor, fontWeight: FontWeight.w600)),
                                    ),
                                    const SizedBox(width: 8),
                                    Text(
                                      createdAt.length >= 16 ? createdAt.substring(0, 16).replaceFirst('T', ' ') : '',
                                      style: TextStyle(fontSize: 11, color: Theme.of(context).colorScheme.outline),
                                    ),
                                  ],
                                ),
                              ],
                            ),
                            trailing: TextButton(
                              onPressed: () => ref.read(alertListProvider.notifier).markRead(alertId),
                              child: const Text('已讀'),
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