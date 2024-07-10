#! /usr/bin/env python
# coding:utf

from settings.setting import cfgs
from utils.hrequest import http_get_request
from cache import AllCache
from cache.order import MarketPriceCache, MarketPriceLimitCache, MarketMacdCache
from cache.plot import SymbolPlotTableCache
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
            redis_client.set(k, val["redis_data"], ex=180)

        elif val["redis_type"] == "hash":
            redis_client.delete(k)
            for _k, _v in val["redis_data"].items():
                redis_client.hset(k, _k, _v)

                if k == SymbolPlotTableCache.key:
                    _symbol = _k.split(":")[0]
                    is_valid = int(_v)
                    if is_valid:
                        SymbolHandle(_symbol).add_plot_to_db()
                    else:
                        SymbolHandle(_symbol).del_plot_to_db()
