import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/feature_flags.dart';
import '../../../core/router/app_router.dart';
import '../application/review_provider.dart';

class ReviewBoardPage extends ConsumerStatefulWidget {
  const ReviewBoardPage({super.key});

  @override
  ConsumerState<ReviewBoardPage> createState() => _ReviewBoardPageState();
}

class _ReviewBoardPageState extends ConsumerState<ReviewBoardPage> {
  @override
  void initState() {
    super.initState();
    Future.microtask(() => ref.read(reviewProvider.notifier).load());
  }

  @override
  Widget build(BuildContext context) {
    final device = getDeviceClass(context);
    return switch (device) {
      DeviceClass.desktop => _ReviewDesktopLayout(),
      DeviceClass.tablet => _ReviewDesktopLayout(),
      DeviceClass.phone => _ReviewDesktopLayout(),
    };
  }
}

class _ReviewDesktopLayout extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final reviewState = ref.watch(reviewProvider);

    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              Text('審核待辦', style: Theme.of(context).textTheme.titleLarge),
              const SizedBox(width: 8),
              Text('${reviewState.tasks.length} 筆',
                  style: TextStyle(color: Theme.of(context).colorScheme.outline)),
              const Spacer(),
              IconButton(
                icon: const Icon(Icons.refresh),
                onPressed: () => ref.read(reviewProvider.notifier).load(),
              ),
            ],
          ),
        ),
        // 標題列
        Container(
          color: Theme.of(context).colorScheme.surfaceContainerHighest,
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
          child: const Row(
            children: [
              SizedBox(width: 100, child: Text('類型', style: TextStyle(fontWeight: FontWeight.w600))),
              SizedBox(width: 80, child: Text('狀態', style: TextStyle(fontWeight: FontWeight.w600))),
              Expanded(child: Text('標題', style: TextStyle(fontWeight: FontWeight.w600))),
              SizedBox(width: 150, child: Text('操作', style: TextStyle(fontWeight: FontWeight.w600))),
            ],
          ),
        ),
        Expanded(
          child: reviewState.loading
              ? const Center(child: CircularProgressIndicator())
              : reviewState.tasks.isEmpty
                  ? Center(
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(Icons.check_circle_outline, size: 64,
                              color: Theme.of(context).colorScheme.outline),
                          const SizedBox(height: 12),
                          Text('沒有待辦任務',
                              style: TextStyle(fontSize: 16, color: Theme.of(context).colorScheme.outline)),
                        ],
                      ),
                    )
                  : ListView.builder(
                      itemCount: reviewState.tasks.length,
                      itemBuilder: (context, index) {
                        final task = reviewState.tasks[index];
                        return _ReviewTaskRow(task: task);
                      },
                    ),
        ),
      ],
    );
  }
}

class _ReviewTaskRow extends ConsumerWidget {
  final Map<String, dynamic> task;
  const _ReviewTaskRow({required this.task});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final taskId = (task['task_id'] ?? '').toString();
    final type = (task['review_type'] ?? '').toString();
    final status = (task['status'] ?? '').toString();
    final title = (task['title'] ?? '').toString();
    final detail = (task['detail'] ?? '').toString();

    final typeLabel = switch (type) {
      'product_confirm' => '品項確認',
      'stock_discrepancy' => '盤點差異',
      'monthly_reconcile' => '月結確認',
      _ => type,
    };

    final statusColor = switch (status) {
      'pending' => Colors.orange,
      'claimed' => Colors.blue,
      'completed' => Colors.green,
      _ => Colors.grey,
    };

    return InkWell(
      onTap: () => _showDetail(context, ref),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        child: Row(
          children: [
            SizedBox(
              width: 100,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: Theme.of(context).colorScheme.surfaceContainerHighest,
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(typeLabel, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
              ),
            ),
            SizedBox(
              width: 80,
              child: Text(status,
                  style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: statusColor)),
            ),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(title, style: const TextStyle(fontSize: 15)),
                  if (detail.isNotEmpty)
                    Text(detail,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(fontSize: 12, color: Theme.of(context).colorScheme.outline)),
                ],
              ),
            ),
            SizedBox(
              width: 150,
              child: Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  if (status == 'pending')
                    TextButton(
                      onPressed: () => ref.read(reviewProvider.notifier).claim(taskId),
                      child: const Text('領取'),
                    ),
                  if (status == 'claimed') ...[
                    ElevatedButton(
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.green,
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(horizontal: 12),
                      ),
                      onPressed: () => ref.read(reviewProvider.notifier).resolve(taskId, 'approved'),
                      child: const Text('通過'),
                    ),
                    const SizedBox(width: 4),
                    TextButton(
                      onPressed: () => ref.read(reviewProvider.notifier).resolve(taskId, 'rejected'),
                      child: const Text('退回', style: TextStyle(color: Colors.red)),
                    ),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  void _showDetail(BuildContext context, WidgetRef ref) {
    final detail = (task['detail'] ?? '').toString();
    final title = (task['title'] ?? '').toString();
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(title),
        content: SizedBox(
          width: 500,
          child: SingleChildScrollView(
            child: Text(detail.isNotEmpty ? detail : '無詳細內容', style: const TextStyle(fontSize: 14)),
          ),
        ),
        actions: [TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('關閉'))],
      ),
    );
  }
}