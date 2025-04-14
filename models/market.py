#! /usr/bin/env python
# coding:utf8

import time

from peewee import (BooleanField, CharField, DecimalField, IntegerField,
                    TextField, AutoField)

from . import Base


class KlineTable(Base):
    id = AutoField()
    symbol = CharField(db_column="symbol", index=True, max_length=10)
    interval_val = CharField(default="4h", db_column="interval_val", help_text="k线间隔", max_length=5)
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
        indexes = (
            (("symbol", "interval_val"), False),  # False 代表普通索引（不是唯一索引）
        )


class EmaTable(Base):
    symbol = CharField(db_column="symbol", index=True)
    interval_val = CharField(default="4h", db_column="interval_val", help_text="k线间隔")
    open_ts = IntegerField(default=0, db_column="open_ts", help_text="开盘时间")
    ema7 = DecimalField(
        db_column="ema7", default=0, max_digits=20, decimal_places=8
    )
    ema20 = DecimalField(
        db_column="ema20", default=0, max_digits=20, decimal_places=8
    )
    ema30 = DecimalField(
        db_column="ema30", default=0, max_digits=20, decimal_places=8
    )
    create_ts = IntegerField(db_column="create_ts", default=int(time.time()))

    class Meta:
        table_name = "ema_table"


class MacdTable(Base):
    id = AutoField()
    symbol = CharField(db_column="symbol", index=True, max_length=10)
    interval_val = CharField(default="4h", db_column="interval_val", help_text="k线间隔", max_length=5)
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
        indexes = (
            (("symbol", "interval_val"), False),  # False 代表普通索引（不是唯一索引）
        )


class KdjTable(Base):
    id = AutoField()
    symbol = CharField(db_column="symbol", index=True, max_length=10)
    interval_val = CharField(default="4h", db_column="interval_val", help_text="k线间隔", max_length=5)
    open_ts = IntegerField(default=0, db_column="open_ts", help_text="开盘时间")
    k_val = DecimalField(
        db_column="k_val", default=0, max_digits=20, decimal_places=8
    )
    d_val = DecimalField(
        db_column="d_val", default=0, max_digits=20, decimal_places=8
    )
    j_val = DecimalField(
        db_column="j_val", default=0, max_digits=20, decimal_places=8
    )
    cfg = CharField(
        db_column="cfg",
        help_text="json配置,"
                  "通用{'period':9,'move_average_period1':3,'move_average_period2':3},"
                  "计算周期9移动平均周期1为3移动平均周期2为3"
    )

    create_ts = IntegerField(db_column="create_ts", default=int(time.time()))

    class Meta:
        table_name = "kdj_table"
        indexes = (
            (("symbol", "interval_val"), False),  # False 代表普通索引（不是唯一索引）
        )


class RsiTable(Base):
    id = AutoField()
    symbol = CharField(db_column="symbol", index=True, max_length=10)
    interval_val = CharField(default="4h", db_column="interval_val", help_text="k线间隔", max_length=5)
    open_ts = IntegerField(default=0, db_column="open_ts", help_text="开盘时间")
    rsi = DecimalField(
        db_column="rsi", default=0, max_digits=20, decimal_places=8
    )
    avg_gain = DecimalField(
        db_column="avg_gain", default=0, max_digits=20, decimal_places=8
    )
    avg_loss = DecimalField(
        db_column="agv_loss", default=0, max_digits=20, decimal_places=8
    )
    period = IntegerField(db_column="status", default=6, help_text="rsi周期")

    create_ts = IntegerField(db_column="create_ts", default=int(time.time()))

    class Meta:
        table_name = "rsi_table"
        indexes = (
            (("symbol", "interval_val"), False),  # False 代表普通索引（不是唯一索引）
        )


class BollTable(Base):
    id = AutoField()
    symbol = CharField(db_column="symbol", index=True, max_length=10)
    interval_val = CharField(default="4h", db_column="interval_val", help_text="k线间隔", max_length=5)
    open_ts = IntegerField(default=0, db_column="open_ts", help_text="开盘时间")
    bbupper = DecimalField(
        db_column="bbupper", default=0, max_digits=20, decimal_places=8
    )
    bbmid = DecimalField(
        db_column="bbmid", default=0, max_digits=20, decimal_places=8
    )
    bblower = DecimalField(
        db_column="bblower", default=0, max_digits=20, decimal_places=8
    )
    sum_close = DecimalField(
        db_column="sum_close", default=0, max_digits=20, decimal_places=8
    )
    sum_sq_close = DecimalField(
        db_column="sum_sq_close", default=0, max_digits=20, decimal_places=8, help_text="收盘价平方的总和"
    )
    period = IntegerField(db_column="period", default=6, help_text="boll周期")

    create_ts = IntegerField(db_column="create_ts", default=int(time.time()))

    class Meta:
        table_name = "boll_table"
        indexes = (
            (("symbol", "interval_val"), False),
        )
