import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../infrastructure/api/api_client.dart';

class CategoryManagementPanel extends ConsumerStatefulWidget {
  const CategoryManagementPanel({super.key});
  @override
  ConsumerState<CategoryManagementPanel> createState() => _CategoryManagementPanelState();
}

class _CategoryManagementPanelState extends ConsumerState<CategoryManagementPanel> {
  List<Map<String, dynamic>> _tree = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _loadTree();
  }

  Future<void> _loadTree() async {
    setState(() => _loading = true);
    final api = ref.read(apiClientProvider);
    try {
      final res = await api.get('/products/categories/tree');
      final body = res.data as Map<String, dynamic>;
      setState(() {
        _tree = (body['data'] as List).cast<Map<String, dynamic>>();
        _loading = false;
      });
    } catch (e) {
      setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Text('分類管理', style: Theme.of(context).textTheme.headlineSmall),
            const Spacer(),
            FilledButton.tonalIcon(
              onPressed: () => _showAddDialog(null, null),
              icon: const Icon(Icons.add),
              label: const Text('新增大分類'),
            ),
          ]),
          const SizedBox(height: 8),
          Text('管理品項分類樹。點擊分類可編輯名稱，或新增子分類。',
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: Theme.of(context).colorScheme.onSurfaceVariant)),
          const SizedBox(height: 16),
          if (_loading) const LinearProgressIndicator(),
          Expanded(
            child: _tree.isEmpty && !_loading
                ? Center(child: Text('尚無分類', style: TextStyle(color: Theme.of(context).colorScheme.outline)))
                : SingleChildScrollView(child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: _tree.map((cat) => _buildCategoryTile(cat, 0)).toList(),
                  )),
          ),
        ],
      ),
    );
  }

  Widget _buildCategoryTile(Map<String, dynamic> cat, int depth) {
    final children = (cat['children'] as List?) ?? [];
    final catId = cat['category_id']?.toString() ?? '';
    final name = cat['name']?.toString() ?? '';

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: EdgeInsets.only(left: depth * 24.0),
          child: ListTile(
            dense: true,
            leading: Icon(
              children.isNotEmpty ? Icons.folder_outlined : Icons.label_outline,
              color: depth == 0 ? Theme.of(context).colorScheme.primary : Theme.of(context).colorScheme.outline,
              size: 20,
            ),
            title: Text(name, style: TextStyle(
              fontSize: depth == 0 ? 16 : 14,
              fontWeight: depth == 0 ? FontWeight.w600 : FontWeight.normal,
            )),
            trailing: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                IconButton(
                  icon: const Icon(Icons.add, size: 18),
                  tooltip: '新增子分類',
                  onPressed: () => _showAddDialog(catId, name),
                ),
                IconButton(
                  icon: const Icon(Icons.edit_outlined, size: 18),
                  tooltip: '編輯',
                  onPressed: () => _showEditDialog(catId, name, cat['sort_order'] as int? ?? 0),
                ),
                IconButton(
                  icon: Icon(Icons.delete_outline, size: 18, color: Colors.red.shade400),
                  tooltip: '刪除',
                  onPressed: () => _confirmDelete(catId, name),
                ),
              ],
            ),
          ),
        ),
        ...children.map((c) => _buildCategoryTile(c as Map<String, dynamic>, depth + 1)),
      ],
    );
  }

  void _showAddDialog(String? parentId, String? parentName) {
    final nameCtrl = TextEditingController();
    final sortCtrl = TextEditingController(text: '0');

    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(parentId == null ? '新增大分類' : '新增子分類（$parentName 下）'),
        content: SizedBox(
          width: 360,
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            TextField(
              controller: nameCtrl,
              autofocus: true,
              decoration: const InputDecoration(labelText: '分類名稱', border: OutlineInputBorder()),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: sortCtrl,
              decoration: const InputDecoration(labelText: '排序（數字越小越前）', border: OutlineInputBorder()),
              keyboardType: TextInputType.number,
            ),
          ]),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('取消')),
          FilledButton(
            onPressed: () async {
              if (nameCtrl.text.trim().isEmpty) return;
              final api = ref.read(apiClientProvider);
              try {
                await api.post('/products/categories', data: {
                  'name': nameCtrl.text.trim(),
                  'parent_id': parentId,
                  'sort_order': int.tryParse(sortCtrl.text) ?? 0,
                });
                if (ctx.mounted) Navigator.pop(ctx);
                _loadTree();
              } catch (e) {
                if (ctx.mounted) {
                  ScaffoldMessenger.of(ctx).showSnackBar(SnackBar(content: Text('建立失敗: $e')));
                }
              }
            },
            child: const Text('建立'),
          ),
        ],
      ),
    );
  }

  void _confirmDelete(String categoryId, String name) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('刪除分類'),
        content: Text('確定要刪除「$name」嗎？\n\n如果底下有子分類或品項，將無法刪除。'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('取消')),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: Colors.red),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('確認刪除'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;

    final api = ref.read(apiClientProvider);
    try {
      await api.delete('/products/categories/$categoryId');
      _loadTree();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('分類「$name」已刪除')));
      }
    } catch (e) {
      if (mounted) {
        var msg = '刪除失敗';
        // 從 DioException 解析後端回傳的錯誤訊息
        try {
          final dynamic err = (e as dynamic).response?.data;
          if (err is Map) {
            msg = (err['detail'] is Map ? err['detail']['message'] : err['detail'] ?? err['message'] ?? msg).toString();
          }
        } catch (_) {}
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
      }
    }
  }

  void _showEditDialog(String categoryId, String currentName, int currentSort) {
    final nameCtrl = TextEditingController(text: currentName);
    final sortCtrl = TextEditingController(text: currentSort.toString());

    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('編輯分類'),
        content: SizedBox(
          width: 360,
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            TextField(
              controller: nameCtrl,
              autofocus: true,
              decoration: const InputDecoration(labelText: '分類名稱', border: OutlineInputBorder()),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: sortCtrl,
              decoration: const InputDecoration(labelText: '排序（數字越小越前）', border: OutlineInputBorder()),
              keyboardType: TextInputType.number,
            ),
          ]),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('取消')),
          FilledButton(
            onPressed: () async {
              if (nameCtrl.text.trim().isEmpty) return;
              final api = ref.read(apiClientProvider);
              try {
                await api.put('/products/categories/$categoryId', data: {
                  'name': nameCtrl.text.trim(),
                  'sort_order': int.tryParse(sortCtrl.text) ?? 0,
                });
                if (ctx.mounted) Navigator.pop(ctx);
                _loadTree();
              } catch (e) {
                if (ctx.mounted) {
                  ScaffoldMessenger.of(ctx).showSnackBar(SnackBar(content: Text('更新失敗: $e')));
                }
              }
            },
            child: const Text('儲存'),
          ),
        ],
      ),
    );
  }
}
