/// 裝置分類。
enum DeviceClass { desktop, tablet, phone }

/// 功能開放等級。
enum FeatureLevel {
  /// Level A：完整開放
  a,

  /// Level B：簡化開放
  b,

  /// Level C：保留入口（顯示 FeatureLockedPage）
  c,
}

/// 功能開放控制 — 集中管理。
///
/// 解鎖一個功能 = 改這裡的一個判斷條件。
/// 不需要新增 route、不需要新增 page、不需要新增 API。
class FeatureFlags {
  static FeatureLevel getLevel(String feature, DeviceClass device) {
    return switch (device) {
      DeviceClass.desktop => _desktopLevel(feature),
      DeviceClass.tablet => _tabletLevel(feature),
      DeviceClass.phone => _phoneLevel(feature),
    };
  }

  static FeatureLevel _desktopLevel(String feature) {
    // Windows 桌面版：所有 Phase A 模組都是 Level A
    return FeatureLevel.a;
  }

  static FeatureLevel _tabletLevel(String feature) {
    return switch (feature) {
      'dashboard' => FeatureLevel.a, // Dashboard
      'pos' => FeatureLevel.b, // 簡化 POS
      'product' => FeatureLevel.b, // 搜尋+基本編輯
      'inventory' => FeatureLevel.a, // 盤點/驗收完整
      'procurement' => FeatureLevel.a, // 進貨驗收
      'stock_count' => FeatureLevel.a, // 盤點
      'customer' => FeatureLevel.b, // 查詢+標記收款
      'review' => FeatureLevel.a, // 審核
      'alert' => FeatureLevel.a, // 通知
      'reporting' => FeatureLevel.c, // Phase C
      'settings' => FeatureLevel.c, // 系統設定
      _ => FeatureLevel.c,
    };
  }

  static FeatureLevel _phoneLevel(String feature) {
    return switch (feature) {
      'dashboard' => FeatureLevel.c, // FeatureLockedPage
      'pos' => FeatureLevel.c, // FeatureLockedPage
      'product' => FeatureLevel.b, // 搜尋+查看
      'inventory' => FeatureLevel.b, // 庫存查詢+單品盤點
      'procurement' => FeatureLevel.c, // FeatureLockedPage
      'stock_count' => FeatureLevel.b, // 單品盤點
      'customer' => FeatureLevel.b, // 查詢+標記收款
      'review' => FeatureLevel.a, // 審核
      'alert' => FeatureLevel.a, // 通知
      'reporting' => FeatureLevel.c,
      'settings' => FeatureLevel.c,
      _ => FeatureLevel.c,
    };
  }
}
