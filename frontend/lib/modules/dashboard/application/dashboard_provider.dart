import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../infrastructure/api/api_client.dart';

class DashboardState {
  final bool loading;
  final Map<String, dynamic>? stats;
  final List<Map<String, dynamic>> todaySales;
  final List<Map<String, dynamic>> lowStockItems;
  final String? error;

  const DashboardState({
    this.loading = false,
    this.stats,
    this.todaySales = const [],
    this.lowStockItems = const [],
    this.error,
  });
}

class DashboardNotifier extends StateNotifier<DashboardState> {
  final ApiClient _api;
  DashboardNotifier(this._api) : super(const DashboardState());

  Future<void> load() async {
    state = const DashboardState(loading: true);
    try {
      final results = await Future.wait([
        _api.get('/dashboard/stats'),
        _api.get('/dashboard/today-sales'),
        _api.get('/dashboard/low-stock'),
      ]);

      final stats = (results[0].data as Map<String, dynamic>)['data'] as Map<String, dynamic>;
      final todaySales = ((results[1].data as Map<String, dynamic>)['data'] as List).cast<Map<String, dynamic>>();
      final lowStock = ((results[2].data as Map<String, dynamic>)['data'] as List).cast<Map<String, dynamic>>();

      state = DashboardState(stats: stats, todaySales: todaySales, lowStockItems: lowStock);
    } catch (e) {
      state = DashboardState(error: e.toString());
    }
  }

  /// 一鍵建採購單。回傳成功訊息或 null。
  Future<String?> autoCreatePurchaseOrders() async {
    try {
      final res = await _api.post('/dashboard/auto-purchase-orders');
      final body = res.data as Map<String, dynamic>;
      await load(); // 重新載入 dashboard 數據
      return body['message']?.toString();
    } catch (e) {
      return null;
    }
  }
}

final dashboardProvider = StateNotifierProvider<DashboardNotifier, DashboardState>((ref) {
  return DashboardNotifier(ref.watch(apiClientProvider));
});
