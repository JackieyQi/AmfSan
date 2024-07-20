#! /usr/bin/env python
# coding:utf8

import json
from decimal import Decimal as D

from business.binance_exchange import BinanceExchangeRequestHandle
# from business.huobi_exchange import HuobiExchangeAccountHandle
from business.market import MarketPriceHandler, MacdInitData
from models.market import KlineTable
from models.order import MacdTable, OrderTradeHistoryTable, SymbolPlotTable
from models.wallet import TotalBalanceHistoryTable
from settings.setting import cfgs
from settings.constants import PLOT_INTERVAL_LIST, PLOT_INTERVAL_CONFIG
from utils.common import decimal2str, str2decimal
from utils.hrequest import http_get_request
from cache.order import MarketMacdCache


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


async def save_kline_job(*args, **kwargs):
    query = SymbolPlotTable.select().where(SymbolPlotTable.is_valid == True)
    for row in query:
        for _interval in PLOT_INTERVAL_LIST:
            await KlineDataSaveHandle(row.symbol, _interval).save_data()


class KlineDataSaveHandle(object):
    def __init__(self, symbol, interval):
        self.symbol = symbol
        self.interval = interval
        self.interval_sec = PLOT_INTERVAL_CONFIG[interval]["interval_sec"]
        self.k_interval = PLOT_INTERVAL_CONFIG[interval]["k_interval"]

    def get_k_lines_by_innerapi(self):
        try:
            db_last_k = (
                KlineTable.select()
                .where(
                    KlineTable.symbol == self.symbol,
                    KlineTable.interval_val == self.interval,
                )
                .order_by(KlineTable.id.desc())
                .limit(1)
                .get()
            )
        except KlineTable.DoesNotExist:
            return

        resp_data = http_get_request(
            f"""{cfgs["http"]["inner_url"]}/api/cache/sync/""",
            {
                "key": "get_k_lines",
                "symbol": self.symbol.upper(),
                "interval": self.interval,
                "start_ts": (db_last_k.open_ts - self.k_interval) * 1000,
             }
        )
        if resp_data:
            return resp_data["data"]

    def __init_cache_data(self):
        macd_cache_data = MarketMacdCache(self.symbol, f"macd_{self.interval}").get()
        if macd_cache_data:
            macd_init_data = {f"macd_{self.interval}": json.loads(macd_cache_data)}
            MacdInitData(macd_init_data).start(self.interval)

    async def save_data(self):
        if not self.interval:
            return

        self.__init_cache_data()

        k_data = self.get_k_lines_by_innerapi()
        if not k_data:
            return

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

            last_db_k = KlineTable.select().where(
                    KlineTable.symbol == self.symbol,
                    KlineTable.open_ts == open_ts,
                    KlineTable.interval_val == self.interval,
            )
            if last_db_k:
                last_db_k.open_ts = open_ts
                last_db_k.open_price = open_price
                last_db_k.high_price = high_price
                last_db_k.low_price = low_price
                last_db_k.close_price = close_price
                last_db_k.volume = volume
                last_db_k.close_ts = close_ts
                last_db_k.asset_volume = asset_volume
                last_db_k.trade_number = trade_number
                last_db_k.buy_volume = buy_volume
                last_db_k.buy_asset_volume = buy_asset_volume
                last_db_k.save()
            else:
                _ = KlineTable.create(
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


async def save_macd_job(*args, **kwargs):
    query = SymbolPlotTable.select().where(SymbolPlotTable.is_valid == True)
    for row in query:
        for _interval in PLOT_INTERVAL_LIST:
            await MacdDataSaveHandle(row.symbol, _interval).save_data()


class MacdDataSaveHandle(object):
    def __init__(self, symbol, interval):
        self.symbol = symbol
        self.interval = interval
        self.interval_sec = PLOT_INTERVAL_CONFIG[interval]["interval_sec"]
        self.k_interval = PLOT_INTERVAL_CONFIG[interval]["k_interval"]

    def get_k_lines_from_db(self):
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

        try:
            db_kline = KlineTable.select().where(
                KlineTable.symbol == self.symbol,
                KlineTable.interval_val == self.interval,
                KlineTable.open_ts >= db_last_macd.opening_ts - self.k_interval,
            ).order_by(KlineTable.id)
        except KlineTable.DoesNotExist:
            return
        return db_kline

    def parsed_k_lines_data(self, data):
        opening_ts = data.open_ts
        opening_price = data.open_price
        closing_price = data.close_price

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
        now_macd = D(decimal2str(now_ema_12 - now_ema_26 - now_dea))
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
            if not MacdTable.select().where(
                    MacdTable.symbol == self.symbol,
                    MacdTable.opening_ts == opening_ts,
                    MacdTable.interval_val == self.interval,
            ):
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

    def __init_macd_cache_data(self):
        cache_data = MarketMacdCache(self.symbol, f"macd_{self.interval}").get()
        if not cache_data:
            return

        macd_init_data = {f"macd_{self.interval}": json.loads(cache_data)}
        MacdInitData(macd_init_data).start(self.interval)

    async def save_data(self):
        if not self.interval:
            return

        self.__init_macd_cache_data()

        k_data = self.get_k_lines_from_db()
        if not k_data:
            return

        for _data in k_data:
            self.parsed_k_lines_data(_data)
