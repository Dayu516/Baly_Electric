import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../infrastructure/api/api_client.dart';

// ═══════════════════════════════════════════════════════
// 分類樹
// ═══════════════════════════════════════════════════════
class CategoryNode {
  final String categoryId;
  final String name;
  final List<CategoryNode> children;

  const CategoryNode({
    required this.categoryId,
    required this.name,
    this.children = const [],
  });

  factory CategoryNode.fromJson(Map<String, dynamic> json) {
    return CategoryNode(
      categoryId: json['category_id'] as String,
      name: json['name'] as String,
      children: (json['children'] as List?)
              ?.map((c) => CategoryNode.fromJson(c as Map<String, dynamic>))
              .toList() ??
          [],
    );
  }
}

class CategoryTreeState {
  final bool loading;
  final List<CategoryNode> tree;
  final String? selectedCategoryId;
  final String? error;

  const CategoryTreeState({
    this.loading = false,
    this.tree = const [],
    this.selectedCategoryId,
    this.error,
  });

  CategoryTreeState copyWith({
    bool? loading,
    List<CategoryNode>? tree,
    String? selectedCategoryId,
    String? error,
  }) {
    return CategoryTreeState(
      loading: loading ?? this.loading,
      tree: tree ?? this.tree,
      selectedCategoryId: selectedCategoryId,
      error: error,
    );
  }
}

class CategoryTreeNotifier extends StateNotifier<CategoryTreeState> {
  final ApiClient _api;

  CategoryTreeNotifier(this._api) : super(const CategoryTreeState());

  Future<void> load() async {
    state = state.copyWith(loading: true, error: null);
    try {
      final response = await _api.get('/products/categories/tree');
      final body = response.data as Map<String, dynamic>;
      final data = (body['data'] as List)
          .map((n) => CategoryNode.fromJson(n as Map<String, dynamic>))
          .toList();
      state = state.copyWith(loading: false, tree: data);
    } catch (e) {
      state = state.copyWith(loading: false, error: e.toString());
    }
  }

  void selectCategory(String? categoryId) {
    state = state.copyWith(
      selectedCategoryId: categoryId == state.selectedCategoryId ? null : categoryId,
    );
  }
}

final categoryTreeProvider =
    StateNotifierProvider<CategoryTreeNotifier, CategoryTreeState>((ref) {
  final api = ref.watch(apiClientProvider);
  return CategoryTreeNotifier(api);
});

// ═══════════════════════════════════════════════════════
// 品項列表
// ═══════════════════════════════════════════════════════
class ProductListState {
  final bool loading;
  final List<Map<String, dynamic>> products;
  final String? error;
  final String searchQuery;

  const ProductListState({
    this.loading = false,
    this.products = const [],
    this.error,
    this.searchQuery = '',
  });

  ProductListState copyWith({
    bool? loading,
    List<Map<String, dynamic>>? products,
    String? error,
    String? searchQuery,
  }) {
    return ProductListState(
      loading: loading ?? this.loading,
      products: products ?? this.products,
      error: error,
      searchQuery: searchQuery ?? this.searchQuery,
    );
  }
}

class ProductListNotifier extends StateNotifier<ProductListState> {
  final ApiClient _api;

  ProductListNotifier(this._api) : super(const ProductListState());

  Future<void> loadProducts({int page = 1, int perPage = 20}) async {
    state = state.copyWith(loading: true, error: null);
    try {
      final response = await _api.get('/products', queryParameters: {
        'page': page,
        'per_page': perPage,
      });
      final data = (response.data as List).cast<Map<String, dynamic>>();
      state = state.copyWith(loading: false, products: data);
    } catch (e) {
      state = state.copyWith(loading: false, error: e.toString());
    }
  }

  Future<void> search(String keyword) async {
    if (keyword.trim().isEmpty) {
      await loadProducts();
      return;
    }
    state = state.copyWith(loading: true, error: null, searchQuery: keyword);
    try {
      final response = await _api.get('/products/search', queryParameters: {
        'q': keyword,
      });
      final body = response.data as Map<String, dynamic>;
      final data = (body['data'] as List).cast<Map<String, dynamic>>();
      state = state.copyWith(loading: false, products: data);
    } catch (e) {
      state = state.copyWith(loading: false, error: e.toString());
    }
  }

  Future<bool> createProduct(Map<String, dynamic> data) async {
    try {
      await _api.post('/products/', data: data);
      await loadProducts();
      return true;
    } catch (e) {
      state = state.copyWith(error: e.toString());
      return false;
    }
  }

  Future<bool> updateProduct(String productId, Map<String, dynamic> data) async {
    try {
      await _api.put('/products/$productId', data: data);
      await loadProducts();
      return true;
    } catch (e) {
      state = state.copyWith(error: e.toString());
      return false;
    }
  }
}

final productListProvider =
    StateNotifierProvider<ProductListNotifier, ProductListState>((ref) {
  final api = ref.watch(apiClientProvider);
  return ProductListNotifier(api);
});