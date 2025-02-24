#! /usr/bin/env python
# coding:utf8

import json
from decimal import Decimal as D

from exts import database
from models import order, user, wallet, market


def command_create_tables():
    print("***************start command_create_tables**************")
    with database:
        database.create_tables(
            [
                order.SymbolPriceChangeHistoryTable,
                order.OrderTradeHistoryTable,
                order.SymbolPlotTable,
                order.MacdTable,
                order.KdjTable,
                wallet.BalanceHistoryTable,
                wallet.TotalBalanceHistoryTable,
                user.EmailMsgHistoryTable,
                market.KlineTable,
            ]
        )

    print("***************end command_create_tables****************")


def command_update_tables():
    from peewee import CharField
    from playhouse.migrate import MySQLMigrator, migrate

    print("***************start command_update_tables**************")

    order_id_field = CharField(default=0)
    migrator = MySQLMigrator(database)
    with database.atomic():
        migrate(
            # migrator.add_column(
            #     "order_trade_history_table", "order_id", order_id_field
            # ),
            migrator.rename_column("macd_table", "interval", "interval_val"),
        )

    print("***************end command_update_tables****************")


def command_insert_mytrades(key, secret, symbol):
    from business.binance_exchange import BinanceExchangeRequestHandle
    from models.order import OrderTradeHistoryTable

    print("***************start command_insert_mytrades**************")

    symbol = symbol.lower()
    trades_data = BinanceExchangeRequestHandle(key, secret).get_my_trades(
        symbol.upper()
    )
    count = 0
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
            symbol=i["symbol"].lower(),
            price=D(i["price"]),
            qty=D(i["qty"]),
            quote_qty=D(i["quoteQty"]),
            trade_ts=int(i["time"] / 1000),
            is_buyer=i["isBuyer"],
            is_maker=i["isMaker"],
            extra_data=json.dumps(i),
        ).save()
        count += 1

    print(f"Insert data count {count}")
    print("***************end command_insert_mytrades****************")


def command_add_new_symbol(symbol):
    from models.order import OrderTradeHistoryTable, SymbolPlotTable

    print("***************start command_add_new_symbol**************")
    symbol = symbol.lower()

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

    print("***************end command_add_new_symbol****************")


def command_save_macd(symbol, interval):
    from msgqueue.tasks.dw import MacdDataSaveHandle

    print("***************start command_save_macd**************")
    if not symbol or not interval:
        return

    _handler = MacdDataSaveHandle(symbol, interval)
    k_data = _handler.get_k_lines_by_openapi()
    if not k_data:
        return f"LOG: no k_data, {symbol}, {interval}"

    for _data in k_data:
        _handler.parsed_k_lines_data(_data)

    print("***************end command_save_macd****************")


def command_init_macd():
    from business.market import MacdInitData
    from models.init_data import MACD_INIT_DATA_ETHUSDT as macd_init_data

    print("***************start command_init_macd**************")

    _handler = MacdInitData(macd_init_data)
    print(f"""
    init_1h: {_handler.init_1h()}
    init_4h: {_handler.init_4h()}
    init_1d: {_handler.init_1d()}
    """)

    print("***************end command_init_macd****************")


if __name__ == "__main__":
    print("RUN: script.")
