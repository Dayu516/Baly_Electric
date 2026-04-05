import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../application/settings_provider.dart';
import 'settings_widgets.dart';

class CompanyInfoPanel extends ConsumerStatefulWidget {
  final bool editable;
  const CompanyInfoPanel({super.key, required this.editable});
  @override
  ConsumerState<CompanyInfoPanel> createState() => _CompanyInfoPanelState();
}

class _CompanyInfoPanelState extends ConsumerState<CompanyInfoPanel> {
  final _nameCtrl = TextEditingController();
  final _shortNameCtrl = TextEditingController();
  final _taxIdCtrl = TextEditingController();
  final _phoneCtrl = TextEditingController();
  final _faxCtrl = TextEditingController();
  final _addressCtrl = TextEditingController();
  final _ownerNameCtrl = TextEditingController();
  final _noteCtrl = TextEditingController();
  bool _initialized = false;

  @override
  void dispose() {
    _nameCtrl.dispose();
    _shortNameCtrl.dispose();
    _taxIdCtrl.dispose();
    _phoneCtrl.dispose();
    _faxCtrl.dispose();
    _addressCtrl.dispose();
    _ownerNameCtrl.dispose();
    _noteCtrl.dispose();
    super.dispose();
  }

  void _fillFromData(Map<String, dynamic> data) {
    _nameCtrl.text = data['name']?.toString() ?? '';
    _shortNameCtrl.text = data['short_name']?.toString() ?? '';
    _taxIdCtrl.text = data['tax_id']?.toString() ?? '';
    _phoneCtrl.text = data['phone']?.toString() ?? '';
    _faxCtrl.text = data['fax']?.toString() ?? '';
    _addressCtrl.text = data['address']?.toString() ?? '';
    _ownerNameCtrl.text = data['owner_name']?.toString() ?? '';
    _noteCtrl.text = data['note']?.toString() ?? '';
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(companyInfoProvider);

    if (!_initialized && state.data != null) {
      _fillFromData(state.data!);
      _initialized = true;
    }

    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 600),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('公司資料', style: Theme.of(context).textTheme.headlineSmall),
            const SizedBox(height: 8),
            Text('設定出貨單抬頭和公司基本資訊', style: Theme.of(context).textTheme.bodyMedium?.copyWith(
              color: Theme.of(context).colorScheme.onSurfaceVariant)),
            const SizedBox(height: 24),
            if (state.loading) const LinearProgressIndicator(),
            if (state.message != null)
              Padding(
                padding: const EdgeInsets.only(bottom: 16),
                child: SuccessBanner(message: state.message!),
              ),
            if (state.error != null)
              Padding(
                padding: const EdgeInsets.only(bottom: 16),
                child: ErrorBanner(message: state.error!),
              ),
            _field('公司名稱', _nameCtrl, enabled: widget.editable),
            _field('簡稱', _shortNameCtrl, enabled: widget.editable),
            _field('統一編號', _taxIdCtrl, enabled: widget.editable),
            _field('電話', _phoneCtrl, enabled: widget.editable),
            _field('傳真', _faxCtrl, enabled: widget.editable),
            _field('地址', _addressCtrl, enabled: widget.editable),
            _field('負責人', _ownerNameCtrl, enabled: widget.editable),
            _field('備註', _noteCtrl, enabled: widget.editable, maxLines: 3),
            if (widget.editable) ...[
              const SizedBox(height: 24),
              FilledButton.icon(
                onPressed: state.loading ? null : _save,
                icon: const Icon(Icons.save),
                label: const Text('儲存'),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _field(String label, TextEditingController ctrl, {bool enabled = true, int maxLines = 1}) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: TextField(
        controller: ctrl,
        enabled: enabled,
        maxLines: maxLines,
        decoration: InputDecoration(
          labelText: label,
          border: const OutlineInputBorder(),
        ),
      ),
    );
  }

  Future<void> _save() async {
    await ref.read(companyInfoProvider.notifier).save({
      'name': _nameCtrl.text,
      'short_name': _shortNameCtrl.text.isEmpty ? null : _shortNameCtrl.text,
      'tax_id': _taxIdCtrl.text.isEmpty ? null : _taxIdCtrl.text,
      'phone': _phoneCtrl.text.isEmpty ? null : _phoneCtrl.text,
      'fax': _faxCtrl.text.isEmpty ? null : _faxCtrl.text,
      'address': _addressCtrl.text.isEmpty ? null : _addressCtrl.text,
      'owner_name': _ownerNameCtrl.text.isEmpty ? null : _ownerNameCtrl.text,
      'note': _noteCtrl.text.isEmpty ? null : _noteCtrl.text,
    });
  }
}
