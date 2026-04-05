import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../application/settings_provider.dart';
import 'settings_widgets.dart';

class UserManagementPanel extends ConsumerWidget {
  final bool isOwner;
  const UserManagementPanel({super.key, required this.isOwner});

  static const _roleLabels = {'owner': '老闆', 'manager': '主管', 'staff': '員工'};

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(userListProvider);

    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text('帳號管理', style: Theme.of(context).textTheme.headlineSmall),
              const Spacer(),
              if (isOwner)
                FilledButton.icon(
                  onPressed: () => _showCreateDialog(context, ref),
                  icon: const Icon(Icons.person_add),
                  label: const Text('新增帳號'),
                ),
            ],
          ),
          const SizedBox(height: 8),
          if (state.error != null)
            Padding(
              padding: const EdgeInsets.only(bottom: 16),
              child: ErrorBanner(message: state.error!),
            ),
          const SizedBox(height: 16),
          if (state.loading) const LinearProgressIndicator(),
          Expanded(
            child: ListView.separated(
              itemCount: state.users.length,
              separatorBuilder: (_, __) => const Divider(height: 1),
              itemBuilder: (context, index) {
                final u = state.users[index];
                final role = u['role']?.toString() ?? 'staff';
                final isActive = u['is_active'] == true;

                return ListTile(
                  leading: CircleAvatar(
                    backgroundColor: isActive
                        ? Theme.of(context).colorScheme.primaryContainer
                        : Theme.of(context).colorScheme.surfaceContainerHighest,
                    child: Text(
                      (u['display_name']?.toString() ?? u['username']?.toString() ?? '?').characters.first,
                      style: TextStyle(
                        color: isActive
                            ? Theme.of(context).colorScheme.onPrimaryContainer
                            : Theme.of(context).colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ),
                  title: Text(u['display_name']?.toString() ?? ''),
                  subtitle: Text('${u['username']}  ·  ${_roleLabels[role] ?? role}'
                      '${isActive ? '' : '  ·  已停用'}'),
                  trailing: isOwner
                      ? PopupMenuButton<String>(
                          onSelected: (action) => _handleAction(context, ref, u, action),
                          itemBuilder: (_) => [
                            const PopupMenuItem(value: 'edit', child: Text('編輯')),
                            const PopupMenuItem(value: 'reset_pw', child: Text('重設密碼')),
                            PopupMenuItem(
                              value: 'toggle_active',
                              child: Text(isActive ? '停用帳號' : '啟用帳號'),
                            ),
                          ],
                        )
                      : null,
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  void _handleAction(BuildContext context, WidgetRef ref, Map<String, dynamic> user, String action) {
    final userId = user['user_id']?.toString() ?? '';
    switch (action) {
      case 'edit':
        _showEditDialog(context, ref, user);
      case 'reset_pw':
        _showResetPasswordDialog(context, ref, userId, user['display_name']?.toString() ?? '');
      case 'toggle_active':
        final isActive = user['is_active'] == true;
        ref.read(userListProvider.notifier).update(userId, {'is_active': !isActive});
    }
  }

  void _showCreateDialog(BuildContext context, WidgetRef ref) {
    final usernameCtrl = TextEditingController();
    final displayNameCtrl = TextEditingController();
    final passwordCtrl = TextEditingController();
    String role = 'staff';

    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDialogState) => AlertDialog(
          title: const Text('新增帳號'),
          content: SizedBox(
            width: 360,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(
                  controller: usernameCtrl,
                  decoration: const InputDecoration(labelText: '帳號', border: OutlineInputBorder()),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: displayNameCtrl,
                  decoration: const InputDecoration(labelText: '顯示名稱', border: OutlineInputBorder()),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: passwordCtrl,
                  obscureText: true,
                  decoration: const InputDecoration(labelText: '密碼', border: OutlineInputBorder()),
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  value: role,
                  decoration: const InputDecoration(labelText: '角色', border: OutlineInputBorder()),
                  items: const [
                    DropdownMenuItem(value: 'staff', child: Text('員工')),
                    DropdownMenuItem(value: 'manager', child: Text('主管')),
                    DropdownMenuItem(value: 'owner', child: Text('老闆')),
                  ],
                  onChanged: (v) { if (v != null) setDialogState(() => role = v); },
                ),
              ],
            ),
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('取消')),
            FilledButton(
              onPressed: () async {
                final ok = await ref.read(userListProvider.notifier).create({
                  'username': usernameCtrl.text,
                  'display_name': displayNameCtrl.text,
                  'password': passwordCtrl.text,
                  'role': role,
                });
                if (ok && ctx.mounted) Navigator.pop(ctx);
              },
              child: const Text('建立'),
            ),
          ],
        ),
      ),
    );
  }

  void _showEditDialog(BuildContext context, WidgetRef ref, Map<String, dynamic> user) {
    final userId = user['user_id']?.toString() ?? '';
    final displayNameCtrl = TextEditingController(text: user['display_name']?.toString() ?? '');
    String role = user['role']?.toString() ?? 'staff';

    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDialogState) => AlertDialog(
          title: const Text('編輯帳號'),
          content: SizedBox(
            width: 360,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(
                  enabled: false,
                  decoration: InputDecoration(
                    labelText: '帳號',
                    border: const OutlineInputBorder(),
                    hintText: user['username']?.toString(),
                  ),
                  controller: TextEditingController(text: user['username']?.toString()),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: displayNameCtrl,
                  decoration: const InputDecoration(labelText: '顯示名稱', border: OutlineInputBorder()),
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  value: role,
                  decoration: const InputDecoration(labelText: '角色', border: OutlineInputBorder()),
                  items: const [
                    DropdownMenuItem(value: 'staff', child: Text('員工')),
                    DropdownMenuItem(value: 'manager', child: Text('主管')),
                    DropdownMenuItem(value: 'owner', child: Text('老闆')),
                  ],
                  onChanged: (v) { if (v != null) setDialogState(() => role = v); },
                ),
              ],
            ),
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('取消')),
            FilledButton(
              onPressed: () async {
                final ok = await ref.read(userListProvider.notifier).update(userId, {
                  'display_name': displayNameCtrl.text,
                  'role': role,
                });
                if (ok && ctx.mounted) Navigator.pop(ctx);
              },
              child: const Text('儲存'),
            ),
          ],
        ),
      ),
    );
  }

  void _showResetPasswordDialog(BuildContext context, WidgetRef ref, String userId, String displayName) {
    final pwCtrl = TextEditingController();

    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text('重設 $displayName 的密碼'),
        content: SizedBox(
          width: 360,
          child: TextField(
            controller: pwCtrl,
            obscureText: true,
            decoration: const InputDecoration(labelText: '新密碼', border: OutlineInputBorder()),
          ),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('取消')),
          FilledButton(
            onPressed: () async {
              final ok = await ref.read(userListProvider.notifier).resetPassword(userId, pwCtrl.text);
              if (ok && ctx.mounted) {
                Navigator.pop(ctx);
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(content: Text('已重設 $displayName 的密碼')),
                );
              }
            },
            child: const Text('確認重設'),
          ),
        ],
      ),
    );
  }
}
