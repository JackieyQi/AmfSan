#! /usr/bin/env python
# coding:utf8

from sanic.views import HTTPMethodView


class AccountInfoView(HTTPMethodView):
    async def get(self, request):
        from business.huobi_exchange import HuobiExchangeAccountHandle
        return HuobiExchangeAccountHandle().get_current_balance()
        # return __name__

