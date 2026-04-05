import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../application/settings_provider.dart';
import 'settings_widgets.dart';

class ParametersPanel extends ConsumerWidget {
  final bool editable;
  const ParametersPanel({super.key, required this.editable});

  static const _paramLabels = {
    'default_tax_rate': '預設稅率',
    'decimal_places': '金額小數位數',
    'receipt_copies': '出貨單列印份數',
    'receipt_title': '出貨單抬頭',
  };

  static const _paramHints = {
    'default_tax_rate': '例：0.05 = 5%',
    'decimal_places': '0 = 整數，2 = 到分',
    'receipt_copies': '列印份數',
    'receipt_title': '空白時使用公司名稱',
  };

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(parametersProvider);

    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 600),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('系統參數', style: Theme.of(context).textTheme.headlineSmall),
            const SizedBox(height: 8),
            Text('調整系統預設行為', style: Theme.of(context).textTheme.bodyMedium?.copyWith(
              color: Theme.of(context).colorScheme.onSurfaceVariant)),
            const SizedBox(height: 24),
            if (state.loading) const LinearProgressIndicator(),
            if (state.error != null)
              Padding(
                padding: const EdgeInsets.only(bottom: 16),
                child: ErrorBanner(message: state.error!),
              ),
            ...state.params.map((p) {
              final key = p['key']?.toString() ?? '';
              final value = p['value']?.toString() ?? '';
              final label = _paramLabels[key] ?? key;
              final hint = _paramHints[key] ?? '';
              return _ParameterRow(
                paramKey: key,
                label: label,
                hint: hint,
                value: value,
                editable: editable,
              );
            }),
          ],
        ),
      ),
    );
  }
}

class _ParameterRow extends ConsumerStatefulWidget {
  final String paramKey;
  final String label;
  final String hint;
  final String value;
  final bool editable;

  const _ParameterRow({
    required this.paramKey,
    required this.label,
    required this.hint,
    required this.value,
    required this.editable,
  });

  @override
  ConsumerState<_ParameterRow> createState() => _ParameterRowState();
}

class _ParameterRowState extends ConsumerState<_ParameterRow> {
  late final TextEditingController _ctrl;
  bool _dirty = false;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _ctrl = TextEditingController(text: widget.value);
    _ctrl.addListener(() {
      final dirty = _ctrl.text != widget.value;
      if (dirty != _dirty) setState(() => _dirty = dirty);
    });
  }

  @override
  void dispose() { _ctrl.dispose(); super.dispose(); }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Row(
        children: [
          Expanded(
            child: TextField(
              controller: _ctrl,
              enabled: widget.editable,
              decoration: InputDecoration(
                labelText: widget.label,
                helperText: widget.hint,
                border: const OutlineInputBorder(),
              ),
            ),
          ),
          if (widget.editable && _dirty) ...[
            const SizedBox(width: 12),
            IconButton.filled(
              onPressed: _saving ? null : _save,
              icon: _saving ? const SizedBox(width: 18, height: 18,
                child: CircularProgressIndicator(strokeWidth: 2)) : const Icon(Icons.check),
              tooltip: '儲存',
            ),
          ],
        ],
      ),
    );
  }

  Future<void> _save() async {
    setState(() => _saving = true);
    final ok = await ref.read(parametersProvider.notifier).update(widget.paramKey, _ctrl.text);
    if (mounted) {
      setState(() { _saving = false; _dirty = !ok; });
      if (ok) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('${widget.label} 已更新'), duration: const Duration(seconds: 2)),
        );
      }
    }
  }
}
