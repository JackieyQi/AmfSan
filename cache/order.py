#! /usr/bin/env python
# coding:utf8

from . import HashCache, StringCache, ListCache


class TickerSentinelCache(StringCache):
    key = "ticker:sentinel"


class MarketPriceCache(HashCache):
    key = "market:price"


class MarketPriceLimitCache(HashCache):
    key = "market:price:limit"


class SymbolPriceChangeHistoryTableCache(ListCache):
    """
    mapping database: models.order.SymbolPlotTable
    :argument
        "{symbol}:
        {str(current_price)}:
        {str(limit_low_price or Decimal('0'))}:
        {str(low_price or Decimal('0'))}:
        {str(limit_high_price or Decimal('0'))}:
        {str(high_price or Decimal('0'))}:
        {int(time.time())}"
    """
    key = "SymbolPriceChangeHistoryTable"


class LimitPriceNoticeValveCache(StringCache):
    # TODO:tmp set symbol
    key = "valve:price:notice:btcusdt"


class LimitPriceNoticeValueCache(StringCache):
    # TODO:tmp set symbol
    key = "value:price:notice:btcusdt"
