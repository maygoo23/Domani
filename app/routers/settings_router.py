"""Global settings routes."""
import logging
from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from ..database import get_db
from ..models.settings import AppSetting

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/settings")


def flash(request: Request, message: str, category: str = "info") -> None:
    if "flash_messages" not in request.session:
        request.session["flash_messages"] = []
    request.session["flash_messages"].append({"message": message, "category": category})


def upsert_setting(db: Session, key: str, value: str) -> None:
    setting = db.query(AppSetting).filter(AppSetting.key == key).first()
    if setting:
        setting.value = value
        setting.updated_at = datetime.now(timezone.utc)
    else:
        db.add(AppSetting(key=key, value=value))


@router.post("")
async def save_settings(
    request: Request,
    smtp_host: str = Form(""),
    smtp_port: int = Form(587),
    smtp_username: str = Form(""),
    smtp_password: str = Form(""),
    smtp_from: str = Form(""),
    smtp_tls: str = Form("false"),
    db: Session = Depends(get_db),
):
    upsert_setting(db, "smtp_host", smtp_host.strip())
    upsert_setting(db, "smtp_port", str(smtp_port))
    upsert_setting(db, "smtp_username", smtp_username.strip())
    # Only update password if provided (don't blank it with empty submit)
    if smtp_password.strip():
        upsert_setting(db, "smtp_password", smtp_password.strip())
    upsert_setting(db, "smtp_from", smtp_from.strip())
    upsert_setting(db, "smtp_tls", smtp_tls)
    db.commit()

    flash(request, "Settings saved.", "success")
    return RedirectResponse("/settings", status_code=303)


@router.post("/test-email")
async def test_email(
    request: Request,
    test_recipient: str = Form(...),
    db: Session = Depends(get_db),
):
    from ..services.alert_service import _get_smtp_settings
    import aiosmtplib
    from email.mime.text import MIMEText

    smtp = _get_smtp_settings(db)
    if not smtp["host"]:
        flash(request, "SMTP not configured. Please save your settings first.", "danger")
        return RedirectResponse("/settings", status_code=303)

    try:
        msg = MIMEText("This is a test email from your Domani instance. Your email alerts are configured correctly!", "plain")
        msg["Subject"] = "Domani — Test Email"
        msg["From"] = smtp["from_addr"]
        msg["To"] = test_recipient

        await aiosmtplib.send(
            msg,
            hostname=smtp["host"],
            port=smtp["port"],
            username=smtp["username"] or None,
            password=smtp["password"] or None,
            use_tls=False,
            start_tls=smtp["use_tls"],
        )
        flash(request, f"Test email sent successfully to {test_recipient}!", "success")
    except Exception as e:
        flash(request, f"Failed to send test email: {e}", "danger")

    return RedirectResponse("/settings", status_code=303)
