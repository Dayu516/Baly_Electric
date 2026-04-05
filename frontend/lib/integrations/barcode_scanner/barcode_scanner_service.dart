/// 條碼掃描器 integration — Phase A 基礎版。
///
/// Phase A 掃碼槍以 HID Keyboard 模式為主，
/// 等同鍵盤輸入，不需要特殊 SDK。
/// 掃碼結果會直接進入 TextField。
///
/// 此 service 預留給 Phase B+ 相機掃碼用。
class BarcodeScannerService {
  /// 使用相機掃碼（iPad 用）。
  /// Phase A 暫不實作，掃碼槍用 HID 即可。
  Future<String?> scanWithCamera() async {
    // TODO Phase B: mobile_scanner package
    return null;
  }
}