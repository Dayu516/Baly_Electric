import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../infrastructure/api/api_client.dart';

class InquiryListState {
  final bool loading;
  final List<Map<String, dynamic>> inquiries;
  final String? error;
  const InquiryListState({this.loading = false, this.inquiries = const [], this.error});
}

class InquiryListNotifier extends StateNotifier<InquiryListState> {
  final ApiClient _api;
  InquiryListNotifier(this._api) : super(const InquiryListState());

  Future<void> load({String? keyword}) async {
    state = const InquiryListState(loading: true);
    try {
      final params = <String, dynamic>{'per_page': '20'};
      if (keyword != null && keyword.isNotEmpty) params['keyword'] = keyword;
      final res = await _api.get('/inquiries/', queryParameters: params);
      final body = res.data as Map<String, dynamic>;
      state = InquiryListState(inquiries: (body['data'] as List).cast<Map<String, dynamic>>());
    } catch (e) {
      state = InquiryListState(error: e.toString());
    }
  }

  Future<bool> deleteInquiry(String id) async {
    try {
      await _api.delete('/inquiries/$id');
      await load();
      return true;
    } catch (_) { return false; }
  }
}

final inquiryListProvider = StateNotifierProvider<InquiryListNotifier, InquiryListState>((ref) {
  return InquiryListNotifier(ref.watch(apiClientProvider));
});

class InquiryDetailState {
  final bool loading;
  final Map<String, dynamic>? data;
  final String? error;
  const InquiryDetailState({this.loading = false, this.data, this.error});
}

class InquiryDetailNotifier extends StateNotifier<InquiryDetailState> {
  final ApiClient _api;
  InquiryDetailNotifier(this._api) : super(const InquiryDetailState());

  Future<void> load(String id) async {
    state = const InquiryDetailState(loading: true);
    try {
      final res = await _api.get('/inquiries/$id');
      final body = res.data as Map<String, dynamic>;
      state = InquiryDetailState(data: body['data'] as Map<String, dynamic>);
    } catch (e) {
      state = InquiryDetailState(error: e.toString());
    }
  }

  void clear() => state = const InquiryDetailState();
}

final inquiryDetailProvider = StateNotifierProvider<InquiryDetailNotifier, InquiryDetailState>((ref) {
  return InquiryDetailNotifier(ref.watch(apiClientProvider));
});
