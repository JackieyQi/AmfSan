#! /usr/bin/env python
# coding:utf8

from sanic.views import HTTPMethodView
from cache.order import MarketPriceLimitCache
from business.market import MarketPriceHandler
from business.binance_exchange import BinanceExchangeRequestHandle


class CacheSyncView(HTTPMethodView):
    async def get(self, request):
        key = request.form.get("key", "").strip().lower()
        if not key:
            return "Invalid params:key"

        if key == "market_price_limit":
            result = MarketPriceHandler().get_all_limit_price()

        elif key == "market_price":
            result = MarketPriceHandler().get_current_price_by_cache()

        elif key == "get_k_lines":
            symbol = request.form.get("symbol", "").strip().lower()
            interval = request.form.get("interval", "").strip().lower()
            start_ts = request.form.get("start_ts", "").strip().lower()

            result = BinanceExchangeRequestHandle().get_k_lines(symbol.upper(), interval, int(start_ts),)
        else:
            result = None

        return result
