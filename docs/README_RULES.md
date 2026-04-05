# 文件權威規則（Single Source of Truth）

## 1. 核心規則（永遠優先）

1. CLAUDE.md
   - AI 開發鐵律
   - 每次生成程式碼必須遵守

2. Constitution.md
   - 系統架構規範
   - transaction / 分層 / 錯誤處理
   - 本質上是「全專案憲法」

---

## 2. 現況（只能描述，不可當規則）

3. PROGRESS.md
   - 當前系統實作狀態
   - API / 模組 / 完成度
   - 不可用來推翻憲法

---

## 3. 歷史（禁止作為決策依據）

4. REFACTORING_LOG.md
   - 過去怎麼改
   - 只能參考，不可當規則

---

## 4. 任務 / 未來（按需載入）

5. Phase_B.md
6. PRODUCT_STRUCTURE_PLAN.md
7. DATA_CLEANER_PROGRESS.md
8. 01~05 規劃文件
9. 專案需求.md

規則：
- 只有做該功能時才可讀
- 不可影響當前架構決策

---

## 核心原則

Claude 每次只允許使用：

- CLAUDE.md
- Constitution.md
- 當前任務說明

禁止混用：
- 歷史
- roadmap
- 舊設計

違反 = 架構污染