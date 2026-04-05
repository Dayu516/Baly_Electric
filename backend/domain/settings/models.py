"""System settings domain models — 純 Python，不依賴外部套件。"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class CompanyInfo:
    name: str = ""
    short_name: str | None = None
    tax_id: str | None = None
    phone: str | None = None
    fax: str | None = None
    address: str | None = None
    owner_name: str | None = None
    note: str | None = None
    updated_at: datetime | None = None


@dataclass
class SystemParameter:
    key: str = ""
    value: str = ""
    description: str | None = None
    updated_at: datetime | None = None
