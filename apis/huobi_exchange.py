#! /usr/bin/env python
# coding:utf8

from sanic.views import HTTPMethodView


class AccountInfoView(HTTPMethodView):
    async def get(self, request):
        return __name__

