#! /usr/bin/env python
# coding:utf8

import time

from peewee import (BooleanField, CharField, DecimalField, IntegerField,
                    TextField)

from . import Base


class UserInfoTable(Base):
    pass


class EmailMsgHistoryTable(Base):
    msg_md5 = CharField(db_column="msg_md5", max_length=32, unique=True)
    msg_content = TextField(db_column="msg_content")
    create_ts = IntegerField(db_column="create_ts", default=int(time.time()))

    class Meta:
        table_name = "email_msg_history_table"
