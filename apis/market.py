#! /usr/bin/env python
# coding:utf8

from decimal import Decimal

from business.market import MarketPriceHandler
from sanic.views import HTTPMethodView
from utils.common import str2decimal
from utils.exception import StandardResponseExc


class MarketPriceView(HTTPMethodView):
    async def get(self, request):
        symbol = request.form.get("symbol")

        result = {}
        price_handler = MarketPriceHandler()
        if symbol:
            symbol = symbol.strip().lower()
            price_data = price_handler.get_limit_price(symbol)

            last_my_trade_price = price_handler.get_last_trade_price(symbol)
            price_data["last_my_trade_price"] = str(last_my_trade_price)

            result[symbol] = price_data
        else:
            all_symbol_limit_price_dict = price_handler.get_all_limit_price()
            for k, v in all_symbol_limit_price_dict.items():
                limit_low_price, limit_high_price = v

                current_price = price_handler.get_current_price(k).get("price")
                last_my_trade_price = price_handler.get_last_trade_price(k)
                result[k] = {
                    "symbol": k,
                    "current_price": current_price,
                    "limit_low_price": str(limit_low_price),
                    "limit_high_price": str(limit_high_price),
                    "last_my_trade_price": str(last_my_trade_price),
                }

        return result

    async def post(self, request):
        low_price = request.form.get("low_price", "0")
        high_price = request.form.get("high_price", "0")
        symbol = request.form.get("symbol", "btcusdt").strip().lower()
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
            return MarketPriceHandler().set_limit_price(
                symbol, str2decimal(new_price), Decimal("0")
            )
        elif side_str == "high":
            return MarketPriceHandler().set_limit_price(
                symbol, Decimal("0"), str2decimal(new_price)
            )
        else:
            raise StandardResponseExc(msg="Error side_str:{}".format(side_str))
