#! /usr/bin/env python
# coding:utf8

from utils.common import to_ctime, str2decimal
from utils.hrequest import http_get_request
from utils.exception import StandardResponseExc
from settings.constants import *
from cache.order import MarketPriceLimitCache


class MarketPriceHandler(object):

    def get_current_price(self, symbol:str="btcusdt"):
        resp_json = http_get_request(HUOBI_TRADE_URL, params={"symbol": symbol})
        if resp_json and resp_json["status"] == "ok":
            price_info = resp_json["tick"]["data"][0]
            ts = int(int(price_info["ts"])/1000)
            return {"price": str(price_info["price"]), "ts": price_info["ts"], "dt": to_ctime(ts)}
        return {}

    def set_limit_price(self, price:str, symbol:str="btcusdt"):
        current_price = self.get_current_price(symbol).get("price")
        if not current_price:
            raise StandardResponseExc()
        result = MarketPriceLimitCache.hset(symbol, price)
        return result

    def get_limit_price(self, symbol:str="btcusdt"):
        current_price = self.get_current_price(symbol).get("price")
        limit_price = MarketPriceLimitCache.hget(symbol)
        return {
            "symbol": symbol,
            "current_price": current_price,
            "limit_price": limit_price,
        }

    def get_all_limit_price(self):
        all_limit_price = MarketPriceLimitCache.hgetall()
        if not all_limit_price:
            return {}
        return {k: str2decimal(v) for k, v in all_limit_price.items()}

