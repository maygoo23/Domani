"""Domain CRUD and action routes."""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.domain import Domain
from ..models.event import DomainEvent, EventType
from ..schemas.domain import DomainCreate, DomainUpdate, validate_domain_name
from ..services import scheduler_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/domains")
templates = Jinja2Templates(directory="app/templates")


def flash(request: Request, message: str, category: str = "info") -> None:
    if "flash_messages" not in request.session:
        request.session["flash_messages"] = []
    request.session["flash_messages"].append({"message": message, "category": category})


@router.post("", response_class=HTMLResponse)
async def add_domain(
    request: Request,
    name: str = Form(...),
    watch_type: str = Form("snag"),
    notes: str = Form(""),
    tags: str = Form(""),
    check_interval_hours: int = Form(6),
    db: Session = Depends(get_db),
):
    # Validate and normalize domain name
    try:
        clean_name = validate_domain_name(name)
    except ValueError as e:
        flash(request, str(e), "danger")
        return RedirectResponse("/domains/add", status_code=303)

    # Check for duplicate
    existing = db.query(Domain).filter(Domain.name == clean_name).first()
    if existing:
        flash(request, f"Domain '{clean_name}' is already being tracked.", "warning")
        return RedirectResponse("/domains/add", status_code=303)

    domain = Domain(
        name=clean_name,
        watch_type=watch_type,
        notes=notes.strip() or None,
        tags=tags.strip() or None,
        check_interval_hours=max(1, min(check_interval_hours, 168)),
    )
    db.add(domain)
    db.flush()

    db.add(DomainEvent(
        domain_id=domain.id,
        event_type=EventType.DOMAIN_ADDED,
        message=f"Domain added for {watch_type} monitoring",
    ))
    db.commit()
    db.refresh(domain)

    # Schedule immediate WHOIS check
    scheduler_service.schedule_domain(domain.id, domain.check_interval_hours, run_now=True)

    flash(request, f"Domain '{clean_name}' added! WHOIS check queued.", "success")
    return RedirectResponse(f"/domains/{domain.id}", status_code=303)


@router.post("/{domain_id}/edit")
async def edit_domain(
    request: Request,
    domain_id: int,
    watch_type: str = Form("snag"),
    notes: str = Form(""),
    tags: str = Form(""),
    check_interval_hours: int = Form(6),
    db: Session = Depends(get_db),
):
    domain = db.query(Domain).filter(Domain.id == domain_id).first()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")

    old_interval = domain.check_interval_hours
    domain.watch_type = watch_type
    domain.notes = notes.strip() or None
    domain.tags = tags.strip() or None
    domain.check_interval_hours = max(1, min(check_interval_hours, 168))

    db.add(DomainEvent(
        domain_id=domain.id,
        event_type=EventType.DOMAIN_UPDATED,
        message="Domain settings updated",
    ))
    db.commit()

    # Reschedule if interval changed
    if old_interval != domain.check_interval_hours:
        scheduler_service.schedule_domain(domain.id, domain.check_interval_hours)

    flash(request, "Domain settings saved.", "success")
    return RedirectResponse(f"/domains/{domain_id}", status_code=303)


@router.post("/{domain_id}/delete")
async def delete_domain(request: Request, domain_id: int, db: Session = Depends(get_db)):
    domain = db.query(Domain).filter(Domain.id == domain_id).first()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")

    name = domain.name
    scheduler_service.remove_domain_job(domain_id)
    db.delete(domain)
    db.commit()

    flash(request, f"Domain '{name}' removed.", "info")
    return RedirectResponse("/", status_code=303)


@router.post("/{domain_id}/refresh", response_class=HTMLResponse)
async def refresh_domain(request: Request, domain_id: int, db: Session = Depends(get_db)):
    """Trigger manual WHOIS refresh — runs immediately in background."""
    domain = db.query(Domain).filter(Domain.id == domain_id).first()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")

    db.add(DomainEvent(
        domain_id=domain.id,
        event_type=EventType.MANUAL_REFRESH,
        message="Manual WHOIS refresh triggered",
    ))
    db.commit()

    # Trigger immediate job run
    import asyncio
    asyncio.create_task(scheduler_service.check_domain_job(domain_id))

    flash(request, f"WHOIS refresh queued for {domain.name}.", "info")

    # Return HTMX-friendly redirect header
    from fastapi.responses import Response
    response = Response(status_code=204)
    response.headers["HX-Redirect"] = f"/domains/{domain_id}"
    return response
