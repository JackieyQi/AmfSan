#! /usr/bin/env python
# coding:utf8

import time
import json
from decimal import Decimal

from cache.order import (LimitPriceNoticeValueCache,
                         LimitPriceNoticeValveCache, MarketPriceLimitCache, SymbolPriceChangeHistoryTableCache,
                         MarketPriceCache)
from cache.plot import CheckMacdCrossGateCache, CheckMacdTrendGateCache,\
    SymbolPlotTableCache, CheckKdjCrossGateCache, CheckKdjCvGateCache
from models.market import KlineTable, MacdTable, KdjTable, EmaTable, RsiTable, BollTable
from models.order import SymbolPriceChangeHistoryTable
from models.user import UserSymbolPlotTable as SymbolPlotTable
from settings.constants import *
from utils.common import str2decimal, to_ctime, decimal2str, Decimal
from utils.exception import StandardResponseExc
from utils.hrequest import http_get_request
from business.binance_exchange import BinanceExchangeRequestHandle
from exts import async_database
from cache import AllCache


class MarketPriceHandler(object):
    def get_current_price(self, symbol: str = "btcusdt"):
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
        current_price = self.get_current_price(symbol).get("price")
        if not current_price:
            raise StandardResponseExc()

        current_price = str2decimal(current_price)
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
        current_price = self.get_current_price(symbol).get("price")
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

    def get_last_trade_price(self, symbol):
        last_trade_price = SymbolPlotTableCache.hget(f"{symbol.lower()}:last_price") or "0"
        return Decimal(last_trade_price) or Decimal("0")

    def get_last_trade_price_by_db(self, symbol):
        query = SymbolPlotTable.select(SymbolPlotTable.last_price).where(
            SymbolPlotTable.symbol == symbol
        )
        if query:
            price = query.get().last_price
        else:
            price = Decimal("0")
        return price


class SymbolHandle(object):
    def __init__(self, symbol="", user_id="root"):
        self.user_id = user_id
        self.symbol = symbol

    async def get_all(self):
        db_rows = await SymbolPlotTable.select().where(
            SymbolPlotTable.user_id == self.user_id
        ).order_by(SymbolPlotTable.create_ts).aio_execute()

        result = []
        for row in db_rows:
            result.append({
                "symbol": row.symbol,
                "is_valid": row.is_valid,
                "create_ts": row.create_ts,
            })
        return result

    def refresh_symbol_cache(self):
        redis_client = AllCache.get_client()
        redis_key = "symbol:cfg"
        redis_client.delete(redis_key)
        redis_client.close()

    def add_plot(self):
        return SymbolPlotTableCache.hset(f"{self.symbol.lower()}:is_valid", 1)

    async def add_plot_to_db(self):
        if self.user_id != "root":
            plot_count = await SymbolPlotTable.select(SymbolPlotTable.id).where(
                SymbolPlotTable.user_id == self.user_id,
            ).aio_count()
            if plot_count >= 3:
                return None

        async with async_database.aio_atomic():
            try:
                db_row = await SymbolPlotTable.select().where(
                    SymbolPlotTable.user_id == self.user_id,
                    SymbolPlotTable.symbol == self.symbol,
                ).aio_get()

                if db_row.is_valid is False:
                    db_row.is_valid = True
                    await db_row.aio_save()
                return db_row

            except SymbolPlotTable.DoesNotExist:
                new_row = SymbolPlotTable(
                    user_id=self.user_id,
                    symbol=self.symbol,
                )
                await new_row.aio_save()
                return new_row

    def del_plot(self):
        self.del_macd_gate()
        self.del_kdj_gate()

        return SymbolPlotTableCache.hset(f"{self.symbol.lower()}:is_valid", 0)

    async def del_plot_to_db(self):
        async with async_database.aio_atomic():
            if self.user_id == "root":
                plot_row = await SymbolPlotTable.delete().where(
                    SymbolPlotTable.symbol == self.symbol,
                ).aio_execute()
            else:
                plot_row = await SymbolPlotTable.delete().where(
                    SymbolPlotTable.user_id == self.user_id,
                    SymbolPlotTable.symbol == self.symbol,
                ).aio_execute()

            if await SymbolPlotTable.select(SymbolPlotTable.id).where(
                    SymbolPlotTable.symbol == self.symbol).aio_exists():
                return {"plot_row": plot_row, }

            kline_del_rows = await KlineTable.delete().where(KlineTable.symbol == self.symbol).aio_execute()
            macd_del_rows = await MacdTable.delete().where(MacdTable.symbol == self.symbol).aio_execute()
            kdj_del_rows = await KdjTable.delete().where(KdjTable.symbol == self.symbol).aio_execute()
            rsi_del_rows = await RsiTable.delete().where(RsiTable.symbol == self.symbol).aio_execute()
            boll_del_rows = await BollTable.delete().where(BollTable.symbol == self.symbol).aio_execute()

        return {
            "plot_row": plot_row, "kline_del_rows": kline_del_rows, "macd_del_rows": macd_del_rows,
            "kdj_del_rows": kdj_del_rows, "rsi_del_rows": rsi_del_rows, "boll_del_rows": boll_del_rows,
        }

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
