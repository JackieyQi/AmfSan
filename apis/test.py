#! /usr/bin/env python
# coding:utf8

import time

from sanic.views import HTTPMethodView
from utils.common import ts2bjfmt


async def get_test(*args, **kwargs):
    return "SUCCESS"


class TestView(HTTPMethodView):
    async def get(self, request):
        result = await get_test()
        return "{}".format(result)


class ServerTimeView(HTTPMethodView):
    async def get(self, request):
        return {"ts": time.time(), "dt": time.ctime(), "bjDt": ts2bjfmt()}
