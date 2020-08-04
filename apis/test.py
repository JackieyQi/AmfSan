#! /usr/bin/env python
# coding:utf8

from sanic.views import HTTPMethodView
from sanic.response import text, json


def get_test(*args, **kwargs):
    return "test", args, kwargs


class TestView(HTTPMethodView):
    async def get(self, request):
        result = await get_test()
        return text("test")

