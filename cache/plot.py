#! /usr/bin/env python
# coding:utf8

from . import HashCache


class CheckMacdCrossGateCache(HashCache):
    key = "gate:macd:cross"


class CheckMacdTrendGateCache(HashCache):
    key = "gate:macd:trend"
