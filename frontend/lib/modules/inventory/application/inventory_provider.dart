import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../infrastructure/api/api_client.dart';

// ═══════════════════════════════════════════════════════
// 庫存列表
// ═══════════════════════════════════════════════════════
class InventoryState {
  final bool loading;
  final List<Map<String, dynamic>> items;
  final int total;
  final Map<String, dynamic>? summary;
  final String? error;

  const InventoryState({this.loading = false, this.items = const [], this.total = 0, this.summary, this.error});

  InventoryState copyWith({bool? loading, List<Map<String, dynamic>>? items, int? total, Map<String, dynamic>? summary, String? error}) {
    return InventoryState(loading: loading ?? this.loading, items: items ?? this.items, total: total ?? this.total, summary: summary ?? this.summary, error: error);
  }
}

class InventoryNotifier extends StateNotifier<InventoryState> {
  final ApiClient _api;
  InventoryNotifier(this._api) : super(const InventoryState());

  Future<void> load({int page = 1, int perPage = 200, String? keyword, bool lowStockOnly = false}) async {
    state = state.copyWith(loading: true, error: null);
    try {
      final params = <String, dynamic>{'page': page, 'per_page': perPage};
      if (keyword != null && keyword.isNotEmpty) params['keyword'] = keyword;
      if (lowStockOnly) params['low_stock_only'] = true;

      final results = await Future.wait([
        _api.get('/inventory/', queryParameters: params),
        _api.get('/inventory/summary'),
      ]);

      final body = results[0].data as Map<String, dynamic>;
      final data = (body['data'] as List).cast<Map<String, dynamic>>();
      final total = body['total'] as int? ?? data.length;

      final summaryBody = results[1].data as Map<String, dynamic>;
      final summary = summaryBody['data'] as Map<String, dynamic>;

      state = state.copyWith(loading: false, items: data, total: total, summary: summary);
    } catch (e) {
      state = state.copyWith(loading: false, error: e.toString());
    }
  }

  Future<void> search(String keyword) async {
    await load(keyword: keyword);
  }
}

final inventoryProvider = StateNotifierProvider<InventoryNotifier, InventoryState>((ref) {
  return InventoryNotifier(ref.watch(apiClientProvider));
});

// ═══════════════════════════════════════════════════════
// 庫存異動紀錄
// ═══════════════════════════════════════════════════════
class MovementsState {
  final bool loading;
  final List<Map<String, dynamic>> movements;
  final String? selectedSkuId;
  final String? error;

  const MovementsState({this.loading = false, this.movements = const [], this.selectedSkuId, this.error});

  MovementsState copyWith({bool? loading, List<Map<String, dynamic>>? movements, String? selectedSkuId, String? error}) {
    return MovementsState(
      loading: loading ?? this.loading,
      movements: movements ?? this.movements,
      selectedSkuId: selectedSkuId ?? this.selectedSkuId,
      error: error,
    );
  }
}

class MovementsNotifier extends StateNotifier<MovementsState> {
  final ApiClient _api;
  MovementsNotifier(this._api) : super(const MovementsState());

  Future<void> loadForSku(String skuId) async {
    state = state.copyWith(loading: true, error: null, selectedSkuId: skuId);
    try {
      final response = await _api.get('/inventory/$skuId/movements');
      final body = response.data as Map<String, dynamic>;
      final data = (body['data'] as List).cast<Map<String, dynamic>>();
      state = state.copyWith(loading: false, movements: data);
    } catch (e) {
      state = state.copyWith(loading: false, error: e.toString());
    }
  }

  void clear() => state = const MovementsState();
}

final movementsProvider = StateNotifierProvider<MovementsNotifier, MovementsState>((ref) {
  return MovementsNotifier(ref.watch(apiClientProvider));
});

// ═══════════════════════════════════════════════════════
// 進貨驗收
// ═══════════════════════════════════════════════════════
class ReceiveLine {
  String skuId;
  String productName;
  int quantity;
  double? unitCost;

  ReceiveLine({required this.skuId, required this.productName, this.quantity = 1, this.unitCost});

  Map<String, dynamic> toJson() => {'sku_id': skuId, 'quantity': quantity, 'unit_cost': unitCost};
}

class ReceiveState {
  final List<ReceiveLine> lines;
  final bool loading;
  final String? error;
  final String? successMessage;

  const ReceiveState({this.lines = const [], this.loading = false, this.error, this.successMessage});

  ReceiveState copyWith({List<ReceiveLine>? lines, bool? loading, String? error, String? successMessage}) {
    return ReceiveState(
      lines: lines ?? this.lines, loading: loading ?? this.loading,
      error: error, successMessage: successMessage,
    );
  }
}

class ReceiveNotifier extends StateNotifier<ReceiveState> {
  final ApiClient _api;
  ReceiveNotifier(this._api) : super(const ReceiveState());

  void addLine(ReceiveLine line) {
    final existing = state.lines.indexWhere((l) => l.skuId == line.skuId);
    if (existing >= 0) {
      final updated = List<ReceiveLine>.from(state.lines);
      updated[existing].quantity += line.quantity;
      state = state.copyWith(lines: updated);
    } else {
      state = state.copyWith(lines: [...state.lines, line]);
    }
  }

  void removeLine(int index) {
    final updated = List<ReceiveLine>.from(state.lines)..removeAt(index);
    state = state.copyWith(lines: updated);
  }

  void updateQuantity(int index, int qty) {
    if (qty <= 0) { removeLine(index); return; }
    final updated = List<ReceiveLine>.from(state.lines);
    updated[index].quantity = qty;
    state = state.copyWith(lines: updated);
  }

  void clear() => state = const ReceiveState();

  Future<void> submit(String supplierId) async {
    if (state.lines.isEmpty) return;
    state = state.copyWith(loading: true, error: null, successMessage: null);
    try {
      await _api.post('/inventory/receive', data: {
        'supplier_id': supplierId,
        'lines': state.lines.map((l) => l.toJson()).toList(),
      });
      final count = state.lines.length;
      state = const ReceiveState();
      state = state.copyWith(successMessage: '進貨完成，$count 筆品項入庫');
    } catch (e) {
      state = state.copyWith(loading: false, error: e.toString());
    }
  }
}

final receiveProvider = StateNotifierProvider<ReceiveNotifier, ReceiveState>((ref) {
  return ReceiveNotifier(ref.watch(apiClientProvider));
});

// ═══════════════════════════════════════════════════════
// 盤點
// ═══════════════════════════════════════════════════════
class CountLine {
  String skuId;
  String productName;
  int bookQuantity;
  int? actualQuantity;

  CountLine({required this.skuId, required this.productName, required this.bookQuantity, this.actualQuantity});

  Map<String, dynamic> toJson() => {'sku_id': skuId, 'actual_quantity': actualQuantity ?? bookQuantity};
}

class CountState {
  final List<CountLine> lines;
  final bool loading;
  final String? error;
  final Map<String, dynamic>? result;

  const CountState({this.lines = const [], this.loading = false, this.error, this.result});

  CountState copyWith({List<CountLine>? lines, bool? loading, String? error, Map<String, dynamic>? result}) {
    return CountState(
      lines: lines ?? this.lines, loading: loading ?? this.loading,
      error: error, result: result,
    );
  }
}

class CountNotifier extends StateNotifier<CountState> {
  final ApiClient _api;
  CountNotifier(this._api) : super(const CountState());

  void loadFromInventory(List<Map<String, dynamic>> inventoryItems) {
    final lines = inventoryItems.map((item) => CountLine(
      skuId: (item['sku_id'] ?? '').toString(),
      productName: (item['product_name'] ?? '').toString(),
      bookQuantity: (item['current_stock'] as num?)?.toInt() ?? 0,
    )).toList();
    state = state.copyWith(lines: lines, result: null);
  }

  void setActualQuantity(int index, int qty) {
    final updated = List<CountLine>.from(state.lines);
    updated[index].actualQuantity = qty;
    state = state.copyWith(lines: updated);
  }

  void clear() => state = const CountState();

  Future<void> submit() async {
    final filledLines = state.lines.where((l) => l.actualQuantity != null).toList();
    if (filledLines.isEmpty) return;

    state = state.copyWith(loading: true, error: null, result: null);
    try {
      final response = await _api.post('/inventory/count', data: {
        'lines': filledLines.map((l) => l.toJson()).toList(),
      });
      final body = response.data as Map<String, dynamic>;
      state = state.copyWith(loading: false, result: body['data'] as Map<String, dynamic>?);
    } catch (e) {
      state = state.copyWith(loading: false, error: e.toString());
    }
  }
}

final countProvider = StateNotifierProvider<CountNotifier, CountState>((ref) {
  return CountNotifier(ref.watch(apiClientProvider));
});