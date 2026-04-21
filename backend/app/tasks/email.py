import asyncio
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from celery_worker import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="tasks.email.send_alert_email", bind=True, max_retries=3, default_retry_delay=60)
def send_alert_email(self, alert_id: int, event_id: int) -> None:
    asyncio.run(_send(self, alert_id, event_id))


async def _send(task, alert_id: int, event_id: int) -> None:
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from app.config import settings
    from app.db.models import Alert, AlertEvent, Ticker, User

    engine = create_async_engine(settings.database_url, echo=False)
    db_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with db_factory() as session:
            event_result = await session.execute(
                select(AlertEvent).where(AlertEvent.id == event_id)
            )
            event = event_result.scalar_one_or_none()
            if event is None:
                return

            alert_result = await session.execute(
                select(Alert).where(Alert.id == alert_id)
            )
            alert = alert_result.scalar_one_or_none()
            if alert is None:
                return

            user_result = await session.execute(
                select(User).where(User.id == alert.user_id)
            )
            user = user_result.scalar_one_or_none()
            if user is None or not user.email:
                return

            bar = event.bar_snapshot or {}
            symbol = bar.get("symbol", "Unknown")
            cond = alert.condition or {}
            indicator = cond.get("indicator", "")
            operator = cond.get("operator", "")
            value = cond.get("value", "")
            condition_summary = f"{indicator} {operator} {value}".strip()

            subject = f"[Stock Alert] {symbol} — {condition_summary}"
            body = (
                f"Your alert for {symbol} triggered at {event.triggered_at.isoformat()}.\n\n"
                f"Condition: {condition_summary}\n"
                f"Bar: O={bar.get('open')} H={bar.get('high')} "
                f"L={bar.get('low')} C={bar.get('close')} V={bar.get('volume')}\n"
            )

            _smtp_send(settings, user.email, subject, body)

            event.notified_email = True
            await session.commit()
    except Exception as exc:
        logger.exception("send_alert_email failed for alert=%d event=%d", alert_id, event_id)
        raise task.retry(exc=exc)
    finally:
        await engine.dispose()


def _smtp_send(settings, to_email: str, subject: str, body: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = to_email
    msg.attach(MIMEText(body, "plain"))

    if settings.smtp_tls:
        server = smtplib.SMTP(settings.smtp_host, settings.smtp_port)
        server.starttls()
    else:
        server = smtplib.SMTP(settings.smtp_host, settings.smtp_port)

    if settings.smtp_user:
        server.login(settings.smtp_user, settings.smtp_password)

    server.sendmail(settings.smtp_from, [to_email], msg.as_string())
    server.quit()
