#! /usr/bin/env python
# coding:utf8

import hashlib
import functools
import time
from datetime import datetime, timedelta
from decimal import ROUND_DOWN, Decimal
from uuid import uuid4
from settings.constants import PLOT_INTERVAL_CONFIG


def generate_token(random_string, length=32):
    return (
        uuid4().hex
        + hashlib.sha256(
            (str(datetime.now()) + str(random_string)).encode("utf8")
        ).hexdigest()
    )[:length].upper()


def to_ctime(ts: int):
    return time.ctime(ts)


def ts2fmt(ts=None):
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts or time.time()))


def ts2bjfmt(ts=None):
    return (datetime.fromtimestamp(ts or time.time()) + timedelta(hours=8)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def decimal2str(val: Decimal, num=8):
    val = val.quantize(Decimal((0, (1,), -num)), ROUND_DOWN)
    return "{:f}".format(val.normalize())


def str2decimal(val: str, num=8):
    return Decimal(decimal2str(Decimal(val), num))


def leading_zeros(val: Decimal):
    """获取小数位前导零的个数"""
    val_str = str(val)
    if "." not in val_str:
        return 0

    int_part, decimal_part = val_str.split(".")
    if int(decimal_part) == 0:
        return 0
    no_zero_decimal_part = decimal_part.lstrip("0")
    leading_zeros = len(decimal_part) - len(no_zero_decimal_part)
    return leading_zeros


def usdt2busd(val: str):
    return val.replace("usdt", "busd").replace("USDT", "BUSD")


def busd2usdt(val: str):
    return val.replace("busd", "usdt").replace("BUSD", "USDT")


def locking(key):
    from cache import AllCache
    redis_client = AllCache.get_client()

    def decorate(func):
        async def wrapper(*args, **kwargs):
            if not redis_client.get(key):
                redis_client.set(key, int(time.time()), ex=900, nx=True)
                response = await func(*args, **kwargs)
                redis_client.delete(key)
                return response
            else:
                return "locking"
        return wrapper
    return decorate


def set_lock_latest(key):
    """
    :param key: "lock_macd_latest:{symbol}:{interval}"
    :param key: "lock_kdj_latest:{symbol}:{interval}"
    :return:
    """
    from cache import AllCache
    redis_client = AllCache.get_client()

    def decorate(func):
        @functools.wraps(func)
        async def wrapper(self, symbol, interval):
            latest_open_ts = await func(self, symbol, interval)
            new_key = f"{key}:{symbol}:{interval}"

            if not redis_client.get(new_key):
                redis_client.set(new_key, latest_open_ts or "", ex=900, nx=True)
            return
        return wrapper
    return decorate


def check_lock_latest(key):
    """
    :param key: "lock_macd_latest:{symbol}:{interval}"
    :param key: "lock_kdj_latest:{symbol}:{interval}"
    :return:
    """
    from cache import AllCache
    redis_client = AllCache.get_client()

    def decorate(func):
        @functools.wraps(func)
        async def wrapper(self, symbol, interval):
            interval_sec = PLOT_INTERVAL_CONFIG[interval]["interval_sec"]
            new_key = f"{key}:{symbol}:{interval}"
            latest_open_ts = redis_client.get(new_key)

            if not latest_open_ts:
                return await func(self, symbol, interval)
            else:
                if int(latest_open_ts) < (int(time.time()) - interval_sec * 7):
                    return
                else:
                    redis_client.delete(new_key)
                    return await func(self, symbol, interval)
        return wrapper
    return decorate
