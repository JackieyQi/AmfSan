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


class MarketMacdCache(StringCache):
    """
    cmd: get macd:btcusdt:1d
    return:
        "{\"macd_1d\":[{\"symbol\":\"btcusdt\",\"interval\":\"1d\",
        \"opening_ts\":1650153600,\"opening_price\":\"40378.70\",
        \"closing_price\":\"39678.12\",\"ema_12\":\"41340.21\",
        \"ema_26\":\"42207.85\",\"dea\":\"-330.05\"},{\"symbol\":
        \"btcusdt\",\"interval\":\"1d\",\"opening_ts\":1650240000,
        \"opening_price\":\"39678.11\",\"closing_price\":\"40801.13\",
        \"ema_12\":\"41257.27\",\"ema_26\":\"42103.64\",\"dea\":\"-433.31\",\"macd\":\"-413.05\"}]}"
    """
    key = "MarketMacdCache"

    def __init__(self, symbol, interval):
        super().__init__()
        MarketMacdCache.key = f"macd:{symbol}:{interval}"


class MarketKdjCache(StringCache):
    """
    cmd: get kdj:btcusdt:1d
    return:
    """
    key = "MarketKdjCache"

    def __init__(self, symbol, interval):
        super().__init__()
        MarketKdjCache.key = f"kdj:{symbol}:{interval}"
