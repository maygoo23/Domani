"""Alert configuration routes."""
import logging
from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.alert import AlertConfig
from ..models.domain import Domain

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/domains")


def flash(request: Request, message: str, category: str = "info") -> None:
    if "flash_messages" not in request.session:
        request.session["flash_messages"] = []
    request.session["flash_messages"].append({"message": message, "category": category})


@router.post("/{domain_id}/alerts")
async def add_alert(
    request: Request,
    domain_id: int,
    method: str = Form(...),
    target: str = Form(...),
    event_types: list[str] = Form(default=[]),
    webhook_secret: str = Form(""),
    db: Session = Depends(get_db),
):
    domain = db.query(Domain).filter(Domain.id == domain_id).first()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")

    if not event_types:
        flash(request, "Please select at least one event type to alert on.", "danger")
        return RedirectResponse(f"/domains/{domain_id}", status_code=303)

    config = AlertConfig(
        domain_id=domain_id,
        method=method,
        target=target.strip(),
        event_types=",".join(event_types),
        webhook_secret=webhook_secret.strip() or None,
    )
    db.add(config)
    db.commit()

    flash(request, f"Alert added: {method} to {target}", "success")
    return RedirectResponse(f"/domains/{domain_id}", status_code=303)


@router.post("/{domain_id}/alerts/{alert_id}/delete")
async def delete_alert(request: Request, domain_id: int, alert_id: int, db: Session = Depends(get_db)):
    alert = db.query(AlertConfig).filter(
        AlertConfig.id == alert_id,
        AlertConfig.domain_id == domain_id,
    ).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    db.delete(alert)
    db.commit()

    flash(request, "Alert removed.", "info")
    return RedirectResponse(f"/domains/{domain_id}", status_code=303)


@router.post("/{domain_id}/alerts/{alert_id}/toggle")
async def toggle_alert(request: Request, domain_id: int, alert_id: int, db: Session = Depends(get_db)):
    alert = db.query(AlertConfig).filter(
        AlertConfig.id == alert_id,
        AlertConfig.domain_id == domain_id,
    ).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.enabled = not alert.enabled
    db.commit()

    status_word = "enabled" if alert.enabled else "disabled"
    flash(request, f"Alert {status_word}.", "info")
    return RedirectResponse(f"/domains/{domain_id}", status_code=303)


@router.post("/{domain_id}/alerts/{alert_id}/test")
async def test_alert(request: Request, domain_id: int, alert_id: int, db: Session = Depends(get_db)):
    """Send a test alert."""
    from ..services.alert_service import send_email_alert, send_webhook_alert, _get_smtp_settings, _build_alert_message

    domain = db.query(Domain).filter(Domain.id == domain_id).first()
    alert = db.query(AlertConfig).filter(
        AlertConfig.id == alert_id,
        AlertConfig.domain_id == domain_id,
    ).first()

    if not domain or not alert:
        raise HTTPException(status_code=404)

    context = _build_alert_message(domain, domain.status, domain.status)
    context["subject"] = f"[TEST] {context['subject']}"

    success = False
    if alert.method == "email":
        smtp = _get_smtp_settings(db)
        success = await send_email_alert(alert, domain, context, smtp)
    elif alert.method == "webhook":
        success = await send_webhook_alert(alert, domain, context)

    msg = "Test alert sent successfully!" if success else "Test alert failed — check your configuration."
    flash(request, msg, "success" if success else "danger")
    return RedirectResponse(f"/domains/{domain_id}", status_code=303)
