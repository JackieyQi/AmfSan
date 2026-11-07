#! /usr/bin/env python
# coding:utf8

import hashlib
import hmac
import time
import json
import aiohttp
import urllib.parse

from utils.hrequest import http_get_request, http_post_request


class BinanceExchangeRequestHandle(object):
    def __init__(self, key=None, secret=None):
        self.base_url = "https://api.binance.com"
        self.key = key
        self.secret = secret

    def _get_sign(self, data):
        m = hmac.new(self.secret.encode("utf-8"), data.encode("utf-8"), hashlib.sha256)
        return m.hexdigest()

    async def get_spot_account_async(self):
        params = {"timestamp": int(time.time() * 1000), "recvWindow": 5000}
        query = urllib.parse.urlencode(params)
        query += "&signature=" + self._get_sign(query)
        return await self._spot_get("/api/v3/account?" + query,
                                    {"X-MBX-APIKEY": self.key})

    async def get_spot_symbols_async(self):
        return await self._spot_get("/api/v3/exchangeInfo?permissions=SPOT")

    async def get_spot_prices_async(self):
        return await self._spot_get("/api/v3/ticker/price")

    async def _spot_get(self, path, headers=None):
        # Never log signed URLs, response bodies or headers containing credentials.
        async with aiohttp.ClientSession(trust_env=True, timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(self.base_url + path, headers=headers) as response:
                if response.status != 200:
                    raise ValueError("Binance spot query failed")
                return await response.json()

    def get_current_price(self, symbol, limit=5):
        payload = {
            "symbol": symbol.upper(),
        }
        if limit:
            payload["limit"] = limit
        resp = http_get_request(self.base_url + "/api/v3/aggTrades", payload)
        return resp
    
    async def get_current_price_async(self, symbol=None, symbol_list=None):
        if symbol:
            query_string = f"symbol={symbol.upper()}"
        elif symbol_list:
            symbols_json = json.dumps(
                [symbol.upper() for symbol in symbol_list],
                separators=(',', ':'))
            query_string = f"symbols={urllib.parse.quote(symbols_json)}"
        else:
            return
            
        async with aiohttp.ClientSession(trust_env=True) as session:
            async with session.get(
                self.base_url + "/api/v3/ticker/price?" + query_string
            ) as response:
                return await response.json()
            
    def get_k_lines(self, symbol, interval, start_ts, limit):
        payload = {
            "symbol": symbol.upper(),
            "interval": interval,
        }
        if start_ts:
            payload["startTime"] = start_ts
        if limit:
            payload["limit"] = limit
        resp = http_get_request(self.base_url + "/api/v3/klines", payload)
        return resp

    def get_my_user_asset(self):
        payload = {
            "timestamp": int(time.time() * 1000),
            "recvWindow": 5000,
        }

        query_string = urlencode(payload, True).replace("%40", "@")
        signature = self._get_sign(query_string)
        payload["signature"] = signature

        headers = {
            "X-MBX-APIKEY": self.key,
        }

        resp = http_post_request(
            self.base_url + "/sapi/v3/asset/getUserAsset", payload, add_headers=headers
        )
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
        resp = http_get_request(self.base_url + "/api/v3/myTrades", payload, add_headers=headers)
        return resp
