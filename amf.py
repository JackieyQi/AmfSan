#! /usr/bin/python
# coding:utf8

from sanic import Sanic
from sanic.response import json


app = Sanic(name=__name__)

from settings.setting import cfgs
app.config.update(cfgs)

from urls import *
