import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../infrastructure/api/api_client.dart';

class AuthState {
  final bool isLoggedIn;
  final String? token;
  final String? userId;
  final String? username;
  final String? displayName;
  final String? role;

  const AuthState({
    this.isLoggedIn = false,
    this.token,
    this.userId,
    this.username,
    this.displayName,
    this.role,
  });

  AuthState copyWith({
    bool? isLoggedIn,
    String? token,
    String? userId,
    String? username,
    String? displayName,
    String? role,
  }) {
    return AuthState(
      isLoggedIn: isLoggedIn ?? this.isLoggedIn,
      token: token ?? this.token,
      userId: userId ?? this.userId,
      username: username ?? this.username,
      displayName: displayName ?? this.displayName,
      role: role ?? this.role,
    );
  }
}

class AuthNotifier extends StateNotifier<AuthState> {
  final ApiClient _api;

  AuthNotifier(this._api) : super(const AuthState());

  Future<void> login(String username, String password) async {
    if (username.isEmpty || password.isEmpty) {
      throw '請輸入帳號和密碼';
    }

    try {
      final response = await _api.post('/auth/login', data: {
        'username': username,
        'password': password,
      });

      final data = response.data as Map<String, dynamic>;
      final token = data['access_token'] as String;

      _api.setToken(token);

      state = AuthState(
        isLoggedIn: true,
        token: token,
        userId: data['user_id'] as String?,
        username: data['username'] as String?,
        displayName: data['display_name'] as String?,
        role: data['role'] as String?,
      );
    } on DioException catch (e) {
      if (e.response?.statusCode == 401) {
        final detail = e.response?.data;
        if (detail is Map && detail.containsKey('detail')) {
          final d = detail['detail'];
          if (d is Map) {
            throw d['message'] ?? '帳號或密碼錯誤';
          }
        }
        throw '帳號或密碼錯誤';
      }
      if (e.type == DioExceptionType.connectionError ||
          e.type == DioExceptionType.connectionTimeout) {
        throw '無法連線到伺服器，請確認網路連線';
      }
      throw '登入失敗：${e.message}';
    }
  }

  void logout() {
    _api.clearToken();
    state = const AuthState();
  }
}

final authProvider = StateNotifierProvider<AuthNotifier, AuthState>((ref) {
  final api = ref.watch(apiClientProvider);
  return AuthNotifier(api);
});