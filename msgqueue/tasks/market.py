#! /usr/bin/env python
# coding:utf8

import hashlib
import time
from decimal import Decimal

from business.binance_exchange import BinanceExchangeRequestHandle
from business.market import MarketPriceHandler
from cache import StringCache
from models.order import MacdTable, SymbolPlotTable
from models.user import EmailMsgHistoryTable
from settings.constants import INNER_GET_PRICE_URL, INNER_GET_UPDATE_PRICE_URL
from utils.common import decimal2str, str2decimal, ts2bjfmt
from utils.templates import (template_macd_cross_notice,
                             template_macd_trend_notice)


def parse_form_data(symbol):
    body = """
    <form action="{url}" method="POST" name="form">
        <p><label for="{}_price">New limit price:</label>
        <input type="text" name="" id="fname"></p>

        <p><label for="last_name">Last Name:</label>
        <input type="text" name="last_name" id="lname"></p>

        <input value="Submit" type="submit" onclick="submitform()">
    </form>
    """


async def check_price(*args, **kwargs):
    market_price_handler = MarketPriceHandler()
    for symbol, price in market_price_handler.get_all_limit_price().items():
        await PlotPriceHandle(symbol, price).check_limit_price()


async def check_macd_cross(*args, **kwargs):
    macd_config = ["4h", "1h", "1d"]
    query = SymbolPlotTable.select().where(SymbolPlotTable.is_valid == True)
    for row in query:
        for _interval in macd_config:
            await PlotMacdHandle(row.symbol, _interval).check_cross()


async def check_macd_trend(*args, **kwargs):
    macd_config = ["4h", "1h", "1d"]
    query = SymbolPlotTable.select().where(SymbolPlotTable.is_valid == True)
    for row in query:
        for _interval in macd_config:
            await PlotMacdHandle(row.symbol, _interval).check_trend()


async def save_macd(*args, **kwargs):
    macd_config = ["4h", "1h", "1d"]
    query = SymbolPlotTable.select().where(SymbolPlotTable.is_valid == True)
    for row in query:
        for _interval in macd_config:
            await MacdDataSaveHandle(row.symbol, _interval).save_data()


class BasePlotHandle(object):
    def __init__(self):
        self.result = {}

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
        current_price_info = self.market_price_handler.get_current_price(self.symbol)
        if "price" not in current_price_info:
            self.result[
                self.symbol
            ] = """
            <br><br><b> {}: </b><br>http get price fail.
            <br><a href={}{}>Get current price info.</a>
            <br>now time: {}.
            """.format(
                self.symbol, INNER_GET_PRICE_URL, self.symbol, ts2bjfmt()
            )
            return

        current_price = str2decimal(current_price_info["price"])
        return current_price

    def __check_limit_low_price(self, current_price):
        if not self.limit_low_price:
            return
        if current_price > self.limit_low_price:
            return

        self.result[
            self.symbol
        ] = """
        <br><br><b> {}: </b><br>new low price:{},
        <br>last limit low price:{} !!!
        <br><a href={}{}>Get current price info.</a>
        <br><a href={}{}/{}/>Update new low price.<a>
        <br>now time: {}.
        """.format(
            self.symbol,
            current_price,
            self.limit_low_price,
            INNER_GET_PRICE_URL,
            self.symbol,
            INNER_GET_UPDATE_PRICE_URL,
            "low",
            self.symbol,
            ts2bjfmt(),
        )

        self.market_price_handler.set_limit_price(
            self.symbol,
            Decimal(decimal2str(self.limit_low_price * Decimal(self.low_incr))),
            Decimal(decimal2str(self.limit_high_price * Decimal(self.low_incr))),
        )

    def __check_limit_high_price(self, current_price):
        if not self.limit_high_price:
            return
        if current_price < self.limit_high_price:
            return

        self.result[
            self.symbol
        ] = """
        <br><br><b> {}: </b><br>new high price:{},
        <br>last limit high price:{} !!!
        <br><a href={}{}>Get current price info.</a>
        <br><a href={}{}/{}/>Update new high price.<a>
        <br>now time: {}.
        """.format(
            self.symbol,
            current_price,
            self.limit_high_price,
            INNER_GET_PRICE_URL,
            self.symbol,
            INNER_GET_UPDATE_PRICE_URL,
            "high",
            self.symbol,
            ts2bjfmt(),
        )

        self.market_price_handler.set_limit_price(
            self.symbol,
            Decimal(decimal2str(self.limit_low_price * Decimal(self.high_incr))),
            Decimal(decimal2str(self.limit_high_price * Decimal(self.high_incr))),
        )

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
            return EmailMsgHistoryTable.get(
                EmailMsgHistoryTable.msg_md5 == email_msg_md5
            )
        except EmailMsgHistoryTable.DoesNotExist:
            pass

        email_content = "".join(self.result.values())
        EmailMsgHistoryTable.create(msg_md5=email_msg_md5, msg_content=email_content)
        await self.send_msg(email_title, email_content)


class MacdDataSaveHandle(object):
    def __init__(self, symbol, interval):
        self.symbol = symbol

        if interval == "4h":
            self.interval = "4h"
            self.interval_sec = 4 * 3600
            self.k_interval = 5 * 3600
        elif interval == "1h":
            self.interval = "1h"
            self.interval_sec = 3600
            self.k_interval = 5400
        elif interval == "1d":
            self.interval = "1d"
            self.interval_sec = 24 * 3600
            self.k_interval = 27 * 3600
        else:
            self.interval, self.interval_sec, self.k_interval = None, None, None

    def get_k_lines_by_openapi(self):
        try:
            db_last_macd = (
                MacdTable.select()
                .where(
                    MacdTable.symbol == self.symbol,
                    MacdTable.interval_val == self.interval,
                )
                .order_by(MacdTable.id.desc())
                .limit(1)
                .get()
            )
        except MacdTable.DoesNotExist:
            return

        resp_k = BinanceExchangeRequestHandle().get_k_lines(
            self.symbol.upper(),
            self.interval,
            (db_last_macd.opening_ts - self.k_interval) * 1000,
        )
        return resp_k

    def __parsed_k_lines_data(self, data):
        opening_ts = int(data[0] / 1000)
        opening_price = Decimal(data[1])
        closing_price = Decimal(data[4])

        _db_rs = (
            MacdTable.select()
            .where(
                MacdTable.symbol == self.symbol,
                MacdTable.interval_val == self.interval,
                MacdTable.opening_ts.in_([opening_ts - self.interval_sec, opening_ts]),
            )
            .order_by(MacdTable.id)
        )
        _db_rs = list(_db_rs)

        last_macd_data = _db_rs[0]
        if len(_db_rs) == 2:
            now_macd_data = _db_rs[1]
        else:
            now_macd_data = None

        now_ema_12 = last_macd_data.ema_12 * 11 / 13 + closing_price * 2 / 13
        now_ema_26 = last_macd_data.ema_26 * 25 / 27 + closing_price * 2 / 27
        now_dea = last_macd_data.dea * 8 / 10 + (now_ema_12 - now_ema_26) * 2 / 10
        # now_dif = now_ema_12 - now_ema_26
        now_macd = Decimal(decimal2str(now_ema_12 - now_ema_26 - now_dea, 2))
        if now_macd_data:
            now_macd_data.opening_ts = opening_ts
            now_macd_data.opening_price = opening_price
            now_macd_data.closing_price = closing_price
            now_macd_data.ema_12 = now_ema_12
            now_macd_data.ema_26 = now_ema_26
            now_macd_data.dea = now_dea
            now_macd_data.macd = now_macd
            now_macd_data.save()
        else:
            now_macd_data = MacdTable.create(
                symbol=self.symbol,
                interval_val=self.interval,
                opening_ts=opening_ts,
                opening_price=opening_price,
                closing_price=closing_price,
                ema_12=now_ema_12,
                ema_26=now_ema_26,
                dea=now_dea,
                macd=now_macd,
            )

    async def save_data(self):
        if not self.interval:
            return

        k_data = self.get_k_lines_by_openapi()
        if not k_data:
            return

        for _data in k_data:
            self.__parsed_k_lines_data(_data)


class PlotMacdHandle(BasePlotHandle):
    def __init__(self, symbol, interval):
        super().__init__()
        self.symbol = symbol

        if interval == "4h":
            self.interval = "4h"
            self.interval_sec = 4 * 3600
            self.k_interval = 5 * 3600
        elif interval == "1h":
            self.interval = "1h"
            self.interval_sec = 3600
            self.k_interval = 5400
        elif interval == "1d":
            self.interval = "1d"
            self.interval_sec = 24 * 3600
            self.k_interval = 27 * 3600
        else:
            self.interval, self.interval_sec, self.k_interval = None, None, None

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
            ] = f"Error: not macd data, {self.symbol}:{self.interval}"
            return await self.send_msg(email_title, "".join(self.result.values()))
        elif len(macd_list) < limit_count:
            self.result[
                self.symbol
            ] = f"Error: too less macd data, {self.symbol}:{self.interval}"
            return await self.send_msg(email_title, "".join(self.result.values()))

        now_macd_data, last_macd_data = macd_list[0], macd_list[1]

        now_ts = int(time.time())
        if now_macd_data.opening_ts < (now_ts - self.interval_sec * 2):
            self.result[self.symbol] = (
                f"Error: no lastest macd data, {self.symbol}:{self.interval}, "
                f"opening_ts:{now_macd_data.opening_ts}, now_ts:{now_ts}"
            )
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
            ] = f"Error: not macd data, {self.symbol}:{self.interval}"
            return await self.send_msg(email_title, "".join(self.result.values()))
        elif len(macd_list) < limit_count:
            self.result[
                self.symbol
            ] = f"Error: too less macd data, {self.symbol}:{self.interval}"
            return await self.send_msg(email_title, "".join(self.result.values()))

        now_macd_data, last_macd_data = macd_list[0], macd_list[1]
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
            history_macd_list = [decimal2str(i.macd) for i in macd_list][::-1]
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
