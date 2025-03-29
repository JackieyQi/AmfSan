#! /usr/bin/env python
# -*- coding: UTF-8 -*-

import json
from models.order import SymbolPlotTable, MacdTable, KdjTable


class BasePlotHandle(object):
    def __init__(self):
        self.result = {}

    def send_msg_unsync(self, email_title, email_content):
        if not self.result:
            return

        from business.mail_serve import send_email
        send_email([
                    "wayley@live.com",
                ], email_title, email_content)

    async def send_msg(self, email_title, email_content, receiver_list=None):
        if not self.result:
            return

        from msgqueue.queue import push_msg

        default_receiver_list = ["wayley@live.com", ]
        await push_msg(
            {
                "bp": "send_email_task",
                "receiver": default_receiver_list if not receiver_list else receiver_list,
                "title": email_title,
                "content": email_content,
            }
        )


async def get_plot_symbols_info(redis_client):
    symbols_info = {}
    redis_key = "symbol:cfg"

    cache_data = redis_client.hgetall(redis_key)
    if not cache_data:
        query = await SymbolPlotTable.select().aio_execute()
        for row in query:
            symbols_info[row.symbol.lower()] = {"valid": int(row.is_valid)}

        query = await MacdTable.select(MacdTable.symbol, MacdTable.interval_val).distinct().aio_execute()
        for row in query:
            if row.symbol.lower() in symbols_info:
                symbols_info[row.symbol.lower()][f"macd:{row.interval_val}"] = 1

        query = await KdjTable.select(KdjTable.symbol, KdjTable.interval_val).distinct().aio_execute()
        for row in query:
            if row.symbol.lower() in symbols_info:
                symbols_info[row.symbol.lower()][f"kdj:{row.interval_val}"] = 1

        for k, v in symbols_info.items():
            redis_client.hset(redis_key, k, json.dumps(v))

    else:
        for k, v in cache_data.items():
            symbols_info[k] = json.loads(v)
    return symbols_info
