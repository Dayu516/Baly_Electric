"""手動執行備份 — 可由 cron 或手動呼叫。

Usage:
    cd backend
    python -m scripts.run_backup
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database import SessionLocal  # noqa: E402
from infrastructure.backup.backup_service import run_backup  # noqa: E402


def main():
    session = SessionLocal()
    try:
        run_backup(session)
    finally:
        session.close()


if __name__ == "__main__":
    main()
