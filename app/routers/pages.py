"""HTML page routes."""
import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.domain import Domain, DomainStatus
from ..models.event import DomainEvent
from ..models.settings import AppSetting
from ..templates_config import templates

logger = logging.getLogger(__name__)
router = APIRouter()


def get_flash(request: Request) -> list[dict]:
    """Extract and clear flash messages from session."""
    return request.session.pop("flash_messages", [])


def flash(request: Request, message: str, category: str = "info") -> None:
    if "flash_messages" not in request.session:
        request.session["flash_messages"] = []
    request.session["flash_messages"].append({"message": message, "category": category})


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    domains = db.query(Domain).order_by(Domain.expires_at.asc().nullslast()).all()

    now = datetime.now(timezone.utc)

    def days_diff(domain):
        if not domain.expires_at:
            return None
        dt = domain.expires_at
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (dt - now).days

    expiring_30 = sum(1 for d in domains if days_diff(d) is not None and 0 <= days_diff(d) <= 30)
    expiring_7 = sum(1 for d in domains if days_diff(d) is not None and 0 <= days_diff(d) <= 7)
    critical_count = sum(1 for d in domains if d.status in (
        DomainStatus.PENDING_DELETE, DomainStatus.AVAILABLE, DomainStatus.REDEMPTION
    ))

    return templates.TemplateResponse(
        request,
        "pages/dashboard.html",
        {
            "domains": domains,
            "total_domains": len(domains),
            "expiring_30": expiring_30,
            "expiring_7": expiring_7,
            "critical_count": critical_count,
            "flash_messages": get_flash(request),
            "now": now,
        },
    )


@router.get("/domains/add", response_class=HTMLResponse)
async def add_domain_page(request: Request):
    return templates.TemplateResponse(
        request,
        "pages/domain_add.html",
        {"flash_messages": get_flash(request)},
    )


@router.get("/domains/{domain_id}", response_class=HTMLResponse)
async def domain_detail(request: Request, domain_id: int, db: Session = Depends(get_db)):
    domain = db.query(Domain).filter(Domain.id == domain_id).first()
    if not domain:
        return templates.TemplateResponse(
            request,
            "pages/404.html",
            {"message": f"Domain #{domain_id} not found"},
            status_code=404,
        )

    events = (
        db.query(DomainEvent)
        .filter(DomainEvent.domain_id == domain_id)
        .order_by(DomainEvent.created_at.desc())
        .limit(100)
        .all()
    )

    from ..services.domain_lifecycle import get_snagging_registrar_links
    snagging_links = get_snagging_registrar_links(domain.name)

    show_snagging = domain.status in (
        DomainStatus.REDEMPTION, DomainStatus.PENDING_DELETE,
        DomainStatus.AVAILABLE, DomainStatus.EXPIRED,
        DomainStatus.EXPIRING_CRITICAL,
    )

    return templates.TemplateResponse(
        request,
        "pages/domain_detail.html",
        {
            "domain": domain,
            "events": events,
            "snagging_links": snagging_links,
            "show_snagging": show_snagging,
            "flash_messages": get_flash(request),
            "now": datetime.now(timezone.utc),
        },
    )


@router.get("/domains/{domain_id}/edit", response_class=HTMLResponse)
async def edit_domain_page(request: Request, domain_id: int, db: Session = Depends(get_db)):
    domain = db.query(Domain).filter(Domain.id == domain_id).first()
    if not domain:
        return templates.TemplateResponse(request, "pages/404.html", {}, status_code=404)

    return templates.TemplateResponse(
        request,
        "pages/domain_edit.html",
        {"domain": domain, "flash_messages": get_flash(request)},
    )


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, db: Session = Depends(get_db)):
    setting_keys = ["smtp_host", "smtp_port", "smtp_username", "smtp_password", "smtp_from", "smtp_tls"]
    db_settings = {s.key: s.value for s in db.query(AppSetting).filter(AppSetting.key.in_(setting_keys)).all()}

    return templates.TemplateResponse(
        request,
        "pages/settings.html",
        {"settings": db_settings, "flash_messages": get_flash(request)},
    )
