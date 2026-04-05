import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../infrastructure/api/api_client.dart';

// ═══════════════════════════════════════════════════════
// 客戶列表
// ═══════════════════════════════════════════════════════
class CustomerListState {
  final bool loading;
  final List<Map<String, dynamic>> customers;
  final String? selectedCustomerId;
  final Map<String, dynamic>? selectedCustomer;
  final String? error;

  const CustomerListState({this.loading = false, this.customers = const [],
      this.selectedCustomerId, this.selectedCustomer, this.error});

  CustomerListState copyWith({bool? loading, List<Map<String, dynamic>>? customers,
      String? selectedCustomerId, Map<String, dynamic>? selectedCustomer, String? error}) {
    return CustomerListState(
      loading: loading ?? this.loading, customers: customers ?? this.customers,
      selectedCustomerId: selectedCustomerId ?? this.selectedCustomerId,
      selectedCustomer: selectedCustomer ?? this.selectedCustomer, error: error,
    );
  }
}

class CustomerListNotifier extends StateNotifier<CustomerListState> {
  final ApiClient _api;
  CustomerListNotifier(this._api) : super(const CustomerListState());

  Future<void> load() async {
    state = state.copyWith(loading: true, error: null);
    try {
      final response = await _api.get('/customers/');
      final body = response.data as Map<String, dynamic>;
      final data = (body['data'] as List).cast<Map<String, dynamic>>();
      state = state.copyWith(loading: false, customers: data);
    } catch (e) {
      state = state.copyWith(loading: false, error: e.toString());
    }
  }

  void select(Map<String, dynamic> customer) {
    state = state.copyWith(
      selectedCustomerId: customer['customer_id']?.toString(),
      selectedCustomer: customer,
    );
  }

  void clearSelection() {
    state = CustomerListState(customers: state.customers);
  }

  Future<bool> create(Map<String, dynamic> data) async {
    try {
      await _api.post('/customers/', data: data);
      await load();
      return true;
    } catch (e) {
      state = state.copyWith(error: e.toString());
      return false;
    }
  }

  Future<bool> update(String customerId, Map<String, dynamic> data) async {
    try {
      await _api.put('/customers/$customerId', data: data);
      await load();
      return true;
    } catch (e) {
      state = state.copyWith(error: e.toString());
      return false;
    }
  }
}

final customerListProvider =
    StateNotifierProvider<CustomerListNotifier, CustomerListState>((ref) {
  return CustomerListNotifier(ref.watch(apiClientProvider));
});

// ═══════════════════════════════════════════════════════
// 應收帳款
// ═══════════════════════════════════════════════════════
class ArState {
  final bool loading;
  final String? message;
  final String? error;

  const ArState({this.loading = false, this.message, this.error});
}

class ArNotifier extends StateNotifier<ArState> {
  final ApiClient _api;
  ArNotifier(this._api) : super(const ArState());

  Future<bool> generateStatement(String customerId, String period) async {
    state = const ArState(loading: true);
    try {
      final response = await _api.post('/customers/accounts-receivable/generate', data: {
        'customer_id': customerId,
        'period': period,
      });
      final body = response.data as Map<String, dynamic>;
      state = ArState(message: body['message']?.toString() ?? '月結單已生成');
      return true;
    } on DioException catch (e) {
      final detail = e.response?.data;
      String msg = '產生月結單失敗';
      if (detail is Map && detail.containsKey('detail')) {
        final d = detail['detail'];
        msg = (d is Map ? d['message'] : d)?.toString() ?? msg;
      }
      state = ArState(error: msg);
      return false;
    } catch (e) {
      state = ArState(error: e.toString());
      return false;
    }
  }

  Future<bool> recordPayment(String arId, double amount) async {
    state = const ArState(loading: true);
    try {
      final response = await _api.post('/customers/accounts-receivable/$arId/payment', data: {
        'amount': amount,
      });
      final body = response.data as Map<String, dynamic>;
      state = ArState(message: body['message']?.toString() ?? '收款完成');
      return true;
    } catch (e) {
      state = ArState(error: e.toString());
      return false;
    }
  }

  void clear() => state = const ArState();
}

final arProvider = StateNotifierProvider<ArNotifier, ArState>((ref) {
  return ArNotifier(ref.watch(apiClientProvider));
});

// ═══════════════════════════════════════════════════════
// 應收帳款列表
// ═══════════════════════════════════════════════════════
class ArListState {
  final bool loading;
  final List<Map<String, dynamic>> items;
  final String? error;

  const ArListState({this.loading = false, this.items = const [], this.error});
}

class ArListNotifier extends StateNotifier<ArListState> {
  final ApiClient _api;
  ArListNotifier(this._api) : super(const ArListState());

  Future<void> load(String customerId) async {
    state = const ArListState(loading: true);
    try {
      final response = await _api.get('/customers/$customerId/accounts-receivable');
      final body = response.data as Map<String, dynamic>;
      final data = (body['data'] as List).cast<Map<String, dynamic>>();
      state = ArListState(items: data);
    } catch (e) {
      state = ArListState(error: e.toString());
    }
  }

  void clear() => state = const ArListState();
}

final arListProvider = StateNotifierProvider<ArListNotifier, ArListState>((ref) {
  return ArListNotifier(ref.watch(apiClientProvider));
});