"""Query Service 基底類別。"""

from sqlalchemy.orm import Session


class BaseQueryService:
    def __init__(self, session: Session):
        self._session = session
