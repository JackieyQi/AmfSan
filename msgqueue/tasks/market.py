#! /usr/bin/env python
# coding:utf8

from utils.common import str2decimal
from business.market import MarketPriceHandler
from settings.constants import INNER_GET_PRICE_URL


def parse_form_data(symbol):
    body = """
    <form action="{url}" method="POST" name="form">
        <p><label for="{}_price">New limit price:</label>
        <input type="text" name="" id="fname"></p>

        <p><label for="last_name">Last Name:</label>
        <input type="text" name="last_name" id="lname"></p>

        <input value="Submit" type="submit" onclick="submitform()">
    </form>
    """


async def check_price(*args, **kwargs):
    notice_result = {}

    market_price_handler = MarketPriceHandler()
    for symbol, price in market_price_handler.get_all_limit_price().items():
        current_price_info = market_price_handler.get_current_price(symbol)
        if "price" not in current_price_info:
            notice_result[symbol] = "<br><br><b> {}: </b><br>http get price fail. <br><a href={}{}>Get current price info.</a>".format(symbol, INNER_GET_PRICE_URL, symbol)
            continue
        current_price = str2decimal(current_price_info["price"])
        if current_price > price:
            notice_result[symbol] = "<br><br><b> {}: </b><br>new high price:{}, <br>last limit price:{} !!! <br><a href={}{}>Get current price info.</a>".format(symbol, current_price, price, INNER_GET_PRICE_URL, symbol)

    if not notice_result:
        return

    from msgqueue.queue import push
    await push({"bp": "send_email_task", "receiver": ['wayley@live.com', ], "title": "New Market Price Notice", "content": "".join(notice_result.values())})

