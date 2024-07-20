#! /usr/bin/env python
# coding:utf8

import time

from peewee import (BooleanField, CharField, DecimalField, IntegerField,
                    TextField)

from . import Base


class KlineTable(Base):
    symbol = CharField(db_column="symbol", index=True)
    interval_val = CharField(default="4h", db_column="interval_val", help_text="k线间隔")
    open_ts = IntegerField(default=0, db_column="open_ts", help_text="开盘时间")
    open_price = DecimalField(
        db_column="open_price", default=0, max_digits=20, decimal_places=8
    )
    high_price = DecimalField(
        db_column="high_price", default=0, max_digits=20, decimal_places=8
    )
    low_price = DecimalField(
        db_column="low_price", default=0, max_digits=20, decimal_places=8
    )
    close_price = DecimalField(
        db_column="close_price", default=0, max_digits=20, decimal_places=8
    )
    volume = DecimalField(
        db_column="volume", default=0, max_digits=20, decimal_places=8, help_text="成交量"
    )
    close_ts = IntegerField(default=0, db_column="close_ts", help_text="收盘时间")
    asset_volume = DecimalField(
        db_column="asset_volume", default=0, max_digits=20, decimal_places=8, help_text="成交额"
    )
    trade_number = IntegerField(default=0, db_column="trade_number", help_text="成交笔数")
    buy_volume = DecimalField(
        db_column="buy_volume", default=0, max_digits=20, decimal_places=8, help_text="主动买入成交量"
    )
    buy_asset_volume = DecimalField(
        db_column="buy_asset_volume", default=0, max_digits=20, decimal_places=8, help_text="主动买入成交额"
    )
    create_ts = IntegerField(db_column="create_ts", default=int(time.time()))

    class Meta:
        table_name = "kline_table"
