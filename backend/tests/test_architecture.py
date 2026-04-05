"""Architecture boundary tests — 自動化護欄。

根據 Constitution §7-8 的規則，掃描 .py 檔的 import 行與語意規則。
與 pytest 一起跑，違規直接 fail。

規則清單：
  - domain-no-external
  - domain-no-infra
  - application-no-api
  - infra-no-upward
  - api-no-orm
  - application-no-sql（排除 builder）
  - write-routes-have-audit
"""

import re
from pathlib import Path

BACKEND = Path(__file__).parent.parent

DOMAIN_DIR = BACKEND / "domain"
APPLICATION_DIR = BACKEND / "application"
INFRASTRUCTURE_DIR = BACKEND / "infrastructure"
API_DIR = BACKEND / "api"

# 匹配 import 行
IMPORT_RE = re.compile(r"^\s*(?:from|import)\s+([\w.]+)")


def _scan_imports(root: Path, forbidden_patterns: list[str], exclude_files: list[str] | None = None) -> list[str]:
    """掃描 root 下所有 .py 檔，找出 import 行匹配 forbidden_patterns 的違規。"""
    violations = []
    exclude = set(exclude_files or [])

    for py_file in root.rglob("*.py"):
        if py_file.name in exclude:
            continue
        try:
            lines = py_file.read_text(encoding="utf-8").splitlines()
        except (UnicodeDecodeError, PermissionError):
            continue

        for i, line in enumerate(lines, 1):
            m = IMPORT_RE.match(line)
            if not m:
                continue
            module = m.group(1)
            for pattern in forbidden_patterns:
                if pattern in module:
                    rel = py_file.relative_to(BACKEND)
                    violations.append(f"{rel}:{i} → {line.strip()}")
    return violations


# ── Batch 1: 直接 fail ────────────────────────────────


class TestDomainNoExternal:
    """domain/ 不可 import sqlalchemy, fastapi, openai, anthropic, redis, celery。"""

    FORBIDDEN = ["sqlalchemy", "fastapi", "openai", "anthropic", "redis", "celery", "langchain"]

    def test_no_external_imports(self):
        violations = _scan_imports(DOMAIN_DIR, self.FORBIDDEN)
        assert violations == [], f"domain/ 不可 import 外部框架：\n" + "\n".join(violations)


class TestDomainNoInfra:
    """domain/ 不可 import infrastructure/。"""

    def test_no_infra_imports(self):
        violations = _scan_imports(DOMAIN_DIR, ["infrastructure"])
        assert violations == [], f"domain/ 不可 import infrastructure：\n" + "\n".join(violations)


class TestApplicationNoApi:
    """application/ 不可 import api/。"""

    def test_no_api_imports(self):
        violations = _scan_imports(APPLICATION_DIR, ["api."])
        assert violations == [], f"application/ 不可 import api：\n" + "\n".join(violations)


class TestInfraNoUpward:
    """infrastructure/ 不可 import application/ 或 api/。"""

    def test_no_upward_imports(self):
        violations = _scan_imports(INFRASTRUCTURE_DIR, ["application.", "api."])
        assert violations == [], f"infrastructure/ 不可 import 上層：\n" + "\n".join(violations)


class TestApiNoOrm:
    """api/ 不可直接 import orm_models（ORM 應透過 repository 隔離）。"""

    def test_no_orm_imports(self):
        violations = _scan_imports(API_DIR, ["orm_models"])
        assert violations == [], f"api/ 不可直接 import ORM models：\n" + "\n".join(violations)


class TestApplicationNoDirectSql:
    """application/ service 不可 import sqlalchemy（__init__.py builder 的 Session 型別除外）。"""

    def test_no_sqlalchemy_in_services(self):
        violations = _scan_imports(APPLICATION_DIR, ["sqlalchemy"], exclude_files=["__init__.py"])
        assert violations == [], f"application/ service 不可 import sqlalchemy：\n" + "\n".join(violations)


# ── 語意規則：寫入 route 必須有 audit ────────────────────

# 少數豁免（非業務寫入操作）
_AUDIT_EXEMPT_ROUTES = {
    "login",  # 登入更新 last_login_at，不是業務寫入
}

ROUTE_RE = re.compile(r"@router\.(post|put|delete|patch)\(")


class TestWriteRoutesHaveAudit:
    """所有有 session.commit() 的寫入 route 必須呼叫 build_audit_service。"""

    def test_all_write_routes_have_audit(self):
        api_v1 = API_DIR / "v1"
        violations = []

        for py_file in api_v1.glob("*.py"):
            try:
                content = py_file.read_text(encoding="utf-8")
            except (UnicodeDecodeError, PermissionError):
                continue

            lines = content.splitlines()
            i = 0
            while i < len(lines):
                # 找到 route decorator
                if ROUTE_RE.search(lines[i]):
                    # 找到函數名
                    func_name = ""
                    for j in range(i, min(i + 5, len(lines))):
                        m = re.match(r"^def\s+(\w+)\(", lines[j])
                        if m:
                            func_name = m.group(1)
                            break

                    if func_name in _AUDIT_EXEMPT_ROUTES:
                        i += 1
                        continue

                    # 收集函數體（到下一個 @router 或文件結尾）
                    func_body = []
                    for j in range(i + 1, len(lines)):
                        if ROUTE_RE.search(lines[j]):
                            break
                        func_body.append(lines[j])

                    body_text = "\n".join(func_body)

                    # 有 session.commit() 但沒有 audit
                    if "session.commit()" in body_text and "build_audit_service" not in body_text:
                        rel = py_file.relative_to(BACKEND)
                        violations.append(f"{rel}:{i+1} → def {func_name}()")

                i += 1

        assert violations == [], (
            f"以下寫入 route 缺少 audit（Constitution §8）：\n" + "\n".join(violations)
        )
