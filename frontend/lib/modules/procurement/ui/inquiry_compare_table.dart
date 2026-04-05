import 'package:flutter/material.dart';

/// 詢價單比價並排表格。
/// 行 = 品項，列 = 供應商，格 = 報價單價。
class InquiryCompareTable extends StatelessWidget {
  final List lines;
  final Set<String> selectedQuoteIds;
  final void Function(String quoteId)? onToggleSelect;

  const InquiryCompareTable({
    super.key,
    required this.lines,
    required this.selectedQuoteIds,
    this.onToggleSelect,
  });

  @override
  Widget build(BuildContext context) {
    if (lines.isEmpty) {
      return Center(child: Text('沒有品項', style: TextStyle(color: Theme.of(context).colorScheme.outline)));
    }

    // 收集所有供應商（按名稱排序、去重）
    final supplierMap = <String, String>{}; // id -> name
    for (final line in lines) {
      for (final q in ((line as Map)['quotes'] as List?) ?? []) {
        final qm = q as Map<String, dynamic>;
        supplierMap[qm['supplier_id'].toString()] = qm['supplier_name']?.toString() ?? '';
      }
    }
    final supplierIds = supplierMap.keys.toList()..sort((a, b) => supplierMap[a]!.compareTo(supplierMap[b]!));

    if (supplierIds.isEmpty) {
      return Center(child: Text('尚無報價，請先記錄供應商報價', style: TextStyle(color: Theme.of(context).colorScheme.outline)));
    }

    // 建立報價 lookup: lineId -> supplierId -> quote
    final quoteLookup = <String, Map<String, Map<String, dynamic>>>{};
    for (final line in lines) {
      final lm = line as Map<String, dynamic>;
      final lineId = lm['line_id'].toString();
      quoteLookup[lineId] = {};
      for (final q in (lm['quotes'] as List?) ?? []) {
        final qm = q as Map<String, dynamic>;
        quoteLookup[lineId]![qm['supplier_id'].toString()] = qm;
      }
    }

    // 找每行最低價
    final lowestByLine = <String, double>{};
    for (final line in lines) {
      final lm = line as Map<String, dynamic>;
      final lineId = lm['line_id'].toString();
      double? min;
      for (final q in (lm['quotes'] as List?) ?? []) {
        final price = (q as Map)['unit_price'] as num?;
        if (price != null && (min == null || price < min)) min = price.toDouble();
      }
      if (min != null) lowestByLine[lineId] = min;
    }

    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: SingleChildScrollView(
        child: DataTable(
          columnSpacing: 16,
          headingRowColor: WidgetStateProperty.all(
            Theme.of(context).colorScheme.surfaceContainerHighest.withValues(alpha: 0.5),
          ),
          columns: [
            const DataColumn(label: Text('品項', style: TextStyle(fontWeight: FontWeight.bold))),
            const DataColumn(label: Text('數量', style: TextStyle(fontWeight: FontWeight.bold)), numeric: true),
            ...supplierIds.map((sid) => DataColumn(
              label: Text(supplierMap[sid] ?? '', style: const TextStyle(fontWeight: FontWeight.bold)),
              numeric: true,
            )),
          ],
          rows: lines.map((line) {
            final lm = line as Map<String, dynamic>;
            final lineId = lm['line_id'].toString();
            final lowest = lowestByLine[lineId];

            return DataRow(cells: [
              DataCell(SizedBox(
                width: 180,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text('${lm["brand"] ?? ""} ${lm["product_name"] ?? ""}',
                      style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
                      overflow: TextOverflow.ellipsis),
                    Text(lm['spec']?.toString() ?? '',
                      style: TextStyle(fontSize: 11, color: Theme.of(context).colorScheme.outline)),
                  ],
                ),
              )),
              DataCell(Text('${lm["quantity"]} ${lm["unit"] ?? ""}')),
              ...supplierIds.map((sid) {
                final quote = quoteLookup[lineId]?[sid];
                if (quote == null) {
                  return DataCell(Text('—', style: TextStyle(color: Theme.of(context).colorScheme.outline)));
                }

                final price = quote['unit_price'] as num;
                final isLowest = lowest != null && price.toDouble() == lowest;
                final isSelected = selectedQuoteIds.contains(quote['quote_id'].toString());
                final qid = quote['quote_id'].toString();

                return DataCell(
                  InkWell(
                    onTap: onToggleSelect != null ? () => onToggleSelect!(qid) : null,
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                      decoration: BoxDecoration(
                        color: isSelected
                            ? Colors.green.withValues(alpha: 0.15)
                            : isLowest
                                ? Colors.green.withValues(alpha: 0.05)
                                : null,
                        borderRadius: BorderRadius.circular(4),
                        border: isSelected ? Border.all(color: Colors.green.shade400) : null,
                      ),
                      child: Row(mainAxisSize: MainAxisSize.min, children: [
                        if (isSelected)
                          Padding(
                            padding: const EdgeInsets.only(right: 4),
                            child: Icon(Icons.check_circle, size: 14, color: Colors.green.shade700),
                          ),
                        Text(
                          '\$${price.toStringAsFixed(0)}',
                          style: TextStyle(
                            fontSize: 14,
                            fontWeight: isLowest ? FontWeight.bold : FontWeight.normal,
                            color: isLowest ? Colors.green.shade700 : null,
                          ),
                        ),
                      ]),
                    ),
                  ),
                );
              }),
            ]);
          }).toList(),
        ),
      ),
    );
  }
}
