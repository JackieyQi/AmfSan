#! /usr/bin/env python
# coding:utf8

import time

from peewee import (BooleanField, CharField, DecimalField, IntegerField,
                    TextField)

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


class MacdTable(Base):
    # id = IntegerField(primary_key=True)
    symbol = CharField(db_column="symbol", index=True)
    interval = CharField(default="4h", db_column="interval", help_text="k线间隔")
    opening_ts = IntegerField(default=0, db_column="opening_ts", help_text="开盘时间")
    opening_price = DecimalField(
        db_column="opening_price", default=0, max_digits=20, decimal_places=8
    )
    closing_price = DecimalField(
        db_column="closing_price", default=0, max_digits=20, decimal_places=8
    )
    ema_12 = DecimalField(
        db_column="ema_12", default=0, max_digits=20, decimal_places=8
    )
    ema_26 = DecimalField(
        db_column="ema_26", default=0, max_digits=20, decimal_places=8
    )
    dea = DecimalField(db_column="dea", default=0, max_digits=20, decimal_places=8)
    macd = DecimalField(db_column="macd", default=0, max_digits=20, decimal_places=8)

    create_ts = IntegerField(db_column="create_ts", default=int(time.time()))

    class Meta:
        table_name = "macd_table"
