#! /usr/bin/env python
# coding:utf8

import time

from peewee import (BooleanField, CharField, DecimalField, IntegerField,
                    TextField, AutoField)
from . import Base


class UserInfoTable(Base):
    id = AutoField()
    uuid = CharField(db_column="uuid", max_length=32)
    email = CharField(db_column="email", max_length=32, unique=True)
    password = CharField(db_column="password")
    invite_code = CharField(db_column="invite_code", max_length=5)
    create_ts = IntegerField(db_column="create_ts", default=int(time.time()))

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

    create_ts = IntegerField(db_column="create_ts", default=int(time.time()))

    class Meta:
        table_name = "symbol_plot_table"
        indexes = (
            (("user_id", "symbol"), True),
        )


class EmailMsgHistoryTable(Base):
    msg_md5 = CharField(db_column="msg_md5", max_length=32, unique=True)
    msg_content = TextField(db_column="msg_content")
    create_ts = IntegerField(db_column="create_ts", default=int(time.time()))

    class Meta:
        table_name = "email_msg_history_table"
