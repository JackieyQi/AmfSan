#! /usr/bin/env python
# coding:utf8

from .huobi_exchange import AccountInfoView as HuobiAccountInfoView
from .market import (MarketInnerPriceView, MarketMacdCrossGateView,
                     MarketMacdTrendGateView, MarketPriceGateView,
                     MarketPriceView)
from .plot import PlotMacdView
from .test import ServerTimeView, TestView
from .cache_sync import CacheSyncView


urls_bp = [
    (TestView.as_view(), "test/"),
    (ServerTimeView.as_view(), "api/time/"),
    (MarketPriceView.as_view(), "api/market/price/"),
    (MarketPriceGateView.as_view(), "api/market/price/gate/"),
    (MarketMacdCrossGateView.as_view(), "api/market/macd/cross/gate/"),
    (MarketMacdTrendGateView.as_view(), "api/market/macd/trend/gate/"),
    (
        MarketInnerPriceView.as_view(),
        "api/market/innerprice/<side_str>/<symbol>/<new_price>/",
    ),
    (CacheSyncView.as_view(), "api/cache/sync/"),

    (PlotMacdView.as_view(), "api/plot/macd/"),

    (HuobiAccountInfoView.as_view(), "nmb"),
]
