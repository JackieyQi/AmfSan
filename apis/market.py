#! /usr/bin/env python
# coding:utf8

import time
from decimal import Decimal

from business.market import (
    BnSymbolHandle,
    CandidateTopPriceNoticeSetting,
    MarketPriceHandler,
    SymbolHandle,
)
from utils.authentication import HTTPMethodView, ProtectedView
from utils.common import str2decimal, decimal2str
from utils.exception import StandardResponseExc


def _normalize_request_value(value):
    if isinstance(value, (list, tuple)):
        return value[0] if value else None
    return value


def _get_request_value(request, *names, default=None):
    try:
        json_data = request.json
    except BaseException:
        json_data = {}
    if not isinstance(json_data, dict):
        json_data = {}

    for name in names:
        value = json_data.get(name)
        if value is not None:
            return _normalize_request_value(value)

        value = request.form.get(name)
        if value is not None:
            return _normalize_request_value(value)

    return default


class MarketPriceView(ProtectedView):
    need_auth = {"post": True}

    async def get(self, request):
        symbol = _get_request_value(request, "symbol")

        result = {}
        price_handler = MarketPriceHandler()
        if symbol:
            symbol = symbol.strip().lower()
            price_data = price_handler.get_limit_price(symbol)

            result[symbol] = price_data
        else:
            all_symbol_limit_price_dict = price_handler.get_all_limit_price()
            for k, v in all_symbol_limit_price_dict.items():
                set_time, limit_low_price, limit_high_price = v

                current_price = price_handler.get_current_price(k).get(k)
                result[k] = {
                    "symbol": k,
                    "current_price": decimal2str(current_price),
                    "limit_low_price": decimal2str(limit_low_price),
                    "limit_high_price": decimal2str(limit_high_price),
                    "set_time": set_time,
                }

        return result

    async def post(self, request):
        low_price = _get_request_value(request, "limit_low_price", "low_price", default=0)
        high_price = _get_request_value(request, "limit_high_price", "high_price", default=0)
        symbol = _get_request_value(request, "symbol", default="")
        symbol = symbol.strip().lower()
        if not low_price and not high_price:
            raise StandardResponseExc()
        if not symbol:
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

        # _ = SymbolHandle(symbol).add_macd_gate()
        # _ = SymbolHandle(symbol).add_kdj_gate()
        price_data = MarketPriceHandler().get_limit_price(symbol)
        return {
            "symbol": symbol,
            "price": {
                "current_price": decimal2str(price_data["current_price"]),
                "limit_low_price": price_data["limit_low_price"],
                "limit_high_price": price_data["limit_high_price"],
                "set_time": price_data["set_time"],
            },
            "set_limit_price_result": set_limit_price_result,
            "set_limit_price_code": set_limit_price_code,
            # "new_plot_result": new_plot_result,
        }


class MarketPriceGateView(HTTPMethodView):
    async def get(self, request):
        symbol = request.form.get("symbol", "").strip().lower()
        if not symbol:
            return "Invalid params:symbol"

        hdel_limit_price_result = MarketPriceHandler().del_limit_price(symbol)

        db_del_plot_result = SymbolHandle(symbol).del_plot()
        return {
            "symbol": symbol,
            "hdel_limit_price_result": hdel_limit_price_result,
            "db_del_plot_result": db_del_plot_result,
            "ts": int(time.time()),
        }


class SubmitMarketLimitPriceView(HTTPMethodView):
    async def get(self, request):
        symbol = request.form.get("symbol", "").strip().lower()
        if not symbol:
            return "Invalid params:symbol"
        low_price = request.form.get("low_price", 0)
        high_price = request.form.get("high_price", 0)
        buy_price = request.form.get("buy_price", 0)
        if not low_price and not high_price:
            raise StandardResponseExc()

        set_time = int(time.time())
        hset_limit_price_result = MarketPriceHandler().set_limit_price(
            symbol, str2decimal(low_price), str2decimal(high_price), set_time
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

        from exts import async_database
        from models.order import PlotBackTestTable

        async with async_database.aio_atomic():
            try:
                last_ticket = await PlotBackTestTable.select().where(
                    PlotBackTestTable.symbol == symbol
                ).order_by(PlotBackTestTable.bid_ts.desc()).aio_get()

                last_ticket.buy_price = str2decimal(buy_price)
                last_ticket.buy_ts = int(time.time())
                last_ticket.ask_curr_price = 0
                last_ticket.ask_price = 0
                last_ticket.ask_ts = 0
                last_ticket.ask_plot_type = 0
                last_ticket.ask_plot_msg = ""
                last_ticket.sell_price = 0
                last_ticket.sell_ts = 0
                last_ticket.hold_time = 0
                last_ticket.profit_percent = 0
                last_ticket.status = 1
                await last_ticket.aio_save()
            except PlotBackTestTable.DoesNotExist:
                pass

        # _ = SymbolHandle(symbol).add_macd_gate()
        # _ = SymbolHandle(symbol).add_kdj_gate()
        return {
            "set_limit_price_result": set_limit_price_result,
            "set_limit_price_code": set_limit_price_code,
            # "new_plot_result": new_plot_result,
        }


class MarketMacdCrossGateView(HTTPMethodView):
    async def get(self, request):
        key = request.form.get("key", "").strip().lower()
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
        key = request.form.get("key", "").strip().lower()
        if not key:
            return "Invalid params:key"
        symbol, interval = key.split("_")

        hdel_plot_trend_result = SymbolHandle(symbol).del_macd_trend_gate(interval)
        return {
            "key": f"{symbol}:{interval}",
            "hdel_plot_trend_result": hdel_plot_trend_result,
        }


class MarketKdjCrossGateView(HTTPMethodView):
    async def get(self, request):
        key = request.form.get("key", "").strip().lower()
        if not key:
            return "Invalid params:key"
        symbol, interval = key.split("_")

        hdel_plot_cross_result = SymbolHandle(symbol).del_kdj_cross_gate(interval)
        return {
            "key": f"{symbol}:{interval}",
            "hdel_plot_cross_result": hdel_plot_cross_result,
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


class MarketPlotManageView(ProtectedView):
    need_auth = {"get": True, "post": True, "delete": True}

    async def get(self, request):
        user = request.ctx.user
        return await SymbolHandle(user_id=user.user_id).get_all()

    async def post(self, request):
        user = request.ctx.user
        symbol = request.json.get("symbol")
        if not all([symbol, ]):
            raise StandardResponseExc(msg="Missing required fields")
        symbol = symbol.strip().lower()

        symbol_handler = SymbolHandle(symbol, user_id=user.user_id)
        user_symbol_info = await symbol_handler.add_symbol()
        if not user_symbol_info:
            raise StandardResponseExc(msg="Plot limit!")

        symbol_handler.refresh_symbol_cache()

        return {"message": "success"}

    async def delete(self, request):
        user = request.ctx.user
        symbol = request.json.get("symbol")
        if not all([symbol, ]):
            raise StandardResponseExc(msg="Missing required fields")
        symbol = symbol.strip().lower()

        symbol_handler = SymbolHandle(symbol, user_id=user.user_id)
        symbol_handler.del_plot()
        result_info = await symbol_handler.delete_symbol()
        symbol_handler.refresh_symbol_cache()
        return result_info


class BnSymbolView(ProtectedView):
    need_auth = {"get": True, "post": True, "delete": True}

    async def get(self, request):
        user = request.ctx.user
        if user.user_id != "root":
            raise StandardResponseExc(msg="Permission denied")
        return await BnSymbolHandle().get_all()


class CandidateTopPriceNoticeSettingView(ProtectedView):
    need_auth = {"get": True, "post": True}

    @staticmethod
    def _ensure_admin(user):
        if user.user_id != "root":
            raise StandardResponseExc(msg="Permission denied")

    @staticmethod
    def _parse_enabled(value):
        if isinstance(value, bool):
            return value
        if value is None:
            raise StandardResponseExc(msg="Missing required fields")
        return str(value).strip().lower() in ("1", "true", "yes", "on")

    async def get(self, request):
        self._ensure_admin(request.ctx.user)
        return {"enabled": CandidateTopPriceNoticeSetting.get_enabled()}

    async def post(self, request):
        self._ensure_admin(request.ctx.user)
        data = request.json or {}
        enabled = self._parse_enabled(data.get("enabled"))
        return CandidateTopPriceNoticeSetting.set_enabled(enabled)
