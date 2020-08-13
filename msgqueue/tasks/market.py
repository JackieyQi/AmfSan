#! /usr/bin/env python
# coding:utf8

from utils.common import str2decimal
from business.market import MarketPriceHandler


async def check_price(*args, **kwargs):
    notice_result = {}

    market_price_handler = MarketPriceHandler()
    for symbol, price in market_price_handler.get_all_limit_price().items():
        current_price_info = market_price_handler.get_current_price(symbol)
        if "price" not in current_price_info:
            notice_result[symbol] = "\n\n {} \nhttp get price fail. \n\n".format(symbol)
            continue
        current_price = str2decimal(current_price_info["price"])
        if current_price > price:
            notice_result[symbol] = "\n\n {} \nnew high price:{}, \nlast limit price:{} !!! \n\n".format(symbol, current_price, price)

    if not notice_result:
        return

    from msgqueue.queue import push
    await push({"bp": "send_email_task", "receiver": ['wayley@live.com', ], "title": "New Market Price Notice", "content": "".join(notice_result.values())})

