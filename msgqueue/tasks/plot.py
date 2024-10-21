#! /usr/bin/env python
# coding:utf8

import hashlib
import time
from decimal import Decimal

from business.market import MarketPriceHandler
from cache.plot import CheckMacdCrossGateCache, CheckMacdTrendGateCache,\
    CheckKdjCrossGateCache, CheckKdjCvGateCache
from models.order import MacdTable, SymbolPlotTable, KdjTable
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
from utils.common import decimal2str, str2decimal, ts2bjfmt
from utils.templates import (template_asset_notice, template_macd_cross_notice,
                             template_macd_trend_notice, template_kdj_cross_notice)


async def check_price(*args, **kwargs):
    market_price_handler = MarketPriceHandler()
    for symbol, price in market_price_handler.get_all_limit_price().items():
        await PlotPriceHandle(symbol, price).check_limit_price()


async def check_balance(*args, **kwargs):
    await PlotAssetHandle().check_balance()


async def check_macd_cross(*args, **kwargs):
    query = SymbolPlotTable.select().where(SymbolPlotTable.is_valid == True)
    for row in query:
        for _interval in PLOT_INTERVAL_LIST:
            if not CheckMacdCrossGateCache.hget(f"{row.symbol}:{_interval}"):
                continue
            await PlotMacdHandle(row.symbol, _interval).check_cross()


async def check_macd_trend(*args, **kwargs):
    query = SymbolPlotTable.select().where(SymbolPlotTable.is_valid == True)
    for row in query:
        for _interval in PLOT_INTERVAL_LIST:
            if not CheckMacdTrendGateCache.hget(f"{row.symbol}:{_interval}"):
                continue
            await PlotMacdHandle(row.symbol, _interval).check_trend()


async def check_kdj_cross(*args, **kwargs):
    query = SymbolPlotTable.select().where(SymbolPlotTable.is_valid == True)
    for row in query:
        for _interval in PLOT_INTERVAL_LIST:
            if not CheckKdjCrossGateCache.hget(f"{row.symbol}:{_interval}"):
                continue
            await PlotKdjHandle(row.symbol, _interval).check_cross()


async def check_kdj_cv(*args, **kwargs):
    pass


class BasePlotHandle(object):
    def __init__(self):
        self.result = {}

    def send_msg_unsync(self, email_title, email_content):
        if not self.result:
            return

        from business.mail_serve import send_email
        send_email([
                    "wayley@live.com",
                ], email_title, email_content)

    async def send_msg(self, email_title, email_content):
        if not self.result:
            return

        from msgqueue.queue import push

        await push(
            {
                "bp": "send_email_task",
                "receiver": [
                    "wayley@live.com",
                ],
                "title": email_title,
                "content": email_content,
            }
        )


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
        limit_low_price, limit_high_price = price

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
        <br><br><b> {self.symbol}: </b><br>new low price:{current_price},
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
        <br><br><b> {self.symbol}: </b><br>new high price:{current_price},
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

    def check_limit_price_unsync(self):
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
            return EmailMsgHistoryTable.get(
                EmailMsgHistoryTable.msg_md5 == email_msg_md5
            )
        except EmailMsgHistoryTable.DoesNotExist:
            pass

        email_content = "".join(self.result.values())
        EmailMsgHistoryTable.create(msg_md5=email_msg_md5, msg_content=email_content)
        self.send_msg_unsync(email_title, email_content)

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
            return EmailMsgHistoryTable.get(
                EmailMsgHistoryTable.msg_md5 == email_msg_md5
            )
        except EmailMsgHistoryTable.DoesNotExist:
            pass

        email_content = "".join(self.result.values())
        EmailMsgHistoryTable.create(msg_md5=email_msg_md5, msg_content=email_content)
        await self.send_msg(email_title, email_content)


class PlotMacdHandle(BasePlotHandle):
    def __init__(self, symbol, interval):
        super().__init__()
        self.symbol = symbol
        self.interval = interval
        self.interval_sec = PLOT_INTERVAL_CONFIG[interval]["interval_sec"]
        self.k_interval = PLOT_INTERVAL_CONFIG[interval]["k_interval"]

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

    def check_cross_unsync(self, limit_count=7):
        email_title = f"{self.symbol} MACD Cross changing Notice"

        if not self.interval:
            return

        query = (
            MacdTable.select()
            .where(
                MacdTable.symbol == self.symbol,
                MacdTable.interval_val == self.interval,
            )
            .order_by(MacdTable.id.desc())
            .limit(limit_count)
        )
        macd_list = [i for i in query]

        if not macd_list:
            self.result[
                self.symbol
            ] = f"""
            <br><a>Error: not macd data, {self.symbol}:{self.interval}</a>
            <br><a href={INNER_GET_DELETE_MACD_CROSS_URL}{self.symbol + '_' + self.interval}>Delete cross check.</a>
            """
            return self.send_msg_unsync(email_title, "".join(self.result.values()))
        elif len(macd_list) < limit_count:
            self.result[
                self.symbol
            ] = f"""
            <br><a>Error: too less macd data, {self.symbol}:{self.interval}</a>
            <br><a href={INNER_GET_DELETE_MACD_CROSS_URL}{self.symbol + '_' + self.interval}>Delete cross check.</a>
            """
            return self.send_msg_unsync(email_title, "".join(self.result.values()))

        now_macd_data, last_macd_data = macd_list[0], macd_list[1]

        now_ts = int(time.time())
        if now_macd_data.opening_ts < (now_ts - self.interval_sec * 7):
            self.result[
                self.symbol
            ] = f"""
            <br><a>Error: no lastest macd data, {self.symbol}:{self.interval}</a>
            <br><a>opening_ts:{ts2bjfmt(now_macd_data.opening_ts)}</a>
            <br><a>now_ts:{ts2bjfmt(now_ts)}</a>
            <br><a href={INNER_GET_DELETE_MACD_CROSS_URL}{self.symbol + '_' + self.interval}>Delete cross check.</a>
            """

            return self.send_msg_unsync(email_title, "".join(self.result.values()))

        if now_macd_data.macd * last_macd_data.macd > 0:
            return self.send_msg_unsync(email_title, "".join(self.result.values()))

        email_msg_md5_str = (
            f"check_cross:{self.symbol}:{self.interval}:{now_macd_data.opening_ts}"
        )
        email_msg_md5 = hashlib.md5(email_msg_md5_str.encode("utf8")).hexdigest()
        try:
            return EmailMsgHistoryTable.get(
                EmailMsgHistoryTable.msg_md5 == email_msg_md5
            )
        except EmailMsgHistoryTable.DoesNotExist:
            history_macd_list = [decimal2str(i.macd) for i in macd_list][::-1]
            self.result[self.symbol] = template_macd_cross_notice(
                self.symbol,
                self.interval,
                last_macd_data.macd,
                now_macd_data.macd,
                now_macd_data.opening_ts,
                history_macd_list,
            )

        email_content = "".join(self.result.values())
        EmailMsgHistoryTable.create(msg_md5=email_msg_md5, msg_content=email_content)
        self.send_msg_unsync(email_title, email_content)

    async def check_cross(self, limit_count=7):
        email_title = f"{self.symbol} MACD Cross changing Notice"

        if not self.interval:
            return

        query = (
            MacdTable.select()
            .where(
                MacdTable.symbol == self.symbol,
                MacdTable.interval_val == self.interval,
            )
            .order_by(MacdTable.id.desc())
            .limit(limit_count)
        )
        macd_list = [i for i in query]

        if not macd_list:
            self.result[
                self.symbol
            ] = f"""
            <br><a>Error: not macd data, {self.symbol}:{self.interval}</a>
            <br><a href={INNER_GET_DELETE_MACD_CROSS_URL}{self.symbol + '_' + self.interval}>Delete cross check.</a>
            """
            return await self.send_msg(email_title, "".join(self.result.values()))
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
            <br><a>Error: no lastest macd data, {self.symbol}:{self.interval}</a>
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
            return EmailMsgHistoryTable.get(
                EmailMsgHistoryTable.msg_md5 == email_msg_md5
            )
        except EmailMsgHistoryTable.DoesNotExist:
            history_macd_list = [decimal2str(i.macd) for i in macd_list][::-1]
            self.result[self.symbol] = template_macd_cross_notice(
                self.symbol,
                self.interval,
                last_macd_data.macd,
                now_macd_data.macd,
                now_macd_data.opening_ts,
                history_macd_list,
            )

        email_content = "".join(self.result.values())
        EmailMsgHistoryTable.create(msg_md5=email_msg_md5, msg_content=email_content)
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

    def check_cross_unsync(self, limit_count=7):
        email_title = f"{self.symbol} KDJ Cross changing Notice"

        if not self.interval:
            return

        query = (
            KdjTable.select()
            .where(
                KdjTable.symbol == self.symbol,
                KdjTable.interval_val == self.interval,
            )
            .order_by(KdjTable.id.desc())
            .limit(limit_count)
        )
        query_list = [i for i in query]

        if not query_list:
            self.result[
                self.symbol
            ] = f"""
            <br><a>Error: not kdj data, {self.symbol}:{self.interval}</a>
            <br><a href={INNER_GET_DELETE_KDJ_CROSS_URL}{self.symbol + '_' + self.interval}>Delete cross check.</a>
            """
            return self.send_msg_unsync(email_title, "".join(self.result.values()))
        elif len(query_list) < limit_count:
            self.result[
                self.symbol
            ] = f"""
            <br><a>Error: too less kdj data, {self.symbol}:{self.interval}</a>
            <br><a href={INNER_GET_DELETE_KDJ_CROSS_URL}{self.symbol + '_' + self.interval}>Delete cross check.</a>
            """
            return self.send_msg_unsync(email_title, "".join(self.result.values()))

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

            return self.send_msg_unsync(email_title, "".join(self.result.values()))

        if (now_data.d_val <= now_data.j_val and last_data.d_val <= last_data.j_val) or (
            now_data.d_val >= now_data.j_val and last_data.d_val >= last_data.j_val
        ):
            return self.send_msg_unsync(email_title, "".join(self.result.values()))

        email_msg_md5_str = (
            f"check_cross:{self.symbol}:{self.interval}:{now_data.open_ts}"
        )
        email_msg_md5 = hashlib.md5(email_msg_md5_str.encode("utf8")).hexdigest()
        try:
            return EmailMsgHistoryTable.get(
                EmailMsgHistoryTable.msg_md5 == email_msg_md5
            )
        except EmailMsgHistoryTable.DoesNotExist:
            self.result[self.symbol] = self.reformat_kdj_cross_notice(last_data, now_data)

        email_content = "".join(self.result.values())
        EmailMsgHistoryTable.create(msg_md5=email_msg_md5, msg_content=email_content)
        self.send_msg_unsync(email_title, email_content)

    async def check_cross(self, limit_count=7):
        email_title = f"{self.symbol} KDJ Cross changing Notice"

        if not self.interval:
            return

        query = (
            KdjTable.select()
            .where(
                KdjTable.symbol == self.symbol,
                KdjTable.interval_val == self.interval,
            )
            .order_by(KdjTable.id.desc())
            .limit(limit_count)
        )
        query_list = [i for i in query]

        if not query_list:
            self.result[
                self.symbol
            ] = f"""
            <br><a>Error: not kdj data, {self.symbol}:{self.interval}</a>
            <br><a href={INNER_GET_DELETE_KDJ_CROSS_URL}{self.symbol + '_' + self.interval}>Delete cross check.</a>
            """
            return await self.send_msg(email_title, "".join(self.result.values()))
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
            return EmailMsgHistoryTable.get(
                EmailMsgHistoryTable.msg_md5 == email_msg_md5
            )
        except EmailMsgHistoryTable.DoesNotExist:
            self.result[self.symbol] = self.reformat_kdj_cross_notice(last_data, now_data)

        email_content = "".join(self.result.values())
        EmailMsgHistoryTable.create(msg_md5=email_msg_md5, msg_content=email_content)
        await self.send_msg(email_title, email_content)

    def reformat_kdj_cross_notice(self, last_data, now_data):
        if now_data.d_val > now_data.j_val:
            cross_str = "NEGATIVE"
        else:
            cross_str = "POSITIVE"

        macd_result = []
        query = (
            MacdTable.select().where(
                MacdTable.symbol == self.symbol,
                MacdTable.interval_val == self.interval,
            ).order_by(MacdTable.id.desc()).limit(3)
        )
        for row in query:
            macd_result.append(decimal2str(row.macd))

        return template_kdj_cross_notice(self.symbol, self.interval, cross_str, macd_result[::-1], now_data.open_ts)

    async def check_trend(self):
        pass
