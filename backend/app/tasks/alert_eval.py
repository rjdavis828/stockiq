import asyncio
import logging
from datetime import datetime, timezone

from celery_worker import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="tasks.alert_eval.evaluate_alerts_for_bar")
def evaluate_alerts_for_bar(symbol: str, bar: dict) -> None:
    asyncio.run(_evaluate(symbol, bar))


async def _evaluate(symbol: str, bar: dict) -> None:
    import pandas as pd
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from app.config import settings
    from app.db.models import Alert, AlertEvent, OHLCVIntraday, Ticker
    from app.scanner.engine import ScannerEngine

    engine = create_async_engine(settings.database_url, echo=False)
    db_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with db_factory() as session:
            ticker_result = await session.execute(
                select(Ticker.id).where(Ticker.symbol == symbol)
            )
            ticker_id = ticker_result.scalar_one_or_none()
            if ticker_id is None:
                return

            alerts_result = await session.execute(
                select(Alert).where(Alert.ticker_id == ticker_id, Alert.status == "active")
            )
            alerts = alerts_result.scalars().all()
            if not alerts:
                return

            prev_result = await session.execute(
                select(OHLCVIntraday)
                .where(OHLCVIntraday.ticker_id == ticker_id, OHLCVIntraday.timeframe == "1m")
                .order_by(OHLCVIntraday.ts.desc())
                .limit(2)
            )
            prev_rows = prev_result.scalars().all()

            rows = []
            for r in reversed(prev_rows):
                rows.append({
                    "open": float(r.open),
                    "high": float(r.high),
                    "low": float(r.low),
                    "close": float(r.close),
                    "volume": r.volume,
                })

            if not rows:
                rows = [{
                    "open": bar["open"], "high": bar["high"], "low": bar["low"],
                    "close": bar["close"], "volume": bar["volume"],
                }]

            df = pd.DataFrame(rows)
            scanner = ScannerEngine.__new__(ScannerEngine)

            now = datetime.now(timezone.utc)
            for alert in alerts:
                try:
                    triggered = scanner.evaluate_condition_on_bar(df, alert.condition)
                except Exception:
                    logger.exception("Condition eval failed for alert %d", alert.id)
                    continue

                if not triggered:
                    continue

                event = AlertEvent(
                    alert_id=alert.id,
                    triggered_at=now,
                    bar_snapshot=bar,
                    notified_ws=False,
                    notified_email=False,
                )
                session.add(event)
                alert.status = "triggered"
                alert.notified_at = now
                await session.flush()

                try:
                    from app.ws.manager import manager
                    await manager.broadcast_user(
                        alert.user_id,
                        {
                            "type": "alert",
                            "alert_id": alert.id,
                            "symbol": symbol,
                            "triggered_at": now.isoformat(),
                            "condition": alert.condition,
                            "bar": bar,
                        },
                    )
                    event.notified_ws = True
                except Exception:
                    logger.exception("WS dispatch failed for alert %d", alert.id)

                try:
                    from app.tasks.email import send_alert_email
                    send_alert_email.delay(alert.id, event.id)
                except Exception:
                    logger.exception("Email queue failed for alert %d", alert.id)

            await session.commit()
    finally:
        await engine.dispose()
