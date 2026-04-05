import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../infrastructure/api/api_client.dart';

class AttributeTemplatePanel extends ConsumerStatefulWidget {
  const AttributeTemplatePanel({super.key});
  @override
  ConsumerState<AttributeTemplatePanel> createState() => _AttributeTemplatePanelState();
}

class _AttributeTemplatePanelState extends ConsumerState<AttributeTemplatePanel> {
  List<Map<String, dynamic>> _categories = [];
  String? _selectedCategoryId;
  String? _selectedCategoryName;
  List<_TemplateRow> _rows = [];
  bool _loading = false;
  bool _dirty = false;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _loadCategories();
  }

  Future<void> _loadCategories() async {
    final api = ref.read(apiClientProvider);
    try {
      final res = await api.get('/products/categories/tree');
      final body = res.data as Map<String, dynamic>;
      final tree = body['data'] as List;
      final flat = <Map<String, dynamic>>[];
      void walk(List items, int depth) {
        for (final item in items) {
          final m = item as Map<String, dynamic>;
          flat.add({'id': m['category_id'], 'name': '${"　" * depth}${m["name"]}', 'raw_name': m['name']});
          if (m['children'] is List) walk(m['children'] as List, depth + 1);
        }
      }
      walk(tree, 0);
      setState(() => _categories = flat);
    } catch (_) {}
  }

  Future<void> _loadTemplates(String categoryId) async {
    setState(() { _loading = true; _rows = []; _dirty = false; });
    final api = ref.read(apiClientProvider);
    try {
      final res = await api.get('/attributes/templates/$categoryId');
      final body = res.data as Map<String, dynamic>;
      final data = (body['data'] as List).cast<Map<String, dynamic>>();
      setState(() {
        _rows = data.map((t) => _TemplateRow(
          key: t['key']?.toString() ?? '',
          unit: t['unit']?.toString(),
          required: t['required'] == true,
          options: (t['options'] as List?)?.cast<String>() ?? [],
          matchPriority: t['match_priority'] as int?,
          matchType: t['match_type']?.toString() ?? 'prefer',
        )).toList();
        _loading = false;
      });
    } catch (e) {
      setState(() => _loading = false);
    }
  }

  Future<void> _save() async {
    setState(() => _saving = true);
    final api = ref.read(apiClientProvider);
    try {
      final data = _rows.where((r) => r.key.isNotEmpty).toList().asMap().entries.map((e) => {
        'key': e.value.key,
        'unit': e.value.unit?.isEmpty == true ? null : e.value.unit,
        'required': e.value.required,
        'options': e.value.options.where((o) => o.isNotEmpty).toList(),
        'match_priority': e.value.matchPriority,
        'match_type': e.value.matchType,
      }).toList();

      await api.put('/attributes/templates/$_selectedCategoryId', data: data);
      setState(() { _dirty = false; _saving = false; });
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('$_selectedCategoryName 屬性模板已儲存'), duration: const Duration(seconds: 2)),
        );
      }
    } catch (e) {
      setState(() => _saving = false);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('儲存失敗: $e')));
      }
    }
  }

  void _addRow() {
    setState(() {
      _rows.add(_TemplateRow(key: '', matchType: 'prefer'));
      _dirty = true;
    });
  }

  void _removeRow(int index) {
    setState(() {
      _rows.removeAt(index);
      _dirty = true;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('分類屬性模板管理', style: Theme.of(context).textTheme.headlineSmall),
          const SizedBox(height: 8),
          Text('設定每個分類的品項應有哪些屬性欄位、可選值、替代品比對規則',
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: Theme.of(context).colorScheme.onSurfaceVariant)),
          const SizedBox(height: 16),

          Row(children: [
            SizedBox(
              width: 300,
              child: DropdownButtonFormField<String>(
                value: _selectedCategoryId,
                decoration: const InputDecoration(labelText: '選擇分類', border: OutlineInputBorder()),
                items: _categories.map((c) => DropdownMenuItem(
                  value: c['id']?.toString(),
                  child: Text(c['name']?.toString() ?? ''),
                )).toList(),
                onChanged: (v) {
                  if (v == null) return;
                  final cat = _categories.firstWhere((c) => c['id'] == v);
                  setState(() {
                    _selectedCategoryId = v;
                    _selectedCategoryName = cat['raw_name']?.toString();
                  });
                  _loadTemplates(v);
                },
              ),
            ),
            const Spacer(),
            if (_selectedCategoryId != null) ...[
              FilledButton.tonalIcon(
                onPressed: _addRow,
                icon: const Icon(Icons.add),
                label: const Text('新增欄位'),
              ),
              const SizedBox(width: 12),
              if (_dirty)
                FilledButton.icon(
                  onPressed: _saving ? null : _save,
                  icon: _saving
                      ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                      : const Icon(Icons.save),
                  label: const Text('儲存'),
                ),
            ],
          ]),
          const SizedBox(height: 16),

          if (_loading) const LinearProgressIndicator(),

          if (_selectedCategoryId != null && !_loading)
            Expanded(
              child: _rows.isEmpty
                  ? Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
                      Icon(Icons.add_circle_outline, size: 48, color: Theme.of(context).colorScheme.outline),
                      const SizedBox(height: 8),
                      Text('此分類尚未設定屬性，點「新增欄位」開始',
                        style: TextStyle(color: Theme.of(context).colorScheme.outline)),
                    ]))
                  : ReorderableListView.builder(
                      itemCount: _rows.length,
                      onReorder: (oldIndex, newIndex) {
                        setState(() {
                          if (newIndex > oldIndex) newIndex--;
                          final item = _rows.removeAt(oldIndex);
                          _rows.insert(newIndex, item);
                          _dirty = true;
                        });
                      },
                      itemBuilder: (context, index) {
                        final row = _rows[index];
                        return _TemplateRowWidget(
                          key: ValueKey('tmpl_$index'),
                          row: row,
                          index: index,
                          onChanged: () => setState(() => _dirty = true),
                          onRemove: () => _removeRow(index),
                        );
                      },
                    ),
            ),
        ],
      ),
    );
  }
}

class _TemplateRow {
  String key;
  String? unit;
  bool required;
  List<String> options;
  int? matchPriority;
  String matchType;

  _TemplateRow({
    required this.key,
    this.unit,
    this.required = false,
    this.options = const [],
    this.matchPriority,
    this.matchType = 'prefer',
  });
}

class _TemplateRowWidget extends StatelessWidget {
  final _TemplateRow row;
  final int index;
  final VoidCallback onChanged;
  final VoidCallback onRemove;

  const _TemplateRowWidget({super.key, required this.row, required this.index, required this.onChanged, required this.onRemove});

  static const _matchTypeLabels = {'must': '必須一致', 'prefer': '優先匹配', 'optional': '有加分'};

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Wrap(
              spacing: 8,
              runSpacing: 8,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                Icon(Icons.drag_handle, color: Theme.of(context).colorScheme.outline, size: 20),
                SizedBox(width: 150, child: TextFormField(
                  initialValue: row.key,
                  decoration: const InputDecoration(labelText: '屬性名稱', border: OutlineInputBorder(), isDense: true),
                  onChanged: (v) { row.key = v; onChanged(); },
                )),
                SizedBox(width: 70, child: TextFormField(
                  initialValue: row.unit ?? '',
                  decoration: const InputDecoration(labelText: '單位', border: OutlineInputBorder(), isDense: true),
                  onChanged: (v) { row.unit = v.isEmpty ? null : v; onChanged(); },
                )),
                FilterChip(
                  label: const Text('必填'),
                  selected: row.required,
                  onSelected: (v) { row.required = v; onChanged(); },
                ),
                SizedBox(width: 120, child: DropdownButtonFormField<String>(
                  value: row.matchType,
                  decoration: const InputDecoration(labelText: '比對', border: OutlineInputBorder(), isDense: true),
                  items: _matchTypeLabels.entries.map((e) => DropdownMenuItem(value: e.key, child: Text(e.value, style: const TextStyle(fontSize: 13)))).toList(),
                  onChanged: (v) { if (v != null) { row.matchType = v; onChanged(); } },
                )),
                SizedBox(width: 65, child: TextFormField(
                  initialValue: row.matchPriority?.toString() ?? '',
                  decoration: const InputDecoration(labelText: '優先序', border: OutlineInputBorder(), isDense: true),
                  keyboardType: TextInputType.number,
                  onChanged: (v) { row.matchPriority = int.tryParse(v); onChanged(); },
                )),
                IconButton(icon: const Icon(Icons.delete_outline, size: 20), color: Colors.red, onPressed: onRemove, tooltip: '刪除此欄位'),
              ],
            ),
            const SizedBox(height: 8),
            Padding(
              padding: const EdgeInsets.only(left: 28),
              child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('可選值：', style: TextStyle(fontSize: 12, color: Theme.of(context).colorScheme.outline)),
                const SizedBox(width: 4),
                Expanded(child: Wrap(
                  spacing: 6,
                  runSpacing: 6,
                  children: [
                    ...row.options.asMap().entries.map((e) => InputChip(
                      label: Text(e.value, style: const TextStyle(fontSize: 12)),
                      onDeleted: () { row.options.removeAt(e.key); onChanged(); },
                      materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                    )),
                    _AddOptionChip(onAdd: (value) { row.options.add(value); onChanged(); }),
                  ],
                )),
              ]),
            ),
          ],
        ),
      ),
    );
  }
}

class _AddOptionChip extends StatefulWidget {
  final void Function(String) onAdd;
  const _AddOptionChip({required this.onAdd});

  @override
  State<_AddOptionChip> createState() => _AddOptionChipState();
}

class _AddOptionChipState extends State<_AddOptionChip> {
  bool _editing = false;
  final _ctrl = TextEditingController();

  @override
  void dispose() { _ctrl.dispose(); super.dispose(); }

  @override
  Widget build(BuildContext context) {
    if (!_editing) {
      return ActionChip(
        label: const Text('+', style: TextStyle(fontSize: 12)),
        onPressed: () => setState(() => _editing = true),
        materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
      );
    }

    return SizedBox(
      width: 100,
      height: 32,
      child: TextField(
        controller: _ctrl,
        autofocus: true,
        style: const TextStyle(fontSize: 12),
        decoration: const InputDecoration(
          isDense: true,
          contentPadding: EdgeInsets.symmetric(horizontal: 8, vertical: 6),
          border: OutlineInputBorder(),
          hintText: '輸入後 Enter',
        ),
        onSubmitted: (v) {
          if (v.trim().isNotEmpty) widget.onAdd(v.trim());
          _ctrl.clear();
          setState(() => _editing = false);
        },
      ),
    );
  }
}
