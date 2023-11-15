#! /usr/bin/env python
# coding:utf

from settings.setting import cfgs
from utils.hrequest import http_get_request
from cache.order import MarketPriceCache, MarketPriceLimitCache
from business.market import MarketPriceHandler


async def sync_cache_job(*args, **kwargs):
    url = f"""{cfgs["http"]["inner_url"]}/api/cache/sync/"""

    resp_data = http_get_request(url, {"key": "market_price"})
    if resp_data:
        for k, v in resp_data["data"].items():
            MarketPriceCache.hset(k.lower(), str(v))

    resp_data = http_get_request(url, {"key": "market_price_limit"})
    if resp_data:
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


