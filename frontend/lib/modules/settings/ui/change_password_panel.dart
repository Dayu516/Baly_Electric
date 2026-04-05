import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../application/settings_provider.dart';
import 'settings_widgets.dart';

class ChangePasswordPanel extends ConsumerStatefulWidget {
  const ChangePasswordPanel({super.key});
  @override
  ConsumerState<ChangePasswordPanel> createState() => _ChangePasswordPanelState();
}

class _ChangePasswordPanelState extends ConsumerState<ChangePasswordPanel> {
  final _oldCtrl = TextEditingController();
  final _newCtrl = TextEditingController();
  final _confirmCtrl = TextEditingController();

  @override
  void dispose() {
    _oldCtrl.dispose();
    _newCtrl.dispose();
    _confirmCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(changePasswordProvider);

    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 400),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('修改密碼', style: Theme.of(context).textTheme.headlineSmall),
            const SizedBox(height: 24),
            if (state.message != null)
              Padding(
                padding: const EdgeInsets.only(bottom: 16),
                child: SuccessBanner(message: state.message!),
              ),
            if (state.error != null)
              Padding(
                padding: const EdgeInsets.only(bottom: 16),
                child: ErrorBanner(message: state.error!),
              ),
            TextField(
              controller: _oldCtrl,
              obscureText: true,
              decoration: const InputDecoration(
                labelText: '舊密碼',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 16),
            TextField(
              controller: _newCtrl,
              obscureText: true,
              decoration: const InputDecoration(
                labelText: '新密碼',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 16),
            TextField(
              controller: _confirmCtrl,
              obscureText: true,
              decoration: const InputDecoration(
                labelText: '確認新密碼',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 24),
            FilledButton.icon(
              onPressed: state.loading ? null : _submit,
              icon: const Icon(Icons.lock_reset),
              label: const Text('更新密碼'),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _submit() async {
    if (_newCtrl.text != _confirmCtrl.text) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('新密碼與確認密碼不一致')),
      );
      return;
    }
    if (_newCtrl.text.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('新密碼不能為空')),
      );
      return;
    }

    final ok = await ref.read(changePasswordProvider.notifier).change(
      _oldCtrl.text,
      _newCtrl.text,
    );
    if (ok && mounted) {
      _oldCtrl.clear();
      _newCtrl.clear();
      _confirmCtrl.clear();
    }
  }
}
