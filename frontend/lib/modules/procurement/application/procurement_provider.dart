import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../infrastructure/api/api_client.dart';

// ═══════════════════════════════════════════════════════
// 採購單列表
// ═══════════════════════════════════════════════════════
class POListState {
  final bool loading;
  final List<Map<String, dynamic>> orders;
  final String? error;

  const POListState({this.loading = false, this.orders = const [], this.error});
}

class POListNotifier extends StateNotifier<POListState> {
  final ApiClient _api;
  POListNotifier(this._api) : super(const POListState());

  String? _statusFilter;
  String? _keyword;

  Future<void> load({String? status, String? keyword}) async {
    if (status != null) _statusFilter = status.isEmpty ? null : status;
    if (keyword != null) _keyword = keyword.isEmpty ? null : keyword;
    state = const POListState(loading: true);
    try {
      final params = <String, dynamic>{'per_page': '20'};
      if (_statusFilter != null) params['status'] = _statusFilter!;
      if (_keyword != null) params['keyword'] = _keyword!;
      final res = await _api.get('/purchase-orders/', queryParameters: params);
      final body = res.data as Map<String, dynamic>;
      final data = (body['data'] as List).cast<Map<String, dynamic>>();
      state = POListState(orders: data);
    } catch (e) {
      state = POListState(error: e.toString());
    }
  }

  Future<bool> deletePO(String poId) async {
    try {
      await _api.delete('/purchase-orders/$poId');
      await load();
      return true;
    } catch (_) { return false; }
  }
}

final poListProvider = StateNotifierProvider<POListNotifier, POListState>((ref) {
  return POListNotifier(ref.watch(apiClientProvider));
});

// ═══════════════════════════════════════════════════════
// 採購單詳情
// ═══════════════════════════════════════════════════════
class PODetailState {
  final bool loading;
  final Map<String, dynamic>? data;
  final String? message;
  final String? error;

  const PODetailState({this.loading = false, this.data, this.message, this.error});
}

class PODetailNotifier extends StateNotifier<PODetailState> {
  final ApiClient _api;
  PODetailNotifier(this._api) : super(const PODetailState());

  Future<void> load(String poId) async {
    state = const PODetailState(loading: true);
    try {
      final res = await _api.get('/purchase-orders/$poId');
      final body = res.data as Map<String, dynamic>;
      state = PODetailState(data: body['data'] as Map<String, dynamic>);
    } catch (e) {
      state = PODetailState(error: e.toString());
    }
  }

  Future<bool> confirm(String poId) async {
    try {
      await _api.post('/purchase-orders/$poId/confirm');
      await load(poId);
      return true;
    } on DioException catch (e) {
      state = PODetailState(data: state.data, error: _extractError(e) ?? '確認失敗');
      return false;
    }
  }

  Future<bool> cancel(String poId) async {
    try {
      await _api.post('/purchase-orders/$poId/cancel');
      await load(poId);
      return true;
    } on DioException catch (e) {
      state = PODetailState(data: state.data, error: _extractError(e) ?? '取消失敗');
      return false;
    }
  }

  Future<bool> receive(String poId, List<Map<String, dynamic>> lines, String? note) async {
    try {
      await _api.post('/purchase-orders/$poId/receive', data: {
        'lines': lines,
        'note': note,
      });
      await load(poId);
      return true;
    } on DioException catch (e) {
      state = PODetailState(data: state.data, error: _extractError(e) ?? '驗收失敗');
      return false;
    }
  }

  void clear() => state = const PODetailState();
}

final poDetailProvider = StateNotifierProvider<PODetailNotifier, PODetailState>((ref) {
  return PODetailNotifier(ref.watch(apiClientProvider));
});

String? _extractError(DioException e) {
  final detail = e.response?.data;
  if (detail is Map && detail.containsKey('detail')) {
    final d = detail['detail'];
    if (d is Map) return d['message']?.toString();
    return d?.toString();
  }
  return null;
}
