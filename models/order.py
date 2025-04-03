#! /usr/bin/env python
# coding:utf8

import time

from peewee import (BooleanField, CharField, DecimalField, IntegerField,
                    TextField, AutoField)

from . import Base


class SymbolPlotTable(Base):
    user_id = CharField(null=False, db_column="user_id")
    symbol = CharField(db_column="symbol", unique=True)
    last_price = DecimalField(
        db_column="last_price",
        default=0,
        max_digits=20,
        decimal_places=8,
        help_text="上次交易价格",
    )
    is_valid = BooleanField(db_column="is_valid", default=True)

    create_ts = IntegerField(db_column="create_ts", default=int(time.time()))

    class Meta:
        table_name = "symbol_plot_table"


class PlotBackTestTable(Base):
    id = AutoField()
    symbol = CharField(db_column="symbol", index=True, max_length=10)
    bid_curr_price = DecimalField(
        db_column="bid_curr_price", default=0, max_digits=20, decimal_places=8
    )
    bid_price = DecimalField(
        db_column="bid_price", default=0, max_digits=20, decimal_places=8
    )
    bid_ts = IntegerField(db_column="bid_ts", default=0)
    bid_plot_type = IntegerField(db_column="bid_plot_type", default=0)
    bid_plot_msg = TextField(db_column="bid_plot_msg")
    buy_price = DecimalField(
        db_column="buy_price", default=0, max_digits=20, decimal_places=8
    )
    buy_ts = IntegerField(db_column="buy_ts", default=0)
    ask_curr_price = DecimalField(
        db_column="ask_curr_price", default=0, max_digits=20, decimal_places=8
    )
    ask_price = DecimalField(
        db_column="ask_price", default=0, max_digits=20, decimal_places=8
    )
    ask_ts = IntegerField(db_column="ask_ts", default=0)
    ask_plot_type = IntegerField(db_column="ask_plot_type", default=0)
    ask_plot_msg = TextField(db_column="ask_plot_msg")
    sell_price = DecimalField(
        db_column="sell_price", default=0, max_digits=20, decimal_places=8
    )
    sell_ts = IntegerField(db_column="sell_ts", default=0)
    hold_time = IntegerField(db_column="hold_time", default=0)
    profit_percent = DecimalField(db_column="profit_percent", max_digits=5, decimal_places=1, default=0)
    status = IntegerField(db_column="status", default=0) # 0:bid;1:buy;2:buyFail;3:ask;4:sell;5:sellFail

    class Meta:
        table_name = "plot_back_test_table"


class SymbolPriceChangeHistoryTable(Base):
    symbol = CharField(db_column="symbol", index=True)
    current_price = DecimalField(
        db_column="current_price", default=0, max_digits=20, decimal_places=8
    )
    limit_low_price = DecimalField(
        db_column="limit_low_price", default=0, max_digits=20, decimal_places=8
    )
    limit_price = DecimalField(
        db_column="low_price", default=0, max_digits=20, decimal_places=8
    )
    limit_high_price = DecimalField(
        db_column="limit_high_price", default=0, max_digits=20, decimal_places=8
    )
    high_price = DecimalField(
        db_column="high_price", default=0, max_digits=20, decimal_places=8
    )
    create_ts = IntegerField(db_column="create_ts", default=int(time.time()))

    class Meta:
        table_name = "symbol_price_change_history_table"


class OrderTable(Base):
    pass


class OrderTradeHistoryTable(Base):
    user_id = CharField(null=False, db_column="user_id")
    trade_id = CharField(db_column="trade_id")
    order_id = CharField(db_column="order_id")
    symbol = CharField(db_column="symbol", index=True)
    price = DecimalField(db_column="price", default=0, max_digits=20, decimal_places=8)
    qty = DecimalField(
        db_column="qty", null=False, default=0, max_digits=20, decimal_places=8
    )
    quote_qty = DecimalField(
        db_column="quote_qty", null=False, default=0, max_digits=20, decimal_places=8
    )
    trade_ts = IntegerField(db_column="trade_ts", default=0, help_text="交易时间")
    is_buyer = BooleanField(db_column="is_buyer", help_text="买入")
    is_maker = BooleanField(db_column="is_maker", help_text="卖出")
    extra_data = TextField()

    create_ts = IntegerField(db_column="create_ts", default=int(time.time()))

    class Meta:
        table_name = "order_trade_history_table"
