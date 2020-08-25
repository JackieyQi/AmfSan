#! /usr/bin/env python
# coding:utf8

from decimal import Decimal
from sanic.views import HTTPMethodView

from business.market import MarketPriceHandler
from utils.exception import StandardResponseExc
from utils.common import str2decimal


class MarketPriceView(HTTPMethodView):
    async def get(self, request):
        symbol = request.form.get("symbol", "btcusdt")

        result = MarketPriceHandler().get_limit_price(symbol)
        return result

    async def post(self, request):
        low_price = request.form.get("low_price", "0")
        high_price = request.form.get("high_price", "0")
        symbol = request.form.get("symbol", "btcusdt")
        if not low_price and not high_price:
            raise StandardResponseExc()

        result = MarketPriceHandler().set_limit_price(
            symbol, str2decimal(low_price), str2decimal(high_price)
        )
        return result


class MarketInnerPriceView(HTTPMethodView):
    async def get(self, request, side_str, symbol, new_price):
        if not symbol or not new_price:
            raise StandardResponseExc()
        if side_str == "low":
            return MarketPriceHandler().set_limit_price(symbol, str2decimal(new_price), Decimal("0"))
        elif side_str == "high":
            return MarketPriceHandler().set_limit_price(symbol, Decimal("0"), str2decimal(new_price))
        else:
            raise StandardResponseExc(msg="Error side_str:{}".format(side_str))

