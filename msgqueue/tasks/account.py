#! /usr/bin/env python
# coding:utf8

from business.huobi_exchange import HuobiExchangeAccountHandle


async def save_account_balance_job(*args, **kwargs):
    account_handler = HuobiExchangeAccountHandle()
    account_handler.save_current_balance()
