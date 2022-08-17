#! /usr/bin/env python
# coding:utf8

import base64
import hashlib
import hmac
from datetime import datetime
from decimal import Decimal
from urllib.parse import quote_plus, urlencode

from models.wallet import BalanceHistoryTable
from utils.common import str2decimal
from utils.hrequest import http_get_request


class BaseExchange(object):
    pass


class SignKeyMixin(object):
    def _get_key(self):
        from settings.setting import cfgs_huobi

        if not cfgs_huobi:
            raise Exception
        public_key = cfgs_huobi["public_key"]
        return public_key

    def sign(self, data):
        from settings.setting import cfgs_huobi

        if not cfgs_huobi:
            raise Exception
        public_key = cfgs_huobi["public_key"]
        secret_key = cfgs_huobi["secret_key"]

        dig = hmac.new(
            secret_key.encode("utf8"), data.encode("utf8"), hashlib.sha256
        ).digest()
        return base64.b64encode(dig)


class HuobiExchangeRequestHandle(SignKeyMixin, BaseExchange):
    def __init__(self, method, uri):
        self.hostname = "api.huobi.pro"
        self.method = method
        self.uri = uri

    def get_base_params(self):
        key = self._get_key()
        params = {
            "AccessKeyId": key,
            "SignatureMethod": "HmacSHA256",
            "SignatureVersion": 2,
            "Timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"),
        }
        return params

    def get_request_body(self, request_data: dict):
        request_data.update(self.get_base_params())
        request_data_str = urlencode(request_data, quote_via=quote_plus)

        sign_data = [
            self.method + "\n",
            self.hostname + "\n",
            self.uri + "\n",
            request_data_str,
        ]
        sign_data = "".join(sign_data)
        request_data["Signature"] = self.sign(sign_data)
        return request_data

    def get_http_data(self, request_data):
        request_data = self.get_request_body(request_data)
        if self.method == "GET":
            resp = http_get_request(
                "https://" + self.hostname + self.uri + "?", request_data
            )
        else:
            resp = None

        return resp


class HuobiExchangeAccountHandle(object):
    def __init__(self):
        self.spot_user_id = "3866258"

    def _parsed_current_balance(self, resp_data):
        result = []
        for val in resp_data["data"]["list"]:
            if val["balance"] == "0":
                continue
            elif str2decimal(val["balance"]) == Decimal("0"):
                continue
            val["balance"] = str2decimal(val["balance"])
            result.append(val)
        return result

    def get_current_balance(self):
        result = HuobiExchangeRequestHandle(
            "GET", "/v1/account/accounts/{}/balance".format(self.spot_user_id)
        ).get_http_data({})
        if "status" not in result:
            return "Error."
        elif result["status"] != "ok":
            return "Error resp."
        else:
            return self._parsed_current_balance(result)

    def get_account_history(self):
        result = HuobiExchangeRequestHandle("GET", "/v1/account/history").get_http_data(
            {
                "account-id": self.spot_user_id,
                "currency": "",
            }
        )

    def get_current_balance_price(self, balance_data, subject_matter="USDT"):
        from business.market import MarketPriceHandler

        price_handler = MarketPriceHandler()

        result = []
        for val in balance_data:
            if val["currency"].upper() == subject_matter.upper():
                val["price"] = None
                val["bid"] = subject_matter.lower()
                result.append(val)
                continue

            symbol = "{}{}".format(val["currency"], subject_matter).lower()
            price_info = price_handler.get_current_price(symbol)
            val["price"] = price_info.get("price")
            val["bid"] = subject_matter.lower()
            result.append(val)
        return result

    def save_current_balance(self):
        balance_data = self.get_current_balance()
        balance_price_data = self.get_current_balance_price(balance_data)

        src_data = []
        for val in balance_price_data:
            src_data.append(
                {
                    "user_id": self.spot_user_id,
                    "coin": val["currency"],
                    "status_type": val["type"],
                    "amount": val["balance"],
                    "price": val["price"],
                    "bid_coin": val["bid"],
                }
            )
        count = BalanceHistoryTable.insert_many(src_data).execute()
        return count
