#! /usr/bin/env python
# coding:utf8

import json
from decimal import Decimal as D

from business.binance_exchange import BinanceExchangeRequestHandle
# from business.huobi_exchange import HuobiExchangeAccountHandle
from business.market import MarketPriceHandler
from models.order import MacdTable, OrderTradeHistoryTable, SymbolPlotTable
from models.wallet import TotalBalanceHistoryTable
from settings.setting import cfgs
from utils.common import decimal2str, str2decimal
from utils.hrequest import http_get_request


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

    price_info = MarketPriceHandler().get_current_price_by_cache("btcusdt")
    current_price = str2decimal(price_info["price"])

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


async def save_macd_job(*args, **kwargs):
    macd_config = ["4h", "1h", "1d"]
    query = SymbolPlotTable.select().where(SymbolPlotTable.is_valid == True)
    for row in query:
        for _interval in macd_config:
            await MacdDataSaveHandle(row.symbol, _interval).save_data()


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

    def get_k_lines_by_innerapi(self):
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

        # resp_k = BinanceExchangeRequestHandle().get_k_lines(
        #     self.symbol.upper(),
        #     self.interval,
        #     (db_last_macd.opening_ts - self.k_interval) * 1000,
        # )

        resp_data = http_get_request(
            f"""{cfgs["http"]["inner_url"]}/api/cache/sync/""",
            {
                "key": "get_k_lines",
                "symbol": self.symbol.upper(),
                "interval": self.interval,
                "start_ts": (db_last_macd.opening_ts - self.k_interval) * 1000,
             }
        )
        if resp_data:
            return resp_data["data"]

    def parsed_k_lines_data(self, data):
        opening_ts = int(data[0] / 1000)
        opening_price = D(data[1])
        closing_price = D(data[4])

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
        now_macd = D(decimal2str(now_ema_12 - now_ema_26 - now_dea, 2))
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
            _ = MacdTable.create(
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

        k_data = self.get_k_lines_by_innerapi()
        if not k_data:
            return

        for _data in k_data:
            self.parsed_k_lines_data(_data)
