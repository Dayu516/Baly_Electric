from datetime import datetime, timezone

from sqlalchemy.orm import Session

from domain.settings.models import CompanyInfo, SystemParameter
from domain.settings.repository import SettingsRepository
from infrastructure.persistence.orm_models import CompanyInfoORM, SystemParameterORM


class SqlSettingsRepository(SettingsRepository):
    def __init__(self, session: Session):
        self._session = session

    def get_company_info(self) -> CompanyInfo:
        orm = self._session.get(CompanyInfoORM, 1)
        if not orm:
            return CompanyInfo()
        return self._to_company(orm)

    def save_company_info(self, info: CompanyInfo) -> CompanyInfo:
        orm = self._session.get(CompanyInfoORM, 1)
        if not orm:
            orm = CompanyInfoORM(id=1)
            self._session.add(orm)
        orm.name = info.name
        orm.short_name = info.short_name
        orm.tax_id = info.tax_id
        orm.phone = info.phone
        orm.fax = info.fax
        orm.address = info.address
        orm.owner_name = info.owner_name
        orm.note = info.note
        orm.updated_at = datetime.now(timezone.utc)
        self._session.flush()
        return self._to_company(orm)

    def get_all_parameters(self) -> list[SystemParameter]:
        orms = self._session.query(SystemParameterORM).order_by(SystemParameterORM.key).all()
        return [self._to_param(o) for o in orms]

    def get_parameter(self, key: str) -> SystemParameter | None:
        orm = self._session.get(SystemParameterORM, key)
        return self._to_param(orm) if orm else None

    def save_parameter(self, param: SystemParameter) -> SystemParameter:
        orm = self._session.get(SystemParameterORM, param.key)
        if not orm:
            orm = SystemParameterORM(key=param.key)
            self._session.add(orm)
        orm.value = param.value
        orm.description = param.description
        orm.updated_at = datetime.now(timezone.utc)
        self._session.flush()
        return self._to_param(orm)

    @staticmethod
    def _to_company(orm: CompanyInfoORM) -> CompanyInfo:
        return CompanyInfo(
            name=orm.name,
            short_name=orm.short_name,
            tax_id=orm.tax_id,
            phone=orm.phone,
            fax=orm.fax,
            address=orm.address,
            owner_name=orm.owner_name,
            note=orm.note,
            updated_at=orm.updated_at,
        )

    @staticmethod
    def _to_param(orm: SystemParameterORM) -> SystemParameter:
        return SystemParameter(
            key=orm.key,
            value=orm.value,
            description=orm.description,
            updated_at=orm.updated_at,
        )
