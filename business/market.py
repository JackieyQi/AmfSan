#! /usr/bin/env python
# coding:utf8

import time
import json
import re
import uuid
from decimal import Decimal

from cache.order import (LimitPriceNoticeValueCache,
                         LimitPriceNoticeValveCache, MarketPriceLimitCache, SymbolPriceChangeHistoryTableCache,
                         MarketPriceCache)
from cache.plot import CheckMacdCrossGateCache, CheckMacdTrendGateCache,\
    CheckKdjCrossGateCache, CheckKdjCvGateCache
from models.market import KlineTable, MacdTable, KdjTable, EmaTable, RsiTable, BollTable, BnSymbolTable
from models.order import SymbolPriceChangeHistoryTable
from models.user import UserSymbolPlotTable
from settings.constants import *
from utils.common import str2decimal, to_ctime, decimal2str, Decimal
from utils.exception import StandardResponseExc
from utils.hrequest import http_get_request
from business.binance_exchange import BinanceExchangeRequestHandle
from exts import async_database
from business.monitor import monitor_lock
from models.strategy_rules import TOP_RISE
from cache import AllCache


class MarketPriceHandler(object):
    def update_current_price(self, symbol: str = "btcusdt"):
        resp_json = BinanceExchangeRequestHandle().get_current_price(symbol)
        if resp_json:
            price_info = resp_json[0]
            ts = int(int(price_info["T"]) / 1000)
            price_str = price_info["p"]

            MarketPriceCache.hset(symbol.lower(), price_str)
            return {
                "price": price_str,
                "ts": price_info["T"],
                "dt": to_ctime(ts),
            }
        return {}
        
    def get_current_price(self, symbol: str = ""):
        if not symbol:
            cache_data = MarketPriceCache.hgetall()
            for k, v in cache_data.items():
                cache_data[k] = str2decimal(v)
            return cache_data
        else:
            cache_price = MarketPriceCache.hget(symbol.lower())
            if cache_price:
                return {
                    symbol.lower(): str2decimal(cache_price),
                }
            return {}

    def get_current_price_from_HUOBI(self, symbol: str = "btcusdt"):
        resp_json = http_get_request(HUOBI_TRADE_URL, {"symbol": symbol})
        if resp_json and resp_json["status"] == "ok":
            price_info = resp_json["tick"]["data"][0]
            ts = int(int(price_info["ts"]) / 1000)
            price_str = decimal2str(Decimal(price_info["price"]))

            MarketPriceCache.hset(symbol.lower(), price_str)
            return {
                "price": price_str,
                "ts": price_info["ts"],
                "dt": to_ctime(ts),
            }
        return {}

    def get_current_price_by_cache(self, symbol=""):
        if not symbol:
            result = MarketPriceCache.hgetall()
        else:
            result = MarketPriceCache.hget(symbol.lower())
        return result

    def set_value_times4limit_price_notice(self, count: int = 1):
        val = LimitPriceNoticeValueCache.get()
        val = 0 if not val else int(val)
        return LimitPriceNoticeValueCache.set(val + count, 15 * 60)

    def get_value_times4limit_price_notice(self):
        val = LimitPriceNoticeValueCache.get()
        return 0 if not val else int(val)

    def set_auto_valve_times4limit_price_notice(
        self, symbol: str = "btcusdt", limit: int = 5
    ):
        return LimitPriceNoticeValveCache.set(limit, 1 * 24 * 60 * 60)

    def get_auto_valve_times4limit_price_notice(self, symbol: str = "btcusdt"):
        notice_times = LimitPriceNoticeValveCache.get()
        if not notice_times:
            return 5
        else:
            return int(notice_times)

    def del_limit_price(self, symbol: str = ""):
        if not symbol:
            return
        return MarketPriceLimitCache.hdel(symbol)

    def set_limit_price(
        self,
        symbol: str = "btcusdt",
        low_price: Decimal = None,
        high_price: Decimal = None,
        new_set_time: int = 0,
    ):
        self.update_current_price(symbol)
        current_price = self.get_current_price(symbol).get(symbol)
        if not current_price:
            raise StandardResponseExc(
                msg="Current price not available for {}".format(symbol)
            )

        if low_price and current_price < low_price:
            raise StandardResponseExc(
                msg="Current price:{} lower low_price".format(current_price)
            )
        if high_price and current_price > high_price:
            raise StandardResponseExc(
                msg="Current price:{} higher high_price".format(current_price)
            )

        limit_price = MarketPriceLimitCache.hget(symbol)
        if not limit_price:
            set_time, limit_low_price, limit_high_price = 0, "", ""
        else:
            set_time, limit_low_price, limit_high_price = limit_price.split(":")

        result = MarketPriceLimitCache.hset(
            symbol,
            "{}:{}:{}".format(
                int(set_time) or new_set_time, low_price or limit_low_price, high_price or limit_high_price
            ),
        )

        # SymbolPriceChangeHistoryTableCache.rpush(
        #     f"{symbol}:"
        #     f"{str(current_price)}:"
        #     f"{str(limit_low_price or Decimal('0'))}:"
        #     f"{str(low_price or Decimal('0'))}:"
        #     f"{str(limit_high_price or Decimal('0'))}:"
        #     f"{str(high_price or Decimal('0'))}:"
        #     f"{int(time.time())}"
        # )
        return result

    def save_limit_price_change_history_to_db(
            self, symbol, current_price, limit_low_price, low_price, limit_high_price, high_price):
        # TODO: 数据更改了才记录
        pass
        # SymbolPriceChangeHistoryTable(
        #     symbol=symbol,
        #     current_price=current_price,
        #     limit_low_price=limit_low_price or Decimal("0"),
        #     low_price=low_price or Decimal("0"),
        #     limit_high_price=limit_high_price or Decimal("0"),
        #     high_price=high_price or Decimal("0"),
        # ).save()

    def get_limit_price(self, symbol: str = "btcusdt"):
        current_price = self.get_current_price(symbol).get(symbol)
        limit_price = MarketPriceLimitCache.hget(symbol)
        if not limit_price:
            set_time, limit_low_price, limit_high_price = 0, "", ""
        else:
            set_time, limit_low_price, limit_high_price = limit_price.split(":")
        return {
            "symbol": symbol,
            "current_price": current_price,
            "limit_low_price": limit_low_price,
            "limit_high_price": limit_high_price,
            "set_time": to_ctime(int(set_time)),
        }

    def get_all_limit_price(self):
        all_limit_price = MarketPriceLimitCache.hgetall()
        if not all_limit_price:
            return {}

        result = {}
        for k, v in all_limit_price.items():
            set_time, limit_low_price, limit_high_price = v.split(":")

            limit_low_price = Decimal(limit_low_price) if limit_low_price else Decimal("0")
            limit_high_price = Decimal(limit_high_price) if limit_high_price else Decimal("0")
            result[k] = (set_time, limit_low_price, limit_high_price)
        return result


class SymbolHandle(object):
    def __init__(self, symbol="", user_id=""):
        self.user_id = user_id
        self.symbol = symbol

    @staticmethod
    def serialize(row):
        return {
            "id": row.id, "user_id": row.user_id, "symbol": row.symbol,
            "is_valid": row.is_valid, "create_ts": row.create_ts,
            "monitor_direction": row.monitor_direction,
            # Direction monitors currently execute ModelTopRise for every symbol.
            "strategy_model": {"key": TOP_RISE["key"], "name": TOP_RISE["name"],
                               "version": TOP_RISE["version"]},
            "take_profit_price": str(row.take_profit_price) if row.take_profit_price is not None else None,
            "stop_loss_price": str(row.stop_loss_price) if row.stop_loss_price is not None else None,
            "last_signal_ts": row.last_signal_ts,
            "last_signal_reason": row.last_signal_reason,
        }

    async def get_all(self):
        query = UserSymbolPlotTable.select()
        if self.user_id != "root":
            query = query.where(UserSymbolPlotTable.user_id == self.user_id)
        rows = await query.order_by(UserSymbolPlotTable.create_ts, UserSymbolPlotTable.id).aio_execute()
        return [self.serialize(row) for row in rows]

    def refresh_symbol_cache(self):
        AllCache.get_client().delete("symbol:cfg")

    def del_plot(self):
        self.del_macd_gate()
        self.del_kdj_gate()

    async def get_owned_monitor(self, monitor_id):
        query = UserSymbolPlotTable.select().where(UserSymbolPlotTable.id == monitor_id)
        if self.user_id != "root":
            query = query.where(UserSymbolPlotTable.user_id == self.user_id)
        try:
            return await query.aio_get()
        except UserSymbolPlotTable.DoesNotExist:
            raise StandardResponseExc(msg="监控配置不存在或无权操作")

    @staticmethod
    def validate_config(data):
        direction = data.get("monitor_direction")
        if direction not in ("buy", "sell"):
            raise StandardResponseExc(msg="请选择买入或卖出监控")
        prices = {}
        for field in ("take_profit_price", "stop_loss_price"):
            value = data.get(field)
            if value in (None, ""):
                prices[field] = None
                continue
            try:
                price = Decimal(str(value))
                if not price.is_finite() or price <= 0 or price >= Decimal("1000000000000"):
                    raise ValueError()
                if price != price.quantize(Decimal("0.00000001")):
                    raise ValueError()
            except Exception:
                raise StandardResponseExc(msg="价格必须为正数，最多 12 位整数、8 位小数")
            prices[field] = price
        if direction == "buy" and any(value is not None for value in prices.values()):
            raise StandardResponseExc(msg="买入监控不设置止盈止损价")
        if (prices["take_profit_price"] is not None and prices["stop_loss_price"] is not None
                and prices["stop_loss_price"] >= prices["take_profit_price"]):
            raise StandardResponseExc(msg="止损价必须低于止盈价")
        return {"monitor_direction": direction, **prices}

    async def add_symbol(self, data):
        if not re.fullmatch(r"[a-z0-9]{2,10}", self.symbol):
            raise StandardResponseExc(msg="币种应为 2–10 位英文字母或数字")
        config = self.validate_config(data)
        async with monitor_lock(f"lock_monitor_user:{self.user_id}"):
            if await UserSymbolPlotTable.select().where(
                UserSymbolPlotTable.user_id == self.user_id,
                UserSymbolPlotTable.symbol == self.symbol,
            ).aio_exists():
                raise StandardResponseExc(msg="该币种已添加，请编辑现有监控")
            if self.user_id != "root":
                count = await UserSymbolPlotTable.select().where(
                    UserSymbolPlotTable.user_id == self.user_id).aio_count()
                if count >= 3:
                    raise StandardResponseExc(msg="最多添加 3 个监控币种")
            row = await UserSymbolPlotTable.aio_create(user_id=self.user_id, symbol=self.symbol, **config)
        self.refresh_symbol_cache()
        return self.serialize(row)

    async def update_monitor(self, monitor_id, data):
        async with monitor_lock(f"lock_monitor:{monitor_id}"):
            row = await self.get_owned_monitor(monitor_id)
            merged = self.serialize(row)
            merged.update({key: data[key] for key in (
                "monitor_direction", "take_profit_price", "stop_loss_price") if key in data})
            if merged["monitor_direction"] == "buy":
                merged.update(take_profit_price=None, stop_loss_price=None)
            config = self.validate_config(merged)
            if "is_valid" in data:
                if not isinstance(data["is_valid"], bool):
                    raise StandardResponseExc(msg="is_valid 必须是布尔值")
                config["is_valid"] = data["is_valid"]
            changed = any(getattr(row, key) != value for key, value in config.items())
            if changed:
                config["config_version"] = uuid.uuid4().hex
                for key, value in config.items():
                    setattr(row, key, value)
                await row.aio_save()
        self.refresh_symbol_cache()
        return self.serialize(row)

    async def delete_symbol(self, monitor_id):
        async with monitor_lock(f"lock_monitor:{monitor_id}"):
            row = await self.get_owned_monitor(monitor_id)
            await UserSymbolPlotTable.delete().where(UserSymbolPlotTable.id == row.id).aio_execute()
        self.refresh_symbol_cache()
        return {"message": "已移除监控，历史行情、指标和信号记录已保留"}

    def add_macd_gate(self, interval=""):
        if interval in PLOT_INTERVAL_LIST:
            CheckMacdCrossGateCache.hset(f"{self.symbol}:{interval}", 1)
            CheckMacdTrendGateCache.hset(f"{self.symbol}:{interval}", 1)
        else:
            for i in PLOT_INTERVAL_LIST:
                CheckMacdCrossGateCache.hset(f"{self.symbol}:{i}", 1)
                CheckMacdTrendGateCache.hset(f"{self.symbol}:{i}", 1)

    def del_macd_gate(self, interval=""):
        if interval in PLOT_INTERVAL_LIST:
            CheckMacdCrossGateCache.hdel(f"{self.symbol}:{interval}")
            CheckMacdTrendGateCache.hdel(f"{self.symbol}:{interval}")
        else:
            for i in PLOT_INTERVAL_LIST:
                CheckMacdCrossGateCache.hdel(f"{self.symbol}:{i}")
                CheckMacdTrendGateCache.hdel(f"{self.symbol}:{i}")

    def del_macd_cross_gate(self, interval):
        return CheckMacdCrossGateCache.hdel(f"{self.symbol}:{interval}")

    def del_macd_trend_gate(self, interval):
        return CheckMacdTrendGateCache.hdel(f"{self.symbol}:{interval}")

    def add_kdj_gate(self, interval=""):
        if interval in PLOT_INTERVAL_LIST:
            CheckKdjCrossGateCache.hset(f"{self.symbol}:{interval}", 1)
        else:
            for i in PLOT_INTERVAL_LIST:
                CheckKdjCrossGateCache.hset(f"{self.symbol}:{i}", 1)

    def del_kdj_gate(self, interval=""):
        if interval in PLOT_INTERVAL_LIST:
            CheckKdjCrossGateCache.hdel(f"{self.symbol}:{interval}")
        else:
            for i in PLOT_INTERVAL_LIST:
                CheckKdjCrossGateCache.hdel(f"{self.symbol}:{i}")

    def del_kdj_cross_gate(self, interval):
        return CheckKdjCrossGateCache.hdel(f"{self.symbol}:{interval}")


class BnSymbolHandle(object):
    def __init__(self):
        self.user_id = "root"

    async def get_all(self):
        db_rows = await BnSymbolTable.select().where(
            BnSymbolTable.is_valid).order_by(BnSymbolTable.create_ts.desc()).aio_execute()
        result = []
        for row in db_rows:
            result.append({
                "symbol": row.symbol,
                "is_valid": row.is_valid,
                "create_ts": row.create_ts,
            })
        return result
    
    async def add_symbol(self, symbol):
        pass


class CandidateTopPriceNoticeSetting(object):
    key = "setting:candidate_top_price_notice_enabled"

    @classmethod
    def get_enabled(cls):
        value = AllCache.get_client().get(cls.key)
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        return value == "1"

    @classmethod
    def set_enabled(cls, enabled):
        AllCache.get_client().set(cls.key, "1" if enabled else "0")
        return {"enabled": cls.get_enabled()}


class MacdInitData(object):
    def __init__(self, macd_init_data):
        self.macd_init_data = macd_init_data

    async def start(self, interval):
        data = self.macd_init_data.get(interval)
        for i in data:

            if await MacdTable.select().where(
                MacdTable.symbol == i["symbol"].lower(),
                MacdTable.opening_ts == i["opening_ts"],
                MacdTable.interval_val == i["interval"].lower(),
            ).aio_execute():
                print("already")
            else:
                r = await MacdTable(
                    symbol=i["symbol"].lower(),
                    interval_val=i["interval"].lower(),
                    opening_ts=i["opening_ts"],
                    opening_price=Decimal(i["opening_price"]),
                    closing_price=Decimal(i["closing_price"]),
                    ema_12=Decimal(i["ema_12"]),
                    ema_26=Decimal(i["ema_26"]),
                    dea=Decimal(i["dea"]),
                    macd=Decimal(i["macd"]) if "macd" in i else 0,
                    create_ts=int(time.time()),
                ).aio_save()

        db_last_macd = (
            await MacdTable.select()
            .where(
                MacdTable.symbol == i["symbol"].lower(),
                MacdTable.interval_val == i["interval"].lower(),
            )
            .order_by(MacdTable.create_ts.desc())
            .limit(1)
            .aio_get()
        )
        return db_last_macd.id


class KdjInitData(object):
    def __init__(self, kdj_init_data):
        self.kdj_init_data = kdj_init_data

    async def start(self, interval):
        interval_sec = PLOT_INTERVAL_CONFIG[interval]["interval_sec"]

        data = self.kdj_init_data.get(interval)
        for i in data:
            _cfg = i["cfg"]
            _period = _cfg["period"]

            if await KdjTable.select().where(
                KdjTable.symbol == i["symbol"].lower(),
                KdjTable.open_ts == i["open_ts"],
                KdjTable.interval_val == i["interval"].lower(),
            ).aio_execute():
                print("already")
            else:
                _ = await KdjTable(
                    symbol=i["symbol"].lower(),
                    interval_val=i["interval"].lower(),
                    open_ts=i["open_ts"],
                    k_val=Decimal(i["k"]),
                    d_val=Decimal(i["d"]),
                    j_val=Decimal(i["j"]),
                    cfg=json.dumps(_cfg),
                    create_ts=int(time.time()),
                ).aio_save()

        db_row = (
            await KdjTable.select()
            .where(
                KdjTable.symbol == i["symbol"].lower(),
                KdjTable.interval_val == i["interval"].lower(),
            )
            .order_by(KdjTable.create_ts.desc())
            .limit(1)
            .aio_get()
        )
        return db_row.id


class EmaInitData(object):
    def __init__(self, init_data):
        self.init_data = init_data

    def start(self, interval):
        data = self.init_data.get(interval)
        for i in data:

            if EmaTable.select().where(
                EmaTable.symbol == i["symbol"].lower(),
                EmaTable.open_ts == i["open_ts"],
                EmaTable.interval_val == i["interval"].lower(),
            ):
                print("already")
            else:
                _ = EmaTable(
                    symbol=i["symbol"].lower(),
                    interval_val=i["interval"].lower(),
                    open_ts=i["open_ts"],
                    ema7=Decimal(i["ema7"]),
                    ema20=Decimal(i["ema20"]),
                    ema30=Decimal(i["ema30"]),
                    create_ts=int(time.time()),
                ).save()


class KlineInitData(object):

    @staticmethod
    def save(symbol, open_ts, interval):
        if KlineTable.select().where(
            KlineTable.symbol == symbol.lower(),
            KlineTable.open_ts == open_ts,
            KlineTable.interval_val == interval.lower(),
        ):
            print("already")
        else:
            KlineTable(
                symbol=symbol.lower(),
                interval_val=interval.lower(),
                open_ts=open_ts,
                create_ts=int(time.time()),
            ).save()
