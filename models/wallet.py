#! /usr/bin/env python
# coding:utf8

import time

from peewee import CharField, DecimalField, IntegerField, TimestampField

from . import Base


class BalanceHistoryTable(Base):
    # id = IntegerField(primary_key=True, auto_increment=True)
    user_id = CharField(null=False, db_column="user_id")
    coin = CharField(null=False, db_column="coin", max_length=10, index=True)
    status_type = CharField(null=False, db_column="status_type", max_length="10")
    amount = DecimalField(
        null=False, db_column="amount", default=0, max_digits=20, decimal_places=8
    )
    price = DecimalField(
        null=True, db_column="price", default=0, max_digits=20, decimal_places=8
    )
    bid_coin = CharField(null=False, db_column="bid_coin", max_length=10)

    create_ts = IntegerField(db_column="create_ts", default=int(time.time()))
    # create_ts = TimestampField(db_column="create_ts", resolution=3) =>BigInt

    class Meta:
        table_name = "balance_history_table"


class DepositHistoryTable(Base):
    pass


class WithdrawHistoryTable(Base):
    pass
