import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../infrastructure/api/api_client.dart';

class ReviewState {
  final bool loading;
  final List<Map<String, dynamic>> tasks;
  final String? error;

  const ReviewState({this.loading = false, this.tasks = const [], this.error});

  ReviewState copyWith({bool? loading, List<Map<String, dynamic>>? tasks, String? error}) {
    return ReviewState(loading: loading ?? this.loading, tasks: tasks ?? this.tasks, error: error);
  }
}

class ReviewNotifier extends StateNotifier<ReviewState> {
  final ApiClient _api;
  ReviewNotifier(this._api) : super(const ReviewState());

  Future<void> load({String? reviewType}) async {
    state = state.copyWith(loading: true, error: null);
    try {
      final params = <String, dynamic>{};
      if (reviewType != null) params['review_type'] = reviewType;
      final response = await _api.get('/reviews/', queryParameters: params);
      final body = response.data as Map<String, dynamic>;
      final data = (body['data'] as List).cast<Map<String, dynamic>>();
      state = state.copyWith(loading: false, tasks: data);
    } catch (e) {
      state = state.copyWith(loading: false, error: e.toString());
    }
  }

  Future<bool> claim(String taskId) async {
    try {
      await _api.post('/reviews/$taskId/claim');
      await load();
      return true;
    } catch (e) {
      state = state.copyWith(error: e.toString());
      return false;
    }
  }

  Future<bool> resolve(String taskId, String resolution) async {
    try {
      await _api.post('/reviews/$taskId/resolve', data: {'resolution': resolution});
      await load();
      return true;
    } catch (e) {
      state = state.copyWith(error: e.toString());
      return false;
    }
  }
}

final reviewProvider = StateNotifierProvider<ReviewNotifier, ReviewState>((ref) {
  return ReviewNotifier(ref.watch(apiClientProvider));
});