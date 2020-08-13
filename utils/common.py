#! /usr/bin/env python
# coding:utf8

import time
import hashlib
from uuid import uuid4
from decimal import Decimal, ROUND_DOWN
from datetime import datetime


def generate_token(random_string, length=32):
	return (uuid4().hex + hashlib.sha256((str(datetime.now()) + str(random_string)).encode("utf8")).hexdigest())[:length].upper()


def to_ctime(ts:int):
    return time.ctime(ts)


def ts2fmt(ts=time.time()):
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))


def decimal2str(val:Decimal, num=8):
    val = val.quantize(Decimal((0, (1,), -num)), ROUND_DOWN)
    return "{:f}".format(val.normalize())


def str2decimal(val:str, num=8):
    return Decimal(val).quantize(Decimal((0, (1,), -num)), ROUND_DOWN).normalize()

