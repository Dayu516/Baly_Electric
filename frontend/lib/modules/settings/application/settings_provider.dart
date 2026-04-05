import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../infrastructure/api/api_client.dart';

// ═══════════════════════════════════════════════════════
// 公司資料
// ═══════════════════════════════════════════════════════
class CompanyInfoState {
  final bool loading;
  final Map<String, dynamic>? data;
  final String? message;
  final String? error;

  const CompanyInfoState({this.loading = false, this.data, this.message, this.error});

  CompanyInfoState copyWith({bool? loading, Map<String, dynamic>? data, String? message, String? error}) {
    return CompanyInfoState(
      loading: loading ?? this.loading,
      data: data ?? this.data,
      message: message,
      error: error,
    );
  }
}

class CompanyInfoNotifier extends StateNotifier<CompanyInfoState> {
  final ApiClient _api;
  CompanyInfoNotifier(this._api) : super(const CompanyInfoState());

  Future<void> load() async {
    state = state.copyWith(loading: true, error: null, message: null);
    try {
      final response = await _api.get('/settings/company');
      final body = response.data as Map<String, dynamic>;
      state = CompanyInfoState(data: body['data'] as Map<String, dynamic>);
    } catch (e) {
      state = CompanyInfoState(error: e.toString());
    }
  }

  Future<bool> save(Map<String, dynamic> data) async {
    state = state.copyWith(loading: true, error: null, message: null);
    try {
      await _api.put('/settings/company', data: data);
      state = CompanyInfoState(data: data, message: '公司資料已儲存');
      return true;
    } on DioException catch (e) {
      final msg = _extractError(e) ?? '儲存失敗';
      state = state.copyWith(loading: false, error: msg);
      return false;
    } catch (e) {
      state = state.copyWith(loading: false, error: e.toString());
      return false;
    }
  }
}

final companyInfoProvider =
    StateNotifierProvider<CompanyInfoNotifier, CompanyInfoState>((ref) {
  return CompanyInfoNotifier(ref.watch(apiClientProvider));
});

// ═══════════════════════════════════════════════════════
// 系統參數
// ═══════════════════════════════════════════════════════
class ParametersState {
  final bool loading;
  final List<Map<String, dynamic>> params;
  final String? message;
  final String? error;

  const ParametersState({this.loading = false, this.params = const [], this.message, this.error});
}

class ParametersNotifier extends StateNotifier<ParametersState> {
  final ApiClient _api;
  ParametersNotifier(this._api) : super(const ParametersState());

  Future<void> load() async {
    state = const ParametersState(loading: true);
    try {
      final response = await _api.get('/settings/parameters');
      final body = response.data as Map<String, dynamic>;
      final data = (body['data'] as List).cast<Map<String, dynamic>>();
      state = ParametersState(params: data);
    } catch (e) {
      state = ParametersState(error: e.toString());
    }
  }

  Future<bool> update(String key, String value) async {
    try {
      await _api.put('/settings/parameters/$key', data: {'value': value});
      await load();
      return true;
    } catch (e) {
      state = ParametersState(params: state.params, error: e.toString());
      return false;
    }
  }
}

final parametersProvider =
    StateNotifierProvider<ParametersNotifier, ParametersState>((ref) {
  return ParametersNotifier(ref.watch(apiClientProvider));
});

// ═══════════════════════════════════════════════════════
// 帳號管理
// ═══════════════════════════════════════════════════════
class UserListState {
  final bool loading;
  final List<Map<String, dynamic>> users;
  final String? message;
  final String? error;

  const UserListState({this.loading = false, this.users = const [], this.message, this.error});
}

class UserListNotifier extends StateNotifier<UserListState> {
  final ApiClient _api;
  UserListNotifier(this._api) : super(const UserListState());

  Future<void> load() async {
    state = const UserListState(loading: true);
    try {
      final response = await _api.get('/users/');
      final body = response.data as Map<String, dynamic>;
      final data = (body['data'] as List).cast<Map<String, dynamic>>();
      state = UserListState(users: data);
    } catch (e) {
      state = UserListState(error: e.toString());
    }
  }

  Future<bool> create(Map<String, dynamic> data) async {
    try {
      await _api.post('/users/', data: data);
      await load();
      return true;
    } on DioException catch (e) {
      state = UserListState(users: state.users, error: _extractError(e) ?? '建立失敗');
      return false;
    } catch (e) {
      state = UserListState(users: state.users, error: e.toString());
      return false;
    }
  }

  Future<bool> update(String userId, Map<String, dynamic> data) async {
    try {
      await _api.put('/users/$userId', data: data);
      await load();
      return true;
    } catch (e) {
      state = UserListState(users: state.users, error: e.toString());
      return false;
    }
  }

  Future<bool> resetPassword(String userId, String newPassword) async {
    try {
      await _api.post('/users/$userId/reset-password', data: {'new_password': newPassword});
      return true;
    } on DioException catch (e) {
      state = UserListState(users: state.users, error: _extractError(e) ?? '重設密碼失敗');
      return false;
    } catch (e) {
      state = UserListState(users: state.users, error: e.toString());
      return false;
    }
  }
}

final userListProvider =
    StateNotifierProvider<UserListNotifier, UserListState>((ref) {
  return UserListNotifier(ref.watch(apiClientProvider));
});

// ═══════════════════════════════════════════════════════
// 改密碼
// ═══════════════════════════════════════════════════════
class ChangePasswordState {
  final bool loading;
  final String? message;
  final String? error;

  const ChangePasswordState({this.loading = false, this.message, this.error});
}

class ChangePasswordNotifier extends StateNotifier<ChangePasswordState> {
  final ApiClient _api;
  ChangePasswordNotifier(this._api) : super(const ChangePasswordState());

  Future<bool> change(String oldPassword, String newPassword) async {
    state = const ChangePasswordState(loading: true);
    try {
      await _api.post('/users/change-password', data: {
        'old_password': oldPassword,
        'new_password': newPassword,
      });
      state = const ChangePasswordState(message: '密碼已更新');
      return true;
    } on DioException catch (e) {
      final msg = _extractError(e) ?? '密碼更新失敗';
      state = ChangePasswordState(error: msg);
      return false;
    } catch (e) {
      state = ChangePasswordState(error: e.toString());
      return false;
    }
  }

  void clear() => state = const ChangePasswordState();
}

final changePasswordProvider =
    StateNotifierProvider<ChangePasswordNotifier, ChangePasswordState>((ref) {
  return ChangePasswordNotifier(ref.watch(apiClientProvider));
});

// ── Helper ─────────────────────────────────────────────

String? _extractError(DioException e) {
  final detail = e.response?.data;
  if (detail is Map && detail.containsKey('detail')) {
    final d = detail['detail'];
    if (d is Map) return d['message']?.toString();
    return d?.toString();
  }
  return null;
}
