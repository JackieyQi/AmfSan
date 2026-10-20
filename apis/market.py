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


def _parse_price_param(value, field_name):
    value = _normalize_request_value(value)
    if value in (None, ""):
        return Decimal("0")
    try:
        return str2decimal(str(value).strip())
    except Exception:
        raise StandardResponseExc(msg=f"Invalid {field_name}: {value}")


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
        raise StandardResponseExc(msg="价格预警已合并到卖出监控，请在监控列表设置止盈止损")


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
        raise StandardResponseExc(msg="旧价格预警链接已停用，请在监控列表设置卖出监控")


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
        raise StandardResponseExc(msg="旧价格预警链接已停用，请在监控列表编辑止盈止损")


class MarketPlotManageView(ProtectedView):
    need_auth = {"get": True, "post": True, "put": True, "delete": True}

    @staticmethod
    def monitor_id(data):
        value = data.get("id")
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise StandardResponseExc(msg="需要有效的监控 ID")
        return value

    async def get(self, request):
        return await SymbolHandle(user_id=request.ctx.user.user_id).get_all()

    async def post(self, request):
        data = request.json or {}
        if not isinstance(data, dict):
            raise StandardResponseExc(msg="请求内容必须为 JSON 对象")
        symbol = data.get("symbol")
        if not isinstance(symbol, str):
            raise StandardResponseExc(msg="需要有效的币种")
        return await SymbolHandle(symbol.strip().lower(), request.ctx.user.user_id).add_symbol(data)

    async def put(self, request):
        data = request.json or {}
        if not isinstance(data, dict):
            raise StandardResponseExc(msg="请求内容必须为 JSON 对象")
        return await SymbolHandle(user_id=request.ctx.user.user_id).update_monitor(self.monitor_id(data), data)

    async def delete(self, request):
        data = request.json or {}
        if not isinstance(data, dict):
            raise StandardResponseExc(msg="请求内容必须为 JSON 对象")
        return await SymbolHandle(user_id=request.ctx.user.user_id).delete_symbol(self.monitor_id(data))


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
