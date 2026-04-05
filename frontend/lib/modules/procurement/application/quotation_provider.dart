import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../infrastructure/api/api_client.dart';

class QuotationListState {
  final bool loading;
  final List<Map<String, dynamic>> items;
  final String? error;
  const QuotationListState({this.loading = false, this.items = const [], this.error});
}

class QuotationListNotifier extends StateNotifier<QuotationListState> {
  final ApiClient _api;
  QuotationListNotifier(this._api) : super(const QuotationListState());

  Future<void> load({String? keyword}) async {
    state = const QuotationListState(loading: true);
    try {
      final params = <String, dynamic>{'per_page': '20'};
      if (keyword != null && keyword.isNotEmpty) params['keyword'] = keyword;
      final res = await _api.get('/quotations/', queryParameters: params);
      final body = res.data as Map<String, dynamic>;
      state = QuotationListState(items: (body['data'] as List).cast<Map<String, dynamic>>());
    } catch (e) {
      state = QuotationListState(error: e.toString());
    }
  }

  Future<bool> deleteQuotation(String id) async {
    try {
      await _api.delete('/quotations/$id');
      await load();
      return true;
    } catch (_) { return false; }
  }
}

final quotationListProvider = StateNotifierProvider<QuotationListNotifier, QuotationListState>((ref) {
  return QuotationListNotifier(ref.watch(apiClientProvider));
});

class QuotationDetailState {
  final bool loading;
  final Map<String, dynamic>? data;
  final String? error;
  const QuotationDetailState({this.loading = false, this.data, this.error});
}

class QuotationDetailNotifier extends StateNotifier<QuotationDetailState> {
  final ApiClient _api;
  QuotationDetailNotifier(this._api) : super(const QuotationDetailState());

  Future<void> load(String id) async {
    state = const QuotationDetailState(loading: true);
    try {
      final res = await _api.get('/quotations/$id');
      final body = res.data as Map<String, dynamic>;
      state = QuotationDetailState(data: body['data'] as Map<String, dynamic>);
    } catch (e) {
      state = QuotationDetailState(error: e.toString());
    }
  }

  void clear() => state = const QuotationDetailState();
}

final quotationDetailProvider = StateNotifierProvider<QuotationDetailNotifier, QuotationDetailState>((ref) {
  return QuotationDetailNotifier(ref.watch(apiClientProvider));
});
