"""APScheduler background task management."""
import logging
from datetime import datetime, timezone
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor
from sqlalchemy.orm import Session

from ..config import settings
from ..database import SessionLocal, engine
from ..models.domain import Domain, DomainStatus, FAST_POLL_STATES
from ..models.event import DomainEvent, EventType
from ..services.whois_service import lookup_domain
from ..services.domain_lifecycle import determine_status, is_alert_worthy_transition
from ..services.alert_service import dispatch_alerts

logger = logging.getLogger(__name__)

_scheduler: Optional[AsyncIOScheduler] = None


def get_scheduler() -> Optional[AsyncIOScheduler]:
    return _scheduler


def init_scheduler() -> AsyncIOScheduler:
    global _scheduler

    jobstores = {
        "default": SQLAlchemyJobStore(engine=engine),
    }
    executors = {
        "default": AsyncIOExecutor(),
    }
    job_defaults = {
        "coalesce": True,
        "max_instances": 1,
        "misfire_grace_time": 300,
    }

    _scheduler = AsyncIOScheduler(
        jobstores=jobstores,
        executors=executors,
        job_defaults=job_defaults,
        timezone="UTC",
    )
    return _scheduler


async def check_domain_job(domain_id: int) -> None:
    """Background job: perform WHOIS check and update domain status."""
    db: Session = SessionLocal()
    try:
        domain = db.query(Domain).filter(Domain.id == domain_id).first()
        if not domain:
            logger.warning("Domain %d not found, skipping WHOIS check", domain_id)
            return

        logger.info("Checking WHOIS for %s", domain.name)
        result = await lookup_domain(domain.name)

        old_status = domain.status
        new_status = determine_status(result, domain.name)

        # Update domain record
        domain.last_checked_at = datetime.now(timezone.utc)
        domain.status = new_status.value

        if result.error:
            domain.consecutive_errors += 1
            domain.last_check_error = result.error
        else:
            domain.consecutive_errors = 0
            domain.last_check_error = None
            domain.registrar = result.registrar
            domain.registrant = result.registrant
            domain.registered_at = result.registered_at
            domain.expires_at = result.expires_at
            domain.updated_at = result.updated_at
            if result.name_servers:
                import json
                domain.name_servers = json.dumps(result.name_servers)

        # Log WHOIS check event
        db.add(DomainEvent(
            domain_id=domain.id,
            event_type=EventType.WHOIS_CHECK,
            new_status=new_status.value,
            message=f"WHOIS check {'failed: ' + result.error if result.error else 'succeeded'}",
            raw_whois=result.raw[:5000] if result.raw else None,
            success=result.error is None,
        ))

        # Handle status transition
        if old_status != new_status.value:
            logger.info("Status change for %s: %s → %s", domain.name, old_status, new_status.value)
            db.add(DomainEvent(
                domain_id=domain.id,
                event_type=EventType.STATUS_CHANGE,
                old_status=old_status,
                new_status=new_status.value,
                message=f"Status changed from {old_status} to {new_status.value}",
            ))
            db.commit()
            db.refresh(domain)

            # Dispatch alerts for worthy transitions
            if is_alert_worthy_transition(old_status, new_status.value):
                await dispatch_alerts(domain, old_status, new_status.value, db)

            # Adjust polling frequency based on new status
            reschedule_on_transition(domain_id, new_status)
        else:
            db.commit()

    except Exception as e:
        logger.exception("Error in check_domain_job for domain %d: %s", domain_id, e)
        db.rollback()
    finally:
        db.close()


def schedule_domain(domain_id: int, interval_hours: int, run_now: bool = False) -> None:
    """Add or replace a recurring WHOIS check job for a domain."""
    if not _scheduler:
        return

    job_id = f"domain_{domain_id}"
    kwargs = {"domain_id": domain_id}

    trigger_kwargs = {"hours": interval_hours}

    if _scheduler.get_job(job_id):
        _scheduler.reschedule_job(
            job_id,
            trigger="interval",
            **trigger_kwargs,
        )
    else:
        _scheduler.add_job(
            check_domain_job,
            trigger="interval",
            id=job_id,
            kwargs=kwargs,
            next_run_time=datetime.now(timezone.utc) if run_now else None,
            **trigger_kwargs,
        )


def reschedule_on_transition(domain_id: int, new_status: DomainStatus) -> None:
    """Adjust polling frequency based on domain's lifecycle state."""
    if new_status in FAST_POLL_STATES:
        interval_minutes = settings.fast_poll_interval_minutes
        logger.info("Domain %d entering fast-poll mode (%dm intervals)", domain_id, interval_minutes)
        if _scheduler:
            job_id = f"domain_{domain_id}"
            if _scheduler.get_job(job_id):
                _scheduler.reschedule_job(job_id, trigger="interval", minutes=interval_minutes)
    # For other statuses, the normal interval will be restored on next full reconcile


def remove_domain_job(domain_id: int) -> None:
    """Remove scheduler job for a domain."""
    if not _scheduler:
        return
    job_id = f"domain_{domain_id}"
    if _scheduler.get_job(job_id):
        _scheduler.remove_job(job_id)


async def reconcile_jobs() -> None:
    """On startup, ensure every domain in DB has a scheduler job."""
    db: Session = SessionLocal()
    try:
        domains = db.query(Domain).all()
        scheduled_ids = {
            int(job.id.replace("domain_", ""))
            for job in (_scheduler.get_jobs() if _scheduler else [])
            if job.id.startswith("domain_")
        }
        domain_ids = {d.id for d in domains}

        # Add missing jobs
        for domain in domains:
            if domain.id not in scheduled_ids:
                interval = domain.check_interval_hours or settings.default_check_interval_hours
                # Run immediately if never checked
                run_now = domain.last_checked_at is None
                schedule_domain(domain.id, interval, run_now=run_now)
                logger.info("Reconciled: added job for domain %s (id=%d)", domain.name, domain.id)

        # Remove orphaned jobs
        for orphan_id in scheduled_ids - domain_ids:
            remove_domain_job(orphan_id)
            logger.info("Reconciled: removed orphaned job for domain id=%d", orphan_id)

    finally:
        db.close()
