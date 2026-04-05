"""ImportCatalogUseCase + DeactivateImportBatchUseCase unit tests."""

import uuid
from unittest.mock import MagicMock

import pytest

from application.use_cases.import_catalog import (
    DeactivateImportBatchUseCase,
    ImportCatalogUseCase,
)
from core.results import Result


FAKE_USER = uuid.uuid4()


# ── ImportCatalogUseCase ─────────────────────────────────


class TestImportCatalogUseCase:
    def _make(self):
        import_service = MagicMock()
        audit = MagicMock()
        session = MagicMock()
        uc = ImportCatalogUseCase(import_service, audit, session)
        return uc, import_service, audit, session

    def test_generates_batch_id(self):
        uc, svc, audit, session = self._make()
        svc.import_csv.return_value = Result.ok(data={"imported": 1})

        uc.execute("csv_content", FAKE_USER)

        # import_csv 被呼叫時帶了 batch_id
        call_args = svc.import_csv.call_args
        assert call_args[1]["batch_id"] is not None

    def test_commits_on_success(self):
        uc, svc, audit, session = self._make()
        svc.import_csv.return_value = Result.ok(data={"imported": 1})

        uc.execute("csv", FAKE_USER)

        session.commit.assert_called_once()

    def test_no_commit_on_failure(self):
        uc, svc, audit, session = self._make()
        svc.import_csv.return_value = Result.fail("ERR", "bad csv")

        result = uc.execute("", FAKE_USER)

        assert not result.success
        session.commit.assert_not_called()

    def test_audit_logged(self):
        uc, svc, audit, session = self._make()
        svc.import_csv.return_value = Result.ok(data={"imported": 5})

        uc.execute("csv", FAKE_USER)

        audit.log.assert_called_once()
        args = audit.log.call_args
        assert args[0][0] == FAKE_USER
        assert args[0][1] == "import_catalog"


# ── DeactivateImportBatchUseCase ─────────────────────────


class TestDeactivateImportBatchUseCase:
    def _make(self):
        audit = MagicMock()
        session = MagicMock()
        uc = DeactivateImportBatchUseCase(audit, session)
        return uc, audit, session

    def test_deactivates_batch(self):
        uc, audit, session = self._make()
        batch_id = uuid.uuid4()

        # Mock execute returns rowcount > 0
        mock_result = MagicMock()
        mock_result.rowcount = 3
        session.execute.return_value = mock_result

        result = uc.execute(batch_id, FAKE_USER)

        assert result.success
        assert result.data["products"] == 3
        audit.log.assert_called_once()
        session.commit.assert_called_once()

    def test_no_data_found(self):
        uc, audit, session = self._make()
        batch_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.rowcount = 0
        session.execute.return_value = mock_result

        result = uc.execute(batch_id, FAKE_USER)

        assert not result.success
        session.commit.assert_not_called()
