#! /usr/bin/env python
# coding:utf8

from . import HashCache, StringCache


class TickerSentinelCache(StringCache):
    key = "ticker:sentinel"


class MarketPriceLimitCache(HashCache):
    key = "market:price:limit"


class LimitPriceNoticeValveCache(StringCache):
    # TODO:tmp set symbol
    key = "valve:price:notice:btcusdt"


class LimitPriceNoticeValueCache(StringCache):
    # TODO:tmp set symbol
    key = "value:price:notice:btcusdt"
