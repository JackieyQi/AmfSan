#! /usr/bin/env python
# coding:utf8

from utils.common import to_ctime
from utils.hrequest import http_get_request
from settings.constants import *


class MarketPriceHandler(object):

    def get_current_price(self, symbol="btcusdt"):
        resp_json = http_get_request(HUOBI_TRADE_URL, params={"symbol": symbol})
        if resp_json and resp_json["status"] == "ok":
            price_info = resp_json["tick"]["data"][0]
            ts = int(int(price_info["ts"])/1000)
            return {"price": price_info["price"], "ts": price_info["ts"], "dt": to_ctime(ts)}
        return {}

