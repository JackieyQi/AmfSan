#! /usr/bin/env python
# coding:utf8

import json
from decimal import Decimal as D

from business.binance_exchange import BinanceExchangeRequestHandle
from business.huobi_exchange import HuobiExchangeAccountHandle
from models.order import OrderTradeHistoryTable, SymbolPlotTable
from settings.setting import cfgs


async def save_account_balance_job(*args, **kwargs):
    account_handler = HuobiExchangeAccountHandle()
    account_handler.save_current_balance()


async def update_trade_history_job(*args, **kwargs):
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
