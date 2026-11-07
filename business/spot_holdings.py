"""Root-owned Binance spot snapshots; no trade or withdrawal operations."""
import hashlib
import json
import logging
import time
import uuid
from decimal import Decimal, InvalidOperation

from business.binance_exchange import BinanceExchangeRequestHandle
from cache import AllCache
from models.user import UserSymbolPlotTable
from settings.setting import cfgs
from utils.exception import StandardResponseExc

SPOT_MODEL = "binance_spot_price"
SNAPSHOT_KEY = "monitor:binance:spot:root"
SYMBOLS_KEY = "monitor:binance:spot:symbols"
MAX_AGE = 60
logger = logging.getLogger(__name__)


def account_fingerprint():
    config = cfgs.get("bian", {})
    return hashlib.sha256((config.get("key", "") + ":" + config.get("secret", "")).encode()).hexdigest()


def missing_credentials():
    config = cfgs.get("bian", {})
    return [env for key, env in (("key", "AMFSAN_BINANCE_KEY"),
                                ("secret", "AMFSAN_BINANCE_SECRET"))
            if not config.get(key)]


def read_snapshot():
    missing = missing_credentials()
    if missing:
        return {"status": "unconfigured", "missing_credentials": missing,
                "updated_ts": 0, "balances": {}, "symbols": {}}
    raw = AllCache.get_client().get(SNAPSHOT_KEY)
    snapshot = json.loads(raw) if raw else {}
    if not snapshot or snapshot.get("account") != account_fingerprint():
        return {"status": "config_mismatch" if snapshot else "pending",
                "updated_ts": 0, "balances": {}, "symbols": {}}
    if snapshot.get("status") == "ok" and not 0 <= time.time() - snapshot.get("updated_ts", 0) <= MAX_AGE:
        snapshot["status"] = "stale"
    return snapshot


def min_holding_usdt():
    return Decimal(cfgs.get("bian", {}).get("min_holding_usdt", "10"))


def usdt_prices(symbols, tickers):
    """Only use the direct price of a supported USDT-quoted spot pair."""
    if not isinstance(tickers, list):
        raise ValueError("Invalid ticker response")
    prices = {}
    for item in tickers:
        try:
            symbol = item["symbol"].lower()
            if symbols.get(symbol, {}).get("quote_asset") != "USDT":
                continue
            price = Decimal(item["price"])
            if price.is_finite() and price > 0:
                prices[symbol] = str(price)
        except (KeyError, TypeError, InvalidOperation):
            continue
    return prices


def position(snapshot, symbol):
    if snapshot.get("status") != "ok":
        return None
    pair = snapshot.get("symbols", {}).get(symbol)
    if not pair or pair.get("quote_asset") != "USDT":
        return None
    amounts = snapshot["balances"].get(pair["base_asset"], {"free": "0", "locked": "0"})
    total = Decimal(amounts["free"]) + Decimal(amounts["locked"])
    rate = snapshot.get("usdt_prices", {}).get(symbol)
    fresh_price = 0 <= time.time() - snapshot.get("valuation_ts", 0) <= MAX_AGE
    value = total * Decimal(rate) if rate is not None and fresh_price else None
    eligible = total > 0 and value is not None and value >= min_holding_usdt()
    return {**pair, **amounts, "total": str(total),
            "value_usdt": str(value) if value is not None else None,
            "eligible": eligible,
            "valuation_status": "unavailable" if value is None else "eligible" if eligible else "below_minimum"}


def require_position(user_id, symbol):
    if user_id != "root":
        raise StandardResponseExc(msg="币安现货卖出监控仅限 root 使用")
    snapshot = read_snapshot()
    if snapshot.get("status") != "ok":
        raise StandardResponseExc(msg="现货持仓同步失败或已过期，请检查服务端只读密钥并刷新持仓")
    holding = position(snapshot, symbol)
    if holding is None:
        raise StandardResponseExc(msg="请选择支持交易的币安 USDT 现货交易对")
    if Decimal(holding["total"]) <= 0:
        raise StandardResponseExc(msg="该交易对的基础币种没有现货持仓")
    if holding["value_usdt"] is None:
        raise StandardResponseExc(msg="无法获取新鲜的 USDT 估值，请稍后刷新持仓")
    if not holding["eligible"]:
        raise StandardResponseExc(msg=f"持仓估值低于 {min_holding_usdt()} USDT 监控门槛")
    return holding


def parse_balances(data):
    if not isinstance(data, dict) or data.get("accountType") != "SPOT" or not isinstance(data.get("balances"), list):
        raise ValueError("Invalid spot account")
    balances = {}
    for item in data["balances"]:
        asset = item["asset"]
        free, locked = Decimal(item["free"]), Decimal(item["locked"])
        if not asset or asset in balances or not all(v.is_finite() and v >= 0 for v in (free, locked)):
            raise ValueError("Invalid balance")
        balances[asset] = {"free": str(free), "locked": str(locked)}
    return balances


async def pause_closed_monitors(snapshot):
    from business.monitor import monitor_lock
    rows = await UserSymbolPlotTable.select().where(
        UserSymbolPlotTable.user_id == "root", UserSymbolPlotTable.is_valid == True,
        UserSymbolPlotTable.monitor_direction == "sell",
        UserSymbolPlotTable.strategy_model_key == SPOT_MODEL,
    ).aio_execute()
    for original in rows:
        pair = snapshot["symbols"].get(original.symbol)
        if not pair or pair.get("quote_asset") != "USDT":
            continue  # Unsupported/delisted pair is not evidence of zero balance.
        balance = snapshot["balances"].get(pair["base_asset"], {"free": "0", "locked": "0"})
        if Decimal(balance["free"]) + Decimal(balance["locked"]) != 0:
            continue
        async with monitor_lock(f"lock_monitor:{original.id}"):
            changed = await UserSymbolPlotTable.update(
                is_valid=False, config_version=uuid.uuid4().hex,
            ).where(UserSymbolPlotTable.id == original.id,
                    UserSymbolPlotTable.config_version == original.config_version,
                    UserSymbolPlotTable.is_valid == True).aio_execute()
            if changed:
                AllCache.get_client().delete("symbol:cfg")


async def sync_spot_holdings():
    # An old/unconfigured worker must not overwrite another worker's valid snapshot.
    if missing_credentials():
        return read_snapshot()
    from business.monitor import monitor_lock
    async with monitor_lock("lock_monitor_spot_sync:root"):
        previous = read_snapshot()
        if time.time() - previous.get("attempt_ts", 0) < 25:
            return previous
        config = cfgs.get("bian", {})
        snapshot = {**previous, "account": account_fingerprint(), "attempt_ts": int(time.time())}
        try:
            if not config.get("key") or not config.get("secret"):
                raise ValueError("Missing credentials")
            client = BinanceExchangeRequestHandle(config["key"], config["secret"])
            cached = AllCache.get_client().get(SYMBOLS_KEY)
            if cached:
                symbols = json.loads(cached)
            else:
                data = await client.get_spot_symbols_async()
                symbols = {item["symbol"].lower(): {
                    "base_asset": item["baseAsset"], "quote_asset": item["quoteAsset"],
                } for item in data["symbols"] if item["status"] == "TRADING"
                    and item.get("isSpotTradingAllowed") is True and item["quoteAsset"] == "USDT"
                    and len(item["symbol"]) <= 10 and item["symbol"].isascii() and item["symbol"].isalnum()}
                if not symbols:
                    raise ValueError("Missing spot symbols")
                AllCache.get_client().set(SYMBOLS_KEY, json.dumps(symbols), ex=3600)
            # Filter old cached exchange metadata as well as fresh responses.
            symbols = {symbol: pair for symbol, pair in symbols.items() if pair.get("quote_asset") == "USDT"}
            balances = parse_balances(await client.get_spot_account_async())
            snapshot.update(status="ok", updated_ts=int(time.time()), balances=balances, symbols=symbols,
                            usdt_prices={}, valuation_ts=0)
            snapshot.pop("usdt_rates", None)
            try:
                snapshot["usdt_prices"] = usdt_prices(symbols, await client.get_spot_prices_async())
                snapshot["valuation_ts"] = int(time.time())
            except Exception:
                # Balance success still permits confirmed closure; never reuse old prices.
                logger.warning("Binance spot valuation failed; sell evaluation suspended")
            # Persist closure before making the new snapshot available to API edits.
            await pause_closed_monitors(snapshot)
        except Exception:
            logger.warning("Binance spot sync failed; sell evaluation suspended")
            snapshot["status"] = "error" if config.get("key") and config.get("secret") else "unconfigured"
        AllCache.get_client().set(SNAPSHOT_KEY, json.dumps(snapshot))
        return snapshot


def public_snapshot(snapshot=None):
    snapshot = dict(read_snapshot() if snapshot is None else snapshot)
    if snapshot.get("status") == "ok" and not 0 <= time.time() - snapshot.get("updated_ts", 0) <= MAX_AGE:
        snapshot["status"] = "stale"
    holdings = []
    if snapshot.get("status") == "ok":
        for symbol in sorted(snapshot.get("symbols", {})):
            holding = position(snapshot, symbol)
            if holding is not None and Decimal(holding["total"]) > 0:
                holdings.append({"symbol": symbol, **holding})
    return {"status": snapshot.get("status", "pending"),
            "missing_credentials": snapshot.get("missing_credentials", []),
            "min_holding_usdt": str(min_holding_usdt()),
            "updated_ts": snapshot.get("updated_ts", 0), "holdings": holdings}
