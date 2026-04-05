"""每日自動備份 — pg_dump + 備份紀錄 + 失敗告警。

Usage:
    python -m infrastructure.backup.backup_service
"""

import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from config import settings
from core.logging import get_logger
from infrastructure.persistence.orm_models import OperationalAlertORM, SystemJobORM

logger = get_logger("backup")


def run_backup(session: Session) -> None:
    job = SystemJobORM(
        job_id=uuid.uuid4(),
        job_type="backup",
        status="running",
    )
    session.add(job)
    session.commit()

    backup_dir = Path(settings.BACKUP_DIR)
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_file = backup_dir / f"ottimo_{timestamp}.sql.gz"

    try:
        cmd = f"pg_dump {settings.DATABASE_URL} | gzip > {backup_file}"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=600)

        if result.returncode != 0:
            raise RuntimeError(f"pg_dump failed: {result.stderr}")

        job.status = "completed"
        job.completed_at = datetime.now(timezone.utc)
        job.detail = f"Backup saved: {backup_file}"
        session.commit()

        logger.info("backup_completed", file=str(backup_file))

        # 清理過期備份
        _cleanup_old_backups(backup_dir, settings.BACKUP_RETAIN_DAYS)

    except Exception as e:
        job.status = "failed"
        job.completed_at = datetime.now(timezone.utc)
        job.error_message = str(e)
        session.commit()

        # 建立告警
        alert = OperationalAlertORM(
            alert_id=uuid.uuid4(),
            alert_type="backup_failed",
            severity="critical",
            title="每日備份失敗",
            detail=str(e),
        )
        session.add(alert)
        session.commit()

        logger.error("backup_failed", error=str(e))


def _cleanup_old_backups(backup_dir: Path, retain_days: int) -> None:
    cutoff = datetime.now(timezone.utc).timestamp() - (retain_days * 86400)
    for f in backup_dir.glob("ottimo_*.sql.gz"):
        if f.stat().st_mtime < cutoff:
            f.unlink()
            logger.info("old_backup_removed", file=str(f))
