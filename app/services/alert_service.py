"""Alert dispatch service — email and webhook delivery."""
import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from typing import Optional

import aiosmtplib
import httpx
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from sqlalchemy.orm import Session

from ..models.alert import AlertConfig
from ..models.domain import Domain
from ..models.event import DomainEvent, EventType

logger = logging.getLogger(__name__)


def _get_smtp_settings(db: Session) -> dict:
    """Load SMTP settings from database or environment."""
    from ..models.settings import AppSetting
    from ..config import settings as app_settings

    keys = ["smtp_host", "smtp_port", "smtp_username", "smtp_password", "smtp_from", "smtp_tls"]
    db_settings = {s.key: s.value for s in db.query(AppSetting).filter(AppSetting.key.in_(keys)).all()}

    return {
        "host": db_settings.get("smtp_host") or app_settings.smtp_host,
        "port": int(db_settings.get("smtp_port") or app_settings.smtp_port),
        "username": db_settings.get("smtp_username") or app_settings.smtp_username,
        "password": db_settings.get("smtp_password") or app_settings.smtp_password,
        "from_addr": db_settings.get("smtp_from") or app_settings.smtp_from,
        "use_tls": (db_settings.get("smtp_tls") or str(app_settings.smtp_tls)).lower() in ("true", "1", "yes"),
    }


def _build_alert_message(domain: Domain, old_status: Optional[str], new_status: str) -> dict:
    """Build alert context dict."""
    days = domain.days_until_expiry
    expires_str = domain.expires_at.strftime("%Y-%m-%d %H:%M UTC") if domain.expires_at else "Unknown"

    if new_status == "available":
        subject = f"🚨 DOMAIN AVAILABLE: {domain.name} is ready to register!"
        body_text = (
            f"Great news! The domain {domain.name} appears to be AVAILABLE for registration.\n\n"
            f"Act fast — popular domains can be claimed within minutes of dropping.\n\n"
            f"Check your favorite registrar: https://www.namecheap.com/domains/registration/results/?domain={domain.name}"
        )
    elif new_status == "pending_delete":
        subject = f"⚠️  PENDING DELETE: {domain.name} dropping soon!"
        body_text = (
            f"The domain {domain.name} has entered the Pending Delete phase.\n\n"
            f"It will be released for registration in approximately 1-5 days.\n"
            f"Now is the time to set up a backorder at your registrar!\n\n"
            f"Expires: {expires_str}"
        )
    elif new_status in ("expiring_soon", "expiring_critical"):
        urgency = "CRITICAL" if new_status == "expiring_critical" else "SOON"
        subject = f"⏰ EXPIRING {urgency}: {domain.name} — {days} days left"
        body_text = (
            f"The domain {domain.name} is expiring {'very ' if days and days <= 7 else ''}soon.\n\n"
            f"Days remaining: {days if days is not None else 'Unknown'}\n"
            f"Expiry date: {expires_str}\n"
            f"Registrar: {domain.registrar or 'Unknown'}\n\n"
            f"{'Renew immediately!' if domain.watch_type == 'own' else 'Get ready to snag it!'}"
        )
    else:
        subject = f"📡 Domain Status Update: {domain.name} → {new_status.replace('_', ' ').title()}"
        body_text = (
            f"Status change detected for {domain.name}.\n\n"
            f"Previous status: {old_status or 'Unknown'}\n"
            f"New status: {new_status}\n"
            f"Expiry date: {expires_str}"
        )

    return {
        "subject": subject,
        "body_text": body_text,
        "domain": domain.name,
        "old_status": old_status,
        "new_status": new_status,
        "expires_at": domain.expires_at.isoformat() if domain.expires_at else None,
        "days_until_expiry": days,
        "registrar": domain.registrar,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


async def send_email_alert(config: AlertConfig, domain: Domain, context: dict, smtp: dict) -> bool:
    """Send email alert via SMTP."""
    if not smtp["host"] or not smtp["from_addr"] or not config.target:
        logger.warning("SMTP not configured, skipping email alert")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = context["subject"]
        msg["From"] = smtp["from_addr"]
        msg["To"] = config.target

        msg.attach(MIMEText(context["body_text"], "plain"))

        await aiosmtplib.send(
            msg,
            hostname=smtp["host"],
            port=smtp["port"],
            username=smtp["username"] or None,
            password=smtp["password"] or None,
            use_tls=False,
            start_tls=smtp["use_tls"],
        )
        logger.info("Email alert sent for %s to %s", domain.name, config.target)
        return True

    except Exception as e:
        logger.error("Failed to send email alert for %s: %s", domain.name, e)
        return False


async def send_webhook_alert(config: AlertConfig, domain: Domain, context: dict) -> bool:
    """Send webhook POST with HMAC signature."""
    if not config.target:
        return False

    payload = json.dumps(context, default=str)

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Domani/0.1",
        "X-Domani-Event": context.get("new_status", "unknown"),
    }

    if config.webhook_secret:
        sig = hmac.new(
            config.webhook_secret.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()
        headers["X-Domani-Signature"] = f"sha256={sig}"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(config.target, content=payload, headers=headers)
            success = response.is_success
            logger.info("Webhook %s for %s: HTTP %s", config.target, domain.name, response.status_code)
            return success

    except Exception as e:
        logger.error("Webhook failed for %s: %s", domain.name, e)
        return False


async def dispatch_alerts(
    domain: Domain,
    old_status: Optional[str],
    new_status: str,
    db: Session,
) -> None:
    """Find matching alert configs and dispatch notifications."""
    context = _build_alert_message(domain, old_status, new_status)
    smtp = _get_smtp_settings(db)

    for config in domain.alert_configs:
        if not config.enabled:
            continue
        if new_status not in config.event_type_list:
            continue

        success = False
        if config.method == "email":
            success = await send_email_alert(config, domain, context, smtp)
        elif config.method == "webhook":
            success = await send_webhook_alert(config, domain, context)

        # Log the attempt
        event = DomainEvent(
            domain_id=domain.id,
            event_type=EventType.ALERT_SENT if success else EventType.ALERT_FAILED,
            new_status=new_status,
            message=f"{'Sent' if success else 'Failed'} {config.method} alert to {config.target}: {context['subject']}",
            success=success,
        )
        db.add(event)

        if success:
            config.last_triggered_at = datetime.now(timezone.utc)

    db.commit()
