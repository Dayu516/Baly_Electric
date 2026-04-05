import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../auth/auth_provider.dart';
import '../feature_flags.dart';
import '../../modules/dashboard/ui/dashboard_page.dart';
import '../../modules/inventory/ui/inventory_page.dart';
import '../../modules/pos/ui/pos_page.dart';
import '../../modules/product/ui/product_page.dart';
import '../../modules/customer/ui/customer_page.dart';
import '../../modules/review_board/ui/review_board_page.dart';
import '../../modules/alert_center/ui/alert_center_page.dart';
import '../../modules/procurement/ui/procurement_page.dart';
import '../../modules/sales/ui/sales_page.dart';
import '../../modules/settings/ui/settings_page.dart';

// ── DeviceClass 判斷 ────────────────────────────────
DeviceClass getDeviceClass(BuildContext context) {
  if (defaultTargetPlatform == TargetPlatform.windows ||
      defaultTargetPlatform == TargetPlatform.macOS ||
      defaultTargetPlatform == TargetPlatform.linux) {
    return DeviceClass.desktop;
  }
  final shortestSide = MediaQuery.of(context).size.shortestSide;
  return shortestSide >= 600 ? DeviceClass.tablet : DeviceClass.phone;
}

final deviceClassProvider = Provider<DeviceClass>((ref) {
  return DeviceClass.desktop;
});

// ── 導覽項目定義 ────────────────────────────────────
class NavItem {
  final String path;
  final IconData icon;
  final String label;
  final bool isSystem;

  const NavItem(this.path, this.icon, this.label, {this.isSystem = false});
}

const _navItems = [
  NavItem('/dashboard', Icons.dashboard, '首頁'),
  NavItem('/pos', Icons.point_of_sale, 'POS 結帳'),
  NavItem('/products', Icons.inventory_2, '商品管理'),
  NavItem('/procurement', Icons.local_shipping, '採購進貨'),
  NavItem('/sales', Icons.receipt_long, '銷售管理'),
  NavItem('/inventory', Icons.warehouse, '庫存總覽'),
  NavItem('/customers', Icons.people, '客戶管理'),
  NavItem('/reviews', Icons.checklist, '審核待辦', isSystem: true),
  NavItem('/alerts', Icons.notifications, '通知中心', isSystem: true),
  NavItem('/settings', Icons.settings, '系統設定', isSystem: true),
];

// ── Router ──────────────────────────────────────────
final appRouterProvider = Provider<GoRouter>((ref) {
  final authState = ref.watch(authProvider);

  return GoRouter(
    initialLocation: '/login',
    redirect: (context, state) {
      final isLoggedIn = authState.isLoggedIn;
      final isLoginRoute = state.matchedLocation == '/login';

      if (!isLoggedIn && !isLoginRoute) return '/login';
      if (isLoggedIn && isLoginRoute) return '/dashboard';
      return null;
    },
    routes: [
      GoRoute(
        path: '/login',
        builder: (context, state) => const LoginPage(),
      ),
      ShellRoute(
        builder: (context, state, child) => AppShell(child: child),
        routes: [
          GoRoute(path: '/dashboard', builder: (context, state) => const DashboardPage()),
          GoRoute(path: '/pos', builder: (context, state) => const PosPage()),
          GoRoute(path: '/products', builder: (context, state) => const ProductPage()),
          GoRoute(path: '/procurement', builder: (context, state) => const ProcurementPage()),
          GoRoute(path: '/sales', builder: (context, state) => const SalesPage()),
          GoRoute(path: '/inventory', builder: (context, state) => const InventoryPage()),
          GoRoute(path: '/customers', builder: (context, state) => const CustomerPage()),
          GoRoute(path: '/reviews', builder: (context, state) => const ReviewBoardPage()),
          GoRoute(path: '/alerts', builder: (context, state) => const AlertCenterPage()),
          GoRoute(path: '/settings', builder: (context, state) => const SettingsPage()),
        ],
      ),
    ],
  );
});

// ═══════════════════════════════════════════════════════
// Login Page
// ═══════════════════════════════════════════════════════
class LoginPage extends ConsumerStatefulWidget {
  const LoginPage({super.key});

  @override
  ConsumerState<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends ConsumerState<LoginPage> {
  final _usernameController = TextEditingController();
  final _passwordController = TextEditingController();
  bool _loading = false;
  String? _error;

  @override
  void dispose() {
    _usernameController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _login() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      await ref.read(authProvider.notifier).login(
            _usernameController.text.trim(),
            _passwordController.text,
          );
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 420),
          child: Card(
            elevation: 8,
            child: Padding(
              padding: const EdgeInsets.all(40),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.store, size: 64, color: Theme.of(context).colorScheme.primary),
                  const SizedBox(height: 12),
                  Text('OTTIMO', style: Theme.of(context).textTheme.titleLarge),
                  const SizedBox(height: 4),
                  Text('電控材料行管理系統',
                      style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                            color: Theme.of(context).colorScheme.outline,
                          )),
                  const SizedBox(height: 36),
                  TextField(
                    controller: _usernameController,
                    decoration: const InputDecoration(
                      labelText: '帳號',
                      prefixIcon: Icon(Icons.person_outline),
                    ),
                    textInputAction: TextInputAction.next,
                    autofocus: true,
                  ),
                  const SizedBox(height: 16),
                  TextField(
                    controller: _passwordController,
                    decoration: const InputDecoration(
                      labelText: '密碼',
                      prefixIcon: Icon(Icons.lock_outline),
                    ),
                    obscureText: true,
                    onSubmitted: (_) => _login(),
                  ),
                  if (_error != null) ...[
                    const SizedBox(height: 16),
                    Container(
                      width: double.infinity,
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: Colors.red.shade50,
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Text(_error!, style: TextStyle(color: Colors.red.shade700, fontSize: 14)),
                    ),
                  ],
                  const SizedBox(height: 28),
                  SizedBox(
                    width: double.infinity,
                    height: 52,
                    child: ElevatedButton(
                      onPressed: _loading ? null : _login,
                      child: _loading
                          ? const SizedBox(
                              height: 22, width: 22,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : const Text('登入', style: TextStyle(fontSize: 18)),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════
// App Shell — Desktop 固定側邊欄
// ═══════════════════════════════════════════════════════
class AppShell extends ConsumerWidget {
  final Widget child;
  const AppShell({super.key, required this.child});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final location = GoRouterState.of(context).matchedLocation;
    final auth = ref.watch(authProvider);
    final selectedIndex = _navItems.indexWhere((n) => n.path == location);

    return Scaffold(
      body: Row(
        children: [
          // ── 固定側邊欄 ──────────────────────────
          SizedBox(
            width: 220,
            child: Column(
              children: [
                // Logo
                Container(
                  padding: const EdgeInsets.fromLTRB(20, 20, 20, 8),
                  child: Row(
                    children: [
                      Icon(Icons.store, size: 28, color: Theme.of(context).colorScheme.primary),
                      const SizedBox(width: 10),
                      Text('OTTIMO',
                          style: Theme.of(context).textTheme.titleMedium?.copyWith(
                                fontWeight: FontWeight.bold,
                              )),
                    ],
                  ),
                ),
                const Divider(),

                // 主要功能
                Padding(
                  padding: const EdgeInsets.fromLTRB(20, 8, 20, 4),
                  child: Align(
                    alignment: Alignment.centerLeft,
                    child: Text('主要功能',
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w600,
                          color: Theme.of(context).colorScheme.outline,
                        )),
                  ),
                ),
                ..._navItems.where((n) => !n.isSystem).map((n) {
                  final idx = _navItems.indexOf(n);
                  return _NavTile(
                    icon: n.icon,
                    label: n.label,
                    selected: idx == selectedIndex,
                    onTap: () => GoRouter.of(context).go(n.path),
                  );
                }),

                const Divider(indent: 16, endIndent: 16),

                // 系統
                Padding(
                  padding: const EdgeInsets.fromLTRB(20, 4, 20, 4),
                  child: Align(
                    alignment: Alignment.centerLeft,
                    child: Text('系統',
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w600,
                          color: Theme.of(context).colorScheme.outline,
                        )),
                  ),
                ),
                ..._navItems.where((n) => n.isSystem).map((n) {
                  final idx = _navItems.indexOf(n);
                  return _NavTile(
                    icon: n.icon,
                    label: n.label,
                    selected: idx == selectedIndex,
                    onTap: () => GoRouter.of(context).go(n.path),
                  );
                }),

                const Spacer(),

                // 使用者資訊 + 登出
                Container(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    children: [
                      const Divider(),
                      const SizedBox(height: 8),
                      Row(
                        children: [
                          CircleAvatar(
                            radius: 18,
                            backgroundColor: Theme.of(context).colorScheme.primaryContainer,
                            child: Text(
                              (auth.displayName ?? auth.username ?? '?')[0].toUpperCase(),
                              style: TextStyle(
                                color: Theme.of(context).colorScheme.onPrimaryContainer,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ),
                          const SizedBox(width: 10),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  auth.displayName?.isNotEmpty == true
                                      ? auth.displayName!
                                      : auth.username ?? '',
                                  style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
                                  overflow: TextOverflow.ellipsis,
                                ),
                                Text(
                                  _roleLabel(auth.role),
                                  style: TextStyle(
                                    fontSize: 12,
                                    color: Theme.of(context).colorScheme.outline,
                                  ),
                                ),
                              ],
                            ),
                          ),
                          IconButton(
                            icon: const Icon(Icons.logout, size: 20),
                            tooltip: '登出',
                            onPressed: () => ref.read(authProvider.notifier).logout(),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),

          // ── 分隔線 ──────────────────────────────
          const VerticalDivider(width: 1, thickness: 1),

          // ── 主內容 ──────────────────────────────
          Expanded(child: child),
        ],
      ),
    );
  }

  String _roleLabel(String? role) {
    return switch (role) {
      'owner' => 'Owner',
      'manager' => 'Manager',
      'staff' => 'Staff',
      _ => '',
    };
  }
}

// ── 側邊欄按鈕 ────────────────────────────────────────
class _NavTile extends StatelessWidget {
  final IconData icon;
  final String label;
  final bool selected;
  final VoidCallback onTap;

  const _NavTile({
    required this.icon,
    required this.label,
    required this.selected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final color = selected
        ? Theme.of(context).colorScheme.primary
        : Theme.of(context).colorScheme.onSurface;
    final bgColor = selected
        ? Theme.of(context).colorScheme.primaryContainer.withOpacity(0.4)
        : Colors.transparent;

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      child: Material(
        color: bgColor,
        borderRadius: BorderRadius.circular(8),
        child: InkWell(
          borderRadius: BorderRadius.circular(8),
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
            child: Row(
              children: [
                Icon(icon, size: 22, color: color),
                const SizedBox(width: 12),
                Text(label, style: TextStyle(fontSize: 15, color: color, fontWeight: selected ? FontWeight.w600 : FontWeight.normal)),
              ],
            ),
          ),
        ),
      ),
    );
  }
}