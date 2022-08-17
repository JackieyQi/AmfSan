#! /usr/bin/env python
# coding:utf8

import hashlib
import hmac
import time
from urllib.parse import urlencode

from utils.hrequest import http_get_request


class BinanceExchangeRequestHandle(object):
    def __init__(self, key=None, secret=None):
        self.base_url = "https://api.binance.com"
        self.key = key
        self.secret = secret

    def _get_sign(self, data):
        m = hmac.new(self.secret.encode("utf-8"), data.encode("utf-8"), hashlib.sha256)
        return m.hexdigest()

    def get_k_lines(self, symbol, interval, start_ts, limit=5):
        request_data = {
            "symbol": symbol.upper(),
            "interval": interval,
            "startTime": start_ts,
            "limit": limit,
        }
        resp = http_get_request(self.base_url + "/api/v3/klines", request_data)
        return resp

    def get_my_trades(self, symbol):
        payload = {
            "symbol": symbol,
            "timestamp": int(time.time() * 1000),
            "recvWindow": 5000,
        }
        query_string = urlencode(payload, True).replace("%40", "@")
        signature = self._get_sign(query_string)
        payload["signature"] = signature

        headers = {
            "X-MBX-APIKEY": self.key,
        }
        resp = http_get_request(self.base_url + "/api/v3/myTrades", payload, headers)
        return resp
