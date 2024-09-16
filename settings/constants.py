#! /usr/bin/env python
# coding:utf8

from .setting import cfgs

HUOBI_TRADE_URL = "https://api.huobi.pro/market/trade"
HUOBI_KLINE_URL = "https://api.huobi.pro/market/history/kline"


INNER_GET_PRICE_URL = "{}/api/market/price?symbol=".format(cfgs["http"]["inner_url"])
INNER_GET_UPDATE_PRICE_URL = "{}/api/market/innerprice/".format(
    cfgs["http"]["inner_url"]
)
INNER_GET_DELETE_LIMIT_PRICE_URL = "{}/api/market/price/gate?symbol=".format(
    cfgs["http"]["inner_url"]
)
INNER_GET_DELETE_MACD_CROSS_URL = "{}/api/market/macd/cross/gate?key=".format(
    cfgs["http"]["inner_url"]
)
INNER_GET_DELETE_MACD_TREND_URL = "{}/api/market/macd/trend/gate?key=".format(
    cfgs["http"]["inner_url"]
)
INNER_GET_DELETE_KDJ_CROSS_URL = "{}/api/market/kdj/cross/gate?key=".format(
    cfgs["http"]["inner_url"]
)
INNER_UPDATE_PRICE_URL = "{}"


PLOT_INTERVAL_LIST = ["5m", "15m", "1h", "4h", "1d"]

PLOT_INTERVAL_CONFIG = {
    "5m": {"interval_sec": 5 * 60, "k_interval": 7 * 60},
    "15m": {"interval_sec": 15 * 60, "k_interval": 23 * 60},
    "1h": {"interval_sec": 60 * 60, "k_interval": 93 * 60},
    "4h": {"interval_sec": 4 * 60 * 60, "k_interval": 5 * 60 * 60},
    "1d": {"interval_sec": 24 * 60 * 60, "k_interval": 29 * 60 * 60},
}
