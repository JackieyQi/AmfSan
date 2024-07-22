#! /usr/bin/env python
# coding:utf8

import ujson as json
from sanic.views import HTTPMethodView
from cache.order import MarketMacdCache, MarketKdjCache
from settings.constants import PLOT_INTERVAL_LIST
from business.market import SymbolHandle


class PlotMacdView(HTTPMethodView):
    async def get(self, request):
        symbol = request.form.get("symbol")

        return symbol

    async def post(self, request):
        """
        json:
            {
            "peopleusdt":{
            "15m":[
                {
                    "symbol": "peopleusdt",
                    "interval": "15m",
                    "opening_ts": 1721471400,
                    "opening_price": "0.08617",
                    "closing_price": "0.08614",
                    "ema_12": "0.08614",
                    "ema_26": "0.08623",
                    "dea": "-0.00005",
                    "macd": "-0.00003"
                },
                {
                    "symbol": "peopleusdt",
                    "interval": "15m",
                    "opening_ts": 1721472300,
                    "opening_price": "0.08613",
                    "closing_price": "0.08620",
                    "ema_12": "0.08615",
                    "ema_26": "0.08622",
                    "dea": "-0.00006",
                    "macd": "-0.00002"
                }
            ]
        }
        }
        :param request:
        :return:
        """
        json_data = request.json
        for symbol, data in json_data.items():
            for _interval in PLOT_INTERVAL_LIST:

                if _interval in data:
                    MarketMacdCache(
                        symbol.lower(),
                        _interval
                    ).set(json.dumps(data[_interval]))

                    SymbolHandle(symbol).add_macd_gate(_interval)

        return "handle over!"


class PlotKdjView(HTTPMethodView):
    async def get(self, request):
        symbol = request.form.get("symbol")

        return symbol

    async def post(self, request):
        json_data = request.json
        for symbol, data in json_data.items():
            for _interval in PLOT_INTERVAL_LIST:

                if _interval in data:
                    MarketKdjCache(
                        symbol.lower(),
                        _interval
                    ).set(json.dumps(data[_interval]))

                    SymbolHandle(symbol).add_kdj_gate(_interval)

        return "handle over!"
