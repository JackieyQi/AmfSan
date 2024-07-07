#! /usr/bin/env python
# coding:utf8

import ujson as json
from sanic.views import HTTPMethodView
from cache.order import MarketMacdCache


class PlotMacdView(HTTPMethodView):
    async def get(self, request):
        symbol = request.form.get("symbol")

        return symbol

    async def post(self, request):
        json_data = request.json
        for symbol, data in json_data.items():
            if "macd_1h" in data:
                MarketMacdCache(symbol.lower(), "macd_1h").set(
                    json.dumps({"macd_1h": data["macd_1h"]})
                )

            if "macd_4h" in data:
                MarketMacdCache(symbol.lower(), "macd_4h").set(
                    json.dumps({"macd_4h": data["macd_4h"]})
                )

            if "macd_1d" in data:
                MarketMacdCache(symbol.lower(), "macd_1d").set(
                    json.dumps({"macd_1d": data["macd_1d"]})
                )

        return "handle over!"
