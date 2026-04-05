# ── 錯誤碼常數 ──────────────────────────────────────────
# 格式：ERR-{CATEGORY}-{NUMBER}
# Category: SYS / AUTH / SEC / BIZ / DB / VAL / EXT

# System
ERR_SYS_001 = "ERR-SYS-001"  # 未預期系統錯誤
ERR_SYS_002 = "ERR-SYS-002"  # 資料庫連線失敗

# Auth
ERR_AUTH_001 = "ERR-AUTH-001"  # 認證失敗（帳密錯誤）
ERR_AUTH_002 = "ERR-AUTH-002"  # Token 過期或無效
ERR_AUTH_003 = "ERR-AUTH-003"  # Token 缺失

# Security
ERR_SEC_001 = "ERR-SEC-001"  # 權限不足

# Business
ERR_BIZ_001 = "ERR-BIZ-001"  # 業務規則違反
ERR_BIZ_002 = "ERR-BIZ-002"  # 資源不存在
ERR_BIZ_003 = "ERR-BIZ-003"  # 重複資料
ERR_BIZ_004 = "ERR-BIZ-004"  # Optimistic lock 衝突

# Validation
ERR_VAL_001 = "ERR-VAL-001"  # 輸入驗證失敗

# Database
ERR_DB_001 = "ERR-DB-001"  # DB 寫入失敗
ERR_DB_002 = "ERR-DB-002"  # DB 查詢失敗

# External
ERR_EXT_001 = "ERR-EXT-001"  # 外部服務呼叫失敗


# ── AppError Hierarchy ──────────────────────────────────
class AppError(Exception):
    """應用層錯誤基底"""

    def __init__(self, code: str, message: str, *, retryable: bool = False):
        self.code = code
        self.message = message
        self.retryable = retryable
        super().__init__(message)


class AuthenticationError(AppError):
    def __init__(self, message: str = "認證失敗"):
        super().__init__(ERR_AUTH_001, message)


class AuthorizationError(AppError):
    def __init__(self, message: str = "權限不足"):
        super().__init__(ERR_SEC_001, message)


class NotFoundError(AppError):
    def __init__(self, entity: str, identifier: str):
        super().__init__(ERR_BIZ_002, f"{entity} '{identifier}' 不存在")


class ConflictError(AppError):
    def __init__(self, message: str = "資料衝突"):
        super().__init__(ERR_BIZ_004, message)


class ValidationError(AppError):
    def __init__(self, message: str):
        super().__init__(ERR_VAL_001, message)
