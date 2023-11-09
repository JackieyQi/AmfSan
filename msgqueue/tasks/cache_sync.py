#! /usr/bin/env python
# coding:utf

from settings.setting import cfgs
from utils.hrequest import http_get_request
from cache.order import MarketPriceCache, MarketPriceLimitCache


async def sync_cache_job(*args, **kwargs):
    url = f"""{cfgs["http"]["inner_url"]}/api/cache/sync/"""

    resp_data = http_get_request(url, {"key": "market_price"})
    if resp_data:
        for k, v in resp_data.items():
            MarketPriceCache.hset(k, v)

    resp_data = http_get_request(url, {"key": "market_price_limit"})
    if resp_data:
        for k, v in resp_data.items():
            MarketPriceLimitCache.hset(k, f"{v[0]}:{v[1]}")

