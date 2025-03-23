#! /usr/bin/env python
# coding:utf8

import hashlib
import logging
import time
from decimal import Decimal

from exts import async_database
from cache import AllCache
from business.market import MarketPriceHandler
from business.back_test import BackTestHandler
from cache.plot import CheckMacdCrossGateCache, CheckMacdTrendGateCache,\
    CheckKdjCrossGateCache, CheckKdjCvGateCache
from models.order import MacdTable, SymbolPlotTable, KdjTable, EmaTable, PlotBackTestTable
from models.market import KlineTable
from models.user import EmailMsgHistoryTable
from models.wallet import TotalBalanceHistoryTable
from settings.constants import (INNER_GET_DELETE_LIMIT_PRICE_URL,
                                INNER_GET_DELETE_MACD_CROSS_URL,
                                INNER_GET_DELETE_MACD_TREND_URL,
                                INNER_GET_DELETE_KDJ_CROSS_URL,
                                INNER_GET_PRICE_URL,
                                INNER_GET_UPDATE_PRICE_URL,
                                PLOT_INTERVAL_LIST, PLOT_INTERVAL_CONFIG,
                                )
from utils.common import decimal2str, str2decimal, ts2bjfmt, check_lock_latest
from utils.templates import (template_asset_notice, template_macd_cross_notice,
                             template_macd_trend_notice, template_kdj_cross_notice, template_ema_cross_notice)
from msgqueue.queue import push_plot_mq

from .base import BasePlotHandle, get_plot_symbols_info
from .plot_gpt import PlotGptHandle

logger = logging.getLogger(__name__)


async def check_price(*args, **kwargs):
    market_price_handler = MarketPriceHandler()

    all_curr_prices = market_price_handler.get_current_price_by_cache()
    await BackTestHandler().update_real_ticket(all_curr_prices)

    for symbol, price in market_price_handler.get_all_limit_price().items():
        await PlotPriceHandle(symbol, price).check_limit_price()


async def check_balance(*args, **kwargs):
    await PlotAssetHandle().check_balance()


async def check_macd_cross(*args, **kwargs):
    logger.debug("check_macd_cross")
    redis_client = AllCache.get_client()
    symbols_info = await get_plot_symbols_info(redis_client)
    for symbol, _info in symbols_info.items():
        if not int(_info.get("valid", 0)):
            continue

        await push_plot_mq({
            "bp": "check_macd_cross_by_symbol",
            "symbol": symbol,
        })
    redis_client.close()


async def check_macd_cross_by_symbol(msg):
    symbol = msg.get("symbol")

    redis_client = AllCache.get_client()
    symbols_info = await get_plot_symbols_info(redis_client)
    _info = symbols_info.get(symbol)
    for _interval in PLOT_INTERVAL_LIST:
        if f"macd:{_interval}" not in _info:
            continue
        elif not CheckMacdCrossGateCache.hget(f"{symbol}:{_interval}"):
            continue
        await PlotMacdHandle(symbol, _interval).check_cross(symbol, _interval)
    redis_client.close()


async def check_macd_trend(*args, **kwargs):
    query = SymbolPlotTable.select().where(SymbolPlotTable.is_valid == True)
    for row in query:
        for _interval in PLOT_INTERVAL_LIST:
            if not CheckMacdTrendGateCache.hget(f"{row.symbol}:{_interval}"):
                continue
            await PlotMacdHandle(row.symbol, _interval).check_trend()


async def check_kdj_cross(*args, **kwargs):
    logger.debug("check_kdj_cross")
    redis_client = AllCache.get_client()
    symbols_info = await get_plot_symbols_info(redis_client)
    for symbol, _info in symbols_info.items():
        if not int(_info.get("valid", 0)):
            continue

        await push_plot_mq({
            "bp": "check_kdj_cross_by_symbol",
            "symbol": symbol,
        })
    redis_client.close()


async def check_kdj_cross_by_symbol(msg):
    symbol = msg.get("symbol")

    redis_client = AllCache.get_client()
    symbols_info = await get_plot_symbols_info(redis_client)
    _info = symbols_info.get(symbol)
    for _interval in PLOT_INTERVAL_LIST:
        if f"macd:{_interval}" not in _info:
            continue
        elif not CheckKdjCrossGateCache.hget(f"{symbol}:{_interval}"):
            continue
        await PlotKdjHandle(symbol, _interval).check_cross(symbol, _interval)
    redis_client.close()


async def check_ema_cross(*args, **kwargs):
    logger.debug("check_ema_cross")
    symbol_list = ["wifusdt", ]
    for symbol in symbol_list:
        for _interval in PLOT_INTERVAL_LIST:
            # if not CheckKdjCrossGateCache.hget(f"{row.symbol}:{_interval}"):
            #     continue
            await PlotEmaHandle(symbol, _interval).check_cross()


async def check_gpt_plot(*args, **kwargs):
    logger.debug("check_gpt_plot")

    redis_client = AllCache.get_client()

    symbols_info = await get_plot_symbols_info(redis_client)
    for symbol in symbols_info.keys():
        if symbol.lower() == "btcusdt":
            continue
        await push_plot_mq({
            "bp": "check_gpt_plot_job_by_symbol",
            "symbol": symbol,
        })
    redis_client.close()


async def check_gpt_plot_job_by_symbol(val):
    symbol = val.get("symbol")
    if not symbol:
        logger.error(f"check_gpt_plot_job_by_symbol, {val}")
        return
    await PlotGptHandle(symbol).check()


async def check_kdj_cv(*args, **kwargs):
    pass


class PlotAssetHandle(BasePlotHandle):
    def __init__(self):
        super(PlotAssetHandle, self).__init__()
        self.user_id = 2
        self.exchange_platform = "binance"

    async def check_balance(self, limit_count=9):
        # TODO: 需要处理 当日净充值和净划入
        self.result["check_balance"] = []

        query = (
            TotalBalanceHistoryTable.select()
            .where(
                TotalBalanceHistoryTable.user_id == self.user_id,
                TotalBalanceHistoryTable.exchange_platform == self.exchange_platform,
            )
            .order_by(TotalBalanceHistoryTable.id.desc())
            .limit(limit_count)
        )
        query_data = [row for row in query][::-1]
        for i, row in enumerate(query_data):
            if i == 0:
                profit_amount, profit_ratio = "", ""
            else:
                profit_amount = row.usdt_val - Decimal(query_data[i - 1].usdt_val)
                profit_ratio = "{}%".format(
                    decimal2str(
                        (profit_amount / Decimal(query_data[i - 1].usdt_val)) * 100,
                        num=2,
                    )
                )
                profit_amount = (
                    f"+${decimal2str(profit_amount, num=2)}"
                    if profit_amount > 0
                    else f"-${decimal2str(profit_amount, num=2)[1:]}"
                )

            self.result["check_balance"].append(
                template_asset_notice(
                    decimal2str(row.btcusdt_price, num=2),
                    decimal2str(row.btc_val, num=2),
                    decimal2str(row.usdt_val, num=2),
                    row.create_ts,
                    profit_amount,
                    profit_ratio,
                )
            )

        email_msg_md5_str = f"check_balance:{query_data[-1].create_ts}"
        email_msg_md5 = hashlib.md5(email_msg_md5_str.encode("utf8")).hexdigest()
        try:
            return EmailMsgHistoryTable.get(
                EmailMsgHistoryTable.msg_md5 == email_msg_md5
            )
        except EmailMsgHistoryTable.DoesNotExist:
            pass

        email_content = "".join(self.result["check_balance"][::-1])
        EmailMsgHistoryTable.create(msg_md5=email_msg_md5, msg_content=email_content)
        email_title = f"check_balance"
        await self.send_msg(email_title, email_content)


class PlotPriceHandle(BasePlotHandle):
    def __init__(self, symbol, price):
        super().__init__()
        set_time, limit_low_price, limit_high_price = price

        self.symbol = symbol
        self.limit_low_price = limit_low_price
        self.limit_high_price = limit_high_price
        self.market_price_handler = MarketPriceHandler()
        self.init_plot_indicator()

    def init_plot_indicator(self):
        self.low_incr = "0.95"
        self.high_incr = "1.05"

    def __get_current_price(self):
        cache_result = self.market_price_handler.get_current_price_by_cache(self.symbol)
        if not cache_result:
            self.result[
                self.symbol
            ] = f"""
            <br><br><b> {self.symbol}: </b><br>http get price fail.
            <br><a href={INNER_GET_PRICE_URL}{self.symbol}>Get current price info.</a>
            <br>now time: {ts2bjfmt()}.<a>
            <br><a href={INNER_GET_DELETE_LIMIT_PRICE_URL}{self.symbol}>Delete price check.<a>
            """
            return

        current_price = str2decimal(cache_result)
        return current_price

    def __check_limit_low_price(self, current_price):
        if not self.limit_low_price:
            return
        if current_price > self.limit_low_price:
            return

        self.result[
            self.symbol
        ] = f"""
        <br><br><b> {self.symbol}: </b><br>‼️ new low price:{current_price},
        <br>last limit low price:{self.limit_low_price} !!!
        <br><a href={INNER_GET_PRICE_URL}{self.symbol}>Get current price info.</a>
        <br><a href={INNER_GET_UPDATE_PRICE_URL}{"low"}/{self.symbol}/>Update new low price.<a>
        <br>now time: {ts2bjfmt()}.<a>
        <br><a href={INNER_GET_DELETE_LIMIT_PRICE_URL}{self.symbol}>Delete price check.<a>
        """

        # TODO:脚本任务, 自动调整本地限价, 同时调用API调整server限价
        # self.market_price_handler.set_limit_price(
        #     self.symbol,
        #     Decimal(decimal2str(self.limit_low_price * Decimal(self.low_incr))),
        #     Decimal(decimal2str(self.limit_high_price * Decimal(self.low_incr))),
        # )

    def __check_limit_high_price(self, current_price):
        if not self.limit_high_price:
            return
        if current_price < self.limit_high_price:
            return

        self.result[
            self.symbol
        ] = f"""
        <br><br><b> {self.symbol}: </b><br>💰💰 new high price:{current_price},
        <br>last limit high price:{self.limit_high_price} !!!
        <br><a href={INNER_GET_PRICE_URL}{self.symbol}>Get current price info.</a>
        <br><a href={INNER_GET_UPDATE_PRICE_URL}{"high"}/{self.symbol}/>Update new high price.<a>
        <br>now time: {ts2bjfmt()}.<a>
        <br><a href={INNER_GET_DELETE_LIMIT_PRICE_URL}{self.symbol}>Delete price check.<a>
        """

        # TODO:脚本任务, 自动调整本地限价, 同时调用API调整server限价
        # self.market_price_handler.set_limit_price(
        #     self.symbol,
        #     Decimal(decimal2str(self.limit_low_price * Decimal(self.high_incr))),
        #     Decimal(decimal2str(self.limit_high_price * Decimal(self.high_incr))),
        # )

    async def check_limit_price(self):
        email_title = f"{self.symbol} Price Notice"

        current_price = self.__get_current_price()
        if not current_price:
            return await self.send_msg(email_title, "".join(self.result.values()))

        self.__check_limit_low_price(current_price)
        self.__check_limit_high_price(current_price)

        if not self.result:
            return

        email_msg_md5_str = f"check_limit_price:{self.symbol}:{self.limit_low_price}:{self.limit_high_price}"
        email_msg_md5 = hashlib.md5(email_msg_md5_str.encode("utf8")).hexdigest()
        try:
            # 当前限价检查存在时，不再推送消息
            return await EmailMsgHistoryTable.aio_get(
                EmailMsgHistoryTable.msg_md5 == email_msg_md5
            )
        except EmailMsgHistoryTable.DoesNotExist:
            pass

        email_content = "".join(self.result.values())
        await EmailMsgHistoryTable.aio_create(msg_md5=email_msg_md5, msg_content=email_content)
        await self.send_msg(email_title, email_content)


class PlotMacdHandle(BasePlotHandle):
    def __init__(self, symbol, interval):
        super().__init__()
        self.symbol = symbol
        self.interval = interval
        self.interval_sec = PLOT_INTERVAL_CONFIG[interval]["interval_sec"]
        self.k_interval = PLOT_INTERVAL_CONFIG[interval]["k_interval"]

    async def get_btc_macd(self):
        result = {}
        for _interval in PLOT_INTERVAL_LIST:
            if _interval not in ["1h", "4h", "1d"]:
                result[_interval] = ""
                continue

            current_data = await MacdTable.select().where(
                MacdTable.symbol == "btcusdt",
                MacdTable.interval_val == _interval,
            ).order_by(MacdTable.id.desc()).aio_get()

            macd_result = "正" if current_data.macd > 0 else "负"
            result[_interval] = macd_result
        return result

    async def get_current_macd(self):
        result = {}
        for _interval in PLOT_INTERVAL_LIST:

            try:
                current_data = await MacdTable.select().where(
                    MacdTable.symbol == self.symbol,
                    MacdTable.interval_val == _interval,
                ).order_by(MacdTable.id.desc()).aio_get()

                macd_result = "正" if current_data.macd > 0 else "负"
            except MacdTable.DoesNotExist:
                macd_result = ""
            result[_interval] = macd_result
        return result

    def get_macd_change_list(self, limit_count=7):
        result = []

        query = (
            MacdTable.select()
            .where(
                MacdTable.symbol == self.symbol,
                MacdTable.interval_val == self.interval,
            )
            .order_by(MacdTable.id.desc())
            .limit(limit_count)
        )
        for row in query:
            result.append(row)

        return result[::-1]

    @check_lock_latest("lock_macd_latest")
    async def check_cross(self, symbol, interval, limit_count=7):
        logger.info(
            f"PlotMacdHandle.check_cross start, symbol:{self.symbol}, interval:{self.interval}, ts:{int(time.time())}")
        email_title = f"{self.symbol} MACD Cross changing Notice"

        if not self.interval:
            return

        query = (
            await MacdTable.select()
            .where(
                MacdTable.symbol == self.symbol,
                MacdTable.interval_val == self.interval,
            )
            .order_by(MacdTable.id.desc())
            .limit(limit_count).aio_execute()
        )
        macd_list = [i for i in query]

        if not macd_list:
            return
        elif len(macd_list) < limit_count:
            self.result[
                self.symbol
            ] = f"""
            <br><a>Error: too less macd data, {self.symbol}:{self.interval}</a>
            <br><a href={INNER_GET_DELETE_MACD_CROSS_URL}{self.symbol + '_' + self.interval}>Delete cross check.</a>
            """
            return await self.send_msg(email_title, "".join(self.result.values()))

        now_macd_data, last_macd_data = macd_list[0], macd_list[1]

        now_ts = int(time.time())
        if now_macd_data.opening_ts < (now_ts - self.interval_sec * 7):
            self.result[
                self.symbol
            ] = f"""
            <br><a>Error: no latest macd data, {self.symbol}:{self.interval}</a>
            <br><a>opening_ts:{ts2bjfmt(now_macd_data.opening_ts)}</a>
            <br><a>now_ts:{ts2bjfmt(now_ts)}</a>
            <br><a href={INNER_GET_DELETE_MACD_CROSS_URL}{self.symbol + '_' + self.interval}>Delete cross check.</a>
            """

            return await self.send_msg(email_title, "".join(self.result.values()))

        if now_macd_data.macd * last_macd_data.macd > 0:
            return await self.send_msg(email_title, "".join(self.result.values()))

        email_msg_md5_str = (
            f"check_cross:{self.symbol}:{self.interval}:{now_macd_data.opening_ts}"
        )
        email_msg_md5 = hashlib.md5(email_msg_md5_str.encode("utf8")).hexdigest()
        try:
            return await EmailMsgHistoryTable.aio_get(EmailMsgHistoryTable.msg_md5 == email_msg_md5)
        except EmailMsgHistoryTable.DoesNotExist:
            if last_macd_data.macd > now_macd_data.macd:
                cross_str = "📉"
            else:
                cross_str = "📈"
            btc_kdj_list = await PlotKdjHandle(self.symbol, self.interval).get_btc_kdj()
            self.result[self.symbol] = template_macd_cross_notice(
                self.symbol,
                self.interval,
                cross_str,
                now_macd_data.opening_ts,
                await self.get_current_macd(),
                btc_kdj_list,
                await self.get_btc_macd()
            )

        email_content = "".join(self.result.values())
        await EmailMsgHistoryTable.aio_create(msg_md5=email_msg_md5, msg_content=email_content)

        logger.info(f"PlotMacdHandle.check_cross finish, start send_msg, symbol:{self.symbol}, interval:{self.interval}, ts:{int(time.time())}")
        await self.send_msg(email_title, email_content)

    async def check_trend(self):
        email_title = f"{self.symbol} MACD Trend changing Notice"
        limit_count = 11

        if not self.interval:
            return

        macd_list = self.get_macd_change_list(limit_count=limit_count)

        if not macd_list:
            self.result[
                self.symbol
            ] = f"""
            <br><a>Error: not macd data, {self.symbol}:{self.interval}</a>
            <br><a href={INNER_GET_DELETE_MACD_TREND_URL}{self.symbol + '_' + self.interval}>Delete trend check.</a>
            """
            # return await self.send_msg(email_title, "".join(self.result.values()))
            return
        elif len(macd_list) < limit_count:
            self.result[
                self.symbol
            ] = f"""
            <br><a>Error: too less macd data, {self.symbol}:{self.interval}</a>
            <br><a href={INNER_GET_DELETE_MACD_TREND_URL}{self.symbol + '_' + self.interval}>Delete trend check.</a>
            """
            return await self.send_msg(email_title, "".join(self.result.values()))

        now_macd_data, last_macd_data = macd_list[-1], macd_list[-2]
        # TODO:
        trend_val = last_macd_data.macd / now_macd_data.macd
        if trend_val < 0:
            return

        # 1h趋势零界:0.4
        if trend_val > 0.4:
            return

        email_msg_md5_str = (
            f"check_trend:{self.symbol}:{self.interval}:{now_macd_data.opening_ts}"
        )
        email_msg_md5 = hashlib.md5(email_msg_md5_str.encode("utf8")).hexdigest()
        try:
            return EmailMsgHistoryTable.get(
                EmailMsgHistoryTable.msg_md5 == email_msg_md5
            )
        except EmailMsgHistoryTable.DoesNotExist:
            history_macd_list = [decimal2str(i.macd) for i in macd_list]
            self.result[self.symbol] = template_macd_trend_notice(
                self.symbol,
                self.interval,
                last_macd_data.macd,
                now_macd_data.macd,
                trend_val,
                now_macd_data.opening_ts,
                history_macd_list,
            )

        email_content = "".join(self.result.values())
        EmailMsgHistoryTable.create(msg_md5=email_msg_md5, msg_content=email_content)
        await self.send_msg(email_title, email_content)


class PlotKdjHandle(BasePlotHandle):
    def __init__(self, symbol, interval):
        super().__init__()
        self.symbol = symbol
        self.interval = interval
        self.interval_sec = PLOT_INTERVAL_CONFIG[interval]["interval_sec"]
        self.k_interval = PLOT_INTERVAL_CONFIG[interval]["k_interval"]

    async def get_btc_kdj(self):
        result = {}
        for _interval in PLOT_INTERVAL_LIST:
            if _interval not in ["1h", "4h", "1d"]:
                result[_interval] = ""
                continue

            current_data = await KdjTable.select().where(
                KdjTable.symbol == "btcusdt",
                KdjTable.interval_val == _interval,
            ).order_by(KdjTable.id.desc()).aio_get()

            macd_result = "+" if current_data.d_val < current_data.j_val else "-"
            result[_interval] = macd_result
        return result

    @check_lock_latest("lock_kdj_latest")
    async def check_cross(self, symbol, interval, limit_count=7):
        logger.info(f"PlotKdjHandle.check_cross start, symbol:{self.symbol}, interval:{self.interval}, ts:{int(time.time())}")
        email_title = f"{self.symbol} KDJ Cross changing Notice"

        if not self.interval:
            return

        query = (
            await KdjTable.select()
            .where(
                KdjTable.symbol == self.symbol,
                KdjTable.interval_val == self.interval,
            )
            .order_by(KdjTable.id.desc())
            .limit(limit_count).aio_execute()
        )
        query_list = [i for i in query]

        if not query_list:
            return
            # TODO: optimize when only set part interval.
            # self.result[
            #     self.symbol
            # ] = f"""
            # <br><a>Error: not kdj data, {self.symbol}:{self.interval}</a>
            # <br><a href={INNER_GET_DELETE_KDJ_CROSS_URL}{self.symbol + '_' + self.interval}>Delete cross check.</a>
            # """
            # return await self.send_msg(email_title, "".join(self.result.values()))
        elif len(query_list) < limit_count:
            self.result[
                self.symbol
            ] = f"""
            <br><a>Error: too less kdj data, {self.symbol}:{self.interval}</a>
            <br><a href={INNER_GET_DELETE_KDJ_CROSS_URL}{self.symbol + '_' + self.interval}>Delete cross check.</a>
            """
            return await self.send_msg(email_title, "".join(self.result.values()))

        now_data, last_data = query_list[0], query_list[1]

        now_ts = int(time.time())
        if now_data.open_ts < (now_ts - self.interval_sec * 7):
            self.result[
                self.symbol
            ] = f"""
            <br><a>Error: no lastest kdj data, {self.symbol}:{self.interval}</a>
            <br><a>open_ts:{ts2bjfmt(now_data.open_ts)}</a>
            <br><a>now_ts:{ts2bjfmt(now_ts)}</a>
            <br><a href={INNER_GET_DELETE_KDJ_CROSS_URL}{self.symbol + '_' + self.interval}>Delete cross check.</a>
            """

            return await self.send_msg(email_title, "".join(self.result.values()))

        if (now_data.d_val <= now_data.j_val and last_data.d_val <= last_data.j_val) or (
            now_data.d_val >= now_data.j_val and last_data.d_val >= last_data.j_val
        ):
            return await self.send_msg(email_title, "".join(self.result.values()))

        email_msg_md5_str = (
            f"check_cross:{self.symbol}:{self.interval}:{now_data.open_ts}"
        )
        email_msg_md5 = hashlib.md5(email_msg_md5_str.encode("utf8")).hexdigest()
        try:
            return await EmailMsgHistoryTable.aio_get(
                EmailMsgHistoryTable.msg_md5 == email_msg_md5
            )
        except EmailMsgHistoryTable.DoesNotExist:
            self.result[self.symbol] = await self.reformat_kdj_cross_notice(last_data, now_data)

        email_content = "".join(self.result.values())
        await EmailMsgHistoryTable.aio_create(msg_md5=email_msg_md5, msg_content=email_content)

        logger.info(f"PlotKdjHandle.check_cross finish, start end_msg, symbol:{self.symbol}, interval:{self.interval}, ts:{int(time.time())}")
        await self.send_msg(email_title, email_content)

    async def reformat_kdj_cross_notice(self, last_data, now_data):
        if now_data.d_val > now_data.j_val:
            cross_str = "📉"
        else:
            cross_str = "📈"

        btc_kdj_list = await self.get_btc_kdj()
        macd_handler = PlotMacdHandle(self.symbol, self.interval)
        btc_macd_list = await macd_handler.get_btc_macd()
        new_macd_list = await macd_handler.get_current_macd()

        return template_kdj_cross_notice(
            self.symbol, self.interval, cross_str,
            new_macd_list, btc_kdj_list, btc_macd_list, now_data.open_ts)

    async def check_trend(self):
        pass


class PlotEmaHandle(BasePlotHandle):
    def __init__(self, symbol, interval):
        super().__init__()
        self.symbol = symbol
        self.interval = interval
        self.interval_sec = PLOT_INTERVAL_CONFIG[interval]["interval_sec"]
        self.k_interval = PLOT_INTERVAL_CONFIG[interval]["k_interval"]

    def get_ma_data(self, ema_data):
        query = (
            KlineTable.select()
                .where(
                KlineTable.symbol == self.symbol,
                KlineTable.interval_val == self.interval,
                KlineTable.open_ts <= ema_data.open_ts,
            )
                .order_by(KlineTable.id.desc())
                .limit(31)
        )
        query_list = [i for i in query]
        if len(query_list) < 31:
            return

        now_ma7 = Decimal(sum([i.close_price for i in query_list[:7]]) / 7)
        last_ma7 = Decimal(sum([i.close_price for i in query_list[1:8]]) / 7)
        now_ma20 = Decimal(sum([i.close_price for i in query_list[:20]]) / 20)
        last_ma20 = Decimal(sum([i.close_price for i in query_list[1:21]]) / 20)
        now_ma30 = Decimal(sum([i.close_price for i in query_list[:30]]) / 30)
        last_ma30 = Decimal(sum([i.close_price for i in query_list[1:31]]) / 30)
        return {
            "now_ma7": now_ma7, "last_ma7": last_ma7,
            "now_ma20": now_ma20, "last_ma20": last_ma20,
            "now_ma30": now_ma30, "last_ma30": last_ma30,
        }

    async def check_cross(self, limit_count=2):
        logger.info(f"PlotEmaHandle.check_cross start, symbol:{self.symbol}, interval:{self.interval}, ts:{int(time.time())}")
        email_title = f"{self.symbol} EMA Cross changing Notice"

        if not self.interval:
            return

        ema_query = (
            EmaTable.select()
            .where(
                EmaTable.symbol == self.symbol,
                EmaTable.interval_val == self.interval,
            )
            .order_by(EmaTable.id.desc())
            .limit(limit_count)
        )
        ema_query_list = [i for i in ema_query]

        if not ema_query_list:
            return
        elif len(ema_query_list) < limit_count:
            self.result[
                self.symbol
            ] = f"""
            <br><a>Error: too less ema data, {self.symbol}:{self.interval}</a>
            """
            return await self.send_msg(email_title, "".join(self.result.values()))

        now_ema_data, last_ema_data = ema_query_list[0], ema_query_list[1]
        ma_data_dict = self.get_ma_data(now_ema_data)
        if not ma_data_dict:
            self.result[
                self.symbol
            ] = f"""
                        <br><a>Error: too less ma data, {self.symbol}:{self.interval}</a>
                        """
            return await self.send_msg(email_title, "".join(self.result.values()))

        last_ema_positive = last_ema_data.ema7 > last_ema_data.ema20 \
                            and last_ema_data.ema7 > last_ema_data.ema30 \
                            and ma_data_dict["last_ma7"] > ma_data_dict["last_ma20"] \
                            and ma_data_dict["last_ma7"] > ma_data_dict["last_ma30"]

        last_ema_negative = last_ema_data.ema7 < last_ema_data.ema20 \
                            and last_ema_data.ema7 < last_ema_data.ema30 \
                            and ma_data_dict["last_ma7"] < ma_data_dict["last_ma20"] \
                            and ma_data_dict["last_ma7"] < ma_data_dict["last_ma30"]

        if last_ema_positive is False \
                and now_ema_data.ema7 > now_ema_data.ema20 \
                and now_ema_data.ema7 > now_ema_data.ema30 \
                and ma_data_dict["now_ma7"] > ma_data_dict["now_ma20"] \
                and ma_data_dict["now_ma7"] > ma_data_dict["now_ma30"]:
            return await self.__send_msg(email_title, now_ema_data, cross_str="📈")

        elif last_ema_negative is False \
                and now_ema_data.ema7 < now_ema_data.ema20 \
                and now_ema_data.ema7 < now_ema_data.ema30 \
                and ma_data_dict["now_ma7"] < ma_data_dict["now_ma20"] \
                and ma_data_dict["now_ma7"] < ma_data_dict["now_ma30"]:
            return await self.__send_msg(email_title, now_ema_data, cross_str="📉")

    async def __send_msg(self, email_title, now_ema_data, cross_str):
        email_msg_md5_str = (
            f"check_cross:{self.symbol}:{self.interval}:{now_ema_data.open_ts}"
        )
        email_msg_md5 = hashlib.md5(email_msg_md5_str.encode("utf8")).hexdigest()
        try:
            return EmailMsgHistoryTable.get(
                EmailMsgHistoryTable.msg_md5 == email_msg_md5
            )
        except EmailMsgHistoryTable.DoesNotExist:
            self.result[self.symbol] = template_ema_cross_notice(
                self.symbol, self.interval, cross_str, now_ema_data.open_ts)

        email_content = "".join(self.result.values())
        EmailMsgHistoryTable.create(msg_md5=email_msg_md5, msg_content=email_content)

        logger.info(f"PlotEmaHandle.check_cross finish, start end_msg, symbol:{self.symbol}, interval:{self.interval}, ts:{int(time.time())}")
        await self.send_msg(email_title, email_content, receiver_list=[])
