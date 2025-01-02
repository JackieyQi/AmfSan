#! /usr/bin/env python
# -*- coding: UTF-8 -*-

import hashlib
import logging
import time
from decimal import Decimal

from models.order import MacdTable, KdjTable
from models.user import EmailMsgHistoryTable
from settings.constants import PLOT_INTERVAL_CONFIG
from utils.common import ts2bjfmt
from utils.templates import template_gpt_plot_notice
from .base import BasePlotHandle

logger = logging.getLogger(__name__)


class PlotGptHandle(BasePlotHandle):
    def __init__(self, symbol):
        super().__init__()
        self.symbol = symbol

        if "1h" not in PLOT_INTERVAL_CONFIG:
            raise Exception("Interval 1h miss.")
        if "4h" not in PLOT_INTERVAL_CONFIG:
            raise Exception("Interval 4h miss.")
        if "1d" not in PLOT_INTERVAL_CONFIG:
            raise Exception("Interval 1d miss.")

    def reformat_notice(self, direction, now_data):
        return template_gpt_plot_notice(self.symbol, direction, now_data.open_ts)

    async def check(self, limit_count=7):
        email_title = f"{self.symbol} GPT Plot Notice"

        macd_list_1d, macd_list_4h, macd_list_1h = None, None, None
        for interval in ["1d", "4h", "1h"]:
            query = (
                MacdTable.select().where(
                    MacdTable.symbol == self.symbol,
                    MacdTable.interval_val == interval,
                )
                    .order_by(MacdTable.id.desc())
                    .limit(limit_count)
            )
            macd_list = [i for i in query]
            if not macd_list:
                return
            if len(macd_list) < limit_count:
                return

            now_macd_data, last_macd_data = macd_list[0], macd_list[1]

            now_ts = int(time.time())
            interval_sec = PLOT_INTERVAL_CONFIG[interval]["interval_sec"]
            if now_macd_data.opening_ts < (now_ts - interval_sec * limit_count):
                self.result[
                    self.symbol
                ] = f"""
                        <br><a>Error: no lastest macd data, {self.symbol}:{interval}</a>
                        <br><a>opening_ts:{ts2bjfmt(now_macd_data.opening_ts)}</a>
                        <br><a>now_ts:{ts2bjfmt(now_ts)}</a>
                        """

                return await self.send_msg(email_title, "".join(self.result.values()))

            if interval == "1d":
                macd_list_1d = macd_list
            elif interval == "4h":
                macd_list_4h = macd_list
            elif interval == "1h":
                macd_list_1h = macd_list

        if macd_list_1d[0].macd < 0:
            return
        if macd_list_4h[0].macd < 0:
            return

        interval = "1h"
        query = (
            KdjTable.select()
                .where(
                KdjTable.symbol == self.symbol,
                KdjTable.interval_val == interval,
            )
                .order_by(KdjTable.id.desc())
                .limit(limit_count)
        )
        query_list = [i for i in query]
        if not query_list:
            return
        elif len(query_list) < limit_count:
            return

        now_data, last_data = query_list[0], query_list[1]

        now_ts = int(time.time())
        interval_sec = PLOT_INTERVAL_CONFIG[interval]["interval_sec"]
        if now_data.open_ts < (now_ts - interval_sec * 7):
            self.result[
                self.symbol
            ] = f"""
                    <br><a>Error: no lastest kdj data, {self.symbol}:{interval}</a>
                    <br><a>open_ts:{ts2bjfmt(now_data.open_ts)}</a>
                    <br><a>now_ts:{ts2bjfmt(now_ts)}</a>
                    """

            return await self.send_msg(email_title, "".join(self.result.values()))

        if now_data.k_val < Decimal("20") and now_data.d_val < Decimal("20") and now_data.j_val < Decimal("20"):
            direction = "📈"
        elif now_data.k_val > Decimal("80") and now_data.d_val > Decimal("80") and now_data.j_val > Decimal("80"):
            direction = "📉"
        else:
            return

        email_msg_md5_str = (
            f"check_gpt_plot:{self.symbol}:{now_data.open_ts}"
        )
        email_msg_md5 = hashlib.md5(email_msg_md5_str.encode("utf8")).hexdigest()
        try:
            return EmailMsgHistoryTable.get(
                EmailMsgHistoryTable.msg_md5 == email_msg_md5
            )
        except EmailMsgHistoryTable.DoesNotExist:
            self.result[self.symbol] = self.reformat_notice(direction, now_data)

        email_content = "".join(self.result.values())
        EmailMsgHistoryTable.create(msg_md5=email_msg_md5, msg_content=email_content)

        logger.info(
            f"PlotGptHandle.check finish, start end_msg, symbol:{self.symbol}, ts:{int(time.time())}")
        await self.send_msg(email_title, email_content)
