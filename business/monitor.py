"""Direction-specific monitor notifications, independent of simulated trades."""
import asyncio
from contextlib import asynccontextmanager
import hashlib
import logging
import time
from decimal import Decimal
from html import escape

from business.binance_exchange import BinanceExchangeRequestHandle
from cache import AllCache
from models.user import EmailMsgHistoryTable, UserSymbolPlotTable, UserInfoTable
from settings.setting import cfgs
from models.strategy_rules import MONITOR_MODELS, monitor_rule

logger = logging.getLogger(__name__)
REASONS = {
    "model_top_rise": "布林贴顶上涨模型",
    "model_daily_ema_hourly_macd": "日线 EMA 多头与小时 MACD 金叉",
    "take_profit": "触及止盈价",
    "stop_loss": "触及止损价",
}


@asynccontextmanager
async def monitor_lock(name):
    # Never block this event loop while another coroutine holding the lock awaits the DB.
    lock = AllCache.get_client().lock(name, timeout=120)
    deadline = time.monotonic() + 5
    while not lock.acquire(blocking=False):
        if time.monotonic() >= deadline:
            from utils.exception import StandardResponseExc
            raise StandardResponseExc(msg="监控正在处理，请稍后重试")
        await asyncio.sleep(0.05)
    try:
        yield
    finally:
        lock.release()


async def enqueue_monitor_notice(row, reason, price, candle_ts):
    from msgqueue.queue import push_msg
    key = f"monitor:{row.id}:{row.user_id}:{row.symbol}:{row.monitor_direction}:{row.config_version}:{reason}:{candle_ts}"
    digest = hashlib.md5(key.encode()).hexdigest()
    if await EmailMsgHistoryTable.select().where(EmailMsgHistoryTable.msg_md5 == digest).aio_exists():
        return
    await push_msg({
        "bp": "send_email_task", "monitor_id": row.id,
        "config_version": row.config_version, "direction": row.monitor_direction,
        "reason": reason, "price": str(price), "candle_ts": candle_ts,
        "created_ts": int(time.time()), "notice_digest": digest,
    }, strict=True)


async def check_monitor_prices():
    rows = list(await UserSymbolPlotTable.select().where(
        UserSymbolPlotTable.is_valid == True,
        UserSymbolPlotTable.monitor_direction == "sell",
        UserSymbolPlotTable.strategy_model_key.in_(
            [key for key in MONITOR_MODELS if monitor_rule(key, "sell") is not None]),
        (UserSymbolPlotTable.take_profit_price.is_null(False)
         | UserSymbolPlotTable.stop_loss_price.is_null(False)),
    ).aio_execute())
    if not rows:
        return
    # Fetch a fresh shared snapshot; old cached prices must not trigger a new alert.
    result = await BinanceExchangeRequestHandle().get_current_price_async(
        symbol_list=sorted({row.symbol for row in rows}))
    if not isinstance(result, list):
        logger.warning("monitor price lookup failed")
        return
    prices = {item["symbol"].lower(): Decimal(item["price"]) for item in result}
    candle_ts = int(time.time()) // 3600 * 3600
    for row in rows:
        price = prices.get(row.symbol)
        if price is None or not price.is_finite() or price <= 0:
            continue
        reason = None
        if row.take_profit_price is not None and price >= row.take_profit_price:
            reason = "take_profit"
        elif row.stop_loss_price is not None and price <= row.stop_loss_price:
            reason = "stop_loss"
        if reason:
            await enqueue_monitor_notice(row, reason, price, candle_ts)


async def deliver_monitor_notice(value):
    from business.mail_serve import send_email
    now = int(time.time())
    if now - value["created_ts"] > 180 or value["candle_ts"] != now // 3600 * 3600:
        return
    monitor_id = value["monitor_id"]
    # API updates/deletions use this same lock. A paused/deleted/edited queued notice is discarded.
    async with monitor_lock(f"lock_monitor:{monitor_id}"):
        try:
            row = await UserSymbolPlotTable.select().where(
                UserSymbolPlotTable.id == monitor_id,
                UserSymbolPlotTable.is_valid == True,
                UserSymbolPlotTable.config_version == value["config_version"],
                UserSymbolPlotTable.monitor_direction == value["direction"],
            ).aio_get()
        except UserSymbolPlotTable.DoesNotExist:
            return
        digest = value["notice_digest"]
        if await EmailMsgHistoryTable.select().where(EmailMsgHistoryTable.msg_md5 == digest).aio_exists():
            return
        if row.user_id == "root":
            recipient = cfgs["administrator_email"]
        else:
            try:
                user = await UserInfoTable.select().where(UserInfoTable.uuid == row.user_id).aio_get()
                recipient = user.email
            except UserInfoTable.DoesNotExist:
                logger.warning("monitor recipient missing, monitor_id:%s", row.id)
                return
        if not recipient:
            logger.warning("monitor recipient empty, monitor_id:%s", row.id)
            return
        direction = "买入机会" if row.monitor_direction == "buy" else "卖出机会"
        if monitor_rule(row.strategy_model_key, row.monitor_direction) is None:
            return
        if value["reason"] == row.strategy_model_key:
            reason = MONITOR_MODELS[row.strategy_model_key]["name"]
        elif row.monitor_direction == "sell" and value["reason"] in ("take_profit", "stop_loss"):
            reason = REASONS[value["reason"]]
        else:
            return
        content = (f"<p>{escape(row.symbol.upper())}：{direction}</p>"
                   f"<p>触发原因：{reason}；当前价格：{escape(value['price'])}</p>"
                   "<p>提醒后继续按当前方向监控。可在监控列表切换方向、暂停或移除。</p>")
        if send_email(recipient, f"{row.symbol.upper()} {direction}提醒", content):
            await EmailMsgHistoryTable.aio_create(msg_md5=digest, msg_content=content)
            row.last_signal_ts = int(time.time())
            row.last_signal_reason = value["reason"]
            await row.aio_save()
