"""Settings repository 介面 — ABC。"""

from abc import ABC, abstractmethod

from domain.settings.models import CompanyInfo, SystemParameter


class SettingsRepository(ABC):
    @abstractmethod
    def get_company_info(self) -> CompanyInfo:
        ...

    @abstractmethod
    def save_company_info(self, info: CompanyInfo) -> CompanyInfo:
        ...

    @abstractmethod
    def get_all_parameters(self) -> list[SystemParameter]:
        ...

    @abstractmethod
    def get_parameter(self, key: str) -> SystemParameter | None:
        ...

    @abstractmethod
    def save_parameter(self, param: SystemParameter) -> SystemParameter:
        ...
