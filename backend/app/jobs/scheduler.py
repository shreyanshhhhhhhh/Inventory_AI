"""Optional in-process nightly exception scan. Off unless EXCEPTION_SCAN_SCHEDULER_ENABLED=true."""

from __future__ import annotations

import logging

from app.core.config import settings
from app.db import SessionLocal
from app.services.jobs import run_exception_scans

logger = logging.getLogger(__name__)

_scheduler = None


def start_scheduler() -> None:
    global _scheduler
    if not settings.exception_scan_scheduler_enabled:
        return
    if _scheduler is not None:
        return
    from apscheduler.schedulers.background import BackgroundScheduler

    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(_tick, "interval", minutes=60, id="exception_scan", replace_existing=True)
    scheduler.start()
    _scheduler = scheduler
    logger.info("exception_scan scheduler started")


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is None:
        return
    _scheduler.shutdown(wait=False)
    _scheduler = None


def _tick() -> None:
    session = SessionLocal()
    try:
        run_exception_scans(session, respect_hour=True, force=False)
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("exception_scan scheduler tick failed")
    finally:
        session.close()
