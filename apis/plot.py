#! /usr/bin/env python
# coding:utf8

import ujson as json
from sanic.views import HTTPMethodView
from cache.order import MarketMacdCache
from settings.constants import PLOT_INTERVAL_LIST
from business.market import SymbolHandle


class PlotMacdView(HTTPMethodView):
    async def get(self, request):
        symbol = request.form.get("symbol")

        return symbol

    async def post(self, request):
        json_data = request.json
        for symbol, data in json_data.items():
            for _interval in PLOT_INTERVAL_LIST:

                macd_interval = f"macd_{_interval}"
                if macd_interval in data:
                    MarketMacdCache(
                        symbol.lower(),
                        macd_interval
                    ).set(json.dumps(data[macd_interval]))

                    SymbolHandle(symbol).add_macd_gate(_interval)

        return "handle over!"
