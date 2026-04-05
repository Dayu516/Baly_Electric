import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../infrastructure/api/api_client.dart';

/// 購物車項目
class CartItem {
  final String skuId;
  final String productName;
  final String? spec;
  double unitPrice;
  int quantity;
  double discountAmount;

  CartItem({
    required this.skuId,
    required this.productName,
    this.spec,
    required this.unitPrice,
    this.quantity = 1,
    this.discountAmount = 0,
  });

  double get lineTotal => unitPrice * quantity - discountAmount;

  Map<String, dynamic> toJson() => {
        'sku_id': skuId,
        'product_name': productName,
        'spec': spec,
        'unit_price': unitPrice,
        'quantity': quantity,
        'discount_amount': discountAmount,
      };
}

/// POS State — 一套 state，三端共用
class PosState {
  final List<CartItem> cart;
  final String? customerId;
  final String paymentMethod;
  final String taxMode; // none / included / extra
  final double orderDiscount;
  final bool loading;
  final String? error;
  final String? lastSaleId;
  final bool checkoutSuccess;

  const PosState({
    this.cart = const [],
    this.customerId,
    this.paymentMethod = 'cash',
    this.taxMode = 'none',
    this.orderDiscount = 0,
    this.loading = false,
    this.error,
    this.lastSaleId,
    this.checkoutSuccess = false,
  });

  double get subtotal => cart.fold(0, (sum, item) => sum + item.lineTotal);
  double get beforeTax => subtotal - orderDiscount;
  double get taxAmount {
    if (taxMode == 'included') return (beforeTax / 1.05 * 0.05);  // 含稅拆出稅額
    if (taxMode == 'extra') return (beforeTax * 0.05);             // 外加5%
    return 0;
  }
  double get total {
    if (taxMode == 'extra') return beforeTax + taxAmount;           // 外加
    return beforeTax;                                               // 含稅或未稅
  }
  double get netAmount {
    if (taxMode == 'included') return beforeTax - taxAmount;        // 含稅拆未稅
    return beforeTax;                                               // 未稅或外加的原價
  }
  int get itemCount => cart.fold(0, (sum, item) => sum + item.quantity);

  PosState copyWith({
    List<CartItem>? cart,
    String? customerId,
    String? paymentMethod,
    String? taxMode,
    double? orderDiscount,
    bool? loading,
    String? error,
    String? lastSaleId,
    bool? checkoutSuccess,
  }) {
    return PosState(
      cart: cart ?? this.cart,
      customerId: customerId ?? this.customerId,
      paymentMethod: paymentMethod ?? this.paymentMethod,
      taxMode: taxMode ?? this.taxMode,
      orderDiscount: orderDiscount ?? this.orderDiscount,
      loading: loading ?? this.loading,
      error: error,
      lastSaleId: lastSaleId,
      checkoutSuccess: checkoutSuccess ?? this.checkoutSuccess,
    );
  }
}

class PosNotifier extends StateNotifier<PosState> {
  final ApiClient _api;

  PosNotifier(this._api) : super(const PosState());

  void addItem(CartItem item) {
    final existing = state.cart.indexWhere((c) => c.skuId == item.skuId);
    if (existing >= 0) {
      final updated = List<CartItem>.from(state.cart);
      updated[existing].quantity += item.quantity;
      state = state.copyWith(cart: updated);
    } else {
      state = state.copyWith(cart: [...state.cart, item]);
    }
  }

  void removeItem(int index) {
    final updated = List<CartItem>.from(state.cart)..removeAt(index);
    state = state.copyWith(cart: updated);
  }

  void updateQuantity(int index, int quantity) {
    if (quantity <= 0) {
      removeItem(index);
      return;
    }
    final updated = List<CartItem>.from(state.cart);
    updated[index].quantity = quantity;
    state = state.copyWith(cart: updated);
  }

  void setPaymentMethod(String method) {
    state = state.copyWith(paymentMethod: method);
  }

  void setTaxMode(String mode) {
    state = state.copyWith(taxMode: mode);
  }

  void setCustomerId(String? id) {
    state = state.copyWith(customerId: id);
  }

  void clearCart() {
    state = const PosState();
  }

  Future<void> checkout() async {
    if (state.cart.isEmpty) return;

    state = state.copyWith(loading: true, error: null, checkoutSuccess: false);
    try {
      final response = await _api.post('/sales/', data: {
        'customer_id': state.customerId,
        'payment_method': state.paymentMethod,
        'tax_mode': state.taxMode,
        'items': state.cart.map((c) => c.toJson()).toList(),
        'discount_amount': state.orderDiscount,
      });

      final data = response.data as Map<String, dynamic>;
      final saleData = data['data'] as Map<String, dynamic>;

      state = PosState(
        lastSaleId: saleData['sale_id'] as String?,
        checkoutSuccess: true,
      );
    } catch (e) {
      state = state.copyWith(loading: false, error: e.toString());
    }
  }
}

final posProvider = StateNotifierProvider<PosNotifier, PosState>((ref) {
  final api = ref.watch(apiClientProvider);
  return PosNotifier(api);
});

// ═══════════════════════════════════════════════════════
// POS 專用搜尋 — 走 /products/search API，回傳 SKU 資料
// ═══════════════════════════════════════════════════════
class PosSearchState {
  final bool loading;
  final List<Map<String, dynamic>> results;
  final String? error;

  const PosSearchState({
    this.loading = false,
    this.results = const [],
    this.error,
  });

  PosSearchState copyWith({
    bool? loading,
    List<Map<String, dynamic>>? results,
    String? error,
  }) {
    return PosSearchState(
      loading: loading ?? this.loading,
      results: results ?? this.results,
      error: error,
    );
  }
}

class PosSearchNotifier extends StateNotifier<PosSearchState> {
  final ApiClient _api;

  PosSearchNotifier(this._api) : super(const PosSearchState());

  Future<void> search(String keyword, {String? customerId}) async {
    if (keyword.trim().isEmpty) {
      state = const PosSearchState();
      return;
    }
    state = state.copyWith(loading: true, error: null);
    try {
      final params = <String, dynamic>{
        'q': keyword,
        'per_page': 20,
      };
      if (customerId != null) params['customer_id'] = customerId;
      final response = await _api.get('/products/search', queryParameters: params);
      final body = response.data as Map<String, dynamic>;
      final data = (body['data'] as List).cast<Map<String, dynamic>>();
      state = PosSearchState(results: data);
    } catch (e) {
      state = state.copyWith(loading: false, error: e.toString());
    }
  }

  void clear() {
    state = const PosSearchState();
  }
}

final posSearchProvider =
    StateNotifierProvider<PosSearchNotifier, PosSearchState>((ref) {
  final api = ref.watch(apiClientProvider);
  return PosSearchNotifier(api);
});