#! /usr/bin/env python
# coding:utf8

from decimal import Decimal

from business.market import MarketPriceHandler, SymbolHandle
from sanic.views import HTTPMethodView
from utils.common import str2decimal, decimal2str
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
            price_data["last_my_trade_price"] = decimal2str(last_my_trade_price, num=2)

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
                    "limit_low_price": decimal2str(limit_low_price),
                    "limit_high_price": decimal2str(limit_high_price),
                    "last_my_trade_price": decimal2str(last_my_trade_price),
                }

        return result

    async def post(self, request):
        low_price = request.form.get("low_price", "0")
        high_price = request.form.get("high_price", "0")
        symbol = request.form.get("symbol", "btcusdt").strip().lower()
        if not low_price and not high_price:
            raise StandardResponseExc()

        hset_limit_price_result = MarketPriceHandler().set_limit_price(
            symbol, str2decimal(low_price), str2decimal(high_price)
        )
        if hset_limit_price_result == 1:
            set_limit_price_result = "success"
            set_limit_price_code = 1
        elif hset_limit_price_result == 0:
            set_limit_price_result = "success"
            set_limit_price_code = 0
        else:
            set_limit_price_result = "fail"
            set_limit_price_code = None

        new_plot_result = SymbolHandle(symbol).add_plot()
        return {
            "set_limit_price_result": set_limit_price_result,
            "set_limit_price_code": set_limit_price_code,
            "new_plot_result": new_plot_result,
        }


class MarketPriceGateView(HTTPMethodView):
    async def get(self, request):
        symbol = request.form.get("symbol").strip().lower()
        if not symbol:
            return "Invalid params:symbol"

        hdel_limit_price_result = MarketPriceHandler().del_limit_price(symbol)

        db_del_plot_result = SymbolHandle(symbol).del_plot()
        return {
            "symbol": symbol,
            "hdel_limit_price_result": hdel_limit_price_result,
            "db_del_plot_result": db_del_plot_result,
        }


class MarketMacdCrossGateView(HTTPMethodView):
    async def get(self, request):
        key = request.form.get("key").strip().lower()
        if not key:
            return "Invalid params:key"
        symbol, interval = key.split("_")

        hdel_plot_cross_result = SymbolHandle(symbol).del_macd_cross_gate(interval)
        return {
            "key": f"{symbol}:{interval}",
            "hdel_plot_cross_result": hdel_plot_cross_result,
        }


class MarketMacdTrendGateView(HTTPMethodView):
    async def get(self, request):
        key = request.form.get("key").strip().lower()
        if not key:
            return "Invalid params:key"
        symbol, interval = key.split("_")

        hdel_plot_trend_result = SymbolHandle(symbol).del_macd_trend_gate(interval)
        return {
            "key": f"{symbol}:{interval}",
            "hdel_plot_trend_result": hdel_plot_trend_result,
        }


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
