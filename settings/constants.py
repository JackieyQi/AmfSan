#! /usr/bin/env python
# coding:utf8

from .setting import cfgs


HUOBI_TRADE_URL = "https://api.huobi.pro/market/trade"
HUOBI_KLINE_URL = "https://api.huobi.pro/market/history/kline"


INNER_GET_PRICE_URL = "{}/api/market/price?symbol=".format(cfgs["http"]["inner_url"])
INNER_GET_UPDATE_PRICE_URL = "{}/api/market/innerprice/".format(cfgs["http"]["inner_url"])
INNER_GET_DELETE_LIMIT_PRICE_URL = "{}/api/market/price/gate?symbol=".format(cfgs["http"]["inner_url"])
INNER_UPDATE_PRICE_URL = "{}"
