#! /usr/bin/env python
# coding:utf8

import hashlib
import functools
import time
import numpy as np
from datetime import datetime, timedelta
from decimal import ROUND_DOWN, Decimal, getcontext
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


def convert_seconds(seconds):
    """
    将秒数转换为天、小时和分钟，忽略秒数。

    Args:
        seconds: 要转换的秒数。

    Returns:
        包含天、小时和分钟的元组。
    """
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    return days, hours, minutes


def decimal2str_old(val: Decimal, num=8):
    # normalize 消耗性能
    val = val.quantize(Decimal((0, (1,), -num)), ROUND_DOWN)
    return "{:f}".format(val.normalize())


def _truncate_and_format_str_decimal(val_str: str, num: int, return_decimal: bool) -> str | Decimal:
    # 处理科学计数法
    if "E" in val_str or "e" in val_str:
        return Decimal(f"{Decimal(val_str):.{num}f}") if return_decimal else f"{Decimal(val_str):.{num}f}"

    # 处理整数
    if "." not in val_str:
        return Decimal(val_str) if return_decimal else val_str

    integer_part, decimal_part = val_str.split(".")
    if len(decimal_part) <= num:
        truncated_decimal_part = decimal_part
    else:
        truncated_decimal_part = decimal_part[:num]
    truncated_decimal_part = truncated_decimal_part.rstrip("0")
    if truncated_decimal_part == "":
        return Decimal(integer_part) if return_decimal else integer_part
    return Decimal(f"{integer_part}.{truncated_decimal_part}") \
        if return_decimal else f"{integer_part}.{truncated_decimal_part}"


def str2str(val: str, num: int = 8) -> str:
    return _truncate_and_format_str_decimal(val, num, False)


def str2decimal(val: str, num: int = 8) -> Decimal:
    return _truncate_and_format_str_decimal(val, num, True)


def decimal2decimal(val: Decimal, num: int = 8) -> Decimal:
    context = getcontext().copy()
    context.rounding = ROUND_DOWN
    return val.quantize(Decimal(f"1e-{num}"), context=context)


def float2decimal(val: float, num: int = 8) -> Decimal:
    context = getcontext().copy()
    context.rounding = ROUND_DOWN
    return Decimal(val).quantize(Decimal(f"1e-{num}"), context=context)


def decimal2str(val: Decimal, num: int = 8) -> str:
    context = getcontext().copy()
    context.rounding = ROUND_DOWN
    quantized_val = val.quantize(Decimal(f"1e-{num}"), context=context)
    return f"{quantized_val:f}".rstrip("0").rstrip(".")


def leading_zeros(val: Decimal):
    """获取小数位前导零的个数"""
    decimal_str = str(val)
    if "E-" in decimal_str:
        # 处理科学计数法
        base, exponent = decimal_str.split("E-")
        num_zeros = int(exponent) - 1
        scale_factor = Decimal(10 ** num_zeros)
        return scale_factor

    elif "." not in decimal_str:
        return

    else:
        int_part, decimal_part = decimal_str.split(".")
        if int(decimal_part) == 0:
            return
        no_zero_decimal_part = decimal_part.lstrip("0")
        num_zeros = len(decimal_part) - len(no_zero_decimal_part)
        return Decimal(10 ** num_zeros)


def autoscale(prices):
    max_decimal = max([abs(p) for p in prices])
    if max_decimal == 0 or max_decimal > Decimal("0.0001"):
        return prices, Decimal(1)
    scale_exp = abs(int(np.floor(np.log10(float(max_decimal))))) + 1
    scale = Decimal(10) ** scale_exp
    return [p * scale for p in prices], scale


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
