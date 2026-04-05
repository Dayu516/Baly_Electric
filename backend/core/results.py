from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass
class Result:
    """統一回傳格式。所有 Application Service 的回傳都走這個結構。"""

    success: bool
    code: str  # "OK" 或錯誤碼 "ERR-SYS-001"
    message: str = ""
    data: Optional[Any] = None
    retryable: bool = False
    severity: str = "info"  # info / warning / error / critical
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def ok(cls, data: Any = None, message: str = "") -> "Result":
        return cls(success=True, code="OK", message=message, data=data)

    @classmethod
    def fail(
        cls,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        severity: str = "error",
        data: Any = None,
    ) -> "Result":
        return cls(
            success=False,
            code=code,
            message=message,
            data=data,
            retryable=retryable,
            severity=severity,
        )
