#! /usr/bin/env python
# coding:utf8

from .test import *
from .market import *


urls_bp = [
    (TestView.as_view(), "test/"),
    (MarketPriceView.as_view(), "api/market/price/"),
    (MarketInnerPriceView.as_view(), "api/market/innerprice/<side_str>/<symbol>/<new_price>/")

]

