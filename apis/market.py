#! /usr/bin/env python
# coding:utf8

from sanic.views import HTTPMethodView
from sanic.response import json as json_view

from msgqueue.queue import push
from business.market import MarketPriceHandler 


class MarketPriceView(HTTPMethodView):
    async def get(self, request):
        result = MarketPriceHandler().get_current_price()
        await push({"bp": "send_email", "receiver": ['wayley@live.com', ], "title": "Market Price", "content": result})
        return json_view(result)

