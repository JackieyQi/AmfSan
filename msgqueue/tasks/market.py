#! /usr/bin/env python
# coding:utf8

from decimal import Decimal

from business.binance_exchange import BinanceExchangeRequestHandle
from business.market import MarketPriceHandler
from cache import StringCache
from models.order import MacdTable, SymbolPlotTable
from settings.constants import INNER_GET_PRICE_URL, INNER_GET_UPDATE_PRICE_URL
from utils.common import decimal2str, str2decimal, ts2bjfmt


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
    notice_result = {}

    market_price_handler = MarketPriceHandler()
    for symbol, price in market_price_handler.get_all_limit_price().items():
        _symbol_result = PlotPriceHandle(symbol, price).get_result()
        notice_result.update(_symbol_result)

    if not notice_result:
        return
    market_price_handler.set_value_times4limit_price_notice()

    from msgqueue.queue import push

    await push(
        {
            "bp": "send_email_task",
            "receiver": [
                "wayley@live.com",
            ],
            "title": "{} New Market Price Notice".format(
                ",".join(list(notice_result.keys()))
            ),
            "content": "".join(notice_result.values()),
        }
    )


async def check_macd(*args, **kwargs):
    macd_config = ["4h", "1h", "1d"]
    query = SymbolPlotTable.select().where(SymbolPlotTable.is_valid == True)
    for row in query:
        for _interval in macd_config:
            await PlotMacdHandle(row.symbol, _interval).get_result()


class PlotPriceHandle(object):
    def __init__(self, symbol, price):
        limit_low_price, limit_high_price = price

        self.result = {}
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

        if (
            self.market_price_handler.get_value_times4limit_price_notice()
            >= self.market_price_handler.get_auto_valve_times4limit_price_notice()
        ):
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

        if (
            self.market_price_handler.get_value_times4limit_price_notice()
            >= self.market_price_handler.get_auto_valve_times4limit_price_notice()
        ):
            self.market_price_handler.set_limit_price(
                self.symbol,
                Decimal(decimal2str(self.limit_low_price * Decimal(self.high_incr))),
                Decimal(decimal2str(self.limit_high_price * Decimal(self.high_incr))),
            )

    def get_result(self):
        current_price = self.__get_current_price()
        if not current_price:
            return self.result

        self.__check_limit_low_price(current_price)
        self.__check_limit_high_price(current_price)
        return self.result


class PlotMacdHandle(object):
    def __init__(self, symbol, interval):
        self.result = {}
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

    def __add_msg_notice(self, opening_ts, last_macd_data, now_macd_data):
        class MacdMsgCountCache(StringCache):
            key = "macd:msg:count:{}:{}:{}".format(
                self.symbol, self.interval, opening_ts
            )

        if MacdMsgCountCache.get():
            return
        MacdMsgCountCache.set(1, 24 * 3600)
        self.result[
            self.symbol
        ] = """
            <br><br><b> {}: </b><br> macd changing. interval: {}, last macd:{}, new macd:{}, opening time:{}
            """.format(
            self.symbol,
            self.interval,
            last_macd_data.macd,
            now_macd_data.macd,
            ts2bjfmt(opening_ts),
        )

    def __parsed_k_lines_data(self, total_count, count, data):
        opening_ts = int(data[0] / 1000)
        opening_price = Decimal(data[1])
        closing_price = Decimal(data[4])

        _db_rs = (
            MacdTable.select()
            .where(
                MacdTable.symbol == self.symbol,
                MacdTable.interval == self.interval,
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
                interval=self.interval,
                opening_ts=opening_ts,
                opening_price=opening_price,
                closing_price=closing_price,
                ema_12=now_ema_12,
                ema_26=now_ema_26,
                dea=now_dea,
                macd=now_macd,
            )

        if last_macd_data.macd * now_macd_data.macd < 0:
            self.__add_msg_notice(opening_ts, last_macd_data, now_macd_data)
        return count + 1

    def get_k_lines_by_openapi(self):
        try:
            db_last_macd = (
                MacdTable.select()
                .where(
                    MacdTable.symbol == self.symbol, MacdTable.interval == self.interval
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

    async def get_result(self):
        if not self.interval:
            return

        k_data = self.get_k_lines_by_openapi()
        if not k_data:
            return

        total_count, count = len(k_data), 1
        for _data in k_data:
            count = self.__parsed_k_lines_data(total_count, count, _data)

        if not self.result:
            return

        from msgqueue.queue import push

        await push(
            {
                "bp": "send_email_task",
                "receiver": [
                    "wayley@live.com",
                ],
                "title": f"{self.symbol} MACD changing Notice",
                "content": "".join(self.result.values()),
            }
        )
