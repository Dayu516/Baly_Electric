## Flutter 跨平台架構規則

### 分層
- `core/` — 共用底座（Results, Errors, Logger, FeatureFlags, Router, Auth, Theme）
- `infrastructure/` — API Client, 離線 SQLite, 同步引擎
- `modules/{name}/application/` — 業務邏輯、State Management (Riverpod)
- `modules/{name}/ui/` — Page, Layout, Widget
- `integrations/` — 外部設備（掃碼器、印表機）
- `features/` — Phase A 為空

### 跨裝置規則
- 一個模組一套 State（Provider），三端共用
- 一個 Page，三個 Layout（Desktop/Tablet/Phone）
- 禁止建 desktopXxxProvider / mobileXxxProvider
- 禁止建 DesktopProductCard / TabletProductCard（同一 widget 內 switch）
- 所有 route 在所有裝置上都註冊
- Level C 模組用 FeatureLockedPage（引導頁，不是錯誤頁）
- Feature Flags 集中在 feature_flags.dart

### 禁止事項
- 禁止用 print()，用 appLogger
- 禁止裝置專用 API（/api/mobile/）
- 禁止每個模組自己寫 FeatureLockedPage

### 開發順序（每個模組）
1. 後端 API（一套，不分裝置）
2. State Management / Provider（一套）
3. Desktop Layout（完整版）
4. Tablet Layout（調整版面）
5. Phone Layout（大部分用 FeatureLockedPage）
6. Feature Flags 設定

### 檔案大小規則
- 單一 .dart 檔案超過 500 行必須拆分
- 每個 Tab panel / section 獨立一個檔案
- 主頁面檔案只做 Tab 切換和組裝，不超過 150 行
- 共用 pattern 出現第 2 次時，抽出到 core/widgets/

### 已知前端債（待修）
| 檔案 | 問題 | 狀態 |
|------|------|------|
| settings_page.dart | 1542 行 → 拆成 7 個獨立 panel 檔案 | ✅ 已修正 |
| product_info_card.dart | 985 行 → 拆成 4 個獨立 tab 檔案 | ✅ 已修正 |
| procurement_page.dart | 搜尋品項 dialog 重複 | ✅ 已抽出 ProductSearchDialog |
| sales_page.dart | 搜尋品項 dialog 重複 | ✅ 已抽出 ProductSearchDialog |
| StatusBadge | procurement 和 sales 各有一份 | ✅ 已抽到 core/widgets/status_badge.dart |

### Phase A 限制
- iPhone Level C 模組用 FeatureLockedPage
- 優先完成 Windows Desktop，再 iPad，最後 iPhone
- 離線功能 A5 才做完整版
