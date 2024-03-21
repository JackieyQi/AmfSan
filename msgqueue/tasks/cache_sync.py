#! /usr/bin/env python
# coding:utf

from settings.setting import cfgs
from utils.hrequest import http_get_request
from cache import AllCache
from cache.order import MarketPriceCache, MarketPriceLimitCache
from business.market import MarketPriceHandler, SymbolHandle


async def sync_cache_job(*args, **kwargs):
    url = f"""{cfgs["http"]["inner_url"]}/api/cache/sync/"""

    resp_data = http_get_request(url, {})
    if not resp_data:
        return

    resp_data = resp_data["data"]
    redis_client = AllCache.get_client()
    for k, val in resp_data.items():
        if val["redis_type"] == "string":
            redis_client.delete(k)
            redis_client.set(k, val["redis_data"])

        elif val["redis_type"] == "hash":
            redis_client.delete(k)
            for _k, _v in val["redis_data"].items():
                redis_client.hset(k, _k, _v)

                if k == "market:price:limit":
                    _symbol = _k.lower()
                    SymbolHandle(_symbol).add_new_plot_to_db()

        # for symbol in all_symbols:
        #     if symbol in current_all_symbols:
        #         continue
        #     SymbolHandle(symbol).del_plot_to_db()
