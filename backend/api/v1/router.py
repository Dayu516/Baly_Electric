"""API v1 Router — 每個資源獨立 prefix，不共用。

URL 結構：
  /api/v1/dashboard/      — 首頁 Dashboard
  /api/v1/auth/           — 認證
  /api/v1/products/       — 品項 CRUD + 搜尋
  /api/v1/skus/           — SKU 詳情
  /api/v1/aliases/        — 品項別名
  /api/v1/attributes/     — 品項屬性 + 分類屬性模板
  /api/v1/categories/     — 分類（由 products router 處理，保持不動）
  /api/v1/sales/          — 交易 + 出貨單
  /api/v1/inventory/      — 庫存
  /api/v1/customers/      — 客戶 + 月結
  /api/v1/backorders/     — 欠貨待補
  /api/v1/suppliers/      — 供應商
  /api/v1/reviews/        — 審核待辦
  /api/v1/alerts/         — 通知
  /api/v1/import/         — 匯入
  /api/v1/products/{id}/supplier-prices — 供應商報價追蹤
  /api/v1/products/{id}/compare-prices — 跨供應商比價
  /api/v1/settings/       — 系統設定（公司資料 + 系統參數）
  /api/v1/users/          — 帳號管理 + 改密碼
"""

from fastapi import APIRouter

from api.v1.dashboard import router as dashboard_router
from api.v1.alerts import router as alert_router
from api.v1.aliases import router as alias_router
from api.v1.backorders import router as backorder_router
from api.v1.alternatives import router as alternatives_router
from api.v1.attributes import router as attributes_router
from api.v1.auth import router as auth_router
from api.v1.customers import router as customer_router
from api.v1.import_catalog import router as import_router
from api.v1.inquiries import router as inquiry_router
from api.v1.inventory import router as inventory_router
from api.v1.product_detail import router as product_detail_router
from api.v1.reports import router as reports_router
from api.v1.products import router as product_router
from api.v1.quotations import router as quotation_router
from api.v1.purchase_orders import router as po_router
from api.v1.receipt import router as receipt_router
from api.v1.reviews import router as review_router
from api.v1.sales import router as sales_router
from api.v1.sales_history import router as sales_history_router
from api.v1.settings import router as settings_router
from api.v1.supplier_prices import router as supplier_price_router
from api.v1.suppliers import router as supplier_router
from api.v1.users import router as user_router

api_v1_router = APIRouter()

# Dashboard
api_v1_router.include_router(dashboard_router, prefix="/dashboard", tags=["dashboard"])

# 認證
api_v1_router.include_router(auth_router, prefix="/auth", tags=["auth"])

# 品項（search 在 products router 裡，必須在 /{product_id} 之前定義）
api_v1_router.include_router(product_router, prefix="/products", tags=["products"])

# SKU 詳情（獨立 prefix 避免跟 products/{product_id} 衝突）
api_v1_router.include_router(product_detail_router, prefix="/skus", tags=["sku-detail"])

# 品項別名
api_v1_router.include_router(alias_router, prefix="/aliases", tags=["aliases"])

# 品項屬性 + 分類屬性模板
api_v1_router.include_router(attributes_router, prefix="/attributes", tags=["attributes"])

# 匯入
api_v1_router.include_router(import_router, prefix="/import", tags=["import"])

# 交易
api_v1_router.include_router(sales_router, prefix="/sales", tags=["sales"])
api_v1_router.include_router(backorder_router, prefix="/backorders", tags=["backorders"])
api_v1_router.include_router(sales_history_router, prefix="/sales", tags=["sales-history"])
api_v1_router.include_router(receipt_router, prefix="/receipts", tags=["receipt"])

# 庫存
api_v1_router.include_router(inventory_router, prefix="/inventory", tags=["inventory"])

# 客戶
api_v1_router.include_router(customer_router, prefix="/customers", tags=["customers"])

# 供應商
api_v1_router.include_router(supplier_router, prefix="/suppliers", tags=["suppliers"])

# 採購單
api_v1_router.include_router(po_router, prefix="/purchase-orders", tags=["purchase-orders"])

# 詢價單
api_v1_router.include_router(inquiry_router, prefix="/inquiries", tags=["inquiries"])

# 供應商報價追蹤（掛在 /products 下）
api_v1_router.include_router(supplier_price_router, prefix="/products", tags=["supplier-prices"])

# 替代品搜尋（掛在 /products 下）
api_v1_router.include_router(alternatives_router, prefix="/products", tags=["alternatives"])

# 審核
api_v1_router.include_router(review_router, prefix="/reviews", tags=["reviews"])

# 通知
api_v1_router.include_router(alert_router, prefix="/alerts", tags=["alerts"])

# 報價單（給客戶）
api_v1_router.include_router(quotation_router, prefix="/quotations", tags=["quotations"])

# 報表
api_v1_router.include_router(reports_router, prefix="/reports", tags=["reports"])

# 系統設定
api_v1_router.include_router(settings_router, prefix="/settings", tags=["settings"])

# 帳號管理
api_v1_router.include_router(user_router, prefix="/users", tags=["users"])