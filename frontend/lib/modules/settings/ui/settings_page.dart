import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/auth/auth_provider.dart';
import '../../../core/feature_flags.dart';
import '../../../core/router/app_router.dart';
import '../../../core/widgets/feature_locked_page.dart';
import '../application/settings_provider.dart';
import 'change_password_panel.dart';
import 'company_info_panel.dart';
import 'parameters_panel.dart';
import 'system_tools_panel.dart';
import 'user_management_panel.dart';

class SettingsPage extends ConsumerStatefulWidget {
  const SettingsPage({super.key});

  @override
  ConsumerState<SettingsPage> createState() => _SettingsPageState();
}

class _SettingsPageState extends ConsumerState<SettingsPage> {
  @override
  void initState() {
    super.initState();
    Future.microtask(() {
      ref.read(companyInfoProvider.notifier).load();
      ref.read(parametersProvider.notifier).load();
      final auth = ref.read(authProvider);
      if (auth.role == 'owner' || auth.role == 'manager') {
        ref.read(userListProvider.notifier).load();
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final device = getDeviceClass(context);
    final level = FeatureFlags.getLevel('settings', device);

    if (level == FeatureLevel.c) {
      return const FeatureLockedPage(
        featureName: '系統設定',
        guidanceMessage: '請在桌面版操作系統設定',
      );
    }

    return const _SettingsDesktopLayout();
  }
}

// ═══════════════════════════════════════════════════════
// Desktop Layout — 左側標籤列 + 右側內容
// ═══════════════════════════════════════════════════════
class _SettingsDesktopLayout extends ConsumerStatefulWidget {
  const _SettingsDesktopLayout();
  @override
  ConsumerState<_SettingsDesktopLayout> createState() => _SettingsDesktopLayoutState();
}

class _SettingsDesktopLayoutState extends ConsumerState<_SettingsDesktopLayout> {
  int _selectedIndex = 0;

  @override
  Widget build(BuildContext context) {
    final auth = ref.watch(authProvider);
    final isOwner = auth.role == 'owner';
    final isManagerOrOwner = auth.role == 'owner' || auth.role == 'manager';

    final tabs = <_SettingsTab>[
      const _SettingsTab(icon: Icons.business, label: '公司資料'),
      const _SettingsTab(icon: Icons.tune, label: '系統參數'),
      if (isOwner) const _SettingsTab(icon: Icons.build_outlined, label: '系統工具'),
      const _SettingsTab(icon: Icons.lock_outline, label: '修改密碼'),
      if (isManagerOrOwner) const _SettingsTab(icon: Icons.people_outline, label: '帳號管理'),
    ];

    final panels = <Widget>[
      CompanyInfoPanel(editable: isOwner),
      ParametersPanel(editable: isOwner),
      if (isOwner) const SystemToolsPanel(),
      const ChangePasswordPanel(),
      if (isManagerOrOwner) UserManagementPanel(isOwner: isOwner),
    ];

    if (_selectedIndex >= tabs.length) {
      _selectedIndex = 0;
    }

    return Row(
      children: [
        SizedBox(
          width: 200,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Padding(
                padding: const EdgeInsets.all(16),
                child: Text('系統設定',
                  style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold)),
              ),
              const Divider(height: 1),
              ...List.generate(tabs.length, (i) {
                final tab = tabs[i];
                final selected = i == _selectedIndex;
                return ListTile(
                  leading: Icon(tab.icon, color: selected ? Theme.of(context).colorScheme.primary : null),
                  title: Text(tab.label),
                  selected: selected,
                  selectedTileColor: Theme.of(context).colorScheme.primaryContainer.withValues(alpha: 0.3),
                  onTap: () => setState(() => _selectedIndex = i),
                );
              }),
            ],
          ),
        ),
        const VerticalDivider(width: 1),
        Expanded(child: panels[_selectedIndex]),
      ],
    );
  }
}

class _SettingsTab {
  final IconData icon;
  final String label;
  const _SettingsTab({required this.icon, required this.label});
}
