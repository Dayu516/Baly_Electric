import 'package:flutter/material.dart';

/// 狀態標籤 — 統一的狀態顯示元件。
/// 合併 procurement 和 sales 兩處的重複實作。
class StatusBadge extends StatelessWidget {
  final String status;
  const StatusBadge({super.key, required this.status});

  static const _labels = {
    // 採購 / 詢價
    'draft': '草稿', 'ordered': '已下單', 'partial_received': '部分到貨',
    'received': '已完成', 'cancelled': '已取消', 'quoting': '詢價中',
    'decided': '已決定', 'converted': '已轉單', 'sent': '已送出',
    'accepted': '已確認', 'expired': '已過期',
    // 銷售
    'voided': '已作廢', 'completed': '完成',
    // 客訂追蹤
    'pending': '待處理', 'sourcing': '訂貨中',
    'partial_arrived': '部分到貨', 'arrived': '已到貨',
    'partial_picked_up': '部分取貨', 'picked_up': '已取走',
  };

  static const _colors = {
    'draft': Colors.grey, 'ordered': Colors.blue, 'partial_received': Colors.orange,
    'received': Colors.green, 'cancelled': Colors.red, 'quoting': Colors.blue,
    'decided': Colors.orange, 'converted': Colors.green, 'sent': Colors.blue,
    'accepted': Colors.orange, 'expired': Colors.red,
    'voided': Colors.red, 'completed': Colors.green,
    // 客訂追蹤
    'pending': Colors.grey, 'sourcing': Colors.blue,
    'partial_arrived': Colors.orange, 'arrived': Colors.teal,
    'partial_picked_up': Colors.deepPurple, 'picked_up': Colors.green,
  };

  @override
  Widget build(BuildContext context) {
    final color = _colors[status] ?? Colors.grey;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(color: color.withValues(alpha: 0.15), borderRadius: BorderRadius.circular(4)),
      child: Text(_labels[status] ?? status, style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: color)),
    );
  }
}
