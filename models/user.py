#! /usr/bin/env python
# coding:utf8

import time
import uuid

from peewee import (BooleanField, CharField, DecimalField, IntegerField,
                    TextField, AutoField)
from . import Base


class UserInfoTable(Base):
    id = AutoField()
    uuid = CharField(db_column="uuid", max_length=32)
    email = CharField(db_column="email", max_length=32, unique=True)
    password = CharField(db_column="password")
    invite_code = CharField(db_column="invite_code", max_length=5)
    create_ts = IntegerField(db_column="create_ts", default=lambda: int(time.time()))

    class Meta:
        table_name = "user_info_table"


class UserSymbolPlotTable(Base):
    id = AutoField()
    user_id = CharField(null=False, db_column="user_id", max_length=32)
    symbol = CharField(db_column="symbol", max_length=10)
    last_price = DecimalField(
        db_column="last_price",
        default=0,
        max_digits=20,
        decimal_places=8,
        help_text="上次交易价格",
    )
    is_valid = BooleanField(db_column="is_valid", default=True)
    monitor_direction = CharField(max_length=4)
    strategy_model_key = CharField(max_length=64, null=True)
    take_profit_price = DecimalField(max_digits=20, decimal_places=8, null=True)
    stop_loss_price = DecimalField(max_digits=20, decimal_places=8, null=True)
    config_version = CharField(max_length=32, default=lambda: uuid.uuid4().hex)
    last_signal_ts = IntegerField(default=0)
    last_signal_reason = CharField(max_length=64, default="")

    create_ts = IntegerField(db_column="create_ts", default=lambda: int(time.time()))

    class Meta:
        table_name = "symbol_plot_table"
        indexes = (
            (("user_id", "symbol"), True),
        )


class EmailMsgHistoryTable(Base):
    msg_md5 = CharField(db_column="msg_md5", max_length=32, unique=True)
    msg_content = TextField(db_column="msg_content")
    create_ts = IntegerField(db_column="create_ts", default=lambda: int(time.time()))

    class Meta:
        table_name = "email_msg_history_table"


class UserStrategyTable(Base):
    id = CharField(primary_key=True, max_length=32, default=lambda: uuid.uuid4().hex)
    user_id = CharField(max_length=32, index=True)
    definition = TextField()
    version = IntegerField(default=1)
    create_ts = IntegerField(default=lambda: int(time.time()))
    update_ts = IntegerField(default=lambda: int(time.time()))

    class Meta:
        table_name = "user_strategy_table"
