#! /usr/bin/env python
# -*- coding: UTF-8 -*-

from decimal import Decimal
from utils.common import decimal2decimal

"""
结构场景 + 条件链判断
"""

"""
# TODO：可设置上限，比如布林带相关因子总分不超过 20。
5. 当前1h最低价 < 下轨,当前1h收盘价回到下轨之上 -> +10 分。
    5.1. 1h的rsi从30反弹 -> +5 分。
    5.2. 1h的MACD 背离增强: 价格创新低，但 MACD 未创新低，背离 -> +5分。


if (self.kline_list_1h[0].low_price < self.bb_list_1h[0].bblower) \
        and (self.kline_list_1h[0].close_price > self.bb_list_1h[0].bblower) \
        and kline_1h_strategies.get_ema_trend()["trend"] != "downward_spiral":
    score_info["todo:bb_1h_lower_get"] = 10
    if self.rsi_list_1h[1].rsi < self.rsi_list_1h[0].rsi < Decimal("30"):
        score_info["todo:bb_1h_rsi_up"] = 5
    if (self.kline_list_1h[0].low_price < self.kline_list_1h[2].low_price) and (
            self.macd_list_1h[0].macd > self.macd_list_1h[2].macd):
        score_info["todo:bb_1h_macd_divergence"] = 5
"""

"""
"""
# TODO:可以考虑“评分走势”的平滑机制
"""
TODO: 可以考虑“评分走势”的平滑机制
你现在是「即时分数」，也就是当前K线满足条件就加分，其实可以进一步强化稳定性，比如：
    额外思路：
    用滑动窗口打分：近3根K线的得分平均 > 60，再考虑买入。
    或者 评分突然从 <50 跳到 >70，说明趋势刚启动，作为额外信号。
"""


# Multi-Factor Condition Tree

class ModelBollMidRebound(object):
    def __init__(self, curr_price):
        self.name = "布林带中轨反弹结构"
        self.curr_price = curr_price
        self.score = 0

    def get_recommend_price(self, curr_low_price):
        recommend_bid_price = (self.curr_price + curr_low_price) / Decimal("2")
        return {
            "recommend_bid_price": decimal2decimal(recommend_bid_price)
        }

    def is_detected(
            self, kline_4h_factors, kline_1h_factors, macd_4h_factors, kdj_1h_factors, rsi_1h_factors):
        # 前置条件：更大周期的4小时的EMA12和EMA26连续上升趋势+4小时MACD没有连续递减
        if kline_4h_factors.is_ema12_continue_up(window_size=5) \
                and kline_4h_factors.is_ema26_continue_up(window_size=5) \
                and not macd_4h_factors.is_continue_down():
            self.score += 10

            # 条件A：当前最低价跌破中轨，收盘价回到中轨上方
            is_4h_structure = kline_4h_factors.get_fake_breakdown_by_bb(index=0, is_low=False)
            if is_4h_structure:
                self.score += 15

            is_1h_structure = kline_1h_factors.get_fake_breakdown_by_bb(index=0, is_low=False)
            if is_1h_structure:
                self.score += 10

            if is_4h_structure or is_1h_structure:

                # 子因子A1：1小时的RSI从低位反弹
                for i in range(3):
                    if rsi_1h_factors.get_breakout_from_low(index=i):
                        self.score += 5
                        break

                # 子因子A2：1小时的KDJ的J底部背离
                is_new_low_price = kline_1h_factors.is_new_low_price(3)
                if kdj_1h_factors.is_j_bullish_divergence(is_new_low_price):
                    self.score += 5

        return self.score >= 22.5 # 大于总分的1/2


