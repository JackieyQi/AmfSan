#! /usr/bin/python
# coding:utf8

from sanic import Sanic
from sanic.response import json


app = Sanic(name=__name__)

from settings.setting import cfgs
app.config.update(cfgs)

from apis import urls_bp
for _val in urls_bp:
    _view, _uri = _val
    app.add_route(_view, _uri)

