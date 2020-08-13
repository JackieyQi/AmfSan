#! /usr/bin/env python
# coding:utf8

from sanic.views import HTTPMethodView


async def get_test(*args, **kwargs):
    from business.market import MarketPriceHandler
    a = MarketPriceHandler().get_all_limit_price()
    return "test", args, kwargs


class TestView(HTTPMethodView):
    async def get(self, request):
        result = await get_test()
        return "test"

