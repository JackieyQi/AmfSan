#! /usr/bin/env python
# -*- coding: UTF-8 -*-

import json
import hashlib
from models.user import UserSymbolPlotTable, EmailMsgHistoryTable
from models.market import MacdTable, KdjTable
from settings.setting import cfgs


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

    async def send_msg(self, email_title, email_msg_md5_str, receiver_list=None):
        if not self.result:
            return
        
        email_msg_md5 = hashlib.md5(email_msg_md5_str.encode("utf8")).hexdigest()
        try:
            # 当前限价检查存在时，不再推送消息
            return await EmailMsgHistoryTable.aio_get(
                EmailMsgHistoryTable.msg_md5 == email_msg_md5
            )
        except EmailMsgHistoryTable.DoesNotExist:
            pass

        email_content = "".join(self.result.values())
        await EmailMsgHistoryTable.aio_create(msg_md5=email_msg_md5, msg_content=email_content)

        from msgqueue.queue import push_msg

        default_receiver_list = [cfgs["administrator_email"], ]
        await push_msg(
            {
                "bp": "send_email_task",
                "receiver": default_receiver_list if not receiver_list else receiver_list,
                "title": email_title,
                "content": email_content,
            }
        )


async def get_plot_symbols_info(redis_client):
    """Use enabled manual monitors as the authoritative shared acquisition pool."""
    rows = await UserSymbolPlotTable.select(UserSymbolPlotTable.symbol).where(
        UserSymbolPlotTable.is_valid == True).distinct().aio_execute()
    return {row.symbol.lower(): {"valid": 1} for row in rows}
