#! /usr/bin/env python
# coding:utf8

from .test import TestView
from .market import MarketPriceView, MarketInnerPriceView
from .huobi_exchange import AccountInfoView as HuobiAccountInfoView


urls_bp = [
    (TestView.as_view(), "test/"),
    (MarketPriceView.as_view(), "api/market/price/"),
    (MarketInnerPriceView.as_view(), "api/market/innerprice/<side_str>/<symbol>/<new_price>/"),

    (HuobiAccountInfoView.as_view(), "nmb"),
]

