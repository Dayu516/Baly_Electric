import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../infrastructure/api/api_client.dart';

// ═══════════════════════════════════════════════════════
// 銷售紀錄
// ═══════════════════════════════════════════════════════
class SalesHistoryState {
  final bool loading;
  final List<Map<String, dynamic>> items;
  final int total;
  final String? error;
  const SalesHistoryState({this.loading = false, this.items = const [], this.total = 0, this.error});
}

class SalesHistoryNotifier extends StateNotifier<SalesHistoryState> {
  final ApiClient _api;
  SalesHistoryNotifier(this._api) : super(const SalesHistoryState());

  Future<void> load({int page = 1, String? period}) async {
    state = const SalesHistoryState(loading: true);
    try {
      final params = <String, dynamic>{'page': page.toString()};
      if (period != null && period.isNotEmpty) params['period'] = period;
      final res = await _api.get('/sales/history', queryParameters: params);
      final body = res.data as Map<String, dynamic>;
      state = SalesHistoryState(
        items: (body['data'] as List).cast<Map<String, dynamic>>(),
        total: body['total'] as int? ?? 0,
      );
    } catch (e) {
      state = SalesHistoryState(error: e.toString());
    }
  }
}

final salesHistoryProvider = StateNotifierProvider<SalesHistoryNotifier, SalesHistoryState>((ref) {
  return SalesHistoryNotifier(ref.watch(apiClientProvider));
});

// Detail
class SaleDetailState {
  final bool loading;
  final Map<String, dynamic>? data;
  const SaleDetailState({this.loading = false, this.data});
}

class SaleDetailNotifier extends StateNotifier<SaleDetailState> {
  final ApiClient _api;
  SaleDetailNotifier(this._api) : super(const SaleDetailState());

  Future<void> load(String saleId) async {
    state = const SaleDetailState(loading: true);
    try {
      final res = await _api.get('/sales/history/$saleId');
      final body = res.data as Map<String, dynamic>;
      state = SaleDetailState(data: body['data'] as Map<String, dynamic>);
    } catch (e) {
      state = const SaleDetailState();
    }
  }

  void clear() => state = const SaleDetailState();
}

final saleDetailProvider = StateNotifierProvider<SaleDetailNotifier, SaleDetailState>((ref) {
  return SaleDetailNotifier(ref.watch(apiClientProvider));
});
