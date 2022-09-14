#! /usr/bin/env python
# coding:utf8

import hashlib
import time
from datetime import datetime, timedelta
from decimal import ROUND_DOWN, Decimal
from uuid import uuid4


def generate_token(random_string, length=32):
    return (
        uuid4().hex
        + hashlib.sha256(
            (str(datetime.now()) + str(random_string)).encode("utf8")
        ).hexdigest()
    )[:length].upper()


def to_ctime(ts: int):
    return time.ctime(ts)


def ts2fmt(ts=time.time()):
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))


def ts2bjfmt(ts=time.time()):
    return (datetime.fromtimestamp(ts) + timedelta(hours=8)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def decimal2str(val: Decimal, num=8):
    val = val.quantize(Decimal((0, (1,), -num)), ROUND_DOWN)
    return "{:f}".format(val.normalize())


def str2decimal(val: str, num=8):
    return Decimal(decimal2str(Decimal(val)))


def usdt2busd(val: str):
    return val.replace("usdt", "busd").replace("USDT", "BUSD")


def busd2usdt(val: str):
    return val.replace("busd", "usdt").replace("BUSD", "USDT")
