#! /usr/bin/env python
# coding:utf8

from amf import app
from apis.test import *
from apis.market import *


app.add_route(TestView.as_view(), "test/")
app.add_route(MarketPriceView.as_view(), "api/market/price/")

