#! /usr/bin/env python
# coding:utf

from settings.setting import cfgs
from utils.hrequest import http_get_request
from cache.order import MarketPriceCache, MarketPriceLimitCache
from business.market import MarketPriceHandler, SymbolHandle


async def sync_cache_job(*args, **kwargs):
    url = f"""{cfgs["http"]["inner_url"]}/api/cache/sync/"""

    resp_data = http_get_request(url, {"key": "market_price"})
    if resp_data:
        MarketPriceCache.delete()
        for k, v in resp_data["data"].items():
            MarketPriceCache.hset(k.lower(), str(v))

    resp_data = http_get_request(url, {"key": "market_price_limit"})
    if resp_data:
        all_symbols = MarketPriceHandler().get_all_limit_price().keys()
        MarketPriceLimitCache.delete()

        current_all_symbols = []
        for k, v in resp_data["data"].items():
            symbol = k.lower()
            limit_price = MarketPriceLimitCache.hget(symbol)
            if not limit_price:
                limit_low_price, limit_high_price = "", ""
            else:
                limit_low_price, limit_high_price = limit_price.split(":")
            MarketPriceLimitCache.hset(symbol, f"{v[0]}:{v[1]}")

            current_price = MarketPriceCache.hget(symbol) or 0
            MarketPriceHandler().save_limit_price_change_history_to_db(
                symbol, current_price, limit_low_price, v[0], limit_high_price, v[1]
            )

            current_all_symbols.append(symbol)

            if symbol not in all_symbols:
                SymbolHandle(symbol).add_new_plot_to_db()

        for symbol in all_symbols:
            if symbol in current_all_symbols:
                continue
            SymbolHandle(symbol).del_plot_to_db()
