#! /usr/bin/env python
# coding:utf8

from . import HashCache, StringCache


class APIRequestCountCache(StringCache):
    key = "api:count"


class CheckMacdCrossGateCache(HashCache):
    key = "gate:macd:cross"


class CheckMacdTrendGateCache(HashCache):
    key = "gate:macd:trend"


class CheckKdjCrossGateCache(HashCache):
    key = "gate:kdj:cross"


class CheckKdjCvGateCache(HashCache):
    """
    离散系数: coefficient of variation
    """
    key = "gate:kdj:cv"
