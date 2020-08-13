#! /usr/bin/env python
# coding:utf8

from sanic.views import HTTPMethodView

from business.market import MarketPriceHandler
from utils.exception import StandardResponseExc


class MarketPriceView(HTTPMethodView):
    async def get(self, request):
        symbol = request.args.get("symbol", "btcusdt")

        result = MarketPriceHandler().get_limit_price(symbol)
        return result

    async def post(self, request):
        price = request.json.get("price")
        symbol = request.json.get("symbol", "btcusdt")
        if not price:
            raise StandardResponseExc()

        result = MarketPriceHandler().set_limit_price(str(price), symbol)
        return result

