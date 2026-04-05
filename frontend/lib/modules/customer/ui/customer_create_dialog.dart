import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../application/customer_provider.dart';

class CustomerCreateDialog extends ConsumerStatefulWidget {
  const CustomerCreateDialog({super.key});

  @override
  ConsumerState<CustomerCreateDialog> createState() => _State();
}

class _State extends ConsumerState<CustomerCreateDialog> {
  // 基本資料
  final _nameCtrl = TextEditingController();
  final _shortNameCtrl = TextEditingController();
  final _taxIdCtrl = TextEditingController();
  String _customerType = 'general';

  // 聯絡資訊
  final _contactCtrl = TextEditingController();
  final _phoneCtrl = TextEditingController();
  final _mobileCtrl = TextEditingController();
  final _emailCtrl = TextEditingController();
  final _lineCtrl = TextEditingController();
  final _addrCtrl = TextEditingController();
  final _shipAddrCtrl = TextEditingController();

  // 交易設定
  String _payTerms = 'cash';
  int? _payDays;
  String _priceLevel = 'retail';
  final _invoiceTitleCtrl = TextEditingController();
  String? _invoiceType;
  final _creditLimitCtrl = TextEditingController();
  final _discountCtrl = TextEditingController();

  // 業務 + 備註
  final _salesRepCtrl = TextEditingController();
  String? _source;
  String? _level;
  final _noteCtrl = TextEditingController();

  bool _loading = false;
  bool _showAdvanced = false;

  static const _typeOptions = {'general': '一般', 'company': '公司戶', 'dealer': '經銷/同業', 'vip': 'VIP', 'project': '專案'};
  static const _payOptions = {'cash': '現金', 'monthly_credit': '月結', 'transfer': '匯款', 'check': '票據'};
  static const _priceOptions = {'retail': '零售價', 'wholesale': '批發價', 'dealer': '同業價', 'project': '專案價', 'vip': 'VIP價'};
  static const _invoiceOptions = {'二聯': '二聯', '三聯': '三聯', '免開': '免開'};
  static const _sourceOptions = ['舊客戶', '介紹', '網路', '展會', '路過', '其他'];
  static const _levelOptions = {'A': 'A', 'B': 'B', 'C': 'C'};

  @override
  void dispose() {
    for (final c in [_nameCtrl, _shortNameCtrl, _taxIdCtrl, _contactCtrl, _phoneCtrl,
        _mobileCtrl, _emailCtrl, _lineCtrl, _addrCtrl, _shipAddrCtrl,
        _invoiceTitleCtrl, _creditLimitCtrl, _discountCtrl, _salesRepCtrl, _noteCtrl]) {
      c.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Dialog(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 680, maxHeight: 720),
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(24, 20, 16, 0),
              child: Row(children: [
                const Icon(Icons.person_add, size: 24),
                const SizedBox(width: 8),
                const Text('新增客戶', style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
                const Spacer(),
                IconButton(icon: const Icon(Icons.close), onPressed: () => Navigator.pop(context)),
              ]),
            ),
            const Divider(),
            Expanded(
              child: SingleChildScrollView(
                padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  // ── 1. 基本資料 ──
                  _sectionTitle('基本資料'),
                  _row([
                    _field(_nameCtrl, '客戶名稱 *', flex: 3),
                    _field(_shortNameCtrl, '簡稱', flex: 2),
                  ]),
                  _row([
                    _field(_taxIdCtrl, '統一編號', flex: 2),
                    _dropdown('客戶類型', _customerType, _typeOptions, (v) => setState(() => _customerType = v!), flex: 2),
                  ]),

                  const SizedBox(height: 16),
                  _sectionTitle('聯絡資訊'),
                  _row([
                    _field(_contactCtrl, '聯絡人', flex: 2),
                    _field(_mobileCtrl, '手機', flex: 2),
                    _field(_phoneCtrl, '公司電話', flex: 2),
                  ]),
                  _row([
                    _field(_emailCtrl, 'Email', flex: 3),
                    _field(_lineCtrl, 'LINE', flex: 2),
                  ]),
                  _field(_addrCtrl, '地址'),
                  const SizedBox(height: 8),
                  _field(_shipAddrCtrl, '送貨地址（不同於公司地址時填）'),

                  const SizedBox(height: 16),
                  _sectionTitle('交易設定'),
                  _row([
                    _dropdown('付款方式', _payTerms, _payOptions, (v) => setState(() => _payTerms = v!), flex: 2),
                    _dropdownNullable('帳期', _payDays?.toString(), {'30': '30天', '45': '45天', '60': '60天', '90': '90天'},
                        (v) => setState(() => _payDays = v != null ? int.tryParse(v) : null), flex: 2),
                    _dropdown('價格等級', _priceLevel, _priceOptions, (v) => setState(() => _priceLevel = v!), flex: 2),
                  ]),
                  _row([
                    _dropdownNullable('發票類型', _invoiceType, _invoiceOptions, (v) => setState(() => _invoiceType = v), flex: 2),
                    _field(_invoiceTitleCtrl, '發票抬頭', flex: 3),
                  ]),

                  // 進階（可收摺）
                  const SizedBox(height: 8),
                  InkWell(
                    onTap: () => setState(() => _showAdvanced = !_showAdvanced),
                    child: Row(children: [
                      Icon(_showAdvanced ? Icons.expand_less : Icons.expand_more, size: 20),
                      const SizedBox(width: 4),
                      Text('更多設定', style: TextStyle(fontSize: 13, color: Theme.of(context).colorScheme.primary)),
                    ]),
                  ),
                  if (_showAdvanced) ...[
                    const SizedBox(height: 8),
                    _row([
                      _field(_creditLimitCtrl, '信用額度', flex: 2, keyboardType: TextInputType.number),
                      _field(_discountCtrl, '預設折扣率', flex: 2, keyboardType: TextInputType.number),
                    ]),
                    _row([
                      _field(_salesRepCtrl, '業務負責人', flex: 2),
                      _dropdownNullable('客戶來源', _source, {for (var s in _sourceOptions) s: s},
                          (v) => setState(() => _source = v), flex: 2),
                      _dropdownNullable('客戶等級', _level, _levelOptions, (v) => setState(() => _level = v), flex: 1),
                    ]),
                  ],

                  const SizedBox(height: 8),
                  TextField(controller: _noteCtrl, decoration: const InputDecoration(labelText: '備註', border: OutlineInputBorder()),
                      maxLines: 2),
                ]),
              ),
            ),
            const Divider(height: 1),
            Padding(
              padding: const EdgeInsets.all(16),
              child: Row(mainAxisAlignment: MainAxisAlignment.end, children: [
                TextButton(onPressed: () => Navigator.pop(context), child: const Text('取消')),
                const SizedBox(width: 12),
                FilledButton(
                  onPressed: _loading ? null : _submit,
                  child: _loading
                      ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                      : const Text('建立'),
                ),
              ]),
            ),
          ],
        ),
      ),
    );
  }

  Widget _sectionTitle(String text) => Padding(
    padding: const EdgeInsets.only(bottom: 8),
    child: Text(text, style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: Theme.of(context).colorScheme.primary)),
  );

  Widget _row(List<Widget> children) => Padding(
    padding: const EdgeInsets.only(bottom: 12),
    child: Row(children: children.expand((w) => [if (children.indexOf(w) > 0) const SizedBox(width: 12), Expanded(child: w)])
        .skip(1).toList()), // skip first SizedBox
  );

  Widget _field(TextEditingController ctrl, String label, {int flex = 1, TextInputType? keyboardType}) =>
      TextField(controller: ctrl, decoration: InputDecoration(labelText: label, border: const OutlineInputBorder(), isDense: true),
          keyboardType: keyboardType);

  Widget _dropdown(String label, String value, Map<String, String> options, ValueChanged<String?> onChanged, {int flex = 1}) =>
      DropdownButtonFormField<String>(
        value: value, decoration: InputDecoration(labelText: label, border: const OutlineInputBorder(), isDense: true),
        items: options.entries.map((e) => DropdownMenuItem(value: e.key, child: Text(e.value))).toList(),
        onChanged: onChanged,
      );

  Widget _dropdownNullable(String label, String? value, Map<String, String> options, ValueChanged<String?> onChanged, {int flex = 1}) =>
      DropdownButtonFormField<String>(
        value: value, decoration: InputDecoration(labelText: label, border: const OutlineInputBorder(), isDense: true),
        items: [const DropdownMenuItem(value: null, child: Text('-')),
          ...options.entries.map((e) => DropdownMenuItem(value: e.key, child: Text(e.value)))],
        onChanged: onChanged,
      );

  Future<void> _submit() async {
    if (_nameCtrl.text.trim().isEmpty) return;
    setState(() => _loading = true);

    final data = <String, dynamic>{
      'name': _nameCtrl.text.trim(),
      'customer_type': _customerType,
      'payment_terms': _payTerms,
      'price_level': _priceLevel,
    };

    void _addIfNotEmpty(String key, TextEditingController ctrl) {
      if (ctrl.text.trim().isNotEmpty) data[key] = ctrl.text.trim();
    }
    _addIfNotEmpty('short_name', _shortNameCtrl);
    _addIfNotEmpty('tax_id', _taxIdCtrl);
    _addIfNotEmpty('contact_person', _contactCtrl);
    _addIfNotEmpty('phone', _phoneCtrl);
    _addIfNotEmpty('mobile', _mobileCtrl);
    _addIfNotEmpty('email', _emailCtrl);
    _addIfNotEmpty('line_id', _lineCtrl);
    _addIfNotEmpty('address', _addrCtrl);
    _addIfNotEmpty('shipping_address', _shipAddrCtrl);
    _addIfNotEmpty('invoice_title', _invoiceTitleCtrl);
    _addIfNotEmpty('note', _noteCtrl);
    _addIfNotEmpty('sales_rep', _salesRepCtrl);

    if (_payDays != null) data['payment_days'] = _payDays;
    if (_invoiceType != null) data['invoice_type'] = _invoiceType;
    if (_source != null) data['source'] = _source;
    if (_level != null) data['customer_level'] = _level;

    final cl = double.tryParse(_creditLimitCtrl.text);
    if (cl != null) data['credit_limit'] = cl;
    final dr = double.tryParse(_discountCtrl.text);
    if (dr != null) data['discount_rate'] = dr;

    final ok = await ref.read(customerListProvider.notifier).create(data);
    setState(() => _loading = false);
    if (ok && mounted) Navigator.pop(context, true);
  }
}
