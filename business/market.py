#! /usr/bin/env python
# coding:utf8

from decimal import Decimal

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

    def set_limit_price(self, symbol:str="btcusdt", low_price:Decimal=None, high_price:Decimal=None):
        current_price = self.get_current_price(symbol).get("price")
        if not current_price:
            raise StandardResponseExc()
        current_price = str2decimal(current_price)
        if low_price and current_price < low_price:
            raise StandardResponseExc(msg="Current price:{} lower low_price".format(current_price))
        if high_price and current_price > high_price:
            raise StandardResponseExc(msg="Current price:{} higher high_price".format(current_price))

        limit_price = MarketPriceLimitCache.hget(symbol)
        if not limit_price:
            limit_low_price, limit_high_price = "", ""
        else:
            limit_low_price, limit_high_price = limit_price.split(":")

        result = MarketPriceLimitCache.hset(
            symbol, "{}:{}".format(low_price or limit_low_price, high_price or limit_high_price)
        )
        return result

    def get_limit_price(self, symbol:str="btcusdt"):
        current_price = self.get_current_price(symbol).get("price")
        limit_price = MarketPriceLimitCache.hget(symbol)
        if not limit_price:
            limit_low_price, limit_high_price = "", ""
        else:
            limit_low_price, limit_high_price = limit_price.split(":")
        return {
            "symbol": symbol,
            "current_price": current_price,
            "limit_low_price": limit_low_price,
            "limit_high_price": limit_high_price,
        }

    def get_all_limit_price(self):
        all_limit_price = MarketPriceLimitCache.hgetall()
        if not all_limit_price:
            return {}
        
        result = {}
        for k, v in all_limit_price.items():
            limit_low_price, limit_high_price = v.split(":")
            if limit_low_price:
                limit_low_price = Decimal(limit_low_price)
            if limit_high_price:
                limit_high_price = Decimal(limit_high_price)
            result[k] = (limit_low_price, limit_high_price)
        return result

