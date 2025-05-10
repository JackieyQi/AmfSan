#! /usr/bin/env python
# coding:utf8

import ujson as json
from utils.authentication import HTTPMethodView, ProtectedView
from cache.order import MarketMacdCache, MarketKdjCache, MarketEmaCache
from settings.constants import PLOT_INTERVAL_LIST
from business.market import SymbolHandle
from business.trade_signal_recorder import TradeSignalViewHandler
from utils.exception import StandardResponseExc


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


class PlotEmaView(HTTPMethodView):
    async def get(self, request):
        symbol = request.form.get("symbol")

        return symbol

    async def post(self, request):
        json_data = request.json
        for symbol, data in json_data.items():
            for _interval in PLOT_INTERVAL_LIST:

                if _interval in data:
                    MarketEmaCache(
                        symbol.lower(),
                        _interval
                    ).set(json.dumps(data[_interval]))

                    # SymbolHandle(symbol).add_kdj_gate(_interval)

        return "handle over!"


class TradeSignalRecordsView(ProtectedView):
    need_auth = {"get": True, }

    async def get(self, request):
        user = request.ctx.user

        page = int(request.args.get("page", 1))
        page_size = int(request.args.get("page_size", 10))
        symbol = request.args.get("symbol")
        status = request.args.get("status")
        if status is not None:
            status = int(status)
        return await TradeSignalViewHandler(user.user_id).get_trade_records(page, page_size, symbol, status)


class TradeSignalRecordDetailView(ProtectedView):
    need_auth = {"get": True, }

    async def get(self, request):
        user = request.ctx.user

        symbol = request.args.get("symbol")
        record_id = request.args.get("id")
        if not all([symbol, record_id]):
            raise StandardResponseExc(msg="Missing required fields")

        return await TradeSignalViewHandler(user.user_id).get_detail_record(symbol, record_id)
