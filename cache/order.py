#! /usr/bin/env python
# coding:utf8

from . import StringCache, HashCache


class TickerSentinelCache(StringCache):
    key = "ticker:sentinel"


class MarketPriceLimitCache(HashCache):
    key = "market:price:limit"

