#! /usr/bin/env python
# coding:utf8

import time
import json
import logging
import math
import numpy as np
import pandas as pd
from decimal import Decimal as D

from business.binance_exchange import BinanceExchangeRequestHandle
# from business.huobi_exchange import HuobiExchangeAccountHandle
from business.market import MarketPriceHandler, MacdInitData, KdjInitData, EmaInitData
from models.market import KlineTable, MacdTable, KdjTable, EmaTable, RsiTable, BollTable
from models.order import OrderTradeHistoryTable
from models.user import UserSymbolPlotTable as SymbolPlotTable
from models.wallet import TotalBalanceHistoryTable
from settings.setting import cfgs
from settings.constants import PLOT_INTERVAL_LIST, PLOT_INTERVAL_CONFIG
from utils.common import decimal2str, str2decimal, locking, \
    set_lock_latest, leading_zeros, decimal2decimal, float2decimal
from utils.hrequest import http_get_request
from exts import async_database
from cache import AllCache, RedisPoolContext
from cache.order import MarketMacdCache, MarketKdjCache, MarketEmaCache, FearAndGreedIndexCache
from msgqueue.queue import push_symbol_mq

from .base import get_plot_symbols_info


logger = logging.getLogger(__name__)


async def save_trade_history_job(*args, **kwargs):
    key, secret = cfgs["bian"]["key"], cfgs["bian"]["secret"]
    binance_handler = BinanceExchangeRequestHandle(key, secret)

    query = SymbolPlotTable.select().where(
        SymbolPlotTable.user_id == 2,
        SymbolPlotTable.is_valid == True,
    )
    for row in query:
        symbol = row.symbol

        trades_data = binance_handler.get_my_trades(symbol.upper())
        for i in trades_data:
            _trade_id = i["id"]

            if OrderTradeHistoryTable.select().where(
                OrderTradeHistoryTable.trade_id == _trade_id
            ):
                continue

            _ = OrderTradeHistoryTable(
                user_id=2,
                trade_id=_trade_id,
                order_id=i["orderId"],
                symbol=symbol,
                price=D(i["price"]),
                qty=D(i["qty"]),
                quote_qty=D(i["quoteQty"]),
                trade_ts=int(i["time"] / 1000),
                is_buyer=i["isBuyer"],
                is_maker=i["isMaker"],
                extra_data=json.dumps(i),
            ).save()

            last_trade = (
                OrderTradeHistoryTable.select()
                .where(OrderTradeHistoryTable.symbol == symbol)
                .order_by(OrderTradeHistoryTable.id.desc())
                .get()
            )

            query = SymbolPlotTable.select().where(
                SymbolPlotTable.user_id == 2, SymbolPlotTable.symbol == symbol
            )
            if query:
                symbol_plot = query.get()
                symbol_plot.last_price = last_trade.price
                symbol_plot.save()
            else:
                SymbolPlotTable(
                    user_id=2,
                    symbol=last_trade.symbol,
                    last_price=last_trade.price,
                ).save()


async def save_account_balance_job(*args, **kwargs):
    # account_handler = HuobiExchangeAccountHandle()
    # account_handler.save_current_balance()

    key, secret = cfgs["bian"]["key"], cfgs["bian"]["secret"]
    account_handler = BinanceExchangeRequestHandle(key, secret)
    asset_data = account_handler.get_my_user_asset()
    if not asset_data:
        return

    current_price = MarketPriceHandler().get_current_price_by_cache("btcusdt")
    current_price = str2decimal(current_price or "0")

    total_btc_valuation = D("0")
    for i in asset_data:
        total_btc_valuation += D(i["btcValuation"])

    total_usdt_valuation = total_btc_valuation * current_price
    total_usdt_valuation = D(decimal2str(total_usdt_valuation))

    TotalBalanceHistoryTable(
        user_id=2,
        btcusdt_price=current_price,
        btc_val=total_btc_valuation,
        usdt_val=total_usdt_valuation,
        exchange_platform="binance",
        exchange_data=json.dumps(asset_data),
    ).save()


async def save_fng_job(*args, **kwargs):
    """
    恐惧与贪婪指数
    :param args:
    :param kwargs:
    :return:
    """
    resp_data = http_get_request(
        "https://api.alternative.me/fng/",
        {"limit": 3},
    )
    if not resp_data:
        return
    fear_and_greed_data = resp_data["data"]
    current_fng_index = fear_and_greed_data[0]["value"]
    FearAndGreedIndexCache.set(int(current_fng_index), 27*3600)
    logger.info(f"save_fng_job, time:{int(time.time())}, index:{current_fng_index}")


@locking("save_kline_job")
async def save_kline_job(*args, **kwargs):
    redis_client = AllCache.get_client()

    symbols_info = await get_plot_symbols_info(redis_client)
    for symbol in symbols_info.keys():
        for _interval in PLOT_INTERVAL_LIST:
            # TODO,
            if _interval not in ["1h", "4h", "1d"]:
                continue
            await KlineDataSaveHandle(symbol, _interval).save_data()
    redis_client.close()


async def save_macd_job(*args, **kwargs):
    redis_client = AllCache.get_client()

    symbols_info = await get_plot_symbols_info(redis_client)
    for symbol, _info in symbols_info.items():
        for _interval in PLOT_INTERVAL_LIST:
            if f"macd:{_interval}" not in _info:
                continue

            if redis_client.get(f"s_macd:{symbol}:{_interval}"):
                continue
            redis_client.set(f"s_macd:{symbol}:{_interval}", 1, 1024)

            await push_symbol_mq({
                "bp": "save_macd_job_by_symbol",
                "symbol": symbol,
                "interval": _interval
            })
    redis_client.close()


async def save_macd_job_by_symbol(msg):
    symbol = msg.get("symbol")
    _interval = msg.get("interval")
    await MacdDataSaveHandle(symbol, _interval).save_data(symbol, _interval)

    with RedisPoolContext() as r:
        r.delete(f"s_macd:{symbol}:{_interval}")


async def save_kdj_job(*args, **kwargs):
    redis_client = AllCache.get_client()

    symbols_info = await get_plot_symbols_info(redis_client)
    for symbol, _info in symbols_info.items():
        for _interval in PLOT_INTERVAL_LIST:
            if f"kdj:{_interval}" not in _info:
                continue

            if redis_client.get(f"s_kdj:{symbol}:{_interval}"):
                continue
            redis_client.set(f"s_kdj:{symbol}:{_interval}", 1, 1024)

            await push_symbol_mq({
                "bp": "save_kdj_job_by_symbol",
                "symbol": symbol,
                "interval": _interval
            })
    redis_client.close()


async def save_kdj_job_by_symbol(msg):
    symbol = msg.get("symbol")
    _interval = msg.get("interval")
    await KdjDataSaveHandle(symbol, _interval).save_data(symbol, _interval)

    with RedisPoolContext() as r:
        r.delete(f"s_kdj:{symbol}:{_interval}")


async def save_indicators_job(*args, **kwargs):
    redis_client = AllCache.get_client()

    symbols_info = await get_plot_symbols_info(redis_client)
    for symbol, _info in symbols_info.items():
        for _interval in PLOT_INTERVAL_LIST:
            # TODO,
            if _interval not in ["1h", "4h", "1d"]:
                continue

            if redis_client.get(f"s_indicators:{symbol}:{_interval}"):
                continue
            redis_client.set(f"s_kdj:{symbol}:{_interval}", 1, 1024)

            await push_symbol_mq({
                "bp": "save_indicators_job_by_symbol",
                "symbol": symbol,
                "interval": _interval
            })
    redis_client.close()


async def save_indicators_job_by_symbol(msg):
    symbol = msg.get("symbol")
    _interval = msg.get("interval")
    await IndicatorsCalculateHandle(symbol, _interval).start_cal()

    with RedisPoolContext() as r:
        r.delete(f"s_indicators:{symbol}:{_interval}")


@locking("save_ema_job")
async def save_ema_job(*args, **kwargs):
    symbol_list = ["wifusdt", ]
    for symbol in symbol_list:
        for _interval in PLOT_INTERVAL_LIST:
            await EmaDataSaveHandle(symbol, _interval).save_data()


class KlineDataSaveHandle(object):
    def __init__(self, symbol, interval):
        self.symbol = symbol
        self.interval = interval
        self.interval_sec = PLOT_INTERVAL_CONFIG[interval]["interval_sec"]
        self.k_interval = PLOT_INTERVAL_CONFIG[interval]["k_interval"]

        self.curr_time = int(time.time())

    async def get_init_indicators_time(self):
        # 考虑到策略窗口值，再增加20个数据点。
        if await KdjTable.select(KdjTable.symbol).where(
                KdjTable.symbol == self.symbol, KdjTable.interval_val == self.interval).aio_exists():
            init_kdj_ts = 0
        else:
            init_kdj_ts = self.curr_time - self.interval_sec * (KDJIndicator.dataset_length + 20)

        if await MacdTable.select(MacdTable.symbol).where(
                MacdTable.symbol == self.symbol, MacdTable.interval_val == self.interval).aio_exists():
            init_macd_ts = 0
        else:
            init_macd_ts = self.curr_time - self.interval_sec * (MACDIndicator.dataset_length + 20)

        if await RsiTable.select(RsiTable.symbol).where(
                RsiTable.symbol == self.symbol, RsiTable.interval_val == self.interval).aio_exists():
            init_rsi_ts = 0
        else:
            init_rsi_ts = self.curr_time - self.interval_sec * (RSIIndicator.dataset_length + 20)

        start_ts = min(init_kdj_ts, init_macd_ts, init_rsi_ts)
        # TODO: 优化，避免每次检查
        if not start_ts:
            return

        try:
            kline_data = (
                await KlineTable.select(KlineTable.open_ts)
                .where(
                    KlineTable.symbol == self.symbol,
                    KlineTable.interval_val == self.interval,
                    KlineTable.open_ts >= start_ts,
                )
                # .order_by(KlineTable.id.desc())
                .limit(1)
                .aio_get()
            )

            if start_ts <= kline_data.open_ts < start_ts + self.interval_sec:
                return
            else:
                return start_ts
        except KlineTable.DoesNotExist:
            return start_ts

    async def get_k_lines_by_innerapi(self, init_start_ts):
        request_params = {
            "key": "get_k_lines",
            "symbol": self.symbol.upper(),
            "interval": self.interval,
        }

        if not init_start_ts:
            try:
                db_last_k = (
                    await KlineTable.select(KlineTable.open_ts)
                    .where(
                        KlineTable.symbol == self.symbol,
                        KlineTable.interval_val == self.interval,
                    )
                    .order_by(KlineTable.id.desc())
                    .limit(1)
                    .aio_get()
                )
                request_params["start_ts"] = (db_last_k.open_ts - self.k_interval) * 1000

            except KlineTable.DoesNotExist:
                request_params["limit"] = 17
        else:
            request_params["start_ts"] = init_start_ts * 1000

        # resp_data = http_get_request(
        #     f"""{cfgs["http"]["inner_url"]}/api/cache/sync/""",
        #     request_params,
        # )
        # if resp_data:
        #     return resp_data["data"]

        result = BinanceExchangeRequestHandle().get_k_lines(
            self.symbol.upper(), self.interval,
            request_params.get("start_ts"),
            request_params.get("limit"),
        )
        return result if result else None

    async def save_data(self):
        if not self.interval:
            return

        init_start_ts = await self.get_init_indicators_time()

        k_data = await self.get_k_lines_by_innerapi(init_start_ts)
        if not k_data:
            return

        async with async_database.aio_atomic():
            for data in k_data:
                open_ts = int(data[0] / 1000)
                open_price = D(data[1])
                high_price = D(data[2])
                low_price = D(data[3])
                close_price = D(data[4])
                volume = D(data[5])
                close_ts = int(data[6] / 1000)
                asset_volume = D(data[7])
                trade_number = int(data[8])
                buy_volume = D(data[9])
                buy_asset_volume = D(data[10])

                query = KlineTable.select().where(
                        KlineTable.symbol == self.symbol,
                        KlineTable.open_ts == open_ts,
                        KlineTable.interval_val == self.interval,
                )
                if await query.aio_exists():
                    last_db_k = await query.aio_get()
                    last_db_k.high_price = high_price
                    last_db_k.low_price = low_price
                    last_db_k.close_price = close_price
                    last_db_k.volume = volume
                    last_db_k.close_ts = close_ts
                    last_db_k.asset_volume = asset_volume
                    last_db_k.trade_number = trade_number
                    last_db_k.buy_volume = buy_volume
                    last_db_k.buy_asset_volume = buy_asset_volume
                    await last_db_k.aio_save()
                else:
                    _ = await KlineTable.aio_create(
                        symbol=self.symbol,
                        interval_val=self.interval,
                        open_ts=open_ts,
                        open_price=open_price,
                        high_price=high_price,
                        low_price=low_price,
                        close_price=close_price,
                        volume=volume,
                        close_ts=close_ts,
                        asset_volume=asset_volume,
                        trade_number=trade_number,
                        buy_volume=buy_volume,
                        buy_asset_volume=buy_asset_volume,
                    )


class MacdDataSaveHandle(object):
    def __init__(self, symbol, interval):
        self.symbol = symbol
        self.interval = interval
        self.interval_sec = PLOT_INTERVAL_CONFIG[interval]["interval_sec"]
        self.k_interval = PLOT_INTERVAL_CONFIG[interval]["k_interval"]

    async def get_k_lines_from_db(self):
        try:
            db_last_macd = (
                await MacdTable.select(MacdTable.opening_ts)
                .where(
                    MacdTable.symbol == self.symbol,
                    MacdTable.interval_val == self.interval,
                )
                .order_by(MacdTable.id.desc())
                .limit(1)
                .aio_get()
            )
            last_macd_ts = db_last_macd.opening_ts
        except MacdTable.DoesNotExist:
            return []

        try:
            _ts = last_macd_ts - self.k_interval
            db_kline = await KlineTable.select().where(
                KlineTable.symbol == self.symbol,
                KlineTable.interval_val == self.interval,
                KlineTable.open_ts >= _ts,
            ).order_by(KlineTable.id).aio_execute()
            return list(db_kline)
        except KlineTable.DoesNotExist:
            return []

    async def parsed_k_lines_data(self, k_lines):
        if not k_lines:
            return None

        opening_tss = [k.open_ts for k in k_lines]
        all_macd_tss = list(set([ts - self.interval_sec for ts in opening_tss] + opening_tss))

        macd_data_dict = {
            (macd.symbol, macd.opening_ts): macd
            for macd in await MacdTable.select().where(
                MacdTable.symbol == self.symbol,
                MacdTable.interval_val == self.interval,
                MacdTable.opening_ts.in_(all_macd_tss),
            ).aio_execute()
        }

        updated_macds = []
        new_macds = []
        last_macd = None

        async with async_database.aio_atomic():
            for k in k_lines:
                opening_ts = k.open_ts
                opening_price = k.open_price
                closing_price = k.close_price

                last_macd = macd_data_dict.get((self.symbol, opening_ts - self.interval_sec))
                now_macd = macd_data_dict.get((self.symbol, opening_ts))

                if not last_macd:
                    continue

                now_ema_12 = last_macd.ema_12 * 11 / 13 + closing_price * 2 / 13
                now_ema_26 = last_macd.ema_26 * 25 / 27 + closing_price * 2 / 27
                now_dea = last_macd.dea * 8 / 10 + (now_ema_12 - now_ema_26) * 2 / 10
                # now_dif = now_ema_12 - now_ema_26
                now_macd_val = decimal2decimal(now_ema_12 - now_ema_26 - now_dea)

                if now_macd:
                    now_macd.opening_ts = opening_ts
                    now_macd.opening_price = opening_price
                    now_macd.closing_price = closing_price
                    now_macd.ema_12 = decimal2decimal(now_ema_12)
                    now_macd.ema_26 = decimal2decimal(now_ema_26)
                    now_macd.dea = decimal2decimal(now_dea)
                    now_macd.macd = now_macd_val
                    await now_macd.aio_save()
                    # updated_macds.append(now_macd)
                else:
                    await MacdTable.aio_create(
                        symbol=self.symbol,
                        interval_val=self.interval,
                        opening_ts=opening_ts,
                        opening_price=opening_price,
                        closing_price=closing_price,
                        ema_12=decimal2decimal(now_ema_12),
                        ema_26=decimal2decimal(now_ema_26),
                        dea=decimal2decimal(now_dea),
                        macd=now_macd_val,
                    )

        # if updated_macds:
        #     MacdTable.bulk_update(updated_macds,
        #                           fields=[MacdTable.opening_ts, MacdTable.opening_price, MacdTable.closing_price,
        #                                   MacdTable.ema_12, MacdTable.ema_26, MacdTable.dea, MacdTable.macd])
        # if new_macds:
        #     MacdTable.bulk_create(new_macds)

        if k_lines:
            return k_lines[-1].open_ts
        return

    async def __init_macd_cache_data(self):
        cache_data = MarketMacdCache(self.symbol, self.interval).get()
        if not cache_data:
            return

        macd_init_data = {self.interval: json.loads(cache_data)}
        await MacdInitData(macd_init_data).start(self.interval)

    @set_lock_latest("lock_macd_latest")
    async def save_data(self, symbol, interval):
        if not self.interval:
            return

        await self.__init_macd_cache_data()

        k_data = await self.get_k_lines_from_db()
        open_ts = await self.parsed_k_lines_data(k_data)
        return open_ts


class KdjDataSaveHandle(object):
    def __init__(self, symbol, interval):
        self.symbol = symbol
        self.interval = interval
        self.interval_sec = PLOT_INTERVAL_CONFIG[interval]["interval_sec"]
        self.k_interval = PLOT_INTERVAL_CONFIG[interval]["k_interval"]

    async def get_k_lines_from_db(self):
        try:
            db_last_kdj = (
                await KdjTable.select(KdjTable.open_ts, KdjTable.cfg)
                .where(
                    KdjTable.symbol == self.symbol,
                    KdjTable.interval_val == self.interval,
                )
                .order_by(KdjTable.id.desc())
                .limit(1)
                .aio_get()
            )
            last_kdj_ts = db_last_kdj.open_ts
            kdj_cfg = json.loads(db_last_kdj.cfg)
            period = kdj_cfg["period"]

            # 计算 KDJ 所需的最小时间
            min_start_ts = last_kdj_ts - period * self.interval_sec
            # 确保查询 K 线数据的起始时间能够覆盖最小时间
            start_ts = min(last_kdj_ts - self.k_interval, min_start_ts)
        except KdjTable.DoesNotExist:
            return []

        try:
            db_kline = await KlineTable.select().where(
                KlineTable.symbol == self.symbol,
                KlineTable.interval_val == self.interval,
                KlineTable.open_ts >= start_ts,
            ).order_by(KlineTable.id).aio_execute()
            return list(db_kline)
        except KlineTable.DoesNotExist:
            return []

    def __calculate_kdj(self, k_lines, last_k, period):
        if len(k_lines) < period:
            return None

        low_price_list = []
        high_price_list = []
        for _row in k_lines:
            low_price_list.append(_row.low_price)
            high_price_list.append(_row.high_price)
        min_price = min(low_price_list)
        max_price = max(high_price_list)
        close_price = k_lines[-1].close_price

        rsv = (close_price - min_price) / (max_price - min_price) * 100
        last_k_val = last_k.k_val
        last_d_val = last_k.d_val

        if not last_k_val or not last_d_val:
            return

        k_val = D(2 / 3) * last_k_val + D(1 / 3) * rsv
        d_val = D(2 / 3) * last_d_val + D(1 / 3) * k_val
        j_val = D(3) * k_val - D(2) * d_val
        return k_val, d_val, j_val

    async def parsed_k_lines_data(self, k_lines):
        if not k_lines:
            return

        opening_tss = [k.open_ts for k in k_lines]
        all_kdj_tss = list(set([ts - self.interval_sec for ts in opening_tss] + opening_tss))

        kdj_data_dict = {
            (kdj.symbol, kdj.open_ts): kdj
            for kdj in await KdjTable.select().where(
                KdjTable.symbol == self.symbol,
                KdjTable.interval_val == self.interval,
                KdjTable.open_ts.in_(all_kdj_tss),
            ).aio_execute()
        }

        async with async_database.aio_atomic():
            for k in k_lines:
                open_ts = k.open_ts
                close_price = k.close_price

                last_kdj = kdj_data_dict.get((self.symbol, open_ts - self.interval_sec))
                now_kdj = kdj_data_dict.get((self.symbol, open_ts))

                if not last_kdj:
                    # logger.error(f"KdjDataSaveHandle, no last_kdj, {self.symbol}, {self.interval}, {open_ts}")
                    continue

                kdj_cfg = json.loads(last_kdj.cfg)
                period = kdj_cfg["period"]

                period_k_lines = [kl for kl in k_lines if
                                  kl.open_ts <= open_ts and kl.open_ts > open_ts - period * self.interval_sec]

                kdj_result = self.__calculate_kdj(period_k_lines, last_kdj, period)
                if not kdj_result:
                    # logger.error(f"KdjDataSaveHandle, no kdj_result, {self.symbol}, {self.interval}, {open_ts}")
                    continue

                k_val, d_val, j_val = kdj_result

                if now_kdj:
                    now_kdj.k_val = decimal2decimal(k_val)
                    now_kdj.d_val = decimal2decimal(d_val)
                    now_kdj.j_val = decimal2decimal(j_val)
                    await now_kdj.aio_save()
                else:
                    await KdjTable.aio_create(
                        symbol=self.symbol,
                        interval_val=self.interval,
                        open_ts=open_ts,
                        k_val=decimal2decimal(k_val),
                        d_val=decimal2decimal(d_val),
                        j_val=decimal2decimal(j_val),
                        cfg=last_kdj.cfg,
                    )

        if k_lines:
            return k_lines[-1].open_ts
        return None

    async def __init_kdj_cache_data(self):
        cache_data = MarketKdjCache(self.symbol, self.interval).get()
        if not cache_data:
            return

        kdj_init_data = {self.interval: json.loads(cache_data)}
        await KdjInitData(kdj_init_data).start(self.interval)

    @set_lock_latest("lock_kdj_latest")
    async def save_data(self, symbol, interval):
        if not self.interval:
            return

        await self.__init_kdj_cache_data()

        k_data = await self.get_k_lines_from_db()
        open_ts = await self.parsed_k_lines_data(k_data)
        return open_ts


class EmaDataSaveHandle(object):
    def __init__(self, symbol, interval):
        self.symbol = symbol
        self.interval = interval
        self.interval_sec = PLOT_INTERVAL_CONFIG[interval]["interval_sec"]
        self.k_interval = PLOT_INTERVAL_CONFIG[interval]["k_interval"]

    def __init_ema_cache_data(self):
        cache_data = MarketEmaCache(self.symbol, self.interval).get()
        if not cache_data:
            return

        init_data = {self.interval: json.loads(cache_data)}
        EmaInitData(init_data).start(self.interval)

    def get_k_lines_from_db(self):
        try:
            db_last_ema = (
                EmaTable.select()
                .where(
                    EmaTable.symbol == self.symbol,
                    EmaTable.interval_val == self.interval,
                )
                .order_by(EmaTable.id.desc())
                .limit(1)
                .get()
            )
        except EmaTable.DoesNotExist:
            return

        try:
            db_kline = KlineTable.select().where(
                KlineTable.symbol == self.symbol,
                KlineTable.interval_val == self.interval,
                KlineTable.open_ts >= db_last_ema.open_ts - self.k_interval,
            ).order_by(KlineTable.id)
        except KlineTable.DoesNotExist:
            return
        return db_kline

    def __calculate_ema(self, last_data, open_ts, close_price):
        result = {}
        n_list = [7, 20, 30]
        for n in n_list:
            if n == 7:
                last_ema = last_data.ema7
                ema = D(2 / (n + 1)) * close_price + D((1 - 2 / (n + 1))) * last_ema
                result["ema7"] = ema
            elif n == 20:
                last_ema = last_data.ema20
                ema = D(2 / (n + 1)) * close_price + D((1 - 2 / (n + 1))) * last_ema
                result["ema20"] = ema
            else:
                last_ema = last_data.ema30
                ema = D(2 / (n + 1)) * close_price + D((1 - 2 / (n + 1))) * last_ema
                result["ema30"] = ema
        return result

    def parsed_k_lines_data(self, data):
        open_ts = data.open_ts
        close_price = data.close_price

        db_query = (
            EmaTable.select()
            .where(
                EmaTable.symbol == self.symbol,
                EmaTable.interval_val == self.interval,
                EmaTable.open_ts.in_([open_ts - self.interval_sec, open_ts]),
            )
            .order_by(EmaTable.id)
        )
        db_query_list = list(db_query)
        if not db_query_list:
            return

        last_data = db_query_list[0]
        if last_data.open_ts != open_ts - self.interval_sec:
            return

        ema_result = self.__calculate_ema(last_data, open_ts, close_price)
        if not ema_result:
            return

        if len(db_query_list) == 2:
            now_ema_data = db_query_list[1]
            now_ema_data.ema7 = ema_result["ema7"]
            now_ema_data.ema20 = ema_result["ema20"]
            now_ema_data.ema30 = ema_result["ema30"]
            now_ema_data.save()
        else:
            if not EmaTable.select().where(
                    EmaTable.symbol == self.symbol,
                    EmaTable.open_ts == open_ts,
                    EmaTable.interval_val == self.interval,
            ):
                _ = EmaTable.create(
                    symbol=self.symbol,
                    interval_val=self.interval,
                    open_ts=open_ts,
                    ema7=ema_result["ema7"],
                    ema20=ema_result["ema20"],
                    ema30=ema_result["ema30"],
                )

    async def save_data(self):
        if not self.interval:
            return

        self.__init_ema_cache_data()

        k_data = self.get_k_lines_from_db()
        if not k_data:
            return

        for _data in k_data:
            self.parsed_k_lines_data(_data)


class MACDIndicator:
    dataset_length = 150 # 数据点为150，macd趋于稳定.

    default_fast_period = 12
    default_slow_period = 26
    default_signal_period = 9

    @classmethod
    def get_origin_macd(cls, prices, fast_period=default_fast_period,
                        slow_period=default_slow_period, signal_period=default_signal_period):
        """
        :param prices: 收盘价的正序数组
        :param fast_period:
        :param slow_period:
        :param signal_period:
        :return:
        """
        # 确保有足够的数据
        if len(prices) < max(fast_period, slow_period) + signal_period:
            return

        # 计算快速EMA（通常是12日）
        fast_ema = [0] * len(prices)
        # 初始化：使用前N个周期的简单平均值
        fast_ema[fast_period - 1] = sum(prices[:fast_period]) / fast_period

        # 计算剩余的快速EMA
        k_fast = D(2 / (fast_period + 1))
        for i in range(fast_period, len(prices)):
            fast_ema[i] = prices[i] * k_fast + fast_ema[i - 1] * (1 - k_fast)

        # 计算慢速EMA（通常是26日）
        slow_ema = [0] * len(prices)
        # 初始化：使用前N个周期的简单平均值
        slow_ema[slow_period - 1] = sum(prices[:slow_period]) / slow_period

        # 计算剩余的慢速EMA
        k_slow = D(2 / (slow_period + 1))
        for i in range(slow_period, len(prices)):
            slow_ema[i] = prices[i] * k_slow + slow_ema[i - 1] * (1 - k_slow)

        # 计算MACD线(DIF)：快速EMA - 慢速EMA
        dif_line = [0] * len(prices)
        for i in range(slow_period, len(prices)):
            dif_line[i] = fast_ema[i] - slow_ema[i]

        # 计算信号线(DEA)：MACD线的EMA
        dea_line = [0] * len(prices)
        # 需要等到有足够的MACD线值才能计算其EMA
        start_idx = slow_period + signal_period - 1
        # 初始化信号线
        dea_line[start_idx] = sum(dif_line[slow_period:start_idx + 1]) / D(signal_period)

        # 计算剩余的信号线
        k_signal = D(2 / (signal_period + 1))
        for i in range(start_idx + 1, len(prices)):
            dea_line[i] = dif_line[i] * k_signal + dea_line[i - 1] * (1 - k_signal)

        # 计算柱状图：MACD
        macd_line = [0] * len(prices)
        for i in range(start_idx, len(prices)):
            macd_line[i] = dif_line[i] - dea_line[i]

        return {
            "fast_ema": decimal2decimal(fast_ema[-1]),
            "slow_ema": decimal2decimal(slow_ema[-1]),
            "dif": decimal2decimal(dif_line[-1]),
            "dea": decimal2decimal(dea_line[-1]),
            "macd": decimal2decimal(macd_line[-1])
        }

    @classmethod
    def calculate_macd_incremental(cls, price, prev_fast_ema, prev_slow_ema, prev_dea,
                                   fast_period=default_fast_period,
                                   slow_period=default_slow_period,
                                   signal_period=default_signal_period
                                   ):

        k_fast = D(2 / (fast_period + 1))
        k_slow = D(2 / (slow_period + 1))
        k_signal = D(2 / (signal_period + 1))

        fast_ema = price * k_fast + prev_fast_ema * (1 - k_fast)
        slow_ema = price * k_slow + prev_slow_ema * (1 - k_slow)
        dif = fast_ema - slow_ema
        dea = dif * k_signal + prev_dea * (1 - k_signal)
        macd = dif - dea
        return {
            "fast_ema": decimal2decimal(fast_ema),
            "slow_ema": decimal2decimal(slow_ema),
            "dea": decimal2decimal(dea), "macd": decimal2decimal(macd),
        }


class KDJIndicator:
    dataset_length = 50 # 数据集为50，kdj趋于稳定.

    default_period = 9
    default_avg_move_1 = 3
    default_avg_move_2 = 3

    @classmethod
    def get_origin_kdj(cls, k_lines, n=default_period, m1=default_avg_move_1, m2=default_avg_move_2):
        """
        计算KDJ指标

        参数:
        k_lines: 数据库的正序的k线数据
        n: RSV计算周期，默认为9
        m1, m2: K和D值的平滑因子，默认都为3

        返回:
        包含K、D、J值的字典
        """
        if len(k_lines) < n:
            return

        high_prices = []
        low_prices = []
        close_prices = []
        for _row in k_lines:
            low_prices.append(_row.low_price)
            high_prices.append(_row.high_price)
            close_prices.append(_row.close_price)

        # 初始化结果数组
        length = len(k_lines)
        rsv_values = [0] * length
        k_values = [50] * length  # 初始K值设为50
        d_values = [50] * length  # 初始D值设为50
        j_values = [50] * length  # 初始J值

        # 计算RSV值
        for i in range(n-1, length):
            period_high = max(high_prices[i-n+1:i+1])
            period_low = min(low_prices[i-n+1:i+1])

            if period_high == period_low:  # 防止除以零
                rsv_values[i] = 50
            else:
                rsv_values[i] = ((close_prices[i] - period_low) / (period_high - period_low)) * 100

        # 计算K、D、J值
        for i in range(n, length):
            k_values[i] = D(2/3) * k_values[i-1] + D(1/3) * rsv_values[i]
            d_values[i] = D(2/3) * d_values[i-1] + D(1/3) * k_values[i]
            j_values[i] = D(3) * k_values[i] - D(2) * d_values[i]

        return {
            "k_val": decimal2decimal(k_values[-1]),
            "d_val": decimal2decimal(d_values[-1]),
            "j_val": decimal2decimal(j_values[-1]),
        }

    @classmethod
    def calculate_kdj_incremental(cls, k_lines, prev_k, prev_d, period=default_period):
        if len(k_lines) < period:
            return None

        if not prev_k or not prev_d:
            return

        low_price_list = []
        high_price_list = []
        for _row in k_lines:
            low_price_list.append(_row.low_price)
            high_price_list.append(_row.high_price)
        min_price = min(low_price_list)
        max_price = max(high_price_list)
        close_price = k_lines[-1].close_price

        rsv = (close_price - min_price) / (max_price - min_price) * 100

        k_val = D(2 / 3) * prev_k + D(1 / 3) * rsv
        d_val = D(2 / 3) * prev_d + D(1 / 3) * k_val
        j_val = D(3) * k_val - D(2) * d_val
        return {
            "k_val": decimal2decimal(k_val),
            "d_val": decimal2decimal(d_val),
            "j_val": decimal2decimal(j_val),
        }


class RSIIndicator:
    dataset_length = 70 # 数据集为70，rsi趋于稳定.

    default_period = 6 # period: RSI周期，默认为6(传统是14)

    @classmethod
    def get_origin_rsi(cls, prices, period=default_period):
        """
        :param prices: 收盘价的正序数组
        :param period:
        :return:
        """
        if len(prices) < (cls.dataset_length-1): # 去掉最新k线
            return

        scale_factor = leading_zeros(prices[0])
        if scale_factor:
            for i, val in enumerate(prices):
                prices[i] = val * scale_factor

        # 计算价格变化
        deltas = np.diff([float(i) for i in prices])

        # 分离上涨和下跌
        gain = np.where(deltas > 0, deltas, 0)
        loss = np.where(deltas < 0, -deltas, 0)

        # 初始平均上涨和下跌
        avg_gain = np.mean(gain[:period])
        avg_loss = np.mean(loss[:period])

        # 计算后续的平均上涨和下跌（使用Wilder的平滑方法）
        for i in range(period, len(deltas)):
            avg_gain = ((period - 1) * avg_gain + gain[i]) / period
            avg_loss = ((period - 1) * avg_loss + loss[i]) / period

        # 计算RS和RSI
        if avg_loss == 0:
            # return 100
            return
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return {"rsi": float2decimal(rsi), "avg_gain": float2decimal(avg_gain), "avg_loss": float2decimal(avg_loss)}

    @classmethod
    def calculate_rsi_incremental(cls, previous_rsi, previous_avg_gain, previous_avg_loss,
                                  current_price, previous_price, period=default_period):
        """
        增量式计算RSI

        参数:
        previous_rsi: 前一个时间点的RSI值
        previous_avg_gain: 前一个时间点的平均上涨
        previous_avg_loss: 前一个时间点的平均下跌
        current_price: 当前价格
        previous_price: 前一个时间点的价格

        返回:
        当前RSI值, 当前平均上涨, 当前平均下跌
        """
        period = D(period)
        # 计算当前价格变化
        price_change = current_price - previous_price

        # 确定上涨或下跌
        current_gain = max(0, price_change)
        current_loss = max(0, -price_change)

        # 更新平均上涨和下跌（使用Wilder的平滑方法）
        avg_gain = ((period - 1) * previous_avg_gain + current_gain) / period
        avg_loss = ((period - 1) * previous_avg_loss + current_loss) / period

        # 计算新的RSI
        if avg_loss == 0:
            rsi = D(100)
        else:
            rs = avg_gain / avg_loss
            rsi = D(100) - (D(100) / (D(1) + rs))

        return {"rsi": decimal2decimal(rsi),
                "avg_gain": decimal2decimal(avg_gain), "avg_loss": decimal2decimal(avg_loss)}


class BollIndicator:
    dataset_length = 40 # 数据集为40，boll趋于稳定.

    default_period = 20 # Boll周期，默认为20
    default_std_multiplier = 2 # 标准查倍数, 通常为2

    @classmethod
    def get_origin_bb(cls, prices, period=default_period, std_multiplier=default_std_multiplier):
        if len(prices) < period:
            return
        prices = prices[:period]

        close_prices_array = np.array([float(i.close_price) for i in prices])

        df = pd.DataFrame({"close": close_prices_array})

        middle_band = df["close"].rolling(window=period).mean()
        std = df["close"].rolling(window=period).std(ddof=0)  # 使用ddof=0参数指定用N作为除数
        higher_band = middle_band + (std * std_multiplier)
        lower_band = middle_band - (std * std_multiplier)
        bandwidth = higher_band - lower_band

        last_higher_band = higher_band.tail(1).values[0]
        last_lower_band = lower_band.tail(1).values[0]
        last_bandwidth = bandwidth.tail(1).values[0]
        last_middle_band = middle_band.tail(1).values[0]

        # 提取最后一个 period 长度的窗口数据
        last_window = close_prices_array[-period:]

        # 初始化滚动变量
        sum_close = np.sum(last_window)
        sum_sq_close = np.sum(last_window ** 2)
        return {"bb_upper": float2decimal(last_higher_band), "bb_lower": float2decimal(last_lower_band),
                "bb_mid": float2decimal(last_middle_band), "sum_close": float2decimal(sum_close),
                "sum_sq_close": float2decimal(sum_sq_close), "period": period, "open_ts": prices[-1].open_ts}

    @classmethod
    def get_close_prices_list(cls, prices_list, open_ts, period=default_period):
        total_len = len(prices_list)
        if total_len < period:
            return

        found_ind = -1
        for i, bb in enumerate(prices_list):
            if bb.open_ts == open_ts:
                found_ind = i
                break
        if found_ind == -1:
            return

        return prices_list[:found_ind+1][-period:]

    @classmethod
    def calculate_bb_incremental(cls, prices_list, previous_open_ts, previous_sum, previous_sum_sq, period=default_period):
        total_len = len(prices_list)
        if total_len < period:
            return

        found_ind = -1
        for i, bb in enumerate(prices_list):
            if bb.open_ts == previous_open_ts:
                found_ind = i
                break
        if found_ind == -1:
            return
        current_price = prices_list[found_ind+1].close_price
        old_close_price = prices_list[found_ind+1-period].close_price

        sum_close = previous_sum + (current_price - old_close_price)
        sum_sq_close = previous_sum_sq + (current_price ** 2 + old_close_price ** 2)

        # 计算布林线
        mean = sum_close / period # 中轨
        # TODO:递增计算有问题
        std = math.sqrt(sum_sq_close / period - mean ** 2)
        std = float2decimal(std)
        upper = mean + 2 * std
        lower = mean - 2 * std
        return {"bb_upper": decimal2decimal(upper), "bb_lower": decimal2decimal(lower),
                "bb_mid": decimal2decimal(mean), "sum_close": decimal2decimal(sum_close),
                "sum_sq_close": decimal2decimal(sum_sq_close), "period": period}


class IndicatorsCalculateHandle(object):
    def __init__(self, symbol, interval):
        self.symbol = symbol
        self.interval = interval
        self.interval_sec = PLOT_INTERVAL_CONFIG[interval]["interval_sec"]
        self.k_interval = PLOT_INTERVAL_CONFIG[interval]["k_interval"]

        self.curr_time = int(time.time())
        self.default_rsi_period = 6

    async def start_cal(self):
        rsi_start_ts, macd_start_ts, kdj_start_ts, bb_start_ts = 0, 0, 0, 0

        rsi_data_dict = {
            (row.symbol, row.open_ts): row
            for row in await RsiTable.select().where(
                RsiTable.symbol == self.symbol,
                RsiTable.interval_val == self.interval,
            ).order_by(RsiTable.id.desc()).limit(3).aio_execute()
        }
        if not rsi_data_dict:
            await self._init_rsi_data()
        else:
            rsi_start_ts = min(rsi_data_dict.keys(), key=lambda x: x[1])[1]

        macd_data_dict = {
            (macd.symbol, macd.opening_ts): macd
            for macd in await MacdTable.select().where(
                MacdTable.symbol == self.symbol,
                MacdTable.interval_val == self.interval,
            ).order_by(MacdTable.id.desc()).limit(3).aio_execute()
        }
        if not macd_data_dict:
            await self._init_macd_data()
        else:
            macd_start_ts = min(macd_data_dict.keys(), key=lambda x: x[1])[1]

        kdj_data_dict = {
            (kdj.symbol, kdj.open_ts): kdj
            for kdj in await KdjTable.select().where(
                KdjTable.symbol == self.symbol,
                KdjTable.interval_val == self.interval,
            ).order_by(KdjTable.id.desc()).limit(3).aio_execute()
        }
        if not kdj_data_dict:
            await self._init_kdj_data()
        else:
            prev_kdj = kdj_data_dict[min(kdj_data_dict.keys(), key=lambda x: x[1])]
            prev_kdj_ts = prev_kdj.open_ts
            kdj_cfg = json.loads(prev_kdj.cfg)
            period = kdj_cfg["period"]
            # 计算 KDJ 所需的最小时间
            min_start_ts = prev_kdj_ts - period * self.interval_sec
            # 确保查询 K 线数据的起始时间能够覆盖最小时间
            kdj_start_ts = min(prev_kdj_ts - self.k_interval, min_start_ts)

        bb_data_dict = {
            (bb.symbol, bb.open_ts): bb
            for bb in await BollTable.select().where(
                BollTable.symbol == self.symbol,
                BollTable.interval_val == self.interval,
            ).order_by(BollTable.id.desc()).limit(3).aio_execute()
        }
        if not bb_data_dict:
            await self._init_bb_data()
        else:
            prev_bb = bb_data_dict[min(bb_data_dict.keys(), key=lambda x: x[1])]
            bb_start_ts = prev_bb.open_ts - self.interval_sec * prev_bb.period

        if start_ts := min(rsi_start_ts, macd_start_ts, kdj_start_ts, bb_start_ts):
            await self.update_indicators(start_ts, rsi_data_dict, macd_data_dict, kdj_data_dict, bb_data_dict)

    async def _get_klines_for_init(self, dataset_length):
        # start_ts = self.curr_time - self.interval_sec * dataset_length

        db_klines = await KlineTable.select().where(
            KlineTable.symbol == self.symbol,
            KlineTable.interval_val == self.interval,
            # KlineTable.open_ts >= start_ts,
        ).order_by(KlineTable.id.desc()).limit(dataset_length).aio_execute()
        # 正序
        db_klines = list(db_klines)
        if len(db_klines) < dataset_length:
            return

        return db_klines[::-1][:-1] # 去掉最新k线

    async def _init_kdj_data(self):
        klines_data = await self._get_klines_for_init(KDJIndicator.dataset_length)
        if not klines_data:
            return

        init_info = KDJIndicator.get_origin_kdj(klines_data)
        if not init_info:
            return

        kdj_cfg = {
            "period": KDJIndicator.default_period,
            "move_average_period1": KDJIndicator.default_avg_move_1,
            "move_average_period2": KDJIndicator.default_avg_move_2,
        }
        await KdjTable.aio_create(
            symbol=self.symbol,
            interval_val=self.interval,
            open_ts=klines_data[-1].open_ts,
            k_val=init_info["k_val"],
            d_val=init_info["d_val"],
            j_val=init_info["j_val"],
            cfg=json.dumps(kdj_cfg),
        )

    async def _init_macd_data(self):
        klines_data = await self._get_klines_for_init(MACDIndicator.dataset_length)
        if not klines_data:
            return

        init_info = MACDIndicator.get_origin_macd([i.close_price for i in klines_data])
        if not init_info:
            return

        await MacdTable.aio_create(
            symbol=self.symbol,
            interval_val=self.interval,
            opening_ts=klines_data[-1].open_ts,
            opening_price=klines_data[-1].open_price,
            closing_price=klines_data[-1].close_price,
            ema_12=init_info["fast_ema"],
            ema_26=init_info["slow_ema"],
            dea=init_info["dea"],
            macd=init_info["macd"],
        )

    async def _init_rsi_data(self):
        klines_data = await self._get_klines_for_init(RSIIndicator.dataset_length)
        if not klines_data:
            return

        init_info = RSIIndicator.get_origin_rsi([i.close_price for i in klines_data])
        if not init_info:
            return

        await RsiTable.aio_create(
            symbol=self.symbol,
            interval_val=self.interval,
            open_ts=klines_data[-1].open_ts,
            rsi=init_info["rsi"],
            avg_gain=init_info["avg_gain"],
            avg_loss=init_info["avg_loss"],
            period=self.default_rsi_period,
        )

    async def _init_bb_data(self):
        klines_data = await self._get_klines_for_init(BollIndicator.dataset_length)
        if not klines_data:
            return

        init_info = BollIndicator.get_origin_bb(klines_data)
        if not init_info:
            return

        await BollTable.aio_create(
            symbol=self.symbol,
            interval_val=self.interval,
            open_ts=init_info["open_ts"],
            bbupper=init_info["bb_upper"],
            bbmid=init_info["bb_mid"],
            bblower=init_info["bb_lower"],
            sum_close=init_info["sum_close"],
            sum_sq_close=init_info["sum_sq_close"],
            period=init_info["period"],
        )

    async def update_indicators(self, start_ts, rsi_data_dict, macd_data_dict, kdj_data_dict, bb_data_dict):
        db_kline = await KlineTable.select().where(
            KlineTable.symbol == self.symbol,
            KlineTable.interval_val == self.interval,
            KlineTable.open_ts >= start_ts,
        ).order_by(KlineTable.id).aio_execute()
        # 正序
        db_kline = list(db_kline)

        async with async_database.aio_atomic(): # 长事务，消耗内存占用，提升性能
            for index, k in enumerate(db_kline):
                open_ts = k.open_ts
                close_price = k.close_price

                if prev_rsi_data := rsi_data_dict.get((self.symbol, open_ts - self.interval_sec)):
                    curr_rsi_info = RSIIndicator.calculate_rsi_incremental(
                        prev_rsi_data.rsi, prev_rsi_data.avg_gain, prev_rsi_data.avg_loss,
                        close_price, db_kline[index - 1].close_price, period=self.default_rsi_period
                    )

                    if curr_rsi_data := rsi_data_dict.get((self.symbol, open_ts)):
                        curr_rsi_data.rsi = curr_rsi_info["rsi"]
                        curr_rsi_data.avg_gain = curr_rsi_info["avg_gain"]
                        curr_rsi_data.avg_loss = curr_rsi_info["avg_loss"]
                        await curr_rsi_data.aio_save()
                    else:
                        inst = await RsiTable.aio_create(
                            symbol=self.symbol,
                            interval_val=self.interval,
                            open_ts=open_ts,
                            rsi=curr_rsi_info["rsi"],
                            avg_gain=curr_rsi_info["avg_gain"],
                            avg_loss=curr_rsi_info["avg_loss"],
                            period=self.default_rsi_period,
                        )
                        rsi_data_dict[(self.symbol, open_ts)] = inst

                if prev_macd_data := macd_data_dict.get((self.symbol, open_ts - self.interval_sec)):
                    curr_macd_info = MACDIndicator.calculate_macd_incremental(
                        close_price, prev_macd_data.ema_12, prev_macd_data.ema_26, prev_macd_data.dea
                    )

                    if now_macd := macd_data_dict.get((self.symbol, open_ts)):
                        now_macd.closing_price = close_price
                        now_macd.ema_12 = curr_macd_info["fast_ema"]
                        now_macd.ema_26 = curr_macd_info["slow_ema"]
                        now_macd.dea = curr_macd_info["dea"]
                        now_macd.macd = curr_macd_info["macd"]
                        await now_macd.aio_save()
                    else:
                        inst = await MacdTable.aio_create(
                            symbol=self.symbol,
                            interval_val=self.interval,
                            opening_ts=open_ts,
                            opening_price=k.open_price,
                            closing_price=close_price,
                            ema_12=curr_macd_info["fast_ema"],
                            ema_26=curr_macd_info["slow_ema"],
                            dea=curr_macd_info["dea"],
                            macd=curr_macd_info["macd"],
                        )
                        macd_data_dict[(self.symbol, open_ts)] = inst

                if prev_kdj_data := kdj_data_dict.get((self.symbol, open_ts - self.interval_sec)):
                    kdj_cfg = json.loads(prev_kdj_data.cfg)
                    period = kdj_cfg["period"]

                    period_k_lines = [kl for kl in db_kline
                                      if kl.open_ts <= open_ts and kl.open_ts > open_ts - period * self.interval_sec]
                    curr_kdj_info = KDJIndicator.calculate_kdj_incremental(
                        period_k_lines, prev_kdj_data.k_val, prev_kdj_data.d_val, period=period
                    )

                    if curr_kdj_data := kdj_data_dict.get((self.symbol, open_ts)):
                        curr_kdj_data.k_val = curr_kdj_info["k_val"]
                        curr_kdj_data.d_val = curr_kdj_info["d_val"]
                        curr_kdj_data.j_val = curr_kdj_info["j_val"]
                        await curr_kdj_data.aio_save()
                    else:
                        inst = await KdjTable.aio_create(
                            symbol=self.symbol,
                            interval_val=self.interval,
                            open_ts=open_ts,
                            k_val=curr_kdj_info["k_val"],
                            d_val=curr_kdj_info["d_val"],
                            j_val=curr_kdj_info["j_val"],
                            cfg=prev_kdj_data.cfg,
                        )
                        kdj_data_dict[(self.symbol, open_ts)] = inst

                if prev_bb_data := bb_data_dict.get((self.symbol, open_ts - self.interval_sec)):
                    # curr_bb_info = BollIndicator.calculate_bb_incremental(
                    #     db_kline, prev_bb_data.open_ts, prev_bb_data.sum_close, prev_bb_data.sum_sq_close
                    # )

                    prices = BollIndicator.get_close_prices_list(db_kline, open_ts)
                    curr_bb_info = BollIndicator.get_origin_bb(prices)

                    if curr_bb_data := bb_data_dict.get((self.symbol, open_ts)):
                        curr_bb_data.bbupper = curr_bb_info["bb_upper"]
                        curr_bb_data.bbmid = curr_bb_info["bb_mid"]
                        curr_bb_data.bblower = curr_bb_info["bb_lower"]
                        curr_bb_data.sum_close = curr_bb_info["sum_close"]
                        curr_bb_data.sum_sq_close = curr_bb_info["sum_sq_close"]
                        curr_bb_data.period = curr_bb_info["period"]
                        await curr_rsi_data.aio_save()
                    else:
                        inst = await BollTable.aio_create(
                            symbol=self.symbol,
                            interval_val=self.interval,
                            open_ts=open_ts,
                            bbupper=curr_bb_info["bb_upper"],
                            bbmid=curr_bb_info["bb_mid"],
                            bblower=curr_bb_info["bb_lower"],
                            sum_close=curr_bb_info["sum_close"],
                            sum_sq_close=curr_bb_info["sum_sq_close"],
                            period=curr_bb_info["period"],
                        )
                        bb_data_dict[(self.symbol, open_ts)] = inst
