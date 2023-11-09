#! /usr/bin/env python
# coding:utf8

from . import HashCache, StringCache


class APIRequestCountCache(StringCache):
    key = "api:count"


class CheckMacdCrossGateCache(HashCache):
    key = "gate:macd:cross"


class CheckMacdTrendGateCache(HashCache):
    key = "gate:macd:trend"


class SymbolPlotTableCache(HashCache):
    """
    mapping database: models.order.SymbolPlotTable
    :argument:
        hget SymbolPlotTable btcusdt:last_price 20000
        hget SymbolPlotTable btcusdt:is_valid 1
    """
    key = "SymbolPlotTable"
