import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../infrastructure/api/api_client.dart';

class AlertListState {
  final bool loading;
  final List<Map<String, dynamic>> alerts;
  final String? error;

  const AlertListState({this.loading = false, this.alerts = const [], this.error});
}

class AlertListNotifier extends StateNotifier<AlertListState> {
  final ApiClient _api;
  AlertListNotifier(this._api) : super(const AlertListState());

  Future<void> load() async {
    state = const AlertListState(loading: true);
    try {
      final response = await _api.get('/alerts/');
      final body = response.data as Map<String, dynamic>;
      final data = (body['data'] as List).cast<Map<String, dynamic>>();
      state = AlertListState(alerts: data);
    } catch (e) {
      state = AlertListState(error: e.toString());
    }
  }

  Future<void> markRead(String alertId) async {
    try {
      await _api.post('/alerts/$alertId/read');
      await load();
    } catch (e) {
      state = AlertListState(alerts: state.alerts, error: e.toString());
    }
  }
}

final alertListProvider = StateNotifierProvider<AlertListNotifier, AlertListState>((ref) {
  return AlertListNotifier(ref.watch(apiClientProvider));
});