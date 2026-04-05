import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/feature_flags.dart';
import '../../../core/router/app_router.dart';
import '../../../core/widgets/feature_locked_page.dart';
import 'pos_search_panel.dart';
import 'pos_cart_panel.dart';

class PosPage extends ConsumerWidget {
  const PosPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final device = getDeviceClass(context);
    final level = FeatureFlags.getLevel('pos', device);

    if (level == FeatureLevel.c) {
      return const FeatureLockedPage(
        featureName: 'POS 結帳',
        guidanceMessage: '請在桌面版操作 POS 結帳功能',
      );
    }

    return switch (device) {
      DeviceClass.desktop => _PosDesktopLayout(),
      DeviceClass.tablet => _PosTabletLayout(),
      DeviceClass.phone => _PosDesktopLayout(),
    };
  }
}

class _PosDesktopLayout extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return const Row(
      children: [
        Expanded(flex: 2, child: ProductSearchPanel()),
        VerticalDivider(width: 1),
        Expanded(flex: 3, child: CartPanel()),
      ],
    );
  }
}

class _PosTabletLayout extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return const Column(
      children: [
        Expanded(flex: 1, child: ProductSearchPanel()),
        Divider(height: 1),
        Expanded(flex: 1, child: CartPanel()),
      ],
    );
  }
}
