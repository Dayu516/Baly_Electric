import pathlib

f = pathlib.Path(r"D:\OneDrive\6_projects\ottimo\frontend\lib\modules\pos\ui\pos_page.dart")
content = f.read_text(encoding="utf-8")

# 找到 build 方法的開頭和結尾
start_marker = "  @override\n  Widget build(BuildContext context) {\n    final pos = ref.watch(posProvider);\n    final custState = ref.watch(customerListProvider);"
end_marker = "      ]),\n    );\n  }\n}\n\n"

# 找最後一個 _CustomerSelectorState 的 build
# 它在 class _CustomerSelectorState 裡面
class_marker = "class _CustomerSelectorState extends ConsumerState<_CustomerSelector>"
class_pos = content.find(class_marker)
assert class_pos > 0, "class not found"

# 從 class 位置往後找 build
build_start = content.find(start_marker, class_pos)
assert build_start > 0, "build start not found"

# 找對應的結尾 — 從 build_start 往後找 "  }\n}\n\n"
search_from = build_start + len(start_marker)
build_end = content.find("      ]),\n    );\n  }\n}", search_from)
assert build_end > 0, f"build end not found"
build_end += len("      ]),\n    );\n  }\n}")

old_build = content[build_start:build_end]

new_build = """  @override
  Widget build(BuildContext context) {
    final pos = ref.watch(posProvider);
    final custState = ref.watch(customerListProvider);
    final selectedId = pos.customerId;

    String? selectedName;
    if (selectedId != null) {
      final found = custState.customers.where(
          (c) => c['customer_id']?.toString() == selectedId).toList();
      if (found.isNotEmpty) selectedName = found[0]['name']?.toString();
    }

    // 已選客戶 → 顯示名稱 + 清除按鈕
    if (selectedName != null) {
      return Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
          decoration: BoxDecoration(
            color: Theme.of(context).colorScheme.primaryContainer.withOpacity(0.2),
            borderRadius: BorderRadius.circular(8),
          ),
          child: Row(children: [
            const Icon(Icons.person, size: 20, color: Colors.blue),
            const SizedBox(width: 8),
            Expanded(child: Text(selectedName, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600))),
            InkWell(onTap: () => _selectCustomer(null),
                child: const Icon(Icons.close, size: 18, color: Colors.grey)),
          ]),
        ),
      );
    }

    // 未選客戶 → 直接輸入框
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
      child: Column(children: [
        TextField(
          controller: _searchCtrl,
          decoration: InputDecoration(
            hintText: '輸入客戶名稱（留空 = 現金散客）',
            prefixIcon: const Icon(Icons.person_search, size: 20),
            isDense: true,
            contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
            suffixIcon: _searchCtrl.text.isNotEmpty
                ? IconButton(icon: const Icon(Icons.clear, size: 16),
                    onPressed: () { _searchCtrl.clear(); setState(() { _filtered = []; _showSearch = false; }); })
                : null,
          ),
          onTap: () => setState(() => _showSearch = true),
          onChanged: (v) {
            final all = ref.read(customerListProvider).customers;
            setState(() {
              _showSearch = true;
              _filtered = v.trim().isEmpty ? []
                  : all.where((c) {
                      final name = (c['name'] ?? '').toString().toLowerCase();
                      final phone = (c['phone'] ?? '').toString();
                      return name.contains(v.toLowerCase()) || phone.contains(v);
                    }).toList();
            });
          },
        ),
        if (_filtered.isNotEmpty)
          ConstrainedBox(
            constraints: const BoxConstraints(maxHeight: 180),
            child: Card(
              margin: const EdgeInsets.only(top: 2),
              child: ListView(shrinkWrap: true, padding: EdgeInsets.zero,
                children: _filtered.take(8).map((c) {
                  final name = (c['name'] ?? '').toString();
                  final phone = (c['phone'] ?? '').toString();
                  final isMonthly = c['payment_terms'] == 'monthly_credit';
                  return ListTile(dense: true, visualDensity: VisualDensity.compact,
                    title: Text(name, style: const TextStyle(fontSize: 14)),
                    subtitle: phone.isNotEmpty ? Text(phone, style: const TextStyle(fontSize: 12)) : null,
                    trailing: isMonthly ? const Text('月結', style: TextStyle(fontSize: 11, color: Colors.blue)) : null,
                    onTap: () => _selectCustomer(c));
                }).toList()),
            ),
          ),
      ]),
    );
  }"""

content = content.replace(old_build, new_build)
f.write_text(content, encoding="utf-8")
print("OK")